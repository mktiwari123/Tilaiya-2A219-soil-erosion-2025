"""Condition satellite DEMs and recompute multiple-flow slope length.

Satellites
  ALOS PALSAR (L-band), the stored 12.5 m whole-metre grid
  TanDEM-X, Copernicus GLO-30 already aligned to that grid
  SRTM (C-band), the 1-arc-second tile N24E085
  ASTER GDEM v3, Terra optical stereo, tile N24E085 elevation only
  (data/dem/ASTGTMV003_N24E085_dem.tif). The matching _num.tif stack
  count is not an elevation surface. Neighbouring tiles lie outside
  the reference grid.

Each surface is bilinear on the ALOS grid where it is not already on that
grid. Closed pits are filled by a priority flood from the mask boundary.
Cells that are still level after the fill receive a 1 mm rise per cell
away from the spill, so a filled flat has a drainage direction. That
increment is a conditioning step. It is not a measured slope.

LS uses the same Desmet-Govers form as scripts/33_copernicus_mfd_ls.py.
The published LS raster and the Arnoldus soil-loss maps are not replaced.
A source whose LS raster and CSV row already exist is left unchanged.
"""

import gzip
import os
from pathlib import Path
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("GDAL_CACHEMAX", "64")

print("import numpy", flush=True)
import numpy as np
print("import pandas", flush=True)
import pandas as pd
print("import rasterio", flush=True)
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

print("import config", flush=True)
import config
from tilaiya.rasters import align_to_reference, read_band, write_band

import importlib.util

SPEC = importlib.util.spec_from_file_location(
    "mfd", ROOT / "scripts" / "33_copernicus_mfd_ls.py"
)
print("import flow module", flush=True)
MFD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MFD)
print("imports done", flush=True)

DEM_DIR = ROOT / "data" / "dem"
SENS = ROOT / "output" / "rasters" / "sensitivity"
TABLES = ROOT / "output" / "tables"
HGT = DEM_DIR / "SRTM_N24E085.hgt.gz"
SRTM_TIF = DEM_DIR / "SRTM_N24E085.tif"
SRTM_GRID = SENS / "SRTM_GL1_12m5.tif"
ASTER_DEM = DEM_DIR / "ASTGTMV003_N24E085_dem.tif"
ASTER_GRID = SENS / "ASTER_GDEM_12m5.tif"
ANNUAL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif"
EPSILON_M = np.float32(0.001)
OFFSETS = MFD.OFFSETS


def write_srtm_geotiff():
    raw = gzip.open(HGT, "rb").read()
    side = 3601
    values = np.frombuffer(raw, dtype=">i2").reshape(side, side).astype(np.float32)
    values[values < -1000] = np.float32(-9999)
    # HGT samples are posts. The first post is the point 85 E, 25 N.
    half = 0.5 / 3600.0
    profile = {
        "driver": "GTiff",
        "height": side,
        "width": side,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(85.0 - half, 25.0 + half, 1.0 / 3600.0, 1.0 / 3600.0),
        "nodata": -9999.0,
        "compress": "lzw",
    }
    SRTM_TIF.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(SRTM_TIF, "w", **profile) as output:
        output.write(values, 1)


def no_downslope(dem, inside):
    z = np.where(inside, dem.astype(np.float32), np.nan)
    views = MFD.neighbor_views(z)
    drains = np.zeros(z.shape, dtype=bool)
    finite = np.isfinite(z)
    for view in views:
        drains |= finite & np.isfinite(view) & (z > view)
    return inside & finite & ~drains


def neighbor_index(height, width):
    rows = np.arange(height, dtype=np.int32)[:, None]
    cols = np.arange(width, dtype=np.int32)[None, :]
    indexes = []
    for d_row, d_col in OFFSETS:
        n_row = rows + d_row
        n_col = cols + d_col
        valid = (n_row >= 0) & (n_row < height) & (n_col >= 0) & (n_col < width)
        indexes.append(np.where(valid, n_row * width + n_col, -1).ravel())
    return indexes


def priority_fill(dem, inside):
    """Barnes priority flood. Boundary cells of the mask are the outlets."""
    import heapq

    z = np.where(inside, dem.astype(np.float32), np.nan)
    height, width = z.shape
    filled = z.copy()
    closed = ~inside | ~np.isfinite(z)
    neighbors = neighbor_index(height, width)
    edge = inside & np.isfinite(z)
    edge[1:-1, 1:-1] = False
    padded = np.pad(inside & np.isfinite(z), 1, constant_values=False)
    for d_row, d_col in OFFSETS:
        view = padded[1 + d_row : 1 + d_row + height, 1 + d_col : 1 + d_col + width]
        edge |= (inside & np.isfinite(z) & ~view)
    heap = []
    flat_z = z.ravel()
    closed_flat = closed.ravel()
    for index in np.flatnonzero(edge):
        heapq.heappush(heap, (float(flat_z[index]), int(index)))
        closed_flat[index] = True
    filled_flat = filled.ravel()
    seen = 0
    while heap:
        elev, index = heapq.heappop(heap)
        seen += 1
        if seen % 1000000 == 0:
            print("filled", seen, flush=True)
        for band in range(8):
            downstream = int(neighbors[band][index])
            if downstream < 0 or closed_flat[downstream]:
                continue
            closed_flat[downstream] = True
            native = float(flat_z[downstream])
            if not np.isfinite(native):
                continue
            spill = native if native >= elev else elev
            if native < elev:
                filled_flat[downstream] = np.float32(elev)
            heapq.heappush(heap, (spill, downstream))
    return filled_flat.reshape(height, width)


