"""Erosivity-weighted cover by land-cover class, linear and exponential.

Reported soil-loss rasters are left in place. The class means are the
cover factors already used in the 2025 scenarios, set beside published
values in the manuscript. No new C table is fitted.
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
from tilaiya.constants import NODATA
from tilaiya.factors import arnoldus_monthly_erosivity, vander_knijff_cover
from tilaiya.monthly import GEE_BANDS

NDVI_BAND = GEE_BANDS.index("NDVI") + 1
CM_BAND = GEE_BANDS.index("Cm") + 1
STACK = ROOT / "data" / "aligned"
SOIL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif"
EROSIVITY = ROOT / "output" / "rasters" / "Erosivity" / "Erosivity_annual.tif"
LULC = config.BASELINE / "Aligned_2.tif" / "LULC_aligned.tif"
OUT = ROOT / "output" / "tables"
WINDOW_ROWS = 256
CLASS_NAME = {0: "Built-up", 1: "Cropland", 2: "Vegetation", 3: "Water", 4: "Barren land"}
RAINFALL = {
    1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
    2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
    3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
    4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
    5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
}
STUDY = {894.0: 1, 1225.0: 2, 786.0: 3, 1046.0: 4, 1292.0: 5}


def finite_block(block, nodata):
    out = np.asarray(block, dtype=np.float32)
    bad = ~np.isfinite(out)
    if nodata is not None:
        bad |= np.isclose(out, nodata)
    bad |= np.isclose(out, NODATA)
    return np.where(bad, np.nan, out)


def windows(height, width):
    for row in range(0, height, WINDOW_ROWS):
        yield row, rasterio.windows.Window(0, row, width, min(WINDOW_ROWS, height - row))


def read_window(src, band, window):
    return finite_block(src.read(band, window=window), src.nodata)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    monthly_r = {cell: arnoldus_monthly_erosivity(rain) for cell, rain in RAINFALL.items()}
    with rasterio.open(SOIL) as soil_src:
        height, width = soil_src.height, soil_src.width
    keys = np.array(sorted(STUDY), dtype=np.float32)
    sum_w = np.zeros(5, dtype=np.float64)
    sum_lin = np.zeros(5, dtype=np.float64)
    sum_exp = np.zeros(5, dtype=np.float64)
    july_n = np.zeros(5, dtype=np.float64)
    july_lin = np.zeros(5, dtype=np.float64)
    july_exp = np.zeros(5, dtype=np.float64)

    with rasterio.open(SOIL) as soil_src, rasterio.open(EROSIVITY) as r_src, rasterio.open(LULC) as lulc_src:
        if (r_src.height, r_src.width) != (height, width) or (lulc_src.height, lulc_src.width) != (height, width):
            raise SystemExit("Cover benchmark grids do not share the soil-loss shape.")
        sources = {month: rasterio.open(STACK / f"Tilaiya_2025_{month:02d}.tif") for month in range(1, 13)}
        try:
            for row, window in windows(height, width):
                support = np.isfinite(read_window(soil_src, 1, window))
                annual_r = read_window(r_src, 1, window)
                classes = np.rint(read_window(lulc_src, 1, window))
                cells = np.full(annual_r.shape, -1, dtype=np.int16)
                finite_r = np.isfinite(annual_r)
                nearest = np.full(annual_r.shape, np.nan, dtype=np.float32)
                if finite_r.any():
                    nearest[finite_r] = keys[np.abs(annual_r[finite_r][:, None] - keys[None, :]).argmin(axis=1)]
                for value, cell in STUDY.items():
                    cells[np.isfinite(nearest) & np.isclose(nearest, np.float32(value))] = cell
                june_cm = read_window(sources[6], CM_BAND, window)
                june_ndvi = read_window(sources[6], NDVI_BAND, window)
                sept_cm = read_window(sources[9], CM_BAND, window)
                sept_ndvi = read_window(sources[9], NDVI_BAND, window)
                for month in range(1, 13):
                    if month == 7:
                        cm = (2.0 / 3.0) * june_cm + (1.0 / 3.0) * sept_cm
                        ndvi = (2.0 / 3.0) * june_ndvi + (1.0 / 3.0) * sept_ndvi
                    elif month == 8:
                        cm = (1.0 / 3.0) * june_cm + (2.0 / 3.0) * sept_cm
                        ndvi = (1.0 / 3.0) * june_ndvi + (2.0 / 3.0) * sept_ndvi
                    else:
                        cm = read_window(sources[month], CM_BAND, window)
                        ndvi = read_window(sources[month], NDVI_BAND, window)
                    c_exp = vander_knijff_cover(ndvi).astype(np.float32)
                    rm = np.full(cm.shape, np.nan, dtype=np.float32)
                    for cell, series in monthly_r.items():
                        rm[cells == cell] = np.float32(series[month - 1])
                    ok = support & np.isfinite(rm) & np.isfinite(cm) & np.isfinite(c_exp) & (classes >= 0) & (classes <= 4)
                    if not ok.any():
                        continue
                    for code in range(5):
                        group = ok & (classes == code)
                        if not group.any():
                            continue
                        weight = rm[group].astype(np.float64)
                        sum_w[code] += float(weight.sum())
                        sum_lin[code] += float((weight * cm[group]).sum())
                        sum_exp[code] += float((weight * c_exp[group]).sum())
                        if month == 7:
                            july_n[code] += float(group.sum())
                            july_lin[code] += float(cm[group].sum())
                            july_exp[code] += float(c_exp[group].sum())
                if row % (WINDOW_ROWS * 4) == 0:
                    print("row", row)
        finally:
            for src in sources.values():
                src.close()

    rows = []
    for code, name in CLASS_NAME.items():
        rows.append(
            {
                "class": name,
                "R_weighted_linear_C": sum_lin[code] / sum_w[code] if sum_w[code] else np.nan,
                "R_weighted_exponential_C": sum_exp[code] / sum_w[code] if sum_w[code] else np.nan,
                "July_linear_C": july_lin[code] / july_n[code] if july_n[code] else np.nan,
                "July_exponential_C": july_exp[code] / july_n[code] if july_n[code] else np.nan,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "cover_by_class_versus_benchmarks.csv", index=False)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
