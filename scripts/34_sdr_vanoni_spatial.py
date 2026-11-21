"""Where the Vanoni-matched delivery grid concentrates sediment.

The stored SDR raster is not replaced. Delivered mass uses the
multiple-flow Copernicus soil-loss grid. Paths in the connectivity index
end at the catchment outlet.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tilaiya.rasters import read_band

SDR = ROOT / "output" / "rasters" / "sensitivity" / "SDR_IC0_vanoni_0.20.tif"
SOIL = ROOT / "output" / "rasters" / "sensitivity" / "SoilLoss_annual_copernicus_mfd.tif"
EROSIVITY = ROOT / "output" / "rasters" / "Erosivity" / "Erosivity_annual.tif"
TABLES = ROOT / "output" / "tables"
HA = 12.5 * 12.5 / 10000.0
STUDY = {894.0: 1, 1225.0: 2, 786.0: 3, 1046.0: 4, 1292.0: 5}


def clean(values):
    out = np.asarray(values, dtype=np.float64)
    out[~np.isfinite(out)] = np.nan
    out[np.isclose(out, -9999)] = np.nan
    return out


def main():
    ratio = clean(read_band(SDR)[0])
    soil = clean(read_band(SOIL)[0])
    both = np.isfinite(ratio) & np.isfinite(soil) & (soil >= 0)
    delivered = np.where(both, soil * ratio, np.nan)
    mass = float(np.nansum(delivered[both]) * HA)
    gross = float(np.nansum(soil[both]) * HA)
    values = ratio[both]
    edges = np.quantile(values, [0, 0.2, 0.4, 0.6, 0.8, 1])
    rows = []
    for index in range(5):
        low, high = edges[index], edges[index + 1]
        if index == 4:
            group = both & (ratio >= low) & (ratio <= high)
        else:
            group = both & (ratio >= low) & (ratio < high)
        part = float(np.nansum(delivered[group]) * HA)
        rows.append(
            {
                "group": f"SDR quintile {index + 1}",
                "sdr_low": float(low),
                "sdr_high": float(high),
                "area_share": float(group.sum() / both.sum()),
                "delivered_share": part / mass if mass else np.nan,
                "mean_sdr": float(np.mean(ratio[group])),
            }
        )
    annual = clean(read_band(EROSIVITY)[0])
    keys = np.array(sorted(STUDY), dtype=np.float64)
    finite = np.isfinite(annual)
    chosen = np.full(annual.shape, np.nan)
    chosen[finite] = keys[np.abs(annual[finite][:, None] - keys[None, :]).argmin(axis=1)]
    cell_rows = []
    for value, cell in STUDY.items():
        group = both & np.isfinite(chosen) & np.isclose(chosen, value)
        part = float(np.nansum(delivered[group]) * HA)
        cell_rows.append(
            {
                "cell": cell,
                "area_share": float(group.sum() / both.sum()) if both.any() else np.nan,
                "mean_sdr": float(np.mean(ratio[group])) if group.any() else np.nan,
                "delivered_share": part / mass if mass else np.nan,
                "gross_mean": float(np.mean(soil[group])) if group.any() else np.nan,
            }
        )
    summary = {
        "n": int(both.sum()),
        "mean_sdr": float(np.mean(values)),
        "gross_t": gross,
        "delivered_t": mass,
        "delivered_m3": mass / 1.45,
        "mass_weighted_sdr": mass / gross if gross else np.nan,
    }
    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([summary]).to_csv(TABLES / "sdr_vanoni_on_mfd.csv", index=False)
    pd.DataFrame(rows).to_csv(TABLES / "sdr_vanoni_quintiles.csv", index=False)
    pd.DataFrame(cell_rows).to_csv(TABLES / "sdr_vanoni_by_rainfall_cell.csv", index=False)
    print(summary)
    print(pd.DataFrame(rows).to_string(index=False))
    print(pd.DataFrame(cell_rows).to_string(index=False))


if __name__ == "__main__":
    main()
