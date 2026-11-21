"""January and July Km by nearest land-cover class.

Km = K * (1 + 0.25 * theta). Theta uses one range for every class: the
5th and 95th percentiles of Sentinel-1 VV on cropland and barren pixels,
pooled across the 2025 months. The stored Km rasters and the Arnoldus
soil-loss rasters are not replaced. A July sensitivity raster is written
only when cropland or barren meets both adoption tests in the script.
"""

import os

os.environ.setdefault("GDAL_CACHEMAX", "64")

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.constants import K_MOISTURE_ALPHA, NODATA
from tilaiya.monthly import GEE_BANDS

VV_BAND = GEE_BANDS.index("VV_dB") + 1
LULC = config.BASELINE / "Aligned_2.tif" / "LULC_aligned.tif"
K_PATH = config.K_FACTOR
SUPPORT_PATH = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif"
OUT = ROOT / "output" / "tables"
SENS = ROOT / "output" / "rasters" / "sensitivity"
WINDOW_ROWS = 256
CLASS_NAME = {0: "Built-up", 1: "Cropland", 2: "Vegetation", 3: "Water", 4: "Barren land"}
POOL_CODES = (1, 4)
POOL_MONTHS = tuple(range(1, 13))
VV_SHIFT_DB = 4.0
KM_SHIFT = 0.005


def stack_path(month):
    name = f"Tilaiya_{config.ANALYSIS_YEAR}_{month:02d}.tif"
    path = config.ALIGNED / name
    if path.exists():
        return path
    raise FileNotFoundError(name)


def finite_block(block, nodata):
    out = np.asarray(block, dtype=np.float32)
    bad = ~np.isfinite(out)
    if nodata is not None and np.isfinite(nodata):
        bad |= np.isclose(out, np.float32(nodata))
    bad |= np.isclose(out, np.float32(NODATA))
    return np.where(bad, np.nan, out)


def windows(height, width):
    for row in range(0, height, WINDOW_ROWS):
        yield row, rasterio.windows.Window(0, row, width, min(WINDOW_ROWS, height - row))


def read_window(src, band, window):
    return finite_block(src.read(band, window=window), src.nodata)


def theta_from_vv(vv, low, high):
    span = float(high - low)
    if not np.isfinite(span) or span <= 0:
        raise SystemExit("Cropland and barren VV percentiles do not define a positive range.")
    return np.clip((vv.astype(np.float64) - low) / span, 0.0, 1.0)


def km_from_theta(k_base, theta):
    return k_base.astype(np.float64) * (1.0 + float(K_MOISTURE_ALPHA) * theta)


def accumulate(mask, values, sums):
    if mask.any():
        sums[0] += int(mask.sum())
        for index, array in enumerate(values, start=1):
            sums[index] += float(array[mask].sum())


