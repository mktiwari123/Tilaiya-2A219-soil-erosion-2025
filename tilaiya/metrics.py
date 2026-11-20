"""Fit statistics named in the methodology.

With the sum-of-squares definition given in the methodology, R2 and
Nash-Sutcliffe efficiency are the same number. Both are reported so
the results table matches the paper's three named metrics. Mean
absolute error is included because the baseline model reports used it.
"""

import numpy as np


def regression_scores(observed, predicted):
    observed = np.asarray(observed, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    valid = np.isfinite(observed) & np.isfinite(predicted)
    observed = observed[valid]
    predicted = predicted[valid]
    if observed.size == 0:
        raise ValueError("No finite pairs to score.")

    residual = observed - predicted
    sum_squared_error = float(np.sum(residual ** 2))
    centred = observed - np.mean(observed)
    sum_centred = float(np.sum(centred ** 2))
    if sum_centred == 0:
        coefficient = np.nan
    else:
        coefficient = 1.0 - (sum_squared_error / sum_centred)

    rmse = float(np.sqrt(np.mean(residual ** 2)))
    mae = float(np.mean(np.abs(residual)))
    return {
        "n": int(observed.size),
        "R2": coefficient,
        "RMSE": rmse,
        "NSE": coefficient,
        "MAE": mae,
    }
