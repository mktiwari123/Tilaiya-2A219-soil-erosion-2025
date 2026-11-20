"""Monthly soil-loss maps for the Tilaiya watershed, 2025.

Am = Rm * Km(t) * LS * Cm(t) * P

Rm is the spatial monthly erosivity raster. Km is Kbase adjusted by the
Sentinel-1 VV wetness index. Cm is the fused monthly cover factor.
LS and P are the static aligned baseline factors. Outputs are masked to
the watershed.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import rasterio
import shapefile

import config
from tilaiya.constants import NODATA
from tilaiya.factors import dynamic_erodibility, monthly_soil_loss, relative_moisture
from tilaiya.monthly import GEE_BANDS
from tilaiya.rasters import read_band, watershed_mask

WATERSHED = Path(r"D:\Downloads MKT\GIS Works\Watershed IARI Whole\watershed.shp")
UTM_PRJ = (
    'PROJCS["WGS_1984_UTM_Zone_45N",'
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],'
    'PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",0.0],'
    'PARAMETER["Central_Meridian",87.0],'
    'PARAMETER["Scale_Factor",0.9996],'
    'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]'
)


def monthly_stack(month):
    name = f"Tilaiya_{config.ANALYSIS_YEAR}_{month:02d}.tif"
    for folder in (config.ALIGNED, config.PROJECT / "gee"):
        path = folder / name
        if path.exists():
            return path
    raise FileNotFoundError(f"Monthly Sentinel stack not found: {name}")


def write_raster(path, array, profile, description):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output_profile = profile.copy()
    output_profile.update(dtype=rasterio.float32, count=1, nodata=NODATA, compress="lzw")
    stored = np.where(np.isfinite(array), array, NODATA).astype(np.float32)
    with rasterio.open(path, "w", **output_profile) as output:
        output.write(stored, 1)
        output.set_band_description(1, description)
    return path


def class_code(annual):
    """Baseline soil-loss classes. 0 is NoData."""
    classes = np.zeros(annual.shape, dtype=np.uint8)
    valid = np.isfinite(annual)
    classes[valid & (annual <= 5)] = 1
    classes[valid & (annual > 5) & (annual <= 15)] = 2
    classes[valid & (annual > 15) & (annual <= 30)] = 3
    classes[valid & (annual > 30) & (annual <= 50)] = 4
    classes[valid & (annual > 50) & (annual <= 100)] = 5
    classes[valid & (annual > 100)] = 6
    return classes


def write_summary_shapefile(path, means):
    reader = shapefile.Reader(str(WATERSHED))
    writer = shapefile.Writer(str(path.with_suffix("")), shapeType=reader.shapeType)
    writer.autoBalance = 1
    writer.field("A_annual", "F", 12, 3)
    for month in range(1, 13):
        writer.field(f"Am_{month:02d}", "F", 12, 3)
    for item in reader.shapes():
        writer.shape(item)
        values = [means["annual"]] + [means[month] for month in range(1, 13)]
        writer.record(*values)
    writer.close()
    reader.close()
    path.with_suffix(".prj").write_text(UTM_PRJ, encoding="utf-8")
    path.with_suffix(".cpg").write_text("UTF-8", encoding="utf-8")


def summarise(array, inside):
    values = array[inside & np.isfinite(array)]
    if values.size == 0:
        return {"pixels": 0, "mean": np.nan, "median": np.nan, "p95": np.nan, "max": np.nan}
    return {
        "pixels": int(values.size),
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def main():
    inside, profile, _watershed = watershed_mask(config.REFERENCE_DEM, WATERSHED)
    k_base, _profile = read_band(config.K_FACTOR)
    ls_factor, _profile = read_band(config.LS_FACTOR)
    p_factor, _profile = read_band(config.P_FACTOR)
    if k_base.shape != inside.shape or ls_factor.shape != inside.shape or p_factor.shape != inside.shape:
        raise SystemExit("K, LS, and P are not on the DEM grid.")

    static = inside & np.isfinite(k_base) & np.isfinite(ls_factor) & np.isfinite(p_factor) & (k_base >= 0)
    annual_sum = np.zeros(inside.shape, dtype=np.float64)
    annual_count = np.zeros(inside.shape, dtype=np.uint8)
    records = []
    monthly_means = {}

    km_dir = config.OUTPUT / "rasters" / "Erodibility"
    loss_dir = config.OUTPUT / "rasters" / "SoilLoss"

    for month in range(1, 13):
        stack = monthly_stack(month)
        cm, _profile = read_band(stack, band=GEE_BANDS.index("Cm") + 1)
        vv_db, _profile = read_band(stack, band=GEE_BANDS.index("VV_dB") + 1)
        erosivity_path = config.OUTPUT / "rasters" / "Erosivity" / f"Erosivity_{month:02d}.tif"
        rm, _profile = read_band(erosivity_path)
        if cm.shape != inside.shape or rm.shape != inside.shape:
            raise SystemExit(f"Month {month} grids do not match the DEM.")

        vv_for_percentile = np.where(static, vv_db, np.nan)
        moisture, theta_min, theta_max = relative_moisture(vv_for_percentile)
        km = dynamic_erodibility(k_base, moisture)
        soil_loss = monthly_soil_loss(rm, km, ls_factor, cm, p_factor)
        valid = (
            static
            & np.isfinite(cm)
            & np.isfinite(vv_db)
            & np.isfinite(rm)
            & np.isfinite(km)
            & np.isfinite(soil_loss)
            & (cm >= 0)
            & (rm >= 0)
            & (soil_loss >= 0)
        )
        km = np.where(valid, km, np.nan)
        soil_loss = np.where(valid, soil_loss, np.nan)
        annual_sum[valid] += soil_loss[valid]
        annual_count[valid] += 1

        write_raster(km_dir / f"Km_{month:02d}.tif", km, profile, f"Km_{month:02d}")
        write_raster(loss_dir / f"SoilLoss_{month:02d}.tif", soil_loss, profile, f"Am_{month:02d}")
        stats = summarise(soil_loss, inside)
        monthly_means[month] = stats["mean"]
        records.append(
            {
                "month": month,
                "VV_p5_dB": theta_min,
                "VV_p95_dB": theta_max,
                "valid_pixels": stats["pixels"],
                "missing_pixels": int(inside.sum() - stats["pixels"]),
                "mean_Am_t_ha": stats["mean"],
                "median_Am_t_ha": stats["median"],
                "p95_Am_t_ha": stats["p95"],
                "max_Am_t_ha": stats["max"],
                "mean_Km": float(np.nanmean(km)),
                "mean_Cm": float(np.nanmean(np.where(valid, cm, np.nan))),
                "mean_Rm": float(np.nanmean(np.where(valid, rm, np.nan))),
            }
        )
        print(
            f"Month {month:02d}: mean Am {stats['mean']:.3f} t/ha, "
            f"valid pixels {stats['pixels']:,}, missing {int(inside.sum() - stats['pixels']):,}"
        )

    complete = annual_count == 12
    annual = np.where(complete, annual_sum, np.nan)
    write_raster(loss_dir / "SoilLoss_annual.tif", annual, profile, "A_annual_dynamic_2025")
    write_raster(
        loss_dir / "SoilLoss_month_count.tif",
        np.where(inside, annual_count.astype(np.float32), np.nan),
        profile,
        "months_with_valid_Am",
    )
    classes = class_code(annual).astype(np.float32)
    classes = np.where(complete, classes, np.nan)
    write_raster(loss_dir / "SoilLoss_annual_class.tif", classes, profile, "E1_to_E6")

    annual_stats = summarise(annual, inside)
    monthly_means["annual"] = annual_stats["mean"]
    summary = pd.DataFrame(records)
    summary_path = config.TABLES / "monthly_soil_loss_2025.csv"
    summary.to_csv(summary_path, index=False)
    shapefile_path = config.OUTPUT / "shapefiles" / "SoilLoss_Monthly_Means_2025.shp"
    write_summary_shapefile(shapefile_path, monthly_means)

    print(f"\nAnnual mean where all 12 months are valid: {annual_stats['mean']:.3f} t/ha/yr")
    print(f"Pixels with all 12 months: {int(complete.sum()):,}")
    print(f"Summary table: {summary_path}")
    print(f"Summary shapefile: {shapefile_path}")
    print(f"Monthly Km rasters: {km_dir}")
    print(f"Monthly soil-loss rasters: {loss_dir}")


if __name__ == "__main__":
    main()
