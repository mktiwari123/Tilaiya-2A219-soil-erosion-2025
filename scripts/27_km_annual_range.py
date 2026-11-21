"""Rescale monthly erodibility on an annual Sentinel-1 VV range.

The reported Arnoldus soil-loss rasters and the stored monthly Km rasters
are left in place. Theta in the reported maps is a 5th-95th stretch inside
each month. Here the same equation Km = K * (1 + 0.25 * theta) uses bounds
taken once from the 2025 series, on the pixels where the stored Km is
finite. Two shared bounds are calculated: the literal annual minimum and
maximum, and the 5th and 95th percentiles of all those month-pixels pooled.
A third theta uses each pixel's own annual minimum and maximum.
"""

import os

os.environ.setdefault("GDAL_CACHEMAX", "64")

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.constants import K_MOISTURE_ALPHA, NODATA
from tilaiya.monthly import GEE_BANDS

VV_BAND = GEE_BANDS.index("VV_dB") + 1
KM_DIR = ROOT / "output" / "rasters" / "Erodibility"
SOIL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
OUT = ROOT / "output" / "tables"
SENS = ROOT / "output" / "rasters" / "sensitivity"
K_PATH = config.K_FACTOR
HA = 12.5 * 12.5 / 10000.0
EDGES = np.linspace(-40.0, 15.0, 1101)
WINDOW_ROWS = 256


def stack_path(month):
    name = f"Tilaiya_{config.ANALYSIS_YEAR}_{month:02d}.tif"
    for folder in (config.ALIGNED, ROOT / "gee"):
        path = folder / name
        if path.exists():
            return path
    raise FileNotFoundError(name)


def finite_block(block, nodata):
    out = block.astype(np.float32, copy=False)
    bad = ~np.isfinite(out)
    if nodata is not None:
        bad |= np.isclose(out, nodata)
    bad |= np.isclose(out, NODATA)
    return np.where(bad, np.nan, out)


def percentile_from_hist(counts, target):
    total = int(counts.sum())
    if total <= 0:
        return np.nan
    mark = target / 100.0 * (total - 1)
    cumulative = np.cumsum(counts)
    index = int(np.searchsorted(cumulative, mark, side="left"))
    index = min(max(index, 0), len(EDGES) - 2)
    return float(0.5 * (EDGES[index] + EDGES[index + 1]))


def theta_block(vv, low, high):
    span = float(high - low)
    if not np.isfinite(span) or span <= 0:
        return np.zeros(vv.shape, dtype=np.float32)
    return np.clip((vv - np.float32(low)) / np.float32(span), 0.0, 1.0).astype(np.float32)


