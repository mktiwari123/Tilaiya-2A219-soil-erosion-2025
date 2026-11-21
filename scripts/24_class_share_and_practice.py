"""Loss share by land-cover class, and a P = 1 scenario.

The reported Arnoldus soil-loss rasters are left in place. P = 1 removes
the support-practice reduction on pixels whose current P is positive.
Pixels with P = 0 stay at zero soil loss, because that value excludes
them from the product rather than applying a conservation practice.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from tilaiya.rasters import read_band, write_band  # noqa: E402

OUT = ROOT / "output" / "tables"
SENS = ROOT / "output" / "rasters" / "sensitivity"
SOIL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
HA = 12.5 * 12.5 / 10000.0
YIELD_LOW = 10.26
YIELD_HIGH = 14.88
VANONI_LOW = 51.4
VANONI_HIGH = 74.5
CLASS_NAME = {0: "Built-up", 1: "Cropland", 2: "Vegetation", 3: "Water", 4: "Barren land"}
SOURCE_CANDIDATES = [
    Path(r"D:\A_RKLSCP\Final_Index\Actual_Raster\Final07072026\LULC_2025_RF_v2.tif"),
    Path(r"D:\A_RKLSCP\Final_Index\Actual_Raster\LULC_2025_RF_v2.tif"),
    Path(r"D:\A_RKLSCP\Final_Index\Actual_Raster\LULC_2025.tif"),
    config.BASELINE / "Aligned_2.tif" / "LULC_aligned.tif",
]


def summarise(values):
    data = values[np.isfinite(values)]
    return {
        "n": int(data.size),
        "mean": float(data.mean()),
        "median": float(np.median(data)),
        "above_100": float(np.mean(data > 100)),
        "mass_t": float(data.sum() * HA),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SENS.mkdir(parents=True, exist_ok=True)
    reported, profile = read_band(SOIL / "SoilLoss_annual.tif")
    exponential = read_band(SENS / "SoilLoss_annual_vander_knijff.tif")[0]
    lookup = read_band(SENS / "SoilLoss_annual_lulc_cover.tif")[0]
    practice = read_band(ROOT / "output" / "rasters" / "Practice" / "P.tif")[0]
    lulc = read_band(config.BASELINE / "Aligned_2.tif" / "LULC_aligned.tif")[0]
    support = np.isfinite(reported)
    classes = np.rint(lulc)

    positive = support & np.isfinite(practice) & (practice > 0)
    practice_one = reported.copy()
    practice_one[positive] = reported[positive] / practice[positive]
    practice_one[~support] = np.nan
    write_band(SENS / "SoilLoss_annual_P_equals_1.tif", practice_one, profile)

    layers = {
        "Linear cover": reported,
        "Exponential NDVI cover": exponential,
        "Land-cover lookup": lookup,
        "Linear cover, P = 1": practice_one,
    }
    scenario_rows = []
    for name, values in layers.items():
        row = {"case": name}
        row.update(summarise(values[support]))
        row["implied_SDR_at_1.0"] = YIELD_LOW / row["mean"]
        row["implied_SDR_at_1.45"] = YIELD_HIGH / row["mean"]
        row["above_yield_high"] = row["mean"] > YIELD_HIGH
        row["below_vanoni"] = row["mean"] < VANONI_LOW
        row["above_vanoni"] = row["mean"] > VANONI_HIGH
        scenario_rows.append(row)
    pd.DataFrame(scenario_rows).to_csv(OUT / "practice_one_scenario.csv", index=False)

    share_rows = []
    for code, name in CLASS_NAME.items():
        group = support & np.isfinite(classes) & np.isclose(classes, code)
        area_share = float(group.sum() / support.sum())
        row = {
            "class": name,
            "pixels": int(group.sum()),
            "area_share": area_share,
            "mean_P": float(np.nanmean(practice[group])) if group.any() else np.nan,
        }
        for label, values in layers.items():
            mass = float(np.nansum(values[group]) * HA)
            total = float(np.nansum(values[support]) * HA)
            row[f"{label} mass share"] = mass / total if total else np.nan
            row[f"{label} mean"] = float(np.nanmean(values[group])) if group.any() else np.nan
            row[f"{label} mass over area"] = (mass / total) / area_share if total and area_share else np.nan
        share_rows.append(row)
    shares = pd.DataFrame(share_rows)
    shares.to_csv(OUT / "loss_share_by_class.csv", index=False)

    provenance = []
    for path in SOURCE_CANDIDATES:
        if not path.exists():
            provenance.append({"path": str(path), "exists": False})
            continue
        with rasterio.open(path) as source:
            provenance.append(
                {
                    "path": str(path),
                    "exists": True,
                    "width": source.width,
                    "height": source.height,
                    "res_x": source.res[0],
                    "res_y": source.res[1],
                    "crs": str(source.crs),
                    "dtype": source.dtypes[0],
                    "nodata": source.nodata,
                }
            )
    pd.DataFrame(provenance).to_csv(OUT / "lulc_source_grids.csv", index=False)
    print(pd.DataFrame(scenario_rows).to_string(index=False))
    print(shares.to_string(index=False))
    print(pd.DataFrame(provenance).to_string(index=False))


if __name__ == "__main__":
    main()
