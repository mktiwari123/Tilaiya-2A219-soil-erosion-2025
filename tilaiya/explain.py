"""SHAP attributions for the XGBoost member of the stack.

TreeSHAP is computed for XGBoost because that Level-0 model captures
the non-linear interactions the methodology asks to explain. The Ridge
blend weights are stored separately and say how the four Level-0
predictions are combined.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _cover_feature(feature_names):
    for name in ("Cm", "C", "SAVI", "NDVI", "RVI"):
        if name in feature_names:
            return name
    return None


def explain_xgboost(model, x_test, feature_names, destination, predictions):
    """Write SHAP tables, a summary plot, and the Cm < 0.15 diagnostic."""
    import shap

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    feature_names = list(feature_names)
    frame = pd.DataFrame(x_test, columns=feature_names)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(frame)
    shap_values = np.asarray(shap_values)
    mean_abs = np.mean(np.abs(shap_values), axis=0)
    importance = pd.DataFrame(
        {"feature": feature_names, "mean_abs_shap": mean_abs}
    ).sort_values("mean_abs_shap", ascending=False)
    importance.to_csv(destination / "shap_importance.csv", index=False)

    direction_rows = []
    for name in feature_names:
        values = frame[name].to_numpy()
        midpoint = float(np.median(values))
        above = values > midpoint
        column = shap_values[:, feature_names.index(name)]
        direction_rows.append(
            {
                "feature": name,
                "holdout_median": midpoint,
                "mean_shap_above_median": float(np.mean(column[above])) if above.any() else np.nan,
                "mean_shap_at_or_below_median": float(np.mean(column[~above])) if (~above).any() else np.nan,
            }
        )
    pd.DataFrame(direction_rows).to_csv(destination / "shap_direction.csv", index=False)

    plt.figure(figsize=(8, 5))
    order = np.argsort(mean_abs)
    plt.barh(np.array(feature_names)[order], mean_abs[order], color="#1f4e79")
    plt.xlabel("Mean absolute SHAP value")
    plt.tight_layout()
    plt.savefig(destination / "shap_importance.png", dpi=200)
    plt.close()

    plt.figure()
    shap.summary_plot(shap_values, frame, show=False)
    plt.tight_layout()
    plt.savefig(destination / "shap_summary.png", dpi=200, bbox_inches="tight")
    plt.close()

    cover_name = _cover_feature(feature_names)
    if cover_name is not None:
        cover = frame[cover_name].to_numpy()
        low_cover = cover < 0.15
        diagnostic = pd.DataFrame(
            [
                {
                    "subset": f"{cover_name} < 0.15",
                    "n": int(low_cover.sum()),
                    "mean_predicted_soil_loss": float(np.mean(predictions[low_cover])) if low_cover.any() else np.nan,
                    "mean_cover": float(np.mean(cover[low_cover])) if low_cover.any() else np.nan,
                },
                {
                    "subset": f"{cover_name} >= 0.15",
                    "n": int((~low_cover).sum()),
                    "mean_predicted_soil_loss": float(np.mean(predictions[~low_cover])) if (~low_cover).any() else np.nan,
                    "mean_cover": float(np.mean(cover[~low_cover])) if (~low_cover).any() else np.nan,
                },
            ]
        )
        diagnostic.to_csv(destination / "cover_threshold_0p15.csv", index=False)

        shap.dependence_plot(
            cover_name,
            shap_values,
            frame,
            show=False,
        )
        plt.tight_layout()
        plt.savefig(destination / f"shap_dependence_{cover_name}.png", dpi=200)
        plt.close()

    if "LS" in feature_names:
        shap.dependence_plot("LS", shap_values, frame, show=False)
        plt.tight_layout()
        plt.savefig(destination / "shap_dependence_LS.png", dpi=200)
        plt.close()

    return importance
