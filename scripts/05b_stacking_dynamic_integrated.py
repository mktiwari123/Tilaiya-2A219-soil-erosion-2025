"""Train the Dynamic Integrated stack.

The calculation is scripts/05_stacking_ensemble.py. This file fixes the
scenario at Dynamic_Integrated so the Reduced Integrated run remains
scripts/05_stacking_ensemble.py and is not overwritten.
"""

import sys
from pathlib import Path
import runpy

STACK = Path(__file__).with_name("05_stacking_ensemble.py")
sys.argv = [str(STACK), "--scenario", "Dynamic_Integrated"]
runpy.run_path(str(STACK), run_name="__main__")
