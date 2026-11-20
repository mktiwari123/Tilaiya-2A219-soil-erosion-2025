"""Monthly RUSLE entry point.

The watershed maps use the spatial IMD erosivity rasters, the Sentinel
cover factor, and the moisture-adjusted K factor. That calculation is
scripts/03_monthly_soil_loss.py. This file remains so an older run
command still produces those same maps.
"""

from pathlib import Path
import runpy

runpy.run_path(
    str(Path(__file__).with_name("03_monthly_soil_loss.py")),
    run_name="__main__",
)
