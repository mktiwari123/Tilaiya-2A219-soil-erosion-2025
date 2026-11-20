"""Add annual means of the monthly factors to the 12,697-point table.

Km uses the full-raster VV percentiles, then the sample pixels. Cm,
SAVI, and RVI are the mean of the monthly values at each sample pixel.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

import config
from tilaiya.factors import dynamic_erodibility, relative_moisture
from tilaiya.monthly import GEE_BANDS
from tilaiya.rasters import read_band


def _monthly_paths(year):
    paths = [config.ALIGNED / f"Tilaiya_{year}_{month:02d}.tif" for month in range(1, 13)]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise SystemExit(
            "Aligned monthly stacks are incomplete. Missing:\n"
            + "\n".join(str(path) for path in missing)
        )
    return paths


def _sample(array, frame):
    return array[frame["row"].to_numpy(), frame["col"].to_numpy()]


def main():
    sample_path = config.DATASETS / "stratified_12697.csv"
    if not sample_path.exists():
        raise SystemExit("Run scripts/04_stratified_sampling.py first.")

    points = pd.read_csv(sample_path)
    k_base, _profile = read_band(config.K_FACTOR)
    paths = _monthly_paths(config.ANALYSIS_YEAR)

    cm_months = []
    savi_months = []
    rvi_months = []
    km_months = []
    for path in paths:
        savi, _profile = read_band(path, band=GEE_BANDS.index("SAVI") + 1)
        cm, _profile = read_band(path, band=GEE_BANDS.index("Cm") + 1)
        rvi, _profile = read_band(path, band=GEE_BANDS.index("RVI") + 1)
        vv, _profile = read_band(path, band=GEE_BANDS.index("VV_dB") + 1)
        moisture, theta_min, theta_max = relative_moisture(vv)
        km = dynamic_erodibility(k_base, moisture)
        cm_months.append(_sample(cm, points))
        savi_months.append(_sample(savi, points))
        rvi_months.append(_sample(rvi, points))
        km_months.append(_sample(km, points))
        print(
            f"{path.name}: VV percentile bounds {theta_min:.2f} to {theta_max:.2f} dB"
        )

    annual = pd.DataFrame(
        {
            "row": points["row"],
            "col": points["col"],
            "Cm": np.nanmean(np.column_stack(cm_months), axis=1),
            "SAVI": np.nanmean(np.column_stack(savi_months), axis=1),
            "RVI": np.nanmean(np.column_stack(rvi_months), axis=1),
            "Km": np.nanmean(np.column_stack(km_months), axis=1),
        }
    )
    annual.to_csv(config.DATASETS / "dynamic_factor_means.csv", index=False)

    for name in ("stratified_12697.csv", "training.csv", "testing.csv"):
        frame = pd.read_csv(config.DATASETS / name)
        merged = frame.drop(columns=[column for column in ("Cm", "SAVI", "RVI", "Km") if column in frame.columns])
        merged = merged.merge(annual, on=["row", "col"], how="left")
        merged.to_csv(config.DATASETS / name, index=False)
        print(f"Updated {name} ({len(merged):,} rows)")


if __name__ == "__main__":
    main()
