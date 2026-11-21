"""Separate the cover factor from the other RUSLE terms.

The reported monthly maps use Cm = clip(1 - 1.18 x canopy index). This
script replaces that cover with the van der Knijff exponential of NDVI,
samples the Raj et al. (2022) India R-factor on the mask, and writes a
factor budget. Reported SoilLoss_Arnoldus rasters are left in place.
"""

from pathlib import Path
import struct
import sys
import zipfile

import numpy as np
import pandas as pd
import rasterio
import requests
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from tilaiya.factors import (  # noqa: E402
    arnoldus_monthly_erosivity,
    corrected_arnoldus_annual,
    vander_knijff_cover,
)
from tilaiya.rasters import read_band, write_band  # noqa: E402

OUT = ROOT / "output" / "tables"
SENS = ROOT / "output" / "rasters" / "sensitivity"
STACK = ROOT / "data" / "aligned"
SOIL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
EROSIVITY = ROOT / "output" / "rasters" / "Erosivity"
IRED_DIR = ROOT / "data" / "erosivity"
IRED_ZIP = IRED_DIR / "IRED.zip"
IRED_URL = (
    "https://zenodo.org/records/6505510/files/"
    "Indian%20Rainfall%20Erosivity%20Dataset%20%28IRED%29.zip?download=1"
)
HA = 12.5 * 12.5 / 10000.0

STUDY = {894.0: 1, 1225.0: 2, 786.0: 3, 1046.0: 4, 1292.0: 5}
RAINFALL = {
    1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
    2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
    3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
    4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
    5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
}


def finite_clean(values):
    out = values.astype(np.float64, copy=True)
    out[out < -1] = np.nan
    return out


def stats(values):
    data = values[np.isfinite(values)]
    if data.size == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan}
    return {"n": int(data.size), "mean": float(data.mean()), "median": float(np.median(data))}


def class_shares(annual):
    data = annual[np.isfinite(annual)]
    breaks = [
        ("0-5", data <= 5),
        ("5-15", (data > 5) & (data <= 15)),
        ("15-30", (data > 15) & (data <= 30)),
        ("30-50", (data > 30) & (data <= 50)),
        ("50-100", (data > 50) & (data <= 100)),
        (">100", data > 100),
    ]
    return {label: float(np.mean(mask)) if data.size else np.nan for label, mask in breaks}


def cell_ids(stored_annual):
    keys = np.array(sorted(STUDY), dtype=float)
    finite = np.isfinite(stored_annual)
    cells = np.full(stored_annual.shape, -1, dtype=np.int16)
    flat = stored_annual[finite]
    index = np.abs(flat[:, None] - keys[None, :]).argmin(axis=1)
    chosen = keys[index]
    nearest = np.full(stored_annual.shape, np.nan)
    nearest[finite] = chosen
    for value, cell in STUDY.items():
        cells[np.isclose(nearest, value)] = cell
    return cells


def month_stack(month):
    return STACK / f"Tilaiya_2025_{month:02d}.tif"


def read_index(month, name):
    band = {"SAVI": 1, "NDVI": 2, "Cm": 9}[name]
    values, _profile = read_band(month_stack(month), band=band)
    return finite_clean(values)


def ensure_ired():
    IRED_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(IRED_DIR.rglob("R-Factor_India.tif")) + list(IRED_DIR.rglob("R-factor_India.tif"))
    if existing:
        return existing[0]
    if not IRED_ZIP.exists():
        print("downloading IRED")
        response = requests.get(IRED_URL, timeout=180)
        response.raise_for_status()
        IRED_ZIP.write_bytes(response.content)
    with zipfile.ZipFile(IRED_ZIP) as archive:
        archive.extractall(IRED_DIR)
    found = list(IRED_DIR.rglob("R-Factor_India.tif")) + list(IRED_DIR.rglob("R-factor_India.tif"))
    if not found:
        raise SystemExit("R-factor GeoTIFF was not in the IRED archive.")
    return found[0]


def sample_ired(path, support, profile):
    transform = profile["transform"]
    rows, cols = np.where(support)
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    transformer = Transformer.from_crs(profile["crs"], "EPSG:4326", always_xy=True)
    lons, lats = transformer.transform(xs, ys)
    with rasterio.open(path) as source:
        samples = np.array(
            [value[0] for value in source.sample(zip(lons, lats), masked=False)],
            dtype=np.float64,
        )
        nodata = source.nodata
    if nodata is not None:
        samples[np.isclose(samples, nodata)] = np.nan
    samples[~np.isfinite(samples)] = np.nan
    grid = np.full(support.shape, np.nan)
    grid[rows, cols] = samples
    summary = stats(samples)
    summary["min"] = float(np.nanmin(samples)) if np.isfinite(samples).any() else np.nan
    summary["max"] = float(np.nanmax(samples)) if np.isfinite(samples).any() else np.nan
    return grid, summary


