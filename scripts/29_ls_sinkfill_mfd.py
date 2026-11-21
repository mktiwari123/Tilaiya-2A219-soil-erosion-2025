"""Sink-filled slope length on the stored DEM. Coded. Not part of the reported maps.

Priority-flood (Barnes, Lehman, and Mulla, 2014) fills closed pits to their
pour point. Cells that already share a whole-metre elevation stay flat.
The published LS raster is not replaced.

Outputs, written only when this script is run:
  output/rasters/sensitivity/LS_sinkfill_d8_mccool.tif
  output/rasters/sensitivity/LS_sinkfill_mfd_desmet.tif
  output/tables/ls_sinkfill_summary.csv
"""

from pathlib import Path
import heapq
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.rasters import read_band, watershed_mask, write_band

CELL = 12.5
DELTAS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
DIST = CELL * np.array([np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)], dtype=np.float64)
SENS = ROOT / "output" / "rasters" / "sensitivity"
TABLES = ROOT / "output" / "tables"
PUBLISHED = ROOT / "output" / "rasters" / "LS" / "LS.tif"


def priority_flood(dem, inside):
    """Fill pits. Spill points are watershed cells that touch the outside."""
    height, width = dem.shape
    filled = np.where(inside, dem.astype(np.float64), np.nan)
    visited = np.zeros(dem.shape, dtype=bool)
    heap = []
    for row in range(height):
        for col in range(width):
            if not inside[row, col]:
                continue
            edge = row == 0 or col == 0 or row == height - 1 or col == width - 1
            if not edge:
                for d_row, d_col in DELTAS:
                    if not inside[row + d_row, col + d_col]:
                        edge = True
                        break
            if edge:
                visited[row, col] = True
                heapq.heappush(heap, (filled[row, col], row, col))
    while heap:
        elevation, row, col = heapq.heappop(heap)
        for d_row, d_col in DELTAS:
            n_row, n_col = row + d_row, col + d_col
            if n_row < 0 or n_col < 0 or n_row >= height or n_col >= width:
                continue
            if visited[n_row, n_col] or not inside[n_row, n_col]:
                continue
            visited[n_row, n_col] = True
            if filled[n_row, n_col] < elevation:
                filled[n_row, n_col] = elevation
            heapq.heappush(heap, (filled[n_row, n_col], n_row, n_col))
    return filled


def d8_slope_and_area(filled, inside):
    height, width = filled.shape
    slope = np.zeros(filled.shape, dtype=np.float64)
    receiver = np.full(filled.size, -1, dtype=np.int32)
    for row in range(height):
        for col in range(width):
            if not inside[row, col]:
                continue
            best = 0.0
            best_index = -1
            here = filled[row, col]
            for index, (d_row, d_col) in enumerate(DELTAS):
                n_row, n_col = row + d_row, col + d_col
                if n_row < 0 or n_col < 0 or n_row >= height or n_col >= width or not inside[n_row, n_col]:
                    continue
                drop = (here - filled[n_row, n_col]) / DIST[index]
                if drop > best:
                    best = drop
                    best_index = n_row * width + n_col
            slope[row, col] = best
            if best_index >= 0:
                receiver[row * width + col] = best_index
    order = np.argsort(np.where(inside, filled, -1.0e30), axis=None)[::-1]
    acc = np.ones(filled.size, dtype=np.float64)
    for index in order:
        if not inside.ravel()[index]:
            break
        downstream = int(receiver[index])
        if downstream >= 0:
            acc[downstream] += acc[index]
    return slope, acc.reshape(filled.shape)


