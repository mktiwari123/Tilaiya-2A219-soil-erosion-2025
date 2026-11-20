"""Explain the Dynamic Integrated XGBoost model with TreeSHAP.

The calculation is scripts/06_shap_xai.py. This file fixes the scenario
at Dynamic_Integrated so the Reduced Integrated explanation remains
scripts/06_shap_xai.py and is not overwritten.
"""

import sys
from pathlib import Path
import runpy

SHAP = Path(__file__).with_name("06_shap_xai.py")
sys.argv = [str(SHAP), "--scenario", "Dynamic_Integrated"]
runpy.run_path(str(SHAP), run_name="__main__")
