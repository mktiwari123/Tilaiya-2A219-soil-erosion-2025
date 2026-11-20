"""Draw publication maps from the Tilaiya rasters.

Run from Visual Studio Code with the configuration "09 Presentation maps",
or from the project folder:

    .\\.venv\\Scripts\\python.exe scripts\\09_presentation_maps.py

Plates are written to output/figures/maps. A single raster can be drawn with
--raster, --title, --units, and --style (classes, stretch, unit, rain, warm).
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _use_project_python():
    """Leave the system Python that Visual Studio Code may have selected."""
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists() or os.environ.get("TILAIYA_VENV") == "1":
        return
    try:
        current = os.path.normcase(str(Path(sys.executable).resolve()))
        target = os.path.normcase(str(venv_python.resolve()))
    except OSError:
        return
    if current == target:
        return
    print(
        "The selected Python does not have the project packages.\n"
        f"Switching to {venv_python}",
        flush=True,
    )
    os.environ["TILAIYA_VENV"] = "1"
    completed = subprocess.run(
        [str(venv_python.resolve()), str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=str(ROOT),
    )
    raise SystemExit(completed.returncode)


_use_project_python()

sys.path.insert(0, str(ROOT))

import argparse

import numpy as np

import config
from tilaiya.maps import (
    MONTH_NAMES,
    hillshade,
    save_map,
    save_panels,
    stretch_limits,
    view_window,
)
from tilaiya.rasters import read_band, watershed_mask

WATERSHED = Path(r"D:\Downloads MKT\GIS Works\Watershed IARI Whole\watershed.shp")
RASTERS = config.OUTPUT / "rasters"
FIGURES = config.FIGURES / "maps"
SUBTITLE = "Tilaiya headwater, sub-watershed 2A219, 2025"


def data_limits(array):
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return 0.0, 1.0
    return float(finite.min()), float(finite.max())


def percentile(array, quantile):
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return 1.0
    return float(np.percentile(finite, quantile))


def prepare_view():
    print("Reading the watershed grid. The first map appears after this step.", flush=True)
    inside, profile, watershed = watershed_mask(config.REFERENCE_DEM, WATERSHED)
    transform = profile["transform"]
    shape = (profile["height"], profile["width"])
    window, extent = view_window(transform, shape, watershed.bounds, pad_m=1200)
    elevation, _profile = read_band(config.REFERENCE_DEM)
    shade = hillshade(elevation)[window]
    return {
        "window": window,
        "extent": extent,
        "shade": shade,
        "geometry": watershed,
        "shape": shape,
    }


def layer(path, view):
    array, _profile = read_band(path)
    if array.shape != view["shape"]:
        raise SystemExit(f"{path} is not on the DEM grid.")
    return array[view["window"]].astype(np.float32)


def draw_one(
    path,
    destination,
    view,
    title,
    units,
    style,
    interpolation="bilinear",
    vmin=None,
    vmax=None,
    note="",
):
    array = layer(path, view) if not isinstance(path, np.ndarray) else path
    subtitle = SUBTITLE if not note else f"{SUBTITLE}. {note}"
    limits = save_map(
        destination,
        array,
        view["shade"],
        view["extent"],
        view["geometry"],
        title,
        subtitle,
        style=style,
        units=units,
        interpolation=interpolation,
        vmin=vmin,
        vmax=vmax,
    )
    print(f"Wrote {destination}")
    return array, limits


def draw_year(
    paths,
    destination,
    view,
    title,
    units,
    style,
    interpolation="bilinear",
    vmin=None,
    vmax=None,
    note="",
    scale="p98",
):
    arrays = [layer(path, view) for path in paths]
    if style == "warm" and vmax is None:
        vmin = 0.0
        if scale == "max":
            vmax = max(data_limits(item)[1] for item in arrays)
        else:
            vmax = max(percentile(item, 98) for item in arrays)
    if style == "rain":
        vmin = 0.0
        vmax = max(data_limits(item)[1] for item in arrays)
    subtitle = SUBTITLE if not note else f"{SUBTITLE}. {note}"
    save_panels(
        destination,
        arrays,
        view["shade"],
        view["extent"],
        view["geometry"],
        MONTH_NAMES,
        title,
        subtitle,
        style=style,
        units=units,
        interpolation=interpolation,
        vmin=vmin,
        vmax=vmax,
    )
    print(f"Wrote {destination}")
    return arrays


def atlas(view):
    loss = RASTERS / "SoilLoss"
    rain = RASTERS / "Rainfall"
    erosivity = RASTERS / "Erosivity"
    km = RASTERS / "Erodibility"
    cover = RASTERS / "Cover"

    draw_one(
        loss / "SoilLoss_annual_class.tif",
        FIGURES / "SoilLoss_annual_class_2025.png",
        view,
        "Annual soil loss, 2025",
        "Soil loss (t/ha/yr)",
        "classes",
        interpolation="nearest",
        note="Grey inside the boundary is NoData.",
    )
    annual, _limits = draw_one(
        loss / "SoilLoss_annual.tif",
        FIGURES / "SoilLoss_annual_2025.png",
        view,
        "Annual soil loss, 2025",
        "t/ha/yr",
        "stretch",
        note="Grey inside the boundary is NoData.",
    )
    low, high = stretch_limits(annual)
    print(f"Annual soil-loss stretch {low:.2f} to {high:.2f} t/ha/yr")

    draw_one(
        RASTERS / "LS" / "LS.tif",
        FIGURES / "LS_2025.png",
        view,
        "Slope-length and steepness factor",
        "LS",
        "stretch",
    )
    draw_one(
        cover / "C_annual_baseline.tif",
        FIGURES / "C_annual_baseline_2025.png",
        view,
        "Annual cover-management factor",
        "C",
        "unit",
    )
    draw_one(
        RASTERS / "Practice" / "P.tif",
        FIGURES / "P_2025.png",
        view,
        "Support-practice factor",
        "P",
        "unit",
    )
    draw_one(
        cover / "Cm_07.tif",
        FIGURES / "Cm_July_2025.png",
        view,
        "Cover-management factor, July 2025",
        "Cm",
        "unit",
    )
    draw_one(
        km / "Km_07.tif",
        FIGURES / "Km_July_2025.png",
        view,
        "Soil erodibility, July 2025",
        "Km (t ha h / ha MJ mm)",
        "warm",
        vmin=0.0,
        vmax=None,
    )
    draw_one(
        rain / "Rainfall_07.tif",
        FIGURES / "Rainfall_July_2025.png",
        view,
        "Rainfall, July 2025",
        "mm",
        "rain",
        interpolation="nearest",
    )
    draw_one(
        erosivity / "Erosivity_07.tif",
        FIGURES / "Erosivity_July_2025.png",
        view,
        "Rainfall erosivity, July 2025",
        "MJ mm / ha h month",
        "warm",
        interpolation="nearest",
    )

    loss_paths = [loss / f"SoilLoss_{month:02d}.tif" for month in range(1, 13)]
    loss_arrays = draw_year(
        loss_paths,
        FIGURES / "SoilLoss_monthly_2025.png",
        view,
        "Monthly soil loss, 2025",
        "t/ha/month",
        "warm",
        note="Colour scale is 0 to the 98th percentile of the monthly maps. Darker red is higher soil loss.",
    )
    print(f"Monthly soil-loss shared maximum {max(percentile(item, 98) for item in loss_arrays):.2f} t/ha")

    draw_year(
        [rain / f"Rainfall_{month:02d}.tif" for month in range(1, 13)],
        FIGURES / "Rainfall_monthly_2025.png",
        view,
        "Monthly rainfall, 2025",
        "mm",
        "rain",
        interpolation="nearest",
        note="Each colour is constant inside an IMD 0.25 degree cell.",
    )
    draw_year(
        [erosivity / f"Erosivity_{month:02d}.tif" for month in range(1, 13)],
        FIGURES / "Erosivity_monthly_2025.png",
        view,
        "Monthly rainfall erosivity, 2025",
        "MJ mm / ha h month",
        "warm",
        interpolation="nearest",
        scale="max",
        note="Modified Fournier erosivity. Each colour is constant inside an IMD 0.25 degree cell.",
    )
    draw_year(
        [cover / f"Cm_{month:02d}.tif" for month in range(1, 13)],
        FIGURES / "Cm_monthly_2025.png",
        view,
        "Monthly cover-management factor, 2025",
        "Cm",
        "unit",
        note="July and August use RVI. The other months use SAVI. Scale is 0 to 1.",
    )
    draw_year(
        [km / f"Km_{month:02d}.tif" for month in range(1, 13)],
        FIGURES / "Km_monthly_2025.png",
        view,
        "Monthly soil erodibility, 2025",
        "Km (t ha h / ha MJ mm)",
        "warm",
        scale="max",
        note="Shared scale from 0 to the maximum monthly Km.",
    )
    connectivity_plates(view)


def connectivity_plates(view):
    """IC and SDR on the same plate layout, stretched to the 2nd–98th percentile."""
    connectivity = config.OUTPUT / "connectivity"
    draw_one(
        connectivity / "IC.tif",
        FIGURES / "IC_2025.png",
        view,
        "Index of connectivity",
        "IC",
        "stretch",
        note="Colour stretch is the 2nd to 98th percentile. Higher IC is more connected.",
    )
    draw_one(
        connectivity / "SDR.tif",
        FIGURES / "SDR_2025.png",
        view,
        "Sediment delivery ratio",
        "SDR",
        "stretch",
        note="Colour stretch is the 2nd to 98th percentile. Higher SDR delivers more soil.",
    )


def one_raster(args, view):
    style = args.style
    array = layer(Path(args.raster), view)
    vmin, vmax = data_limits(array)
    if style == "stretch":
        vmin, vmax = stretch_limits(array)
    if style == "unit":
        vmin, vmax = 0.0, 1.0
    if args.vmin is not None:
        vmin = args.vmin
    if args.vmax is not None:
        vmax = args.vmax
    destination = Path(args.output) if args.output else FIGURES / (Path(args.raster).stem + ".png")
    save_map(
        destination,
        array,
        view["shade"],
        view["extent"],
        view["geometry"],
        args.title or Path(args.raster).stem,
        SUBTITLE,
        style=style,
        units=args.units or "",
        interpolation="nearest" if style in ("classes", "rain") else "bilinear",
        vmin=vmin,
        vmax=vmax,
    )
    print(f"Wrote {destination}")
    print(f"Colour limits {vmin:.4g} to {vmax:.4g}")


def main():
    parser = argparse.ArgumentParser(description="Draw Tilaiya presentation maps.")
    parser.add_argument("--raster", help="Draw one GeoTIFF instead of the full atlas.")
    parser.add_argument("--title", default="")
    parser.add_argument("--units", default="")
    parser.add_argument("--style", default="stretch", choices=("classes", "stretch", "unit", "rain", "warm"))
    parser.add_argument("--vmin", type=float)
    parser.add_argument("--vmax", type=float)
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--only",
        default="",
        choices=("", "connectivity"),
        help="Draw one plate group. connectivity writes IC and SDR only.",
    )
    args = parser.parse_args()
    view = prepare_view()
    if args.raster:
        one_raster(args, view)
    elif args.only == "connectivity":
        connectivity_plates(view)
    else:
        atlas(view)


if __name__ == "__main__":
    main()
