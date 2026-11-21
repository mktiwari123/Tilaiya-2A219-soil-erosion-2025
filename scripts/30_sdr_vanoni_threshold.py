"""Write the delivery-ratio grid whose unweighted mean is the Vanoni ratio.

IC0 = -6.2868 is the threshold already solved in ic0_recentering.csv so the
unweighted mean SDR is 0.20. The stored SDR raster is not replaced. Flow
paths remain those of the existing connectivity index: they end at the
catchment outlet, because no reservoir shoreline mask is in the project.
The sigmoid does not change which cells are more connected than others.

Coded. Run from Visual Studio only when the ratio map is wanted.
Output: output/rasters/sensitivity/SDR_IC0_vanoni_0.20.tif
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tilaiya.rasters import read_band, write_band

IC_PATH = ROOT / "output" / "connectivity" / "IC.tif"
ANNUAL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif"
SENS = ROOT / "output" / "rasters" / "sensitivity"
TABLES = ROOT / "output" / "tables"
IC0 = -6.2867631445749765
SDR_MAX = 0.8
K_IC = 1.2
HA = 12.5 * 12.5 / 10000.0


def clean(values):
    out = np.asarray(values, dtype=np.float64)
    out[~np.isfinite(out)] = np.nan
    out[np.isclose(out, -9999.0)] = np.nan
    return out


def main():
    SENS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    ic, profile = read_band(IC_PATH)
    ic = clean(ic)
    soil = clean(read_band(ANNUAL)[0])
    ratio = SDR_MAX / (1.0 + np.exp((IC0 - ic) / K_IC))
    finite = np.isfinite(ic)
    both = finite & np.isfinite(soil) & (soil >= 0)
    gross = float(np.sum(soil[both]) * HA)
    delivered = float(np.sum(soil[both] * ratio[both]) * HA)
    row = {
        "IC0": IC0,
        "n": int(finite.sum()),
        "mean_SDR": float(np.nanmean(ratio[finite])),
        "median_SDR": float(np.nanmedian(ratio[finite])),
        "mass_weighted_SDR": delivered / gross if gross else np.nan,
        "delivered_t": delivered,
        "delivered_m3": delivered / 1.45,
        "note": "Unweighted mean set to the Vanoni ratio. Paths end at the outlet.",
    }
    pd.DataFrame([row]).to_csv(TABLES / "sdr_vanoni_threshold.csv", index=False)
    write_band(SENS / "SDR_IC0_vanoni_0.20.tif", np.where(finite, ratio, np.nan), profile)
    print(row)
    print("Stored SDR.tif was not replaced.")


if __name__ == "__main__":
    main()