def drain_flats(filled, inside):
    """Raise level cells by 1 mm per cell away from a draining neighbour."""
    from collections import deque

    surface = np.where(inside, filled.astype(np.float32), np.nan)
    flat = no_downslope(surface, inside)
    if not flat.any():
        return surface, 0
    finite = np.isfinite(surface)
    drains = ~flat & inside & finite
    padded = np.pad(drains, 1, constant_values=False)
    height, width = flat.shape
    touch = np.zeros(flat.shape, dtype=bool)
    for d_row, d_col in OFFSETS:
        view = padded[1 + d_row : 1 + d_row + height, 1 + d_col : 1 + d_col + width]
        touch |= view
    seed = flat & touch
    queue = deque(int(index) for index in np.flatnonzero(seed))
    distance = np.full(flat.size, -1, dtype=np.int32)
    distance[np.flatnonzero(seed)] = 1
    neighbors = neighbor_index(height, width)
    flat_flat = flat.ravel()
    while queue:
        index = queue.popleft()
        step = int(distance[index]) + 1
        for band in range(8):
            nxt = int(neighbors[band][index])
            if nxt >= 0 and flat_flat[nxt] and distance[nxt] < 0:
                distance[nxt] = step
                queue.append(nxt)
    changed = distance > 0
    surface.ravel()[changed] = surface.ravel()[changed] + EPSILON_M * distance[changed]
    return surface, int(changed.sum())


def steepest(dem, inside):
    """Steepest downward slope, rise over run. No flow accumulation."""
    z = np.where(inside, dem.astype(np.float32), np.nan)
    views = MFD.neighbor_views(z)
    slope_max = np.zeros(z.shape, dtype=np.float32)
    finite = np.isfinite(z)
    for index, view in enumerate(views):
        drop = (z - view) / np.float32(MFD.DIST[index])
        drop = np.where(finite & np.isfinite(view) & (drop > 0), drop, np.float32(0))
        np.maximum(slope_max, drop, out=slope_max)
    return slope_max


def metrics(name, satellite, dem, inside, filled, conditioned, n_conditioned, slope, ls, soil):
    raw_zero = no_downslope(dem, inside)
    filled_zero = no_downslope(filled, inside)
    still_zero = no_downslope(conditioned, inside)
    both = inside & np.isfinite(soil) & (soil >= 0) & np.isfinite(ls)
    loss = soil[both]
    n_inside = max(int(inside.sum()), 1)
    return {
        "dem": name,
        "satellite": satellite,
        "n": int(both.sum()),
        "raw_flat_share": float(raw_zero.sum() / n_inside),
        "filled_flat_share": float(filled_zero.sum() / n_inside),
        "still_flat_share": float(still_zero.sum() / n_inside),
        "gentle_share": float(np.mean(np.degrees(np.arctan(slope[inside])) < 0.5)),
        "pit_share": float(np.mean((filled[inside] > dem[inside] + np.float32(0.01)))),
        "conditioned_cells": n_conditioned,
        "ls_zero_share": float((both & (ls == 0)).sum() / max(int(both.sum()), 1)),
        "ls_mean": float(np.mean(ls[both])),
        "ls_median": float(np.median(ls[both])),
        "soil_mean": float(np.mean(loss)),
        "soil_median": float(np.median(loss)),
        "share_0_to_5": float(np.mean(loss <= 5)),
        "share_above_100": float(np.mean(loss > 100)),
    }


def summarise(name, satellite, dem, inside, cells, monthly, profile):
    raw_zero = no_downslope(dem, inside)
    print(name, "fill", flush=True)
    filled = priority_fill(dem, inside)
    filled_zero = no_downslope(filled, inside)
    print(name, "flats", int(filled_zero.sum()), flush=True)
    conditioned, n_conditioned = drain_flats(filled, inside)
    still_zero = no_downslope(conditioned, inside)
    print(name, "flow", flush=True)
    slope, area = MFD.multiple_flow(conditioned, inside)
    ls = MFD.desmet_govers(area, slope)
    del area
    ls = np.where(inside, ls, np.nan).astype(np.float32)
    print(name, "soil", flush=True)
    soil = MFD.annual_soil_loss(ls, cells, monthly)
    both = inside & np.isfinite(soil) & (soil >= 0) & np.isfinite(ls)
    write_band(SENS / f"LS_{name}_filled_mfd.tif", ls, profile)
    write_band(
        SENS / f"DEM_{name}_conditioned.tif",
        np.where(inside, conditioned, np.nan).astype(np.float32),
        profile,
    )
    write_band(
        SENS / f"SoilLoss_annual_{name}_filled_mfd.tif",
        np.where(both, soil, np.nan).astype(np.float32),
        profile,
    )
    return metrics(name, satellite, dem, inside, filled, conditioned, n_conditioned, slope, ls, soil)