def mean_from(total, count):
    if count <= 0:
        return np.nan
    return total / count


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SENS.mkdir(parents=True, exist_ok=True)
    months_available = []
    for month in POOL_MONTHS:
        path = stack_path(month)
        months_available.append(month)
        print("stack", path.name, flush=True)
    if len(months_available) < 12:
        raise SystemExit("Expected twelve 2025 stacks in data/aligned.")

    with rasterio.open(SUPPORT_PATH) as support_src:
        height, width = support_src.height, support_src.width
        profile = support_src.profile.copy()
    with rasterio.open(K_PATH) as k_src, rasterio.open(LULC) as lulc_src, rasterio.open(stack_path(1)) as vv_src:
        for label, src in (("K", k_src), ("LULC", lulc_src), ("VV", vv_src)):
            if (src.height, src.width) != (height, width):
                raise SystemExit(f"{label} grid is {src.width}x{src.height}, support is {width}x{height}.")
        if vv_src.count < VV_BAND:
            raise SystemExit(f"VV band {VV_BAND} is missing from {vv_src.name}.")

    print("pass 1: cropland and barren VV percentiles", flush=True)
    samples = []
    support_n = 0
    with rasterio.open(SUPPORT_PATH) as support_src, rasterio.open(LULC) as lulc_src:
        sources = {month: rasterio.open(stack_path(month)) for month in months_available}
        try:
            for row, window in windows(height, width):
                support = np.isfinite(read_window(support_src, 1, window))
                support_n += int(support.sum())
                classes = np.rint(read_window(lulc_src, 1, window))
                pool_class = support & ((classes == POOL_CODES[0]) | (classes == POOL_CODES[1]))
                if not pool_class.any():
                    continue
                for month in months_available:
                    vv = read_window(sources[month], VV_BAND, window)
                    keep = pool_class & np.isfinite(vv)
                    if keep.any():
                        samples.append(np.ascontiguousarray(vv[keep], dtype=np.float32))
                if row % (WINDOW_ROWS * 4) == 0:
                    print("percentile row", row, flush=True)
        finally:
            for src in sources.values():
                src.close()

    if not samples:
        raise SystemExit("No cropland or barren VV samples on the annual support.")
    pooled = np.concatenate(samples)
    del samples
    p5, p95 = np.percentile(pooled, [5.0, 95.0])
    p5 = float(p5)
    p95 = float(p95)
    print(
        "annual support",
        support_n,
        "pool n",
        int(pooled.size),
        "p5",
        round(p5, 4),
        "p95",
        round(p95, 4),
        flush=True,
    )
    del pooled

    print("pass 2: January and July class means", flush=True)
    # count, VV Jan, VV Jul, theta Jan, theta Jul, Km Jan, Km Jul, K
    totals = {code: np.zeros(8, dtype=np.float64) for code in CLASS_NAME}
    with rasterio.open(SUPPORT_PATH) as support_src, rasterio.open(LULC) as lulc_src, rasterio.open(K_PATH) as k_src, rasterio.open(
        stack_path(1)
    ) as jan_src, rasterio.open(stack_path(7)) as jul_src:
        for row, window in windows(height, width):
            support = np.isfinite(read_window(support_src, 1, window))
            classes = np.rint(read_window(lulc_src, 1, window))
            k_base = read_window(k_src, 1, window)
            vv_jan = read_window(jan_src, VV_BAND, window)
            vv_jul = read_window(jul_src, VV_BAND, window)
            paired = (
                support
                & np.isfinite(vv_jan)
                & np.isfinite(vv_jul)
                & np.isfinite(k_base)
                & (k_base >= 0)
                & np.isfinite(classes)
            )
            if not paired.any():
                continue
            theta_jan = theta_from_vv(vv_jan, p5, p95)
            theta_jul = theta_from_vv(vv_jul, p5, p95)
            km_jan = km_from_theta(k_base, theta_jan)
            km_jul = km_from_theta(k_base, theta_jul)
            for code in CLASS_NAME:
                mask = paired & (classes == code)
                if not mask.any():
                    continue
                bucket = totals[code]
                bucket[0] += float(mask.sum())
                bucket[1] += float(vv_jan[mask].sum())
                bucket[2] += float(vv_jul[mask].sum())
                bucket[3] += float(theta_jan[mask].sum())
                bucket[4] += float(theta_jul[mask].sum())
                bucket[5] += float(km_jan[mask].sum())
                bucket[6] += float(km_jul[mask].sum())
                bucket[7] += float(k_base[mask].astype(np.float64).sum())
            if row % (WINDOW_ROWS * 4) == 0:
                print("class row", row, flush=True)

    def row_for(name, bucket):
        count = bucket[0]
        vv_jan = mean_from(bucket[1], count)
        vv_jul = mean_from(bucket[2], count)
        km_jan = mean_from(bucket[5], count)
        km_jul = mean_from(bucket[6], count)
        return {
            "class": name,
            "n": int(count),
            "mean_VV_Jan_dB": vv_jan,
            "mean_VV_Jul_dB": vv_jul,
            "dVV_Jul_minus_Jan_dB": vv_jul - vv_jan,
            "mean_theta_Jan": mean_from(bucket[3], count),
            "mean_theta_Jul": mean_from(bucket[4], count),
            "mean_Km_Jan": km_jan,
            "mean_Km_Jul": km_jul,
            "dKm_Jul_minus_Jan": km_jul - km_jan,
            "mean_K": mean_from(bucket[7], count),
        }

    rows = [row_for(CLASS_NAME[code], totals[code]) for code in CLASS_NAME]
    land_codes = (0, 1, 2, 4)
    all_codes = (0, 1, 2, 3, 4)
    rows.append(row_for("All land", sum(totals[code] for code in land_codes)))
    rows.append(row_for("All pixels", sum(totals[code] for code in all_codes)))
    frame = pd.DataFrame(rows)

    exposed = frame[frame["class"].isin(["Cropland", "Barren land"])]
    pulse_classes = []
    for _, item in exposed.iterrows():
        if float(item["dVV_Jul_minus_Jan_dB"]) >= VV_SHIFT_DB and float(item["dKm_Jul_minus_Jan"]) >= KM_SHIFT:
            pulse_classes.append(str(item["class"]))
    raster_written = False
    raster_path = SENS / "Km_July_soil_exposed_p5p95.tif"
    if pulse_classes:
        print("pass 3: July sensitivity raster", pulse_classes, flush=True)
        july = np.full((height, width), NODATA, dtype=np.float32)
        with rasterio.open(SUPPORT_PATH) as support_src, rasterio.open(K_PATH) as k_src, rasterio.open(stack_path(7)) as jul_src:
            for row, window in windows(height, width):
                support = np.isfinite(read_window(support_src, 1, window))
                k_base = read_window(k_src, 1, window)
                vv_jul = read_window(jul_src, VV_BAND, window)
                ok = support & np.isfinite(vv_jul) & np.isfinite(k_base) & (k_base >= 0)
                if not ok.any():
                    continue
                km_jul = km_from_theta(k_base, theta_from_vv(vv_jul, p5, p95))
                block = july[row : row + int(window.height)]
                block[ok] = km_jul[ok].astype(np.float32)
        profile.update(dtype=rasterio.float32, count=1, nodata=NODATA, compress="lzw")
        with rasterio.open(raster_path, "w", **profile) as dst:
            dst.write(july, 1)
            dst.set_band_description(1, "July Km, cropland and barren 2025 VV p5-p95")
        raster_written = True
        del july

    pool_text = "all 12 months of 2025" if months_available == list(range(1, 13)) else "months " + ",".join(f"{month:02d}" for month in months_available)
    if raster_written:
        outcome = f"July sensitivity raster written to {raster_path.relative_to(ROOT).as_posix()}."
    else:
        outcome = "No sensitivity raster was written. Stored Km rasters were not replaced."
    note = (
        f"Common range is the 5th and 95th percentiles of VV on cropland and barren "
        f"pixels of the annual support, pooled over {pool_text} "
        f"(p5={p5:.4f} dB, p95={p95:.4f} dB). The same range is applied to every class. "
        f"Theta is clipped to 0-1. Km = K*(1+{K_MOISTURE_ALPHA:.2f}*theta). {outcome}"
    )
    frame["note"] = note
    destination = OUT / "km_class_season.csv"
    frame.to_csv(destination, index=False)
    print(frame.drop(columns=["note"]).to_string(index=False), flush=True)
    print(note, flush=True)
    print("raster_written", raster_written, flush=True)
    for _, item in exposed.iterrows():
        fraction = float(item["dKm_Jul_minus_Jan"]) / float(item["mean_K"]) if item["mean_K"] else np.nan
        print(
            item["class"],
            "dVV",
            round(float(item["dVV_Jul_minus_Jan_dB"]), 4),
            "dKm",
            round(float(item["dKm_Jul_minus_Jan"]), 6),
            "dKm/mean_K",
            round(float(fraction), 4),
            flush=True,
        )


if __name__ == "__main__":
    main()
