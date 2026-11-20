"""Report which baseline rasters and new inputs are ready."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config


def main():
    required = {
        "Reference DEM": config.REFERENCE_DEM,
        "K factor (Kbase)": config.K_FACTOR,
        "LS factor": config.LS_FACTOR,
        "P factor": config.P_FACTOR,
        "Baseline C factor": config.C_FACTOR,
        "Predictor stack": config.PREDICTOR_STACK,
        "Annual soil loss": config.ANNUAL_SOIL_LOSS,
    }
    optional = {
        "IMD daily rainfall": config.DAILY_RAINFALL_CSV,
        "Reservoir mask": config.RESERVOIR_MASK,
    }

    print("Baseline inputs")
    ready = True
    for label, path in required.items():
        found = path.exists()
        ready = ready and found
        print(f"  [{'ok' if found else 'missing'}] {label}: {path}")

    print("\nOptional inputs")
    for label, path in optional.items():
        print(f"  [{'ok' if path.exists() else 'not yet'}] {label}: {path}")

    downloads = sorted(config.GEE_DOWNLOADS.glob("Tilaiya_*.tif"))
    print(f"\nEarth Engine downloads in data/gee: {len(downloads)}")
    print(f"Earth Engine project id: {config.EE_PROJECT or '(not set)'}")
    print(f"Analysis year: {config.ANALYSIS_YEAR}")
    if ready:
        print("\nBaseline rasters are in place. Next: python scripts/04_stratified_sampling.py")
    else:
        print("\nA baseline raster path in config.py needs to be corrected before sampling.")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
