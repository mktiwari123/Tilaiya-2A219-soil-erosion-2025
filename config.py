"""Paths for the Tilaiya advanced project.

Baseline rasters are read from the annual RUSLE study and are not
modified. New monthly factors, samples, and models are written only
inside this project.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent


def _relaunch_in_project_venv():
    """Use Tilaiya_Advanced\\.venv when VS Code starts another Python.

    The Run button follows the interpreter selected in the status bar.
    That interpreter does not have the project packages. Restart the
    same command with the project interpreter instead of failing on
    the first missing import.
    """
    venv_python = PROJECT / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists() or os.environ.get("TILAIYA_VENV") == "1":
        return
    try:
        if Path(sys.executable).resolve() == venv_python.resolve():
            return
        script = Path(sys.argv[0]).resolve()
    except (OSError, ValueError):
        return
    if script.suffix.lower() != ".py":
        return
    if PROJECT != script and PROJECT not in script.parents:
        return
    os.environ["TILAIYA_VENV"] = "1"
    completed = subprocess.run([str(venv_python), *sys.argv], cwd=str(PROJECT))
    raise SystemExit(completed.returncode)


_relaunch_in_project_venv()

from tilaiya.constants import CELL_SIZE_M

# Annual study inputs. Read only.
BASELINE = Path(r"D:\A_RKLSCP\Final_Index\Actual_Raster")
REFERENCE_DEM = BASELINE / "DEM.tif"
# K, C, and P are used from the grid already aligned to DEM.tif.
# The source K and P GeoTIFFs are coarser or still in geographic coordinates.
ALIGNED_BASELINE = BASELINE / "Aligned_2.tif"
RAINFALL_EROSIVITY = ALIGNED_BASELINE / "R_aligned.tif"
K_FACTOR = ALIGNED_BASELINE / "K_aligned.tif"
LS_FACTOR = ALIGNED_BASELINE / "LS_aligned.tif"
C_FACTOR = ALIGNED_BASELINE / "C_aligned.tif"
P_FACTOR = ALIGNED_BASELINE / "P_aligned.tif"
PREDICTOR_STACK = BASELINE / "Aligned_Gen_1.tif" / "stacked_ANN_input_2025.tif"
ANNUAL_SOIL_LOSS = BASELINE / "Aligned_2.tif" / "Annual_Soil_Loss_RUSLE_2025.tif"

# Adopted analysis boundary: sub-watershed 2A219, 715.02 km².
# The HydroBASINS dam catchment is a comparison only and is not the study area.
WATERSHED = PROJECT / "output" / "shapefiles" / "Tilaiya_2A219_study_mask.shp"

# Optional reservoir mask on the DEM grid. Value 1 marks Tilaiya Reservoir
# water. Leave the file absent to route connectivity to the catchment outlet.
RESERVOIR_MASK = PROJECT / "data" / "reservoir_mask.tif"

# ALOS PALSAR 12.5 m grid, WGS 84 / UTM zone 45N.
# Read from DEM.tif so Earth Engine exports snap to the same pixels.
CRS_EPSG = 32645
GRID_WIDTH = 2777
GRID_HEIGHT = 2677
GRID_TRANSFORM = (CELL_SIZE_M, 0.0, 311579.4375, 0.0, -CELL_SIZE_M, 2698245.25)
GRID_BOUNDS = (311579.4375, 2664782.75, 346291.9375, 2698245.25)

# Earth Engine. Set EE_PROJECT to the Cloud project that owns the
# Earth Engine API before running gee/export_monthly_factors.py.
EE_PROJECT = "ee-watershed-iari"
ANALYSIS_YEAR = 2025
EXPORT_SAR_CLIMATOLOGY = False
SAR_START_YEAR = 2020
SAR_END_YEAR = 2025
DRIVE_FOLDER = "Tilaiya_Advanced"

DATA = PROJECT / "data"
GEE_DOWNLOADS = DATA / "gee"
RAINFALL_DIR = DATA / "rainfall"
DAILY_RAINFALL_CSV = RAINFALL_DIR / "imd_daily.csv"
ALIGNED = DATA / "aligned"
OUTPUT = PROJECT / "output"
TABLES = OUTPUT / "tables"
FIGURES = OUTPUT / "figures"
MODELS = OUTPUT / "models"
DATASETS = OUTPUT / "datasets"

for _folder in (
    DATA,
    GEE_DOWNLOADS,
    RAINFALL_DIR,
    ALIGNED,
    OUTPUT,
    TABLES,
    FIGURES,
    MODELS,
    DATASETS,
):
    _folder.mkdir(parents=True, exist_ok=True)
