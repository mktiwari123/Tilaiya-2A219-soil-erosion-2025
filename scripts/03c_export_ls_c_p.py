"""Copy LS, annual C, monthly Cm, and P onto the watershed grid.

The soil-loss script reads these factors from the baseline folder. This
script writes watershed-masked copies into output/rasters so the factor
set sits with the rainfall, erosivity, Km, and soil-loss maps.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

import config
from tilaiya.monthly import GEE_BANDS, gee_filename
from tilaiya.rasters import read_band, watershed_mask, write_band

WATERSHED = Path(r"D:\Downloads MKT\GIS Works\Watershed IARI Whole\watershed.shp")


def save_masked(source, destination, inside, profile, description):
    array, _profile = read_band(source) if not isinstance(source, np.ndarray) else (source, None)
    if array.shape != inside.shape:
        raise SystemExit(f"{destination.name} is not on the DEM grid.")
    masked = np.where(inside & np.isfinite(array), array, np.nan)
    write_band(destination, masked, profile)
    print(f"Wrote {destination}")


def main():
    inside, profile, _watershed = watershed_mask(config.REFERENCE_DEM, WATERSHED)
    save_masked(config.LS_FACTOR, config.OUTPUT / "rasters" / "LS" / "LS.tif", inside, profile, "LS")
    save_masked(config.P_FACTOR, config.OUTPUT / "rasters" / "Practice" / "P.tif", inside, profile, "P")
    save_masked(
        config.C_FACTOR,
        config.OUTPUT / "rasters" / "Cover" / "C_annual_baseline.tif",
        inside,
        profile,
        "C_annual_baseline",
    )

    cover_dir = config.OUTPUT / "rasters" / "Cover"
    for month in range(1, 13):
        name = gee_filename(config.ANALYSIS_YEAR, month)
        stack = None
        for folder in (config.ALIGNED, config.PROJECT / "gee"):
            candidate = folder / name
            if candidate.exists():
                stack = candidate
                break
        if stack is None:
            raise SystemExit(f"Monthly stack not found: {name}")
        cm, _profile = read_band(stack, band=GEE_BANDS.index("Cm") + 1)
        save_masked(cm, cover_dir / f"Cm_{month:02d}.tif", inside, profile, f"Cm_{month:02d}")


if __name__ == "__main__":
    main()