def recover(name, satellite, dem, inside):
    """Use grids already written, and fill once more for the pit diagnostics."""
    print(name, "recover", flush=True)
    ls = MFD.clean(read_band(SENS / f"LS_{name}_filled_mfd.tif")[0])
    soil = MFD.clean(read_band(SENS / f"SoilLoss_annual_{name}_filled_mfd.tif")[0])
    conditioned = MFD.clean(read_band(SENS / f"DEM_{name}_conditioned.tif")[0])
    filled = priority_fill(dem, inside)
    filled_zero = no_downslope(filled, inside)
    n_conditioned = int((np.isfinite(conditioned) & np.isfinite(filled) & (np.abs(conditioned - filled) > np.float32(1.0e-4))).sum())
    slope = steepest(conditioned, inside)
    row = metrics(name, satellite, dem, inside, filled, conditioned, n_conditioned, slope, ls, soil)
    row["filled_flat_share"] = float(filled_zero.sum() / max(int(inside.sum()), 1))
    return row


def recorded_dems():
    path = TABLES / "dem_satellite_ls.csv"
    if not path.exists():
        return set()
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip():
            names.add(line.split(",", 1)[0])
    return names


def products_ready(name):
    return all(
        (SENS / filename).exists()
        for filename in (
            f"LS_{name}_filled_mfd.tif",
            f"DEM_{name}_conditioned.tif",
            f"SoilLoss_annual_{name}_filled_mfd.tif",
        )
    )


def append_row(row):
    """Add one dem row. Existing rows for other dems are kept as stored text."""
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / "dem_satellite_ls.csv"
    frame = pd.DataFrame([row])
    if not path.exists():
        frame.to_csv(path, index=False)
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [lines[0]] if lines else []
    replaced = False
    for line in lines[1:]:
        if line.split(",", 1)[0] == str(row["dem"]):
            replaced = True
            continue
        kept.append(line)
    extra = frame.to_csv(index=False, header=False, lineterminator="\n")
    if not extra.endswith("\n"):
        extra += "\n"
    if replaced:
        path.write_text("\n".join(kept) + "\n" + extra, encoding="utf-8")
        return
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        path.write_bytes(raw + b"\n")
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(extra)


def main():
    if not SRTM_GRID.exists():
        if not SRTM_TIF.exists():
            write_srtm_geotiff()
        align_to_reference(SRTM_TIF, config.REFERENCE_DEM, SRTM_GRID, resampling="bilinear")
    if not ASTER_GRID.exists():
        print("align ASTER", ASTER_DEM.name, "elevation only; num tiles ignored", flush=True)
        align_to_reference(ASTER_DEM, config.REFERENCE_DEM, ASTER_GRID, resampling="bilinear")
    with rasterio.open(config.REFERENCE_DEM) as source:
        profile = source.profile.copy()
    annual = MFD.clean(read_band(ANNUAL)[0])
    support = np.isfinite(annual)
    cells, monthly = MFD.rainfall_cells(annual.shape)
    sources = [
        ("alos", "ALOS PALSAR L-band", config.REFERENCE_DEM),
        ("copernicus", "TanDEM-X Copernicus GLO-30", MFD.COP),
        ("srtm", "SRTM C-band", SRTM_GRID),
        ("aster", "ASTER GDEM, Terra optical stereo (ASTER), not radar", ASTER_GRID),
    ]
    recorded = recorded_dems()
    for name, satellite, path in sources:
        ls_path = SENS / f"LS_{name}_filled_mfd.tif"
        if ls_path.exists() and name in recorded:
            print(name, "skip, LS raster and CSV row already exist", flush=True)
            continue
        dem = MFD.clean(read_band(path)[0])
        inside = support & np.isfinite(dem)
        print(name, "inside", int(inside.sum()), flush=True)
        if products_ready(name):
            row = recover(name, satellite, dem, inside)
        else:
            row = summarise(name, satellite, dem, inside, cells, monthly, profile)
        print(row, flush=True)
        append_row(row)
        del dem, inside, row
        import gc
        gc.collect()
    print(pd.read_csv(TABLES / "dem_satellite_ls.csv").to_string(index=False))
    print("Published LS and Arnoldus soil-loss rasters were not replaced.")


if __name__ == "__main__":
    import traceback

    try:
        print("start", flush=True)
        main()
    except Exception:
        traceback.print_exc()
        raise
