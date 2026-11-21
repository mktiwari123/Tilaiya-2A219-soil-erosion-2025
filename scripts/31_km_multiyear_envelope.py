"""Stretch Sentinel-1 VV on a 2020–2025 envelope, if those stacks exist.

The aligned series in this project is 2025 only. This script does not invent
the missing years. When any month from 2020 through 2024 is absent it writes
the inventory and stops. The reported Km rasters are never replaced.

Run from Visual Studio after the earlier-year stacks are aligned as
data/aligned/Tilaiya_YYYY_MM.tif with the same bands as the 2025 files.
"""

import os

os.environ.setdefault("GDAL_CACHEMAX", "64")

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STACK = ROOT / "data" / "aligned"
TABLES = ROOT / "output" / "tables"
YEARS = range(2020, 2026)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    rows = []
    missing = []
    for year in YEARS:
        for month in range(1, 13):
            path = STACK / f"Tilaiya_{year}_{month:02d}.tif"
            present = path.exists()
            rows.append({"year": year, "month": month, "present": present, "path": str(path)})
            if not present:
                missing.append(path.name)
    frame = pd.DataFrame(rows)
    frame.to_csv(TABLES / "km_multiyear_availability.csv", index=False)
    print(f"months present: {int(frame['present'].sum())} of {len(frame)}")
    if missing:
        print("Missing stacks, so no multi-year Km was calculated.")
        print("First missing file:", missing[0])
        print("Count missing:", len(missing))
        return
    raise SystemExit(
        "All 72 months are present. The stretch itself is not in this inventory "
        "script: add the windowed rescale from scripts/27_km_annual_range.py "
        "before calculating Km, and do not replace the stored Km rasters."
    )


if __name__ == "__main__":
    main()