def mfd_slope_and_area(filled, inside):
    height, width = filled.shape
    acc = np.ones(filled.size, dtype=np.float64)
    slope = np.zeros(filled.shape, dtype=np.float64)
    receivers = [[] for _ in range(filled.size)]
    for row in range(height):
        for col in range(width):
            if not inside[row, col]:
                continue
            here = filled[row, col]
            parts = []
            for index, (d_row, d_col) in enumerate(DELTAS):
                n_row, n_col = row + d_row, col + d_col
                if not (0 <= n_row < height and 0 <= n_col < width and inside[n_row, n_col]):
                    continue
                drop = (here - filled[n_row, n_col]) / DIST[index]
                if drop > 0:
                    parts.append((n_row * width + n_col, drop))
            if not parts:
                continue
            total = sum(item[1] for item in parts)
            slope[row, col] = max(item[1] for item in parts)
            receivers[row * width + col] = [(index, value / total) for index, value in parts]
    order = np.argsort(np.where(inside, filled, -1.0e30), axis=None)[::-1]
    for index in order:
        if not inside.ravel()[index]:
            break
        for downstream, share in receivers[index]:
            acc[downstream] += acc[index] * share
    return slope, acc.reshape(filled.shape)


def usle_mccool(area_cells, slope_tan):
    angle = np.arctan(np.clip(slope_tan, 0, None))
    percent = slope_tan * 100.0
    m_break = np.where(percent >= 5, 0.5, np.where(percent >= 3, 0.4, np.where(percent >= 1, 0.3, 0.2)))
    length = np.maximum(area_cells * CELL, CELL)
    steepness = np.where(percent < 9, 10.8 * np.sin(angle) + 0.03, 16.8 * np.sin(angle) - 0.50)
    steepness = np.clip(steepness, 0, None)
    return np.where(slope_tan > 0, (length / 22.13) ** m_break * steepness, 0.0)


def desmet_govers(area_cells, slope_tan):
    """Multiple-flow form. Specific catchment area uses one cell width."""
    angle = np.arctan(np.clip(slope_tan, 0, None))
    specific = np.maximum(area_cells * CELL, CELL)
    values = (specific / 22.13) ** 0.4 * (np.sin(angle) / 0.0896) ** 1.3
    return np.where(slope_tan > 0, values, 0.0)


def summarise(name, values, inside):
    data = values[inside & np.isfinite(values)]
    return {
        "surface": name,
        "n": int(data.size),
        "mean": float(data.mean()) if data.size else np.nan,
        "median": float(np.median(data)) if data.size else np.nan,
        "share_exactly_zero": float(np.mean(np.isclose(data, 0.0))) if data.size else np.nan,
    }


def main():
    SENS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    inside, profile, _shape = watershed_mask(config.REFERENCE_DEM, config.WATERSHED)
    dem = read_band(config.REFERENCE_DEM)[0]
    dem = np.where(inside, dem, np.nan)
    print("priority-flood")
    filled = priority_flood(dem, inside)
    raised = inside & np.isfinite(dem) & (filled > dem + 1.0e-6)
    print("cells raised", int(raised.sum()))
    print("D8")
    d8_slope, d8_area = d8_slope_and_area(filled, inside)
    print("multiple flow")
    mfd_slope, mfd_area = mfd_slope_and_area(filled, inside)
    d8_ls = usle_mccool(d8_area, d8_slope)
    mfd_ls = desmet_govers(mfd_area, mfd_slope)
    published = read_band(PUBLISHED)[0]
    published = np.where(np.isfinite(published) & ~np.isclose(published, -9999), published, np.nan)
    rows = [
        summarise("Published LS", published, inside & np.isfinite(published)),
        summarise("Sink-filled D8, USLE length and McCool S", d8_ls, inside),
        summarise("Sink-filled multiple flow, Desmet-Govers", mfd_ls, inside),
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(TABLES / "ls_sinkfill_summary.csv", index=False)
    write_band(SENS / "LS_sinkfill_d8_mccool.tif", np.where(inside, d8_ls, np.nan), profile)
    write_band(SENS / "LS_sinkfill_mfd_desmet.tif", np.where(inside, mfd_ls, np.nan), profile)
    print(frame.to_string(index=False))
    print("Published LS.tif was not replaced.")


if __name__ == "__main__":
    main()
