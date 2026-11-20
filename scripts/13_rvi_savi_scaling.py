"""Scale July and August cover by a SAVI-RVI line fitted outside those months.

The official Cm and soil-loss rasters are left in place. This writes a
comparison table only.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "output" / "tables"
STACK = ROOT / "data" / "aligned"
NODATA = -9999.0
# tilaiya.monthly.GEE_BANDS
BAND = {"SAVI": 1, "Cm_optical": 5, "RVI": 8, "Cm": 9}


def band(month, name):
    path = STACK / f"Tilaiya_2025_{month:02d}.tif"
    with rasterio.open(path) as src:
        values = src.read(BAND[name]).astype(np.float32)
        nodata = src.nodata
    values = values.astype(np.float64)
    if nodata is not None:
        values[np.isclose(values, nodata)] = np.nan
    values[np.isclose(values, NODATA)] = np.nan
    return values


def sample_pairs(month, rng, n=80000):
    savi = band(month, "SAVI")
    rvi = band(month, "RVI")
    ok = np.isfinite(savi) & np.isfinite(rvi) & (savi >= 0) & (savi <= 1.2) & (rvi >= 0) & (rvi <= 1.2)
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return np.empty(0), np.empty(0)
    take = rng.choice(idx, size=min(n, idx.size), replace=False)
    return rvi.ravel()[take], savi.ravel()[take]


def soil(month):
    path = ROOT / "output" / "rasters" / "SoilLoss" / f"SoilLoss_{month:02d}.tif"
    with rasterio.open(path) as src:
        values = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        values[np.isclose(values, nodata)] = np.nan
    values[np.isclose(values, NODATA)] = np.nan
    return values


def stats(name, values):
    data = values[np.isfinite(values)]
    return {
        "series": name,
        "n": int(data.size),
        "median": float(np.median(data)),
        "mean": float(data.mean()),
        "p95": float(np.percentile(data, 95)),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    rvi_s = []
    savi_s = []
    for month in (1, 2, 3, 4, 5, 6, 9, 10, 11, 12):
        rvi, savi = sample_pairs(month, rng)
        rvi_s.append(rvi)
        savi_s.append(savi)
    x = np.concatenate(rvi_s)
    y = np.concatenate(savi_s)
    design = np.column_stack([np.ones(x.size), x])
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    intercept, slope = (float(coef[0]), float(coef[1]))
    fitted = intercept + slope * x
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot

    rows = []
    for month in (6, 7, 8):
        rvi = band(month, "RVI")
        cm = band(month, "Cm")
        loss = soil(month)
        savi_hat = np.clip(intercept + slope * rvi, 0, 1)
        cm_new = np.clip(1 - 1.18 * savi_hat, 0.001, 1)
        cm_new[~np.isfinite(rvi)] = np.nan
        scaled = np.full(loss.shape, np.nan)
        ok = np.isfinite(loss) & np.isfinite(cm) & np.isfinite(cm_new) & (cm > 0)
        scaled[ok] = loss[ok] * (cm_new[ok] / cm[ok])
        rows.append(stats(f"month {month} official", loss))
        rows.append(stats(f"month {month} RVI scaled to SAVI", scaled))
        both = ok
        rows.append(
            {
                "series": f"month {month} floor fraction official",
                "n": int(both.sum()),
                "median": float(np.mean(np.isclose(cm[both], 0.001, atol=1e-6))),
                "mean": float(np.mean(np.isclose(cm_new[both], 0.001, atol=1e-6))),
                "p95": np.nan,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "rvi_savi_cover_scaling.csv", index=False)
    pd.DataFrame(
        [{"intercept": intercept, "slope": slope, "r2": r2, "n_fit": int(x.size), "months": "1-6,9-12"}]
    ).to_csv(OUT / "rvi_savi_fit.csv", index=False)
    print(intercept, slope, r2, x.size)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
