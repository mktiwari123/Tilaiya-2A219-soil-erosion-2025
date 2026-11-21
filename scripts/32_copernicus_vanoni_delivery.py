"""Apply the Vanoni-matched delivery grid to the Copernicus soil-loss map.

The Copernicus LS soil-loss raster and the stored SDR raster are left in
place. Delivered rate is hillslope soil loss times the IC0 = -6.29 ratio.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tilaiya.rasters import read_band, write_band

SOIL = ROOT / "output" / "rasters" / "sensitivity" / "SoilLoss_annual_copernicus_LS.tif"
SDR = ROOT / "output" / "rasters" / "sensitivity" / "SDR_IC0_vanoni_0.20.tif"
OUT_RASTER = ROOT / "output" / "rasters" / "sensitivity" / "Delivered_copernicus_LS_IC0_vanoni.tif"
OUT_TABLE = ROOT / "output" / "tables" / "copernicus_vanoni_delivery.csv"
HA = 12.5 * 12.5 / 10000.0
DENSITY = 1.45


def clean(values):
    out = np.asarray(values, dtype=np.float64)
    out[~np.isfinite(out)] = np.nan
    out[np.isclose(out, -9999.0)] = np.nan
    return out


def main():
    soil, profile = read_band(SOIL)
    ratio = clean(read_band(SDR)[0])
    soil = clean(soil)
    both = np.isfinite(soil) & np.isfinite(ratio) & (soil >= 0)
    delivered = np.where(both, soil * ratio, np.nan)
    gross_t = float(np.sum(soil[both]) * HA)
    delivered_t = float(np.sum(delivered[both]) * HA)
    row = {
        "n": int(both.sum()),
        "gross_mean_t_ha": float(np.mean(soil[both])),
        "gross_median_t_ha": float(np.median(soil[both])),
        "share_gross_above_100": float(np.mean(soil[both] > 100)),
        "share_gross_0_to_5": float(np.mean(soil[both] <= 5)),
        "mean_SDR": float(np.mean(ratio[both])),
        "mass_weighted_SDR": delivered_t / gross_t if gross_t else np.nan,
        "delivered_mean_t_ha": float(np.mean(delivered[both])),
        "delivered_median_t_ha": float(np.median(delivered[both])),
        "gross_t": gross_t,
        "gross_m3": gross_t / DENSITY,
        "delivered_t": delivered_t,
        "delivered_m3": delivered_t / DENSITY,
        "median_inside_51_75": 51 <= float(np.median(soil[both])) <= 75,
    }
    OUT_TABLE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(OUT_TABLE, index=False)
    write_band(OUT_RASTER, delivered, profile)
    print(row)


if __name__ == "__main__":
    main()
