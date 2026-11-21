"""Desmet-Govers multiple-flow LS on Copernicus GLO-30.

The published LS raster and the reported Arnoldus soil-loss maps are not
replaced. LS is zero only where every neighbour is at the same elevation
or higher. Contributing area is the slope-weighted multiple-flow
accumulation. The length-slope factor is the specific-catchment form
used by Moore and Burch (1986) and Desmet and Govers (1996):

    LS = 1.4 * (A_s / 22.13)^0.4 * (sin β / 0.0896)^1.3

A_s is contributing area per unit width, in metres. β is the steepest
downslope angle.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tilaiya.factors import arnoldus_monthly_erosivity
from tilaiya.rasters import read_band, write_band

CELL = 12.5
AREA = CELL * CELL
OFFSETS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
DIST = CELL * np.array([np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)], dtype=np.float64)
COP = ROOT / "output" / "rasters" / "sensitivity" / "Copernicus_GLO30_12m5.tif"
ANNUAL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif"
KM_DIR = ROOT / "output" / "rasters" / "Erodibility"
P_PATH = ROOT / "output" / "rasters" / "Practice" / "P.tif"
STACK = ROOT / "data" / "aligned"
EROSIVITY = ROOT / "output" / "rasters" / "Erosivity" / "Erosivity_annual.tif"
SENS = ROOT / "output" / "rasters" / "sensitivity"
TABLES = ROOT / "output" / "tables"
RAINFALL = {
    1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
    2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
    3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
    4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
    5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
}
STUDY = {894.0: 1, 1225.0: 2, 786.0: 3, 1046.0: 4, 1292.0: 5}


def clean(values):
    out = np.asarray(values, dtype=np.float32)
    bad = ~np.isfinite(out) | np.isclose(out, -9999) | np.isclose(out, 32767)
    return np.where(bad, np.nan, out)


def neighbor_views(array):
    padded = np.pad(array, 1, constant_values=np.nan)
    height, width = array.shape
    views = []
    for d_row, d_col in OFFSETS:
        views.append(padded[1 + d_row : 1 + d_row + height, 1 + d_col : 1 + d_col + width])
    return views


def multiple_flow(dem, inside):
    """Slope-proportional area. Returns steepest slope (rise/run) and cell count."""
    z = np.where(inside, dem.astype(np.float32), np.nan)
    views = neighbor_views(z)
    height, width = z.shape
    weights = []
    slope_max = np.zeros((height, width), dtype=np.float32)
    for index, view in enumerate(views):
        drop = (z - view) / np.float32(DIST[index])
        drop = np.where(np.isfinite(drop) & (drop > 0), drop, np.float32(0))
        weights.append(drop)
        np.maximum(slope_max, drop, out=slope_max)
    total = np.zeros((height, width), dtype=np.float32)
    for drop in weights:
        total += drop
    order = np.argsort(np.where(inside, z, np.float32(-1.0e30)), axis=None)[::-1]
    acc = np.ones(height * width, dtype=np.float64)
    flat_inside = inside.ravel()
    flat_z = z.ravel()
    flat_total = total.ravel()
    flat_w = [item.ravel() for item in weights]
    neighbors = []
    rows = np.arange(height, dtype=np.int32)[:, None]
    cols = np.arange(width, dtype=np.int32)[None, :]
    for d_row, d_col in OFFSETS:
        n_row = rows + d_row
        n_col = cols + d_col
        valid = (n_row >= 0) & (n_row < height) & (n_col >= 0) & (n_col < width)
        index = np.where(valid, n_row * width + n_col, -1).ravel()
        neighbors.append(index)
    for count, index in enumerate(order):
        if not flat_inside[index] or not np.isfinite(flat_z[index]):
            break
        area = acc[index]
        share_total = float(flat_total[index])
        if share_total <= 0:
            continue
        for band in range(8):
            downstream = int(neighbors[band][index])
            portion = float(flat_w[band][index])
            if downstream >= 0 and portion > 0:
                acc[downstream] += area * (portion / share_total)
        if count and count % 1000000 == 0:
            print("accumulated", count)
    return slope_max, acc.reshape(height, width)


def desmet_govers(area_cells, slope_tan):
    specific = np.maximum(area_cells, 1.0) * CELL
    angle = np.arctan(np.clip(slope_tan, 0, None))
    values = 1.4 * (specific / 22.13) ** 0.4 * (np.sin(angle) / 0.0896) ** 1.3
    return np.where(slope_tan > 0, values, 0.0).astype(np.float32)


def rainfall_cells(shape_r):
    annual = clean(read_band(EROSIVITY)[0])
    keys = np.array(sorted(STUDY), dtype=np.float32)
    cells = np.full(annual.shape, -1, dtype=np.int16)
    finite = np.isfinite(annual)
    if finite.any():
        chosen = keys[np.abs(annual[finite][:, None] - keys[None, :]).argmin(axis=1)]
        nearest = np.full(annual.shape, np.nan, dtype=np.float32)
        nearest[finite] = chosen
        for value, cell in STUDY.items():
            cells[np.isfinite(nearest) & np.isclose(nearest, np.float32(value))] = cell
    monthly = {cell: arnoldus_monthly_erosivity(rain) for cell, rain in RAINFALL.items()}
    return cells, monthly


def annual_soil_loss(ls, cells, monthly):
    june = clean(read_band(STACK / "Tilaiya_2025_06.tif", band=9)[0])
    september = clean(read_band(STACK / "Tilaiya_2025_09.tif", band=9)[0])
    practice = clean(read_band(P_PATH)[0])
    total = np.zeros(ls.shape, dtype=np.float64)
    valid = np.ones(ls.shape, dtype=bool)
    for month in range(1, 13):
        if month == 7:
            cover = (2.0 / 3.0) * june + (1.0 / 3.0) * september
        elif month == 8:
            cover = (1.0 / 3.0) * june + (2.0 / 3.0) * september
        else:
            cover = clean(read_band(STACK / f"Tilaiya_2025_{month:02d}.tif", band=9)[0])
        km = clean(read_band(KM_DIR / f"Km_{month:02d}.tif")[0])
        erosivity = np.full(ls.shape, np.nan, dtype=np.float32)
        for cell, series in monthly.items():
            erosivity[cells == cell] = np.float32(series[month - 1])
        soil = erosivity.astype(np.float64) * km * ls * cover * practice
        dry = np.isfinite(erosivity) & np.isclose(erosivity, 0) & np.isfinite(km) & np.isfinite(ls) & np.isfinite(cover) & np.isfinite(practice)
        soil = np.where(dry, 0.0, soil)
        finite = np.isfinite(soil) & (soil >= 0)
        valid &= finite | dry
        total += np.where(finite, soil, 0.0)
        print("month", month)
    return np.where(valid, total, np.nan)


def main():
    SENS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    dem, profile = read_band(COP)
    dem = clean(dem)
    support = np.isfinite(clean(read_band(ANNUAL)[0]))
    inside = np.isfinite(dem) & support
    print("inside", int(inside.sum()))
    print("multiple flow")
    slope, area = multiple_flow(dem, inside)
    ls = desmet_govers(area, slope)
    ls = np.where(inside, ls, np.nan)
    print("LS mean", float(np.nanmean(ls[inside])), "zero share", float(np.mean(np.isclose(ls[inside], 0))))
    cells, monthly = rainfall_cells(dem.shape)
    print("soil loss")
    soil = annual_soil_loss(ls, cells, monthly)
    both = inside & np.isfinite(soil)
    data = soil[both]
    row = {
        "n": int(both.sum()),
        "ls_mean": float(np.nanmean(ls[inside])),
        "ls_median": float(np.nanmedian(ls[inside])),
        "ls_zero_share": float(np.mean(np.isclose(ls[inside], 0))),
        "soil_mean": float(data.mean()) if data.size else np.nan,
        "soil_median": float(np.median(data)) if data.size else np.nan,
        "share_0_to_5": float(np.mean(data <= 5)) if data.size else np.nan,
        "share_above_100": float(np.mean(data > 100)) if data.size else np.nan,
    }
    pd.DataFrame([row]).to_csv(TABLES / "copernicus_mfd_desmet.csv", index=False)
    write_band(SENS / "LS_copernicus_mfd_desmet.tif", ls, profile)
    write_band(SENS / "SoilLoss_annual_copernicus_mfd.tif", soil, profile)
    print(row)
    print("Published LS and Arnoldus soil-loss rasters were not replaced.")


if __name__ == "__main__":
    main()
