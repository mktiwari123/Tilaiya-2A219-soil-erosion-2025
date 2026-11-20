"""Pixel-level check of the June-July soil-loss median.

Reads the completed monthly rasters. Does not redraw them.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import ANNUAL_SOIL_LOSS  # noqa: E402

OUT = ROOT / "output" / "tables"
NODATA = -9999.0
RASTERS = ROOT / "output" / "rasters"


def read(path):
    import rasterio

    with rasterio.open(path) as src:
        values = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        values = np.where(np.isclose(values, nodata), np.nan, values)
    values = np.where(np.isclose(values, NODATA), np.nan, values)
    return values


def summarize(name, values):
    data = values[np.isfinite(values)]
    return {
        "series": name,
        "n": int(data.size),
        "min": float(data.min()),
        "p25": float(np.percentile(data, 25)),
        "median": float(np.median(data)),
        "mean": float(data.mean()),
        "p75": float(np.percentile(data, 75)),
        "p95": float(np.percentile(data, 95)),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a6 = read(RASTERS / "SoilLoss" / "SoilLoss_06.tif")
    a7 = read(RASTERS / "SoilLoss" / "SoilLoss_07.tif")
    c6 = read(RASTERS / "Cover" / "Cm_06.tif")
    c7 = read(RASTERS / "Cover" / "Cm_07.tif")
    k6 = read(RASTERS / "Erodibility" / "Km_06.tif")
    k7 = read(RASTERS / "Erodibility" / "Km_07.tif")
    r6 = read(RASTERS / "Erosivity" / "Erosivity_06.tif")
    r7 = read(RASTERS / "Erosivity" / "Erosivity_07.tif")

    both = np.isfinite(a6) & np.isfinite(a7) & np.isfinite(c6) & np.isfinite(c7)
    both = both & np.isfinite(k6) & np.isfinite(k7) & np.isfinite(r6) & np.isfinite(r7)
    rows = [summarize("June all finite", a6), summarize("July all finite", a7)]
    rows.append(summarize("July where Cm > 0.15", a7[(np.isfinite(a7)) & (np.isfinite(c7)) & (c7 > 0.15)]))
    rows.append(summarize("July where Cm > 0.001", a7[(np.isfinite(a7)) & (np.isfinite(c7)) & (c7 > 0.001 + 1e-6)]))
    rows.append(summarize("July on June-valid pixels", a7[both]))
    rows.append(summarize("June on shared pixels", a6[both]))

    positive = both & (a6 > 0.01) & (r6 > 0)
    ratio = np.full(a6.shape, np.nan)
    factor = np.full(a6.shape, np.nan)
    ratio[positive] = a7[positive] / a6[positive]
    factor[positive] = (r7[positive] / r6[positive]) * (k7[positive] / k6[positive]) * (c7[positive] / c6[positive])
    rows.append(summarize("A_July / A_June where A_June > 0.01", ratio))
    rows.append(summarize("factor ratio R*K*C", factor))
    residual = np.full(a6.shape, np.nan)
    residual[positive] = ratio[positive] / factor[positive]
    rows.append(summarize("(A ratio) / (R*K*C ratio)", residual))

    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "july_june_pixel_ratios.csv", index=False)

    shared_a7 = a7[both]
    floor = both & np.isclose(c7, 0.001, atol=1e-6)
    low = both & (c7 <= 0.15)
    detail = {
        "shared_pixels": int(both.sum()),
        "july_fraction_below_0.01_on_shared": float(np.mean(shared_a7 < 0.01)),
        "july_fraction_below_june_median_on_shared": float(np.mean(shared_a7 < np.median(a6[both]))),
        "shared_pixels_on_july_floor": int(floor.sum()),
        "median_A_july_on_floor": float(np.median(a7[floor])) if floor.any() else np.nan,
        "median_A_june_on_those_floor_pixels": float(np.median(a6[floor])) if floor.any() else np.nan,
        "median_A_july_where_Cm_gt_0.15": float(np.median(a7[both & (c7 > 0.15)])),
        "median_A_june_on_those_Cm_gt_0.15_pixels": float(np.median(a6[both & (c7 > 0.15)])),
        "n_Cm_gt_0.15": int((both & (c7 > 0.15)).sum()),
        "median_ratio_where_Cm_gt_0.15_and_A6_gt_0.01": float(np.nanmedian(ratio[positive & (c7 > 0.15)])),
        "median_factor_where_Cm_gt_0.15_and_A6_gt_0.01": float(np.nanmedian(factor[positive & (c7 > 0.15)])),
        "spearman_ratio_vs_factor": float(spearmanr(ratio[positive], factor[positive], nan_policy="omit").statistic),
    }
    pd.DataFrame([detail]).to_csv(OUT / "july_june_same_pixel_summary.csv", index=False)

    dynamic = read(RASTERS / "SoilLoss" / "SoilLoss_annual.tif")
    baseline = read(ANNUAL_SOIL_LOSS)
    overlap = np.isfinite(dynamic) & np.isfinite(baseline) & (baseline > -1) & (dynamic >= 0)
    d = dynamic[overlap]
    b = baseline[overlap]
    log_ok = (d > 0) & (b > 0)
    corr = {
        "n": int(overlap.sum()),
        "pearson_r": float(np.corrcoef(d, b)[0, 1]),
        "spearman_r": float(spearmanr(d, b).statistic),
        "pearson_r_log10": float(np.corrcoef(np.log10(d[log_ok]), np.log10(b[log_ok]))[0, 1]),
        "n_log": int(log_ok.sum()),
    }
    pd.DataFrame([corr]).to_csv(OUT / "annual_map_rank_correlation.csv", index=False)

    print(frame.to_string(index=False))
    print(pd.DataFrame([detail]).T.to_string())
    print(pd.DataFrame([corr]).to_string(index=False))
    _ = low


if __name__ == "__main__":
    main()