def windows(height, width):
    for row in range(0, height, WINDOW_ROWS):
        yield rasterio.windows.Window(0, row, width, min(WINDOW_ROWS, height - row))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SENS.mkdir(parents=True, exist_ok=True)
    with rasterio.open(KM_DIR / "Km_01.tif") as probe, rasterio.open(K_PATH) as k_src:
        height, width = probe.height, probe.width
        profile = probe.profile.copy()
        if (k_src.height, k_src.width) != (height, width):
            raise SystemExit(f"K grid is {k_src.width}x{k_src.height}, Km grid is {width}x{height}.")
    counts = np.zeros(EDGES.size - 1, dtype=np.int64)
    series_min = np.inf
    series_max = -np.inf
    pixel_min = np.full((height, width), np.inf, dtype=np.float32)
    pixel_max = np.full((height, width), -np.inf, dtype=np.float32)
    month_vv_sum = np.zeros(12, dtype=np.float64)
    month_vv_n = np.zeros(12, dtype=np.int64)

    print("pass 1: annual VV range")
    for month in range(1, 13):
        with rasterio.open(stack_path(month)) as src, rasterio.open(KM_DIR / f"Km_{month:02d}.tif") as km_src:
            vv_nodata = src.nodata
            km_nodata = km_src.nodata
            for window in windows(height, width):
                vv = finite_block(src.read(VV_BAND, window=window), vv_nodata)
                km = finite_block(km_src.read(1, window=window), km_nodata)
                ok = np.isfinite(vv) & np.isfinite(km)
                if not ok.any():
                    continue
                sample = vv[ok]
                counts += np.histogram(sample, bins=EDGES)[0]
                series_min = min(series_min, float(sample.min()))
                series_max = max(series_max, float(sample.max()))
                month_vv_sum[month - 1] += float(sample.sum())
                month_vv_n[month - 1] += int(sample.size)
                row = int(window.row_off)
                row_end = row + int(window.height)
                block_min = pixel_min[row:row_end]
                block_max = pixel_max[row:row_end]
                block_min[ok] = np.minimum(block_min[ok], vv[ok])
                block_max[ok] = np.maximum(block_max[ok], vv[ok])
        mean_vv = month_vv_sum[month - 1] / month_vv_n[month - 1]
        print(month, "mean VV", round(mean_vv, 3), "n", int(month_vv_n[month - 1]))

    p5 = percentile_from_hist(counts, 5)
    p95 = percentile_from_hist(counts, 95)
    print("annual min/max", series_min, series_max, "pooled p5/p95", p5, p95)

    bounds = {
        "annual min max": (series_min, series_max),
        "annual p5 p95": (p5, p95),
        "pixel min max": None,
    }
    monthly_rows = []
    summary_rows = []
    for name, pair in bounds.items():
        print("pass", name)
        total = np.zeros((height, width), dtype=np.float64)
        seen = np.zeros((height, width), dtype=np.uint8)
        km_sum = np.zeros(12, dtype=np.float64)
        km_n = np.zeros(12, dtype=np.int64)
        a_sum = np.zeros(12, dtype=np.float64)
        a_n = np.zeros(12, dtype=np.int64)
        for month in range(1, 13):
            with rasterio.open(stack_path(month)) as src, rasterio.open(KM_DIR / f"Km_{month:02d}.tif") as km_src, rasterio.open(
                SOIL / f"SoilLoss_{month:02d}.tif"
            ) as soil_src, rasterio.open(K_PATH) as k_src:
                for window in windows(height, width):
                    vv = finite_block(src.read(VV_BAND, window=window), src.nodata)
                    km_old = finite_block(km_src.read(1, window=window), km_src.nodata)
                    soil = finite_block(soil_src.read(1, window=window), soil_src.nodata)
                    k_base = finite_block(k_src.read(1, window=window), k_src.nodata)
                    ok = np.isfinite(vv) & np.isfinite(km_old) & (km_old > 0) & np.isfinite(soil) & np.isfinite(k_base) & (k_base >= 0)
                    if name == "pixel min max":
                        row = int(window.row_off)
                        row_end = row + int(window.height)
                        low = pixel_min[row:row_end]
                        high = pixel_max[row:row_end]
                        span = high - low
                        theta = np.clip((vv - low) / span, 0.0, 1.0)
                        theta[~np.isfinite(span) | (span <= 0)] = 0.0
                    else:
                        theta = theta_block(vv, pair[0], pair[1])
                    km = k_base * (1.0 + K_MOISTURE_ALPHA * theta)
                    scaled = soil * (km / km_old)
                    ok = ok & np.isfinite(km) & np.isfinite(scaled) & (scaled >= 0)
                    if not ok.any():
                        continue
                    row = int(window.row_off)
                    row_end = row + int(window.height)
                    block_total = total[row:row_end]
                    block_seen = seen[row:row_end]
                    block_total[ok] += scaled[ok]
                    block_seen[ok] += 1
                    km_sum[month - 1] += float(km[ok].sum())
                    km_n[month - 1] += int(ok.sum())
                    a_sum[month - 1] += float(scaled[ok].sum())
                    a_n[month - 1] += int(ok.sum())
            monthly_rows.append(
                {
                    "case": name,
                    "month": month,
                    "mean_VV_dB": month_vv_sum[month - 1] / month_vv_n[month - 1],
                    "n": int(km_n[month - 1]),
                    "mean_Km": km_sum[month - 1] / km_n[month - 1],
                    "mean_A": a_sum[month - 1] / a_n[month - 1],
                }
            )
            print(month, "Km", round(km_sum[month - 1] / km_n[month - 1], 5), "A", round(a_sum[month - 1] / a_n[month - 1], 3))
        full = seen == 12
        data = total[full]
        gross = float(data.sum() * HA)
        summary_rows.append(
            {
                "case": name,
                "annual_min_dB": series_min,
                "annual_max_dB": series_max,
                "pooled_p5_dB": p5,
                "pooled_p95_dB": p95,
                "n": int(full.sum()),
                "mean_t_ha": float(data.mean()) if data.size else np.nan,
                "median_t_ha": float(np.median(data)) if data.size else np.nan,
                "above_100": float(np.mean(data > 100)) if data.size else np.nan,
                "gross_t": gross,
                "gross_m3": gross / 1.45,
            }
        )
        if name in ("annual min max", "annual p5 p95"):
            out = np.where(full, total, np.nan).astype(np.float32)
            stem = "minmax" if name == "annual min max" else "p5p95"
            profile.update(dtype=rasterio.float32, count=1, nodata=NODATA, compress="lzw")
            destination = SENS / f"SoilLoss_annual_Km_annual_{stem}.tif"
            with rasterio.open(destination, "w", **profile) as dst:
                dst.write(np.where(np.isfinite(out), out, NODATA).astype(np.float32), 1)
        del total, seen

    monthly = pd.DataFrame(monthly_rows)
    summary = pd.DataFrame(summary_rows)
    monthly.to_csv(OUT / "km_annual_range_monthly.csv", index=False)
    summary.to_csv(OUT / "km_annual_range_summary.csv", index=False)
    print(monthly.to_string(index=False))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
