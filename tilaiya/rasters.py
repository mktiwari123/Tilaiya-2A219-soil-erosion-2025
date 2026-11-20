"""Raster helpers that keep every layer on the ALOS 12.5 m grid."""

from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from tilaiya.constants import NODATA


def read_band(path, band=1):
    path = Path(path)
    with rasterio.open(path) as source:
        array = source.read(band).astype(np.float64)
        nodata = source.nodata
        if nodata is not None:
            array = np.where(np.isclose(array, nodata), np.nan, array)
        array = np.where(np.isfinite(array), array, np.nan)
        profile = source.profile.copy()
    return array, profile


def write_band(path, array, profile, nodata=NODATA):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = np.where(np.isfinite(array), array, nodata).astype(np.float32)
    profile = profile.copy()
    profile.update(dtype=rasterio.float32, count=1, nodata=nodata, compress="lzw")
    with rasterio.open(path, "w", **profile) as destination:
        destination.write(output, 1)
    return path


def align_to_reference(source_path, reference_path, destination_path, resampling="bilinear"):
    """Warp one raster onto the reference DEM grid."""
    method = Resampling.bilinear if resampling == "bilinear" else Resampling.nearest
    with rasterio.open(reference_path) as reference, rasterio.open(source_path) as source:
        profile = reference.profile.copy()
        profile.update(dtype=rasterio.float32, count=1, nodata=NODATA, compress="lzw")
        destination = np.full((reference.height, reference.width), NODATA, dtype=np.float32)
        reproject(
            source=rasterio.band(source, 1),
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=reference.transform,
            dst_crs=reference.crs,
            dst_nodata=NODATA,
            resampling=method,
        )
    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(destination_path, "w", **profile) as output:
        output.write(destination, 1)
    return destination_path


def align_stack(source_path, reference_path, destination_path, resampling="bilinear"):
    """Warp every band of a monthly stack onto the reference DEM grid."""
    method = Resampling.bilinear if resampling == "bilinear" else Resampling.nearest
    with rasterio.open(reference_path) as reference, rasterio.open(source_path) as source:
        profile = reference.profile.copy()
        profile.update(
            dtype=rasterio.float32,
            count=source.count,
            nodata=NODATA,
            compress="lzw",
        )
        destination_path = Path(destination_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(destination_path, "w", **profile) as output:
            for band in range(1, source.count + 1):
                destination = np.full((reference.height, reference.width), NODATA, dtype=np.float32)
                reproject(
                    source=rasterio.band(source, band),
                    destination=destination,
                    src_transform=source.transform,
                    src_crs=source.crs,
                    src_nodata=source.nodata,
                    dst_transform=reference.transform,
                    dst_crs=reference.crs,
                    dst_nodata=NODATA,
                    resampling=method,
                )
                output.write(destination, band)
                output.set_band_description(band, source.descriptions[band - 1] or f"band_{band}")
    return destination_path


def cell_centres(transform, rows, cols):
    """Return x, y of pixel centres for row and column indexes."""
    xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def sample_rows(array, rows, cols):
    return array[rows, cols]


def watershed_mask(dem_path, watershed_path):
    """Boolean mask of the watershed on the DEM grid, excluding DEM NoData."""
    import shapefile
    from rasterio.features import rasterize
    from shapely.geometry import shape
    from shapely.ops import unary_union

    with rasterio.open(dem_path) as dem:
        profile = dem.profile.copy()
        elevation = dem.read(1)
        dem_nodata = dem.nodata
        grid_transform = dem.transform
        grid_shape = (dem.height, dem.width)

    reader = shapefile.Reader(str(watershed_path))
    watershed = unary_union([shape(item.__geo_interface__) for item in reader.shapes()])
    reader.close()
    inside = rasterize(
        [(watershed, 1)],
        out_shape=grid_shape,
        transform=grid_transform,
        fill=0,
        dtype="uint8",
    ).astype(bool)
    if dem_nodata is not None:
        inside &= ~np.isclose(elevation, dem_nodata)
    inside &= np.isfinite(elevation)
    return inside, profile, watershed
