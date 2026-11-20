"""Diagnostics for the review of delivery, cover, erosivity shape, and SHAP.

These checks read completed rasters and tables. They do not redraw soil-loss
maps, refit the stacks, or calibrate the delivery sigmoid.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import ANNUAL_SOIL_LOSS  # noqa: E402

OUT = ROOT / "output" / "tables"
NODATA = -9999.0
RAINFALL = {
    1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
    2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
    3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
    4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
    5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
}


def valid_array(path):
    with rasterio.open(path) as src:
        values = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        values = np.where(values == nodata, np.nan, values)
    values = np.where(values == NODATA, np.nan, values)
    return values


def cover_row(month):
    values = valid_array(ROOT / "output" / "rasters" / "Cover" / f"Cm_{month:02d}.tif")
    data = values[np.isfinite(values)]
    floor = np.isclose(data, 0.001, atol=1e-6)
    return {
        "month": month,
        "n": int(data.size),
        "min": float(data.min()),
        "p05": float(np.percentile(data, 5)),
        "median": float(np.median(data)),
        "mean": float(data.mean()),
        "p95": float(np.percentile(data, 95)),
        "fraction_at_0.001_floor": float(floor.mean()),
        "fraction_below_0.05": float(np.mean(data < 0.05)),
        "fraction_below_0.15": float(np.mean(data < 0.15)),
    }


def monthly_shares(exponent):
    rows = []
    for cell, monthly in RAINFALL.items():
        rain = np.asarray(monthly, dtype=float)
        annual = rain.sum()
        mfi = np.where(annual > 0, rain**2 / annual, 0.0)
        rm = np.where(mfi > 0, 1.8219 * mfi**exponent, 0.0)
        total = rm.sum()
        shares = rm / total
        rows.append(
            {
                "cell": cell,
                "exponent": exponent,
                "june_share": float(shares[5]),
                "july_share": float(shares[6]),
                "august_share": float(shares[7]),
                "june_july_share": float(shares[5] + shares[6]),
                "peak_month": int(np.argmax(shares) + 1),
            }
        )
    return rows


def holdout_tail(path, scenario):
    frame = pd.read_csv(path)
    error = (frame["predicted"] - frame["SoilLoss"]) ** 2
    total = float(error.sum())
    extreme = frame["SoilLoss"] > 100
    top = error.nlargest(27)
    return {
        "scenario": scenario,
        "n": int(len(frame)),
        "n_above_100": int(extreme.sum()),
        "sse_share_above_100": float(error[extreme].sum() / total),
        "sse_share_top_27_squared_errors": float(top.sum() / total),
        "max_observed": float(frame["SoilLoss"].max()),
    }


def annual_comparison():
    dynamic = valid_array(ROOT / "output" / "rasters" / "SoilLoss" / "SoilLoss_annual.tif")
    baseline = valid_array(ANNUAL_SOIL_LOSS)
    both = np.isfinite(dynamic) & np.isfinite(baseline) & (baseline > -1)
    d = dynamic[both]
    b = baseline[both]
    diff = d - b
    return {
        "n_overlap": int(both.sum()),
        "mean_dynamic": float(d.mean()),
        "mean_baseline": float(b.mean()),
        "median_dynamic": float(np.median(d)),
        "median_baseline": float(np.median(b)),
        "mean_difference_dynamic_minus_baseline": float(diff.mean()),
        "median_difference": float(np.median(diff)),
        "pearson_r": float(np.corrcoef(d, b)[0, 1]),
        "fraction_dynamic_within_20_percent": float(np.mean(np.abs(diff) <= 0.2 * np.maximum(b, 1e-6))),
    }


def annual_c():
    values = valid_array(ROOT / "output" / "rasters" / "Cover" / "C_annual_baseline.tif")
    data = values[np.isfinite(values)]
    return {
        "n": int(data.size),
        "min": float(data.min()),
        "p05": float(np.percentile(data, 5)),
        "median": float(np.median(data)),
        "mean": float(data.mean()),
        "fraction_below_0.15": float(np.mean(data < 0.15)),
        "fraction_below_0.05": float(np.mean(data < 0.05)),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cover = pd.DataFrame([cover_row(month) for month in (6, 7, 8, 9)])
    cover.to_csv(OUT / "cover_floor_june_september.csv", index=False)

    shares = []
    for exponent in (1.0, 1.211, 1.5, 2.0):
        shares.extend(monthly_shares(exponent))
    share_frame = pd.DataFrame(shares)
    share_frame.to_csv(OUT / "erosivity_exponent_monthly_shares.csv", index=False)

    tails = pd.DataFrame(
        [
            holdout_tail(OUT / "Reduced_Integrated_holdout_predictions.csv", "Reduced_Integrated"),
            holdout_tail(OUT / "Dynamic_Integrated_holdout_predictions.csv", "Dynamic_Integrated"),
        ]
    )
    tails.to_csv(OUT / "holdout_squared_error_concentration.csv", index=False)

    comparison = pd.DataFrame([annual_comparison()])
    comparison.to_csv(OUT / "annual_map_pixel_comparison.csv", index=False)

    c_stats = pd.DataFrame([annual_c()])
    c_stats.to_csv(OUT / "annual_c_distribution.csv", index=False)

    print(cover.to_string(index=False))
    print(share_frame.to_string(index=False))
    print(tails.to_string(index=False))
    print(comparison.to_string(index=False))
    print(c_stats.to_string(index=False))


if __name__ == "__main__":
    main()
