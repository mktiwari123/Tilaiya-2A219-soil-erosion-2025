"""Borselli connectivity and Tilaiya sediment yield from an annual soil-loss map.

The weighting surface is the dynamic annual-mean Cm when that file
exists, otherwise the baseline annual C factor. Supply
data/reservoir_mask.tif (1 = reservoir) to end flow paths at Tilaiya
Reservoir rather than at the catchment outlet.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import config
from tilaiya.connectivity import connectivity_index
from tilaiya.constants import CELL_SIZE_M, PIXEL_AREA_HA
from tilaiya.rasters import read_band, write_band
from tilaiya.sediment import sediment_delivery_ratio, sediment_mass_tonnes, siltation_volume_m3


def _mean_cm():
    cm_paths = []
    for month in range(1, 13):
        path = config.ALIGNED / f"Tilaiya_{config.ANALYSIS_YEAR}_{month:02d}.tif"
        if path.exists():
            cm_paths.append(path)
    if not cm_paths:
        return None
    from tilaiya.monthly import GEE_BANDS

    band = GEE_BANDS.index("Cm") + 1
    layers = [read_band(path, band=band)[0] for path in cm_paths]
    stack = np.stack(layers, axis=0)
    finite = np.isfinite(stack)
    total = np.nansum(np.where(finite, stack, 0.0), axis=0)
    count = finite.sum(axis=0)
    with np.errstate(invalid="ignore"):
        return np.where(count > 0, total / count, np.nan)


def main():
    if not config.REFERENCE_DEM.exists():
        raise SystemExit(f"DEM not found: {config.REFERENCE_DEM}")

    elevation, profile = read_band(config.REFERENCE_DEM)
    # ALOS NoData is 32767. read_band converts the file NoData to NaN.
    # Elevations at or below zero are outside this catchment grid.
    valid_dem = np.isfinite(elevation)

    dynamic_candidates = (
        config.OUTPUT / "rasters" / "SoilLoss" / "SoilLoss_annual.tif",
        config.OUTPUT / "monthly_rusle" / "A_annual_dynamic.tif",
    )
    dynamic_annual = next((path for path in dynamic_candidates if path.exists()), None)
    if dynamic_annual is not None:
        soil_loss, _profile = read_band(dynamic_annual)
        soil_loss_source = dynamic_annual
    else:
        soil_loss, _profile = read_band(config.ANNUAL_SOIL_LOSS)
        soil_loss_source = config.ANNUAL_SOIL_LOSS

    weight = _mean_cm()
    if weight is None:
        weight, _profile = read_band(config.C_FACTOR)
        weight_source = config.C_FACTOR
    else:
        weight_source = config.ALIGNED

    if elevation.shape != weight.shape or elevation.shape != soil_loss.shape:
        raise SystemExit("DEM, cover weight, and soil-loss rasters must share the ALOS grid.")

    reservoir = None
    if config.RESERVOIR_MASK.exists():
        reservoir, _profile = read_band(config.RESERVOIR_MASK)
        reservoir = np.isfinite(reservoir) & (reservoir > 0)

    print("Computing D8 connectivity. On the full 12.5 m grid this takes several minutes.")
    result = connectivity_index(
        elevation,
        weight,
        cell_size=CELL_SIZE_M,
        valid=valid_dem & np.isfinite(weight),
        reservoir=reservoir,
    )
    delivery = sediment_delivery_ratio(result["ic"])
    hillslope = np.isfinite(soil_loss) & np.isfinite(delivery) & (soil_loss >= 0)
    if reservoir is not None:
        hillslope &= ~reservoir

    mass = sediment_mass_tonnes(np.where(hillslope, soil_loss, np.nan), np.where(hillslope, delivery, np.nan), PIXEL_AREA_HA)
    volume = siltation_volume_m3(mass)

    out_dir = config.OUTPUT / "connectivity"
    write_band(out_dir / "IC.tif", result["ic"], profile)
    write_band(out_dir / "SDR.tif", delivery, profile)

    summary = pd.DataFrame(
        [
            {
                "soil_loss_source": str(soil_loss_source),
                "weight_source": str(weight_source),
                "reservoir_mask": str(config.RESERVOIR_MASK) if reservoir is not None else "",
                "valid_cells": result["valid_cells"],
                "processed_cells": result["processed_cells"],
                "sediment_yield_t_yr": mass,
                "siltation_volume_m3_yr": volume,
                "pixel_area_ha": PIXEL_AREA_HA,
                "bulk_density_t_m3": 1.45,
            }
        ]
    )
    summary.to_csv(out_dir / "sediment_yield_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"\nWrote {out_dir / 'IC.tif'}")
    print(f"Wrote {out_dir / 'SDR.tif'}")


if __name__ == "__main__":
    main()
