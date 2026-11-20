"""July cover bins and annual means under three cover treatments.

Official soil-loss rasters are not replaced. This writes comparison tables.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config

OUT = ROOT / "output" / "tables"
STACK = ROOT / "data" / "aligned"
SOIL = ROOT / "output" / "rasters" / "SoilLoss"
NODATA = -9999.0
BAND = {"SAVI": 1, "Cm_optical": 5, "RVI": 8, "Cm": 9}


def read_raster(path):
    with rasterio.open(path) as src:
        values = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        values[np.isclose(values, nodata)] = np.nan
    values[np.isclose(values, NODATA)] = np.nan
    values[values < 0] = np.nan
    return values


def band(month, name):
    path = STACK / f"Tilaiya_2025_{month:02d}.tif"
    with rasterio.open(path) as src:
        values = src.read(BAND[name]).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        values[np.isclose(values, nodata)] = np.nan
    values[np.isclose(values, NODATA)] = np.nan
    return values


def soil(month):
    return read_raster(SOIL / f"SoilLoss_{month:02d}.tif")


def summarise(name, values):
    data = values[np.isfinite(values)]
    return {
        "treatment": name,
        "n": int(data.size),
        "mean": float(np.mean(data)),
        "median": float(np.median(data)),
        "p95": float(np.percentile(data, 95)),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ls = read_raster(config.LS_FACTOR)
    a6 = soil(6)
    a7 = soil(7)
    cm7 = band(7, "Cm")
    shared = np.isfinite(a6) & np.isfinite(a7) & np.isfinite(cm7) & np.isfinite(ls)
    bins = [
        ("Cm = 0.001", np.isclose(cm7, 0.001, atol=1e-6)),
        ("0.001 < Cm <= 0.05", (cm7 > 0.001 + 1e-6) & (cm7 <= 0.05)),
        ("0.05 < Cm <= 0.15", (cm7 > 0.05) & (cm7 <= 0.15)),
        ("0.15 < Cm <= 0.40", (cm7 > 0.15) & (cm7 <= 0.40)),
        ("Cm > 0.40", cm7 > 0.40),
    ]
    rows = []
    n_shared = int(shared.sum())
    below = shared & (a7 < 0.01)
    n_below = int(below.sum())
    for label, mask in bins:
        sel = shared & mask
        n = int(sel.sum())
        rows.append(
            {
                "bin": label,
                "n": n,
                "share": n / n_shared,
                "share_of_A_below_0.01": int((sel & below).sum()) / n_below,
                "fraction_of_bin_below_0.01": float(np.mean(a7[sel] < 0.01)) if n else np.nan,
                "median_A_july": float(np.median(a7[sel])) if n else np.nan,
                "median_A_june": float(np.median(a6[sel])) if n else np.nan,
                "median_LS": float(np.median(ls[sel])) if n else np.nan,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "july_cover_bins.csv", index=False)
    print(frame.to_string(index=False))
    low = shared & (a7 < 0.01)
    high = shared & (a7 >= 0.01)
    extra = pd.DataFrame(
        [
            {
                "group": "July A < 0.01",
                "n": int(low.sum()),
                "median_LS": float(np.median(ls[low])),
                "median_Cm": float(np.median(cm7[low])),
                "median_A_june": float(np.median(a6[low])),
            },
            {
                "group": "July A >= 0.01",
                "n": int(high.sum()),
                "median_LS": float(np.median(ls[high])),
                "median_Cm": float(np.median(cm7[high])),
                "median_A_june": float(np.median(a6[high])),
            },
        ]
    )
    extra.to_csv(OUT / "july_low_loss_versus_rest.csv", index=False)
    print(extra.to_string(index=False))
    print("shared", n_shared, "below_0.01", n_below, n_below / n_shared)

    months = {m: soil(m) for m in range(1, 13)}
    valid = np.ones(a7.shape, dtype=bool)
    for values in months.values():
        valid &= np.isfinite(values)
    official = np.zeros(a7.shape, dtype=np.float64)
    for values in months.values():
        official += np.where(valid, values, 0.0)
    official[~valid] = np.nan

    def rescale(month, new_cm):
        old = band(month, "Cm")
        out = months[month].copy()
        ok = valid & np.isfinite(new_cm) & np.isfinite(old) & (old > 0)
        out[ok] = months[month][ok] * (new_cm[ok] / old[ok])
        out[~valid] = np.nan
        return out

    optical_annual = official.copy()
    gap_annual = official.copy()
    line_annual = official.copy()
    intercept, slope = 0.23487652445509008, 0.09754669155761421
    month_rows = []
    for month, weight_june in ((7, 2 / 3), (8, 1 / 3)):
        cm_opt = band(month, "Cm_optical")
        cm_june = band(6, "Cm")
        cm_sep = band(9, "Cm")
        gap = weight_june * cm_june + (1 - weight_june) * cm_sep
        rvi = band(month, "RVI")
        savi_hat = np.clip(intercept + slope * rvi, 0, 1)
        cm_line = np.clip(1 - 1.18 * savi_hat, 0.001, 1)
        cm_line[~np.isfinite(rvi)] = np.nan
        for name, new_cm, total in (
            ("optical SAVI", cm_opt, optical_annual),
            ("June-September interpolation", gap, gap_annual),
            ("RVI line", cm_line, line_annual),
        ):
            replaced = rescale(month, new_cm)
            delta = np.where(valid, replaced - months[month], 0.0)
            total += np.nan_to_num(delta, nan=0.0)
            month_rows.append(summarise(f"{name} month {month}", replaced))
            month_rows.append(
                {
                    "treatment": f"{name} month {month} optical or new cover finite",
                    "n": int((valid & np.isfinite(new_cm)).sum()),
                    "mean": np.nan,
                    "median": np.nan,
                    "p95": np.nan,
                }
            )
    annual_rows = [
        summarise("official RVI July-August", official),
        summarise("July-August Cm from SAVI where the optical factor is finite", optical_annual),
        summarise("July-August Cm interpolated between June and September", gap_annual),
        summarise("July-August Cm from the SAVI-on-RVI line", line_annual),
    ]
    annual = pd.DataFrame(annual_rows)
    monthly = pd.DataFrame(month_rows)
    annual.to_csv(OUT / "annual_mean_cover_treatments.csv", index=False)
    monthly.to_csv(OUT / "monthly_cover_treatments.csv", index=False)
    print(annual.to_string(index=False))
    print(monthly.to_string(index=False))


if __name__ == "__main__":
    main()