def read_dbf(path):
    raw = Path(path).read_bytes()
    nrec, header_len, rec_len = struct.unpack("<IHH", raw[4:12])
    fields = []
    cursor = 32
    while raw[cursor] != 0x0D:
        name = raw[cursor : cursor + 11].split(b"\x00", 1)[0].decode("latin1")
        length = raw[cursor + 16]
        fields.append((name, length))
        cursor += 32
    rows = []
    for index in range(nrec):
        start = header_len + index * rec_len
        record = raw[start + 1 : start + rec_len]
        offset = 0
        row = {}
        for name, length in fields:
            row[name] = record[offset : offset + length].decode("latin1").strip()
            offset += length
        rows.append(row)
    return pd.DataFrame(rows)


def arcgrid_stats(path):
    if not Path(path).exists():
        return {"n": 0, "mean": np.nan, "median": np.nan, "min": np.nan}
    with rasterio.open(path) as source:
        array = source.read(1).astype(np.float64)
        nodata = source.nodata
    if nodata is not None:
        array[np.isclose(array, nodata)] = np.nan
    data = array[np.isfinite(array)]
    if data.size == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "min": np.nan}
    return {
        "n": int(data.size),
        "mean": float(data.mean()),
        "median": float(np.median(data)),
        "min": float(data.min()),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SENS.mkdir(parents=True, exist_ok=True)

    reported, profile = read_band(SOIL / "SoilLoss_annual.tif")
    support = np.isfinite(reported)
    stored_annual, _erosivity_profile = read_band(EROSIVITY / "Erosivity_annual.tif")
    cells = cell_ids(stored_annual)
    annual_r = {cell: corrected_arnoldus_annual(rain) for cell, rain in RAINFALL.items()}
    monthly_r = {cell: arnoldus_monthly_erosivity(rain) for cell, rain in RAINFALL.items()}
    r_map = np.full(reported.shape, np.nan)
    for cell, value in annual_r.items():
        r_map[cells == cell] = value

    ndvi_june = read_index(6, "NDVI")
    ndvi_september = read_index(9, "NDVI")
    ndvi_july = (2.0 / 3.0) * ndvi_june + (1.0 / 3.0) * ndvi_september
    ndvi_august = (1.0 / 3.0) * ndvi_june + (2.0 / 3.0) * ndvi_september
    cm_june = read_index(6, "Cm")
    cm_september = read_index(9, "Cm")
    cm_july = (2.0 / 3.0) * cm_june + (1.0 / 3.0) * cm_september
    cm_august = (1.0 / 3.0) * cm_june + (2.0 / 3.0) * cm_september

    observed_july = read_index(7, "NDVI")
    july_observed = support & np.isfinite(observed_july) & (observed_july > -1) & (observed_july < 1)

    annual_exp = np.zeros(reported.shape, dtype=np.float64)
    annual_exp_valid = np.ones(reported.shape, dtype=bool)
    numer_linear = np.zeros(reported.shape, dtype=np.float64)
    numer_exp = np.zeros(reported.shape, dtype=np.float64)
    weight = np.zeros(reported.shape, dtype=np.float64)
    cover_rows = []

    for month in range(1, 13):
        soil, _month_profile = read_band(SOIL / f"SoilLoss_{month:02d}.tif")
        soil = finite_clean(soil)
        if month == 7:
            ndvi = ndvi_july
            cm = cm_july
        elif month == 8:
            ndvi = ndvi_august
            cm = cm_august
        else:
            ndvi = read_index(month, "NDVI")
            cm = read_index(month, "Cm")
        c_exp = vander_knijff_cover(ndvi)
        rm = np.full(reported.shape, np.nan)
        for cell in range(1, 6):
            rm[cells == cell] = monthly_r[cell][month - 1]
        both = np.isfinite(soil) & np.isfinite(cm) & (cm > 0) & np.isfinite(c_exp)
        scaled = np.full(reported.shape, np.nan)
        scaled[both] = soil[both] * (c_exp[both] / cm[both])
        dry = np.isfinite(soil) & np.isclose(soil, 0.0) & np.isfinite(c_exp)
        scaled[dry] = 0.0
        annual_exp_valid &= np.isfinite(scaled)
        annual_exp += np.where(np.isfinite(scaled), scaled, 0.0)
        weighted = support & np.isfinite(rm) & np.isfinite(cm) & np.isfinite(c_exp)
        numer_linear[weighted] += rm[weighted] * cm[weighted]
        numer_exp[weighted] += rm[weighted] * c_exp[weighted]
        weight[weighted] += rm[weighted]
        on_support = support & np.isfinite(cm) & np.isfinite(c_exp) & np.isfinite(ndvi)
        cover_rows.append(
            {
                "month": month,
                "ndvi_source": "interpolated June-September" if month in (7, 8) else "monthly composite",
                "n": int(on_support.sum()),
                "mean_ndvi": float(np.mean(ndvi[on_support])) if on_support.any() else np.nan,
                "median_ndvi": float(np.median(ndvi[on_support])) if on_support.any() else np.nan,
                "mean_linear_C": float(np.mean(cm[on_support])) if on_support.any() else np.nan,
                "mean_exponential_C": float(np.mean(c_exp[on_support])) if on_support.any() else np.nan,
                "median_exponential_C": float(np.median(c_exp[on_support])) if on_support.any() else np.nan,
                "share_linear_C_above_0.40": float(np.mean(cm[on_support] > 0.40)) if on_support.any() else np.nan,
                "share_exponential_C_above_0.40": float(np.mean(c_exp[on_support] > 0.40)) if on_support.any() else np.nan,
            }
        )
        print(
            f"month {month:02d} NDVI {cover_rows[-1]['mean_ndvi']:.3f} "
            f"linear C {cover_rows[-1]['mean_linear_C']:.3f} "
            f"exp C {cover_rows[-1]['mean_exponential_C']:.3f}"
        )

    annual_exp = np.where(support & annual_exp_valid, annual_exp, np.nan)
    write_band(SENS / "SoilLoss_annual_vander_knijff.tif", annual_exp, profile)

    ired_path = ensure_ired()
    ired_grid, ired_summary = sample_ired(ired_path, support, profile)
    write_band(SENS / "R_IRED_Raj2022_on_mask.tif", ired_grid, profile)
    ratio = np.full(reported.shape, np.nan)
    can_scale = support & np.isfinite(ired_grid) & np.isfinite(r_map) & (r_map > 0)
    ratio[can_scale] = ired_grid[can_scale] / r_map[can_scale]
    annual_ired = np.where(can_scale, reported * ratio, np.nan)
    annual_both = np.where(can_scale & np.isfinite(annual_exp), annual_exp * ratio, np.nan)
    write_band(SENS / "SoilLoss_annual_IRED_R.tif", annual_ired, profile)
    write_band(SENS / "SoilLoss_annual_vdk_and_IRED.tif", annual_both, profile)

    k_factor, _k_profile = read_band(config.K_FACTOR)
    ls_factor, _ls_profile = read_band(ROOT / "output" / "rasters" / "LS" / "LS.tif")
    p_factor, _p_profile = read_band(ROOT / "output" / "rasters" / "Practice" / "P.tif")
    c_annual, _c_profile = read_band(config.C_FACTOR)
    october_ndvi = read_index(10, "NDVI")
    effective_linear = np.where(support & (weight > 0), numer_linear / weight, np.nan)
    effective_exp = np.where(support & (weight > 0), numer_exp / weight, np.nan)

    def on(values):
        return stats(values[support]) if values.shape == support.shape else stats(values)

    scenario_rows = []
    for name, values in (
        ("Reported linear cover and Arnoldus R", reported),
        ("van der Knijff cover and Arnoldus R", annual_exp),
        ("Linear cover and IRED R", annual_ired),
        ("van der Knijff cover and IRED R", annual_both),
    ):
        row = stats(values)
        shares = class_shares(values)
        row["case"] = name
        row["gross_t"] = float(np.nansum(values) * HA)
        row["share_above_100"] = shares[">100"]
        row["share_0_5"] = shares["0-5"]
        scenario_rows.append(row)
        print(name, {key: row[key] for key in ("n", "mean", "median", "share_above_100")})

    p_on = p_factor[support & np.isfinite(p_factor)]
    p_rounded = np.round(p_on, 3)
    unique, counts = np.unique(p_rounded, return_counts=True)
    p_rows = [
        {"P": float(value), "pixels": int(count), "share": float(count / p_on.size)}
        for value, count in zip(unique, counts)
        if count / p_on.size > 0.001
    ]

    october_on = support & np.isfinite(october_ndvi) & np.isfinite(c_annual)
    october_exp = vander_knijff_cover(october_ndvi)
    arcgrid = arcgrid_stats(r"D:\A_RKLSCP\C_Resample2")

    budget = pd.DataFrame(
        [
            {
                "factor": "R",
                "reported_mean": on(r_map)["mean"],
                "reported_median": on(r_map)["median"],
                "comparison": "Raj et al. 2022 IRED, 1979-2018",
                "comparison_mean": ired_summary["mean"],
                "comparison_median": ired_summary["median"],
                "ratio_reported_to_comparison": on(r_map)["mean"] / ired_summary["mean"],
            },
            {
                "factor": "K",
                "reported_mean": on(k_factor)["mean"],
                "reported_median": on(k_factor)["median"],
                "comparison": "No independent K grid was sampled",
                "comparison_mean": np.nan,
                "comparison_median": np.nan,
                "ratio_reported_to_comparison": np.nan,
            },
            {
                "factor": "LS",
                "reported_mean": on(ls_factor)["mean"],
                "reported_median": on(ls_factor)["median"],
                "comparison": "Standard LS on Copernicus, from sensitivity_dem_soil_loss.csv context",
                "comparison_mean": np.nan,
                "comparison_median": np.nan,
                "ratio_reported_to_comparison": np.nan,
            },
            {
                "factor": "C",
                "reported_mean": stats(effective_linear)["mean"],
                "reported_median": stats(effective_linear)["median"],
                "comparison": "Erosivity-weighted van der Knijff C",
                "comparison_mean": stats(effective_exp)["mean"],
                "comparison_median": stats(effective_exp)["median"],
                "ratio_reported_to_comparison": stats(effective_linear)["mean"] / stats(effective_exp)["mean"],
            },
            {
                "factor": "P",
                "reported_mean": on(p_factor)["mean"],
                "reported_median": on(p_factor)["median"],
                "comparison": "P = 1, no support practice",
                "comparison_mean": 1.0,
                "comparison_median": 1.0,
                "ratio_reported_to_comparison": on(p_factor)["mean"],
            },
        ]
    )

    notes = pd.DataFrame(
        [
            {"item": "support_pixels", "value": int(support.sum())},
            {"item": "july_observed_ndvi_pixels", "value": int(july_observed.sum())},
            {"item": "july_observed_ndvi_share", "value": float(july_observed.sum() / support.sum())},
            {"item": "october_ndvi_median", "value": float(np.median(october_ndvi[october_on]))},
            {"item": "october_vdk_C_median", "value": float(np.median(october_exp[october_on]))},
            {"item": "annual_baseline_C_median", "value": float(np.median(c_annual[october_on]))},
            {"item": "arcgrid_exponential_C_median", "value": arcgrid["median"]},
            {"item": "arcgrid_exponential_C_mean", "value": arcgrid["mean"]},
            {"item": "arcgrid_exponential_C_min", "value": arcgrid["min"]},
            {"item": "ired_min", "value": ired_summary["min"]},
            {"item": "ired_max", "value": ired_summary["max"]},
            {"item": "effective_linear_C_mean", "value": stats(effective_linear)["mean"]},
            {"item": "effective_exponential_C_mean", "value": stats(effective_exp)["mean"]},
        ]
    )

    vat_path = Path(r"D:\A_RKLSCP\Final_Index\Actual_Raster\Final07072026\LULC_2025_RF_v2.tif.vat.dbf")
    p_vat_path = Path(r"D:\A_RKLSCP\ANNUAL\P_FACTOR.tif.vat.dbf")
    if p_vat_path.exists():
        read_dbf(p_vat_path).to_csv(OUT / "p_factor_lookup.csv", index=False)
    if vat_path.exists():
        read_dbf(vat_path).to_csv(OUT / "lulc_2025_lookup.csv", index=False)

    pd.DataFrame(cover_rows).to_csv(OUT / "cover_ndvi_monthly.csv", index=False)
    pd.DataFrame(scenario_rows).to_csv(OUT / "cover_erosivity_scenarios.csv", index=False)
    budget.to_csv(OUT / "factor_budget.csv", index=False)
    pd.DataFrame([ired_summary]).to_csv(OUT / "ired_erosivity_sample.csv", index=False)
    pd.DataFrame(p_rows).to_csv(OUT / "p_factor_values.csv", index=False)
    notes.to_csv(OUT / "cover_erosivity_notes.csv", index=False)
    print(budget.to_string(index=False))
    print(notes.to_string(index=False))


if __name__ == "__main__":
    main()
