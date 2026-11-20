"""Two-level stack: XGBoost, CatBoost, Random Forest, and MLP, then Ridge.

Level-0 models make out-of-fold predictions on the training points.
The Ridge meta-regressor is fit to those predictions only, then the
base models are refit on all training points and applied to the
30 percent holdout.

Folds are 2 km spatial blocks when coordinates are present. The holdout
itself stays a stratified random 70/30 split so it remains comparable
with the baseline annual study.
"""

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, KFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from tilaiya.constants import (
    CAT_PARAMS,
    MLP_PARAMS,
    N_FOLDS,
    RANDOM_STATE,
    RF_PARAMS,
    RIDGE_ALPHA,
    XGB_PARAMS,
)
from tilaiya.metrics import regression_scores


def _require_boosting_libraries():
    try:
        from catboost import CatBoostRegressor
        from xgboost import XGBRegressor
    except ImportError as error:
        raise ImportError(
            "Install the stacking libraries with: pip install -r requirements.txt"
        ) from error
    return XGBRegressor, CatBoostRegressor


def make_base_models():
    """Return fresh Level-0 estimators in methodology order."""
    xgb_class, catboost_class = _require_boosting_libraries()
    return {
        "XGBoost": xgb_class(**XGB_PARAMS),
        "CatBoost": catboost_class(**CAT_PARAMS),
        "RandomForest": RandomForestRegressor(**RF_PARAMS),
        "MLP": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("mlp", MLPRegressor(**MLP_PARAMS)),
            ]
        ),
    }


def fold_splits(n_samples, groups=None):
    """Five spatial-block folds, or shuffled folds when blocks are unavailable."""
    if n_samples < N_FOLDS:
        raise ValueError(f"Need at least {N_FOLDS} training rows for cross-validation.")
    if groups is not None and len(np.unique(groups)) >= N_FOLDS:
        splitter = GroupKFold(n_splits=N_FOLDS)
        splits = list(splitter.split(np.zeros(n_samples), groups=np.asarray(groups)))
        return splits, "spatial_block_2km"

    splitter = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    return list(splitter.split(np.zeros(n_samples))), "random"


def _out_of_fold(factory, x_train, y_train, splits):
    predictions = np.full(len(y_train), np.nan, dtype=np.float64)
    for train_index, validation_index in splits:
        model = factory()
        model.fit(x_train[train_index], y_train[train_index])
        predictions[validation_index] = model.predict(x_train[validation_index])
    if not np.isfinite(predictions).all():
        raise RuntimeError("Out-of-fold predictions did not cover every training point.")
    return predictions


def fit_stack(x_train, y_train, x_test, y_test, groups=None):
    """Fit the Level-0 models and the Level-1 Ridge blender."""
    splits, fold_kind = fold_splits(len(y_train), groups)

    base_names = list(make_base_models().keys())
    oof = np.column_stack(
        [
            _out_of_fold(lambda name=name: make_base_models()[name], x_train, y_train, splits)
            for name in base_names
        ]
    )

    meta = Ridge(alpha=RIDGE_ALPHA, fit_intercept=True)
    meta.fit(oof, y_train)
    oof_prediction = meta.predict(oof)

    fitted = {}
    test_columns = []
    for name in base_names:
        model = make_base_models()[name]
        model.fit(x_train, y_train)
        fitted[name] = model
        test_columns.append(model.predict(x_test))
    test_level0 = np.column_stack(test_columns)
    test_prediction = meta.predict(test_level0)

    scores = {
        "cross_validation": regression_scores(y_train, oof_prediction),
        "holdout": regression_scores(y_test, test_prediction),
    }
    for column, name in enumerate(base_names):
        scores[name] = regression_scores(y_test, test_level0[:, column])

    return {
        "models": fitted,
        "meta": meta,
        "base_names": base_names,
        "fold_kind": fold_kind,
        "oof_prediction": oof_prediction,
        "test_prediction": test_prediction,
        "test_level0": test_level0,
        "scores": scores,
        "meta_coefficients": dict(zip(base_names, meta.coef_.tolist())),
        "meta_intercept": float(meta.intercept_),
    }
