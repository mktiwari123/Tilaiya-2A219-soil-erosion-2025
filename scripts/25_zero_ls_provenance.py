"""Classify published LS zeros on the annual support.

The published LS raster and the Arnoldus soil-loss rasters are not replaced.
Routing uses the same steepest-descent D8 already scored in script 20.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.rasters import read_band

DEM_NODATA = 32767.0
TABLES = ROOT / "output" / "tables"
COPERNICUS_GRID = ROOT / "output" / "rasters" / "sensitivity" / "Copernicus_GLO30_12m5.tif"


CELL = 12.5
OFFSETS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
DISTANCES = CELL * np.array([np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)], dtype=np.float32)


def d8_slope_and_receiver(dem):
    """Steepest-descent slope (rise/run). One neighbour is held at a time."""
    z = np.where(np.isfinite(dem), dem.astype(np.float32), np.float32(np.nan))
    height, width = z.shape
    padded = np.pad(z, 1, constant_values=np.float32(np.nan))
    max_slope = np.zeros((height, width), dtype=np.float32)
    best = np.zeros((height, width), dtype=np.uint8)
    for index, ((row_shift, col_shift), distance) in enumerate(zip(OFFSETS, DISTANCES)):
        neighbour = padded[1 + row_shift : 1 + row_shift + height, 1 + col_shift : 1 + col_shift + width]
        drop = (z - neighbour) / distance
        better = np.isfinite(drop) & (drop > max_slope)
        max_slope[better] = drop[better]
        best[better] = np.uint8(index)
    di = np.array([-1, -1, -1, 0, 0, 1, 1, 1], dtype=np.int32)
    dj = np.array([-1, 0, 1, -1, 1, -1, 0, 1], dtype=np.int32)
    rows = np.arange(height, dtype=np.int32)[:, None]
    cols = np.arange(width, dtype=np.int32)[None, :]
    receiver_row = rows + di[best]
    receiver_col = cols + dj[best]
    receiver = np.full(height * width, -1, dtype=np.int32)
    has_exit = max_slope.ravel() > 0
    receiver[has_exit] = (receiver_row * width + receiver_col).ravel()[has_exit]
    return max_slope.astype(np.float32), receiver


def accumulate(dem, receiver):
    height, width = dem.shape
    elev = np.where(np.isfinite(dem), dem.astype(np.float32), np.float32(-1.0e30)).ravel()
    order = np.argsort(elev, kind="mergesort")[::-1]
    acc = np.ones(height * width, dtype=np.float32)
    for index in order:
        if elev[index] < -1.0e29:
            break
        downstream = int(receiver[index])
        if downstream >= 0:
            acc[downstream] += acc[index]
    return acc.reshape(height, width)


def clean(values):
    out = np.asarray(values, dtype=np.float32)
    out[~np.isfinite(out)] = np.nan
    out[np.isclose(out, -9999.0)] = np.nan
    return out


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    dem = read_band(config.REFERENCE_DEM)[0]
    dem = np.where(np.isclose(dem, DEM_NODATA), np.nan, dem.astype(np.float32))
    published = clean(read_band(ROOT / "output" / "rasters" / "LS" / "LS.tif")[0])
    annual = clean(read_band(ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif")[0])
    lulc = read_band(config.BASELINE / "Aligned_2.tif" / "LULC_aligned.tif")[0]
    water = np.rint(lulc) == 3
    support = np.isfinite(annual) & np.isfinite(published)
    zero = support & np.isclose(published, 0.0)
    del annual, lulc

    print("D8 on the integer-metre DEM")
    slope, receiver = d8_slope_and_receiver(dem)
    acc = accumulate(dem, receiver)
    flat = np.isclose(slope, 0.0)
    print("Copernicus D8 slope")
    cop = clean(read_band(COPERNICUS_GRID)[0])
    slope_cop, _receiver_cop = d8_slope_and_receiver(cop)
    del cop, _receiver_cop
    cop_deg = np.degrees(np.arctan(slope_cop))
    cop_pct = slope_cop * 100.0

    groups = [
        ("Published LS exactly 0", zero),
        ("Water", zero & water),
        ("No water, no D8 drop, accumulation 1", zero & ~water & flat & np.isclose(acc, 1.0)),
        ("No water, no D8 drop, accumulation above 1", zero & ~water & flat & (acc > 1)),
        ("No water, D8 drop positive", zero & ~water & ~flat),
        ("Published LS positive", support & (published > 0)),
    ]
    n_zero = int(zero.sum())
    n_support = int(support.sum())
    rows = []
    for name, mask in groups:
        count = int(mask.sum())
        rows.append(
            {
                "group": name,
                "pixels": count,
                "share_of_zero_LS": count / n_zero if n_zero and name != "Published LS positive" else np.nan,
                "share_of_annual_support": count / n_support if n_support else np.nan,
                "median_integer_slope_percent": float(np.median(slope[mask] * 100.0)) if count else np.nan,
                "median_copernicus_slope_percent": float(np.median(cop_pct[mask])) if count else np.nan,
                "share_copernicus_slope_above_0.5_deg": float(np.mean(cop_deg[mask] > 0.5)) if count else np.nan,
                "median_accumulation_cells": float(np.median(acc[mask])) if count else np.nan,
                "share_accumulation_equals_1": float(np.mean(np.isclose(acc[mask], 1.0))) if count else np.nan,
                "share_one_metre_cardinal_step": float(np.mean(np.isclose(slope[mask] * 100.0, 8.0, atol=0.05))) if count else np.nan,
                "share_one_metre_diagonal_step": float(np.mean(np.isclose(slope[mask] * 100.0, 100.0 / (12.5 * np.sqrt(2)), atol=0.05))) if count else np.nan,
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(TABLES / "zero_ls_provenance.csv", index=False)
    print("annual support", n_support, "zero LS", n_zero, "share", n_zero / n_support)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
