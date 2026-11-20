"""Snap Earth Engine monthly stacks to the ALOS 12.5 m DEM grid."""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import rasterio

import config
from tilaiya.monthly import gee_filename
from tilaiya.rasters import align_stack


def same_grid(source_path, reference_path):
    with rasterio.open(source_path) as source, rasterio.open(reference_path) as reference:
        return (
            source.crs == reference.crs
            and source.width == reference.width
            and source.height == reference.height
            and source.transform == reference.transform
        )


def place_on_reference_grid(source, destination, reference):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    if same_grid(source, reference):
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)
        return "already on the DEM grid"
    align_stack(source, reference, destination)
    return "warped onto the DEM grid"


def monthly_sources():
    """Find the twelve downloads in data/gee or beside the Earth Engine scripts."""
    folders = [config.GEE_DOWNLOADS, config.PROJECT / "gee"]
    found = {}
    for folder in folders:
        if not folder.exists():
            continue
        for path in folder.glob("Tilaiya_*.tif"):
            found.setdefault(path.name, path)
    return [found[name] for name in sorted(found)]


def main():
    sources = monthly_sources()
    if not sources:
        raise SystemExit(
            "No GeoTIFF files in data/gee or gee.\n"
            "Download Tilaiya_2025_01.tif through Tilaiya_2025_12.tif "
            "from the Drive folder Tilaiya_Advanced into one of those folders."
        )
    if not config.REFERENCE_DEM.exists():
        raise SystemExit(f"Reference DEM not found: {config.REFERENCE_DEM}")

    for source in sources:
        destination = config.ALIGNED / source.name
        print(f"Aligning {source.name}")
        note = place_on_reference_grid(source, destination, config.REFERENCE_DEM)
        print(f"  {note}: {destination}")

    expected = config.ALIGNED / gee_filename(config.ANALYSIS_YEAR, 1)
    if not expected.exists():
        print(
            f"\nAligned files are present, but {expected.name} was not among them. "
            "Monthly RUSLE looks for Tilaiya_<year>_<month>.tif."
        )


if __name__ == "__main__":
    main()
