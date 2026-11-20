"""Assemble monthly soil-loss maps from aligned dynamic factors."""

from pathlib import Path

import numpy as np
import pandas as pd

from tilaiya.factors import dynamic_erodibility, monthly_soil_loss, relative_moisture
from tilaiya.rasters import read_band, write_band

GEE_BANDS = (
    "SAVI",
    "NDVI",
    "NDBI",
    "MNDWI",
    "Cm_optical",
    "VV_dB",
    "VH_dB",
    "RVI",
    "Cm",
)


def gee_filename(year, month):
    return f"Tilaiya_{int(year)}_{int(month):02d}.tif"


def sum_monthly_maps(monthly_maps):
    """Sum monthly soil loss and keep a cell only where a month is finite."""
    stack = np.stack([np.asarray(month, dtype=np.float64) for month in monthly_maps], axis=0)
    finite = np.isfinite(stack)
    total = np.nansum(np.where(finite, stack, 0.0), axis=0)
    return np.where(finite.any(axis=0), total, np.nan)


def _band(path, name):
    index = GEE_BANDS.index(name) + 1
    array, profile = read_band(path, band=index)
    return array, profile


def build_monthly_rusle(
    aligned_dir,
    year,
    erosivity_table,
    k_base,
    ls_factor,
    p_factor,
    profile,
    destination,
):
    """Earlier catchment-mean Rm calculation.

    The maps used for the study are written by scripts/03_monthly_soil_loss.py.
    That script reads a separate erosivity raster for each month. This
    function remains only as the single-value Rm version.
    """
    aligned_dir = Path(aligned_dir)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    erosivity = erosivity_table.set_index("month")["Rm"]
    monthly_loss = []
    records = []

    for month in range(1, 13):
        path = aligned_dir / gee_filename(year, month)
        if not path.exists():
            raise FileNotFoundError(
                f"Missing aligned monthly stack: {path}\n"
                "Export it from gee/export_monthly_factors.py or the Code Editor "
                "script, then run scripts/02_align_dynamic_factors.py."
            )
        cm, _month_profile = _band(path, "Cm")
        vv_db, _month_profile = _band(path, "VV_dB")
        moisture, theta_min, theta_max = relative_moisture(vv_db)
        km = dynamic_erodibility(k_base, moisture)
        rm = float(erosivity.loc[month])
        soil_loss = monthly_soil_loss(rm, km, ls_factor, cm, p_factor)
        valid = np.isfinite(k_base) & np.isfinite(ls_factor) & np.isfinite(p_factor)
        km = np.where(valid, km, np.nan)
        soil_loss = np.where(valid & np.isfinite(cm) & np.isfinite(moisture), soil_loss, np.nan)
        write_band(destination / f"Km_{month:02d}.tif", km, profile)
        write_band(destination / f"Am_{month:02d}.tif", soil_loss, profile)
        monthly_loss.append(soil_loss)
        records.append(
            {
                "month": month,
                "Rm": rm,
                "theta_min_vv_db": theta_min,
                "theta_max_vv_db": theta_max,
                "mean_Km": float(np.nanmean(km)),
                "mean_Cm": float(np.nanmean(cm)),
                "mean_Am": float(np.nanmean(soil_loss)),
            }
        )

    annual = sum_monthly_maps(monthly_loss)
    write_band(destination / "A_annual_dynamic.tif", annual, profile)
    summary = pd.DataFrame(records)
    summary.to_csv(destination / "monthly_summary.csv", index=False)
    return annual, summary
