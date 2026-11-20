"""Sediment yield from the saved SDR and each annual soil-loss map.

This does not recompute flow paths. IC and SDR come from
scripts/07_connectivity_sediment_yield.py. The November 2026 connectivity
run multiplied SDR by the baseline annual soil-loss raster, because the
dynamic map was not in the folder that script checked at the time.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import config
from tilaiya.constants import BULK_DENSITY_T_M3, PIXEL_AREA_HA
from tilaiya.rasters import read_band
from tilaiya.sediment import sediment_mass_tonnes, siltation_volume_m3

CONNECTIVITY = config.OUTPUT / "connectivity"


def summarise(name, soil_loss, delivery):
    overlap = np.isfinite(soil_loss) & np.isfinite(delivery) & (soil_loss >= 0)
    loss = np.where(overlap, soil_loss, np.nan)
    ratio = np.where(overlap, delivery, np.nan)
    gross = float(np.nansum(loss * PIXEL_AREA_HA))
    delivered = sediment_mass_tonnes(loss, ratio, PIXEL_AREA_HA)
    return {
        "soil_loss_map": name,
        "overlap_pixels": int(overlap.sum()),
        "mean_soil_loss_t_ha_yr": float(np.nanmean(loss)),
        "gross_erosion_t_yr": gross,
        "sediment_yield_t_yr": delivered,
        "siltation_volume_m3_yr": siltation_volume_m3(delivered),
        "delivery_fraction": delivered / gross if gross else np.nan,
        "pixel_area_ha": PIXEL_AREA_HA,
        "bulk_density_t_m3": BULK_DENSITY_T_M3,
    }


def main():
    ic, _profile = read_band(CONNECTIVITY / "IC.tif")
    delivery, _profile = read_band(CONNECTIVITY / "SDR.tif")
    finite_ic = ic[np.isfinite(ic)]
    finite_sdr = delivery[np.isfinite(delivery)]
    distribution = pd.DataFrame(
        [
            {
                "layer": "IC",
                "n": int(finite_ic.size),
                "mean": float(np.mean(finite_ic)),
                "median": float(np.median(finite_ic)),
                "p05": float(np.percentile(finite_ic, 5)),
                "p95": float(np.percentile(finite_ic, 95)),
            },
            {
                "layer": "SDR",
                "n": int(finite_sdr.size),
                "mean": float(np.mean(finite_sdr)),
                "median": float(np.median(finite_sdr)),
                "p05": float(np.percentile(finite_sdr, 5)),
                "p95": float(np.percentile(finite_sdr, 95)),
            },
        ]
    )
    distribution_path = config.TABLES / "connectivity_distribution.csv"
    distribution.to_csv(distribution_path, index=False)

    sources = [
        ("baseline_annual_rusle", config.ANNUAL_SOIL_LOSS),
        ("dynamic_annual_sum", config.OUTPUT / "rasters" / "SoilLoss" / "SoilLoss_annual.tif"),
    ]
    rows = []
    for name, path in sources:
        if not path.exists():
            print(f"Missing {path}")
            continue
        soil_loss, _profile = read_band(path)
        rows.append(summarise(name, soil_loss, delivery))
    table = pd.DataFrame(rows)
    table_path = config.TABLES / "sediment_yield_by_source.csv"
    table.to_csv(table_path, index=False)
    print(distribution.to_string(index=False))
    print(table.to_string(index=False))
    print(f"\nWrote {distribution_path}")
    print(f"Wrote {table_path}")


if __name__ == "__main__":
    main()
