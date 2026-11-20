"""IMD monthly rainfall and erosivity for the Tilaiya watershed.

Shapefiles keep one polygon per 0.25 degree cell. GeoTIFF rasters burn
those same cell values onto the 12.5 m ALOS DEM grid and mask them to
the watershed, so they can be multiplied with the other RUSLE factors.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import rasterio
import shapefile
from rasterio.features import rasterize
from rasterio.warp import transform
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

import config
from tilaiya.constants import NODATA
from tilaiya.factors import monthly_erosivity

IMD_DIR = Path(
    r"D:\Downloads MKT\HydroMeteorological Data\Gridded Rainfall Data"
    r"\Gridded Rainfall Data 2015 to 2024\rain"
)
WATERSHED = Path(r"D:\Downloads MKT\GIS Works\Watershed IARI Whole\watershed.shp")

N_LAT = 129
N_LON = 135
LAT0 = 6.5
LON0 = 66.5
CELL = 0.25
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


def read_year(year):
    path = IMD_DIR / f"{year}.grd"
    if not path.exists():
        raise FileNotFoundError(path)
    values = np.fromfile(path, dtype="<f4")
    expected = N_LAT * N_LON
    if values.size % expected != 0:
        raise ValueError(f"{path.name} is not a {N_LAT} by {N_LON} daily grid.")
    grid = values.reshape(-1, N_LAT, N_LON)
    return np.where(grid < -900, np.nan, grid)


def cell_polygon(lon, lat):
    half = CELL / 2.0
    corner_lon = [lon - half, lon + half, lon + half, lon - half]
    corner_lat = [lat - half, lat - half, lat + half, lat + half]
    easting, northing = transform("EPSG:4326", "EPSG:32645", corner_lon, corner_lat)
    return list(zip(easting, northing)), easting, northing


def watershed_geometry():
    reader = shapefile.Reader(str(WATERSHED))
    parts = [shape(item.__geo_interface__) for item in reader.shapes()]
    reader.close()
    return unary_union(parts)


def cells_over_watershed(watershed):
    selected = []
    for lat_index, lat in enumerate(LAT0 + np.arange(N_LAT) * CELL):
        for lon_index, lon in enumerate(LON0 + np.arange(N_LON) * CELL):
            ring, easting, northing = cell_polygon(float(lon), float(lat))
            if max(easting) < watershed.bounds[0] or min(easting) > watershed.bounds[2]:
                continue
            if max(northing) < watershed.bounds[1] or min(northing) > watershed.bounds[3]:
                continue
            polygon = shape(
                {"type": "Polygon", "coordinates": [ring + [ring[0]]]}
            )
            if polygon.intersects(watershed):
                selected.append((lat_index, lon_index, float(lon), float(lat), ring))
    return selected


def write_polygons(path, fields, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = shapefile.Writer(str(path.with_suffix("")), shapeType=shapefile.POLYGON)
    writer.autoBalance = 1
    for name, kind, size, decimals in fields:
        writer.field(name, kind, size, decimals)
    for ring, values in records:
        writer.poly([ring])
        writer.record(*values)
    writer.close()
    path.with_suffix(".prj").write_text(UTM_PRJ, encoding="utf-8")
    path.with_suffix(".cpg").write_text("UTF-8", encoding="utf-8")


def write_grid_rasters(name, monthly_layers, annual_layer, watershed):
    """Burn each IMD cell onto the 12.5 m DEM grid and clip to the watershed."""
    with rasterio.open(config.REFERENCE_DEM) as dem:
        profile = dem.profile.copy()
        dem_values = dem.read(1)
        dem_nodata = dem.nodata
        grid_transform = dem.transform
        grid_shape = (dem.height, dem.width)

    inside = rasterize(
        [(watershed, 1)],
        out_shape=grid_shape,
        transform=grid_transform,
        fill=0,
        dtype="uint8",
    ).astype(bool)
    if dem_nodata is not None:
        inside &= ~np.isclose(dem_values, dem_nodata)

    folder = config.OUTPUT / "rasters" / name
    folder.mkdir(parents=True, exist_ok=True)
    profile.update(dtype=rasterio.float32, count=1, nodata=NODATA, compress="lzw")

    def burn(values_by_polygon):
        burned = rasterize(
            values_by_polygon,
            out_shape=grid_shape,
            transform=grid_transform,
            fill=NODATA,
            dtype="float32",
        )
        return np.where(inside, burned, NODATA).astype(np.float32)

    written = []
    january = None
    for month, layer in enumerate(monthly_layers, start=1):
        burned = burn(layer)
        if january is None:
            january = burned
        path = folder / f"{name}_{month:02d}.tif"
        with rasterio.open(path, "w", **profile) as output:
            output.write(burned, 1)
            output.set_band_description(1, f"{name}_{month:02d}")
        written.append(path)

    annual_path = folder / f"{name}_annual.tif"
    with rasterio.open(annual_path, "w", **profile) as output:
        output.write(burn(annual_layer), 1)
        output.set_band_description(1, f"{name}_annual")
    written.append(annual_path)

    missing = int((inside & np.isclose(january, NODATA)).sum())
    print(f"{name}: {len(written)} rasters, watershed pixels without a value: {missing}")
    return written


def main():
    rainfall = read_year(config.ANALYSIS_YEAR)
    n_days = rainfall.shape[0]
    dates = pd.date_range(f"{config.ANALYSIS_YEAR}-01-01", periods=n_days, freq="D")
    watershed = watershed_geometry()
    cells = cells_over_watershed(watershed)
    if not cells:
        raise SystemExit("No IMD cells intersect the watershed.")

    rain_fields = [("cell_id", "N", 8, 0), ("lon", "F", 10, 4), ("lat", "F", 10, 4)]
    erosivity_fields = list(rain_fields)
    for month in range(1, 13):
        rain_fields.append((f"P_{month:02d}", "F", 12, 3))
        erosivity_fields.append((f"Rm_{month:02d}", "F", 12, 3))
    rain_fields.append(("P_annual", "F", 12, 3))
    erosivity_fields.append(("Rm_annual", "F", 12, 3))

    rain_records = []
    erosivity_records = []
    table_rows = []
    rain_months = [[] for _ in range(12)]
    erosivity_months = [[] for _ in range(12)]
    rain_annual = []
    erosivity_annual = []
    for cell_number, (lat_index, lon_index, lon, lat, ring) in enumerate(cells, start=1):
        series = pd.Series(rainfall[:, lat_index, lon_index], index=dates)
        month_index = pd.date_range(f"{config.ANALYSIS_YEAR}-01-01", periods=12, freq="MS")
        monthly_mm = (
            series.resample("MS").sum().reindex(month_index, fill_value=0.0).to_numpy(dtype=float)
        )
        annual_mm = float(np.nansum(monthly_mm))
        erosivity = np.nan_to_num(monthly_erosivity(monthly_mm, annual_mm), nan=0.0)
        polygon = Polygon(ring)
        rain_records.append((ring, [cell_number, lon, lat, *monthly_mm.tolist(), annual_mm]))
        erosivity_records.append(
            (ring, [cell_number, lon, lat, *erosivity.tolist(), float(np.sum(erosivity))])
        )
        for month in range(12):
            rain_months[month].append((polygon, float(monthly_mm[month])))
            erosivity_months[month].append((polygon, float(erosivity[month])))
            table_rows.append(
                {
                    "cell_id": cell_number,
                    "lon": lon,
                    "lat": lat,
                    "month": month + 1,
                    "precip_mm": monthly_mm[month],
                    "Rm": float(erosivity[month]),
                }
            )
        rain_annual.append((polygon, annual_mm))
        erosivity_annual.append((polygon, float(np.sum(erosivity))))

    destination = config.OUTPUT / "shapefiles"
    rainfall_path = destination / f"IMD_Rainfall_Monthly_{config.ANALYSIS_YEAR}.shp"
    erosivity_path = destination / f"IMD_Erosivity_Monthly_{config.ANALYSIS_YEAR}.shp"
    write_polygons(rainfall_path, rain_fields, rain_records)
    write_polygons(erosivity_path, erosivity_fields, erosivity_records)
    table = pd.DataFrame(table_rows)
    table_path = destination / f"IMD_monthly_cells_{config.ANALYSIS_YEAR}.csv"
    table.to_csv(table_path, index=False)

    print(f"IMD cells intersecting the watershed: {len(cells)}")
    print(table.groupby("month")[["precip_mm", "Rm"]].mean().round(2).to_string())
    print(f"\nRainfall shapefile:  {rainfall_path}")
    print(f"Erosivity shapefile: {erosivity_path}")
    print(f"Cell table:          {table_path}")
    write_grid_rasters("Rainfall", rain_months, rain_annual, watershed)
    write_grid_rasters("Erosivity", erosivity_months, erosivity_annual, watershed)


if __name__ == "__main__":
    main()
