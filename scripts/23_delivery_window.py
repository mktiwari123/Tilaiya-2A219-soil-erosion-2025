"""Test each soil-loss scenario against reservoir yield and area-based delivery ratios.

The Raj et al. (2022) grid is re-read for a regional check. A land-cover
lookup is applied as a third cover scenario. Reported soil-loss rasters
are left in place.
"""

from pathlib import Path
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from tilaiya.factors import vander_knijff_cover  # noqa: E402
from tilaiya.rasters import read_band, write_band  # noqa: E402

OUT = ROOT / "output" / "tables"
SENS = ROOT / "output" / "rasters" / "sensitivity"
SOIL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
STACK = ROOT / "data" / "aligned"
HA = 12.5 * 12.5 / 10000.0
MASK_KM2 = 715.02
OFFICIAL_KM2 = 984.0
YIELD_LOW = 10.26  # t/ha/yr at 1.0 t/m3
YIELD_HIGH = 14.88  # t/ha/yr at 1.45 t/m3

# Power functions as stated by Lim et al. (2005), area in km2.
SDR_CURVES = {
    "Vanoni 1975": (0.4724, -0.125),
    "USDA 1972": (0.5656, -0.11),
    "Boyce 1975": (0.3750, -0.2382),
}
CLASS_COVER = {0: 0.002, 1: 0.28, 2: 0.005, 3: 0.0, 4: 1.0}
CLASS_NAME = {0: "Built-up", 1: "Cropland", 2: "Vegetation", 3: "Water", 4: "Barren land"}


def read_dbf(path):
    raw = Path(path).read_bytes()
    nrec, header_len, rec_len = struct.unpack("<IHH", raw[4:12])
    fields = []
    cursor = 32
    while raw[cursor] != 0x0D:
        name = raw[cursor : cursor + 11].split(b"\x00", 1)[0].decode("latin1")
        fields.append((name, raw[cursor + 16]))
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


def sdr(area_km2, coefficient, exponent):
    return coefficient * area_km2**exponent


def weighted_ratio(weight, numerator, denominator):
    mask = np.isfinite(weight) & np.isfinite(numerator) & np.isfinite(denominator) & (weight > 0)
    denom = float(np.sum(weight[mask] * denominator[mask]))
    if denom == 0:
        return np.nan
    return float(np.sum(weight[mask] * numerator[mask]) / denom)


def xlsx_sheets(path):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared.append("".join(node.text or "" for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")))
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = []
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            sheets.append(sheet.attrib.get("name"))
        frames = {}
        for index, name in enumerate(sheets, start=1):
            root = ET.fromstring(book.read(f"xl/worksheets/sheet{index}.xml"))
            rows = []
            for row in root.findall("m:sheetData/m:row", ns):
                values = []
                for cell in row.findall("m:c", ns):
                    kind = cell.attrib.get("t")
                    node = cell.find("m:v", ns)
                    text = "" if node is None or node.text is None else node.text
                    if kind == "s" and text:
                        text = shared[int(text)]
                    values.append(text)
                rows.append(values)
            width = max((len(row) for row in rows), default=0)
            rows = [row + [""] * (width - len(row)) for row in rows]
            frames[name] = pd.DataFrame(rows)
        return frames


def sample_point(path, lon, lat):
    with rasterio.open(path) as source:
        value = next(source.sample([(lon, lat)]))[0]
        return float(value), str(source.crs), source.dtypes[0]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reported, profile = read_band(SOIL / "SoilLoss_annual.tif")
    support = np.isfinite(reported)
    scenarios = {
        "Linear cover, Arnoldus R": reported,
        "Exponential NDVI cover, Arnoldus R": read_band(SENS / "SoilLoss_annual_vander_knijff.tif")[0],
        "Linear cover, India-grid R": read_band(SENS / "SoilLoss_annual_IRED_R.tif")[0],
        "Exponential NDVI cover, India-grid R": read_band(SENS / "SoilLoss_annual_vdk_and_IRED.tif")[0],
    }

    window_rows = []
    for area_name, area in (("mask 715 km2", MASK_KM2), ("official catchment 984 km2", OFFICIAL_KM2)):
        for curve, (coefficient, exponent) in SDR_CURVES.items():
            ratio = sdr(area, coefficient, exponent)
            window_rows.append(
                {
                    "area": area_name,
                    "curve": curve,
                    "SDR": ratio,
                    "gross_at_1.0_t_m3": YIELD_LOW / ratio,
                    "gross_at_1.45_t_m3": YIELD_HIGH / ratio,
                }
            )
    window = pd.DataFrame(window_rows)
    window.to_csv(OUT / "delivery_ratio_window.csv", index=False)

    vanoni_official = float(window.loc[(window["curve"] == "Vanoni 1975") & window["area"].str.startswith("official"), "SDR"].iloc[0])
    gross_low = YIELD_LOW / vanoni_official
    gross_high = YIELD_HIGH / vanoni_official

    test_rows = []
    for name, values in scenarios.items():
        data = values[support & np.isfinite(values)]
        mean = float(data.mean())
        test_rows.append(
            {
                "case": name,
                "mean": mean,
                "above_yield_low": mean > YIELD_LOW,
                "above_yield_high": mean > YIELD_HIGH,
                "implied_SDR_at_1.0": YIELD_LOW / mean,
                "implied_SDR_at_1.45": YIELD_HIGH / mean,
                "inside_vanoni_window": gross_low <= mean <= gross_high,
                "below_vanoni_window": mean < gross_low,
                "above_vanoni_window": mean > gross_high,
            }
        )

    # Third cover: annual land-cover lookup, constant through the year.
    lulc, _lulc_profile = read_band(config.BASELINE / "Aligned_2.tif" / "LULC_aligned.tif")
    # The aligned land-cover grid contains fractional cells from resampling.
    # Nearest class recovers the categorical codes 0-4.
    lulc_class = np.rint(lulc)
    cover = np.full(reported.shape, np.nan)
    for code, value in CLASS_COVER.items():
        cover[np.isfinite(lulc) & np.isclose(lulc_class, code)] = value
    p_factor, _p_profile = read_band(ROOT / "output" / "rasters" / "Practice" / "P.tif")
    ls_factor, _ls_profile = read_band(ROOT / "output" / "rasters" / "LS" / "LS.tif")
    k_factor, _k_profile = read_band(config.K_FACTOR)

    # Rebuild effective linear C from the monthly stacks already used in script 22.
    from tilaiya.factors import arnoldus_monthly_erosivity, corrected_arnoldus_annual

    rainfall = {
        1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
        2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
        3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
        4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
        5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
    }
    study = {894.0: 1, 1225.0: 2, 786.0: 3, 1046.0: 4, 1292.0: 5}
    stored_annual, _profile = read_band(ROOT / "output" / "rasters" / "Erosivity" / "Erosivity_annual.tif")
    keys = np.array(sorted(study), dtype=float)
    finite = np.isfinite(stored_annual)
    cells = np.full(stored_annual.shape, -1, dtype=np.int16)
    flat = stored_annual[finite]
    chosen = keys[np.abs(flat[:, None] - keys[None, :]).argmin(axis=1)]
    nearest = np.full(stored_annual.shape, np.nan)
    nearest[finite] = chosen
    for value, cell in study.items():
        cells[np.isclose(nearest, value)] = cell
    monthly_r = {cell: arnoldus_monthly_erosivity(rain) for cell, rain in rainfall.items()}

    def band(month, index):
        values, _band_profile = read_band(STACK / f"Tilaiya_2025_{month:02d}.tif", band=index)
        values = values.astype(np.float64)
        values[values < -1] = np.nan
        return values

    cm_june = band(6, 9)
    cm_september = band(9, 9)
    ndvi_june = band(6, 2)
    ndvi_september = band(9, 2)
    annual_lookup = np.zeros(reported.shape, dtype=np.float64)
    valid = np.ones(reported.shape, dtype=bool)
    numer_lin = np.zeros(reported.shape)
    numer_exp = np.zeros(reported.shape)
    weight_r = np.zeros(reported.shape)
    for month in range(1, 13):
        soil, _month_profile = read_band(SOIL / f"SoilLoss_{month:02d}.tif")
        if month == 7:
            cm = (2.0 / 3.0) * cm_june + (1.0 / 3.0) * cm_september
            ndvi = (2.0 / 3.0) * ndvi_june + (1.0 / 3.0) * ndvi_september
        elif month == 8:
            cm = (1.0 / 3.0) * cm_june + (2.0 / 3.0) * cm_september
            ndvi = (1.0 / 3.0) * ndvi_june + (2.0 / 3.0) * ndvi_september
        else:
            cm = band(month, 9)
            ndvi = band(month, 2)
        c_exp = vander_knijff_cover(ndvi)
        rm = np.full(reported.shape, np.nan)
        for cell in range(1, 6):
            rm[cells == cell] = monthly_r[cell][month - 1]
        scaled = np.full(reported.shape, np.nan)
        ok = np.isfinite(soil) & np.isfinite(cm) & (cm > 0) & np.isfinite(cover)
        scaled[ok] = soil[ok] * (cover[ok] / cm[ok])
        dry = np.isfinite(soil) & np.isclose(soil, 0.0) & np.isfinite(cover)
        scaled[dry] = 0.0
        valid &= np.isfinite(scaled)
        annual_lookup += np.where(np.isfinite(scaled), scaled, 0.0)
        weighted = support & np.isfinite(rm) & np.isfinite(cm) & np.isfinite(c_exp)
        numer_lin[weighted] += rm[weighted] * cm[weighted]
        numer_exp[weighted] += rm[weighted] * c_exp[weighted]
        weight_r[weighted] += rm[weighted]
    annual_lookup = np.where(support & valid, annual_lookup, np.nan)
    write_band(SENS / "SoilLoss_annual_lulc_cover.tif", annual_lookup, profile)
    lookup_values = annual_lookup[support & np.isfinite(annual_lookup)]
    lookup_mean = float(lookup_values.mean()) if lookup_values.size else np.nan
    print("lookup n", int(lookup_values.size), "median", float(np.median(lookup_values)) if lookup_values.size else np.nan, "above100", float(np.mean(lookup_values > 100)) if lookup_values.size else np.nan)
    test_rows.append(
        {
            "case": "Land-cover lookup as cover, Arnoldus R",
            "mean": lookup_mean,
            "above_yield_low": lookup_mean > YIELD_LOW,
            "above_yield_high": lookup_mean > YIELD_HIGH,
            "implied_SDR_at_1.0": YIELD_LOW / lookup_mean if lookup_mean else np.nan,
            "implied_SDR_at_1.45": YIELD_HIGH / lookup_mean if lookup_mean else np.nan,
            "inside_vanoni_window": gross_low <= lookup_mean <= gross_high,
            "below_vanoni_window": lookup_mean < gross_low,
            "above_vanoni_window": lookup_mean > gross_high,
        }
    )
    pd.DataFrame(test_rows).to_csv(OUT / "scenario_versus_yield.csv", index=False)

    c_lin = np.where(weight_r > 0, numer_lin / weight_r, np.nan)
    c_exp = np.where(weight_r > 0, numer_exp / weight_r, np.nan)
    r_map = np.full(reported.shape, np.nan)
    annual_r = {cell: corrected_arnoldus_annual(rain) for cell, rain in rainfall.items()}
    for cell, value in annual_r.items():
        r_map[cells == cell] = value
    ratio_rows = [
        {"weight": "R only", "linear_over_exponential": weighted_ratio(r_map, c_lin, c_exp)},
        {"weight": "R times LS", "linear_over_exponential": weighted_ratio(r_map * ls_factor, c_lin, c_exp)},
        {"weight": "R times K times LS times P", "linear_over_exponential": weighted_ratio(r_map * k_factor * ls_factor * p_factor, c_lin, c_exp)},
        {"weight": "soil-loss mean ratio", "linear_over_exponential": float(np.nanmean(reported[support]) / np.nanmean(scenarios["Exponential NDVI cover, Arnoldus R"][support]))},
    ]
    pd.DataFrame(ratio_rows).to_csv(OUT / "cover_ratio_weights.csv", index=False)

    both = support & np.isfinite(lulc) & np.isfinite(p_factor)
    crosstab_rows = []
    for code, name in CLASS_NAME.items():
        group = both & np.isfinite(lulc_class) & np.isclose(lulc_class, code)
        count = int(group.sum())
        if count == 0:
            continue
        values, counts = np.unique(np.round(p_factor[group], 3), return_counts=True)
        for value, n_value in zip(values, counts):
            if n_value / count < 0.01:
                continue
            crosstab_rows.append(
                {
                    "class": name,
                    "class_code": code,
                    "lookup_C": CLASS_COVER[code],
                    "pixels": count,
                    "P": float(value),
                    "share_of_class": float(n_value / count),
                }
            )
    pd.DataFrame(crosstab_rows).to_csv(OUT / "p_versus_lulc.csv", index=False)
    class_rows = []
    for code, name in CLASS_NAME.items():
        group = support & np.isfinite(lulc_class) & np.isclose(lulc_class, code)
        class_rows.append(
            {
                "class": name,
                "pixels": int(group.sum()),
                "share": float(group.sum() / support.sum()),
                "lookup_C": CLASS_COVER[code],
                "mean_linear_C": float(np.nanmean(c_lin[group])) if group.any() else np.nan,
            }
        )
    pd.DataFrame(class_rows).to_csv(OUT / "lulc_cover_classes.csv", index=False)

    ired = next((ROOT / "data" / "erosivity").rglob("R-Factor_India.tif"))
    checks = []
    for label, lon, lat in (
        ("mask centroid approx", 85.37, 24.25),
        ("Cherrapunji", 91.70, 25.27),
        ("Hazaribagh", 85.36, 23.99),
    ):
        value, crs, dtype = sample_point(ired, lon, lat)
        checks.append({"place": label, "lon": lon, "lat": lat, "R": value, "crs": crs, "dtype": dtype})
    excel = next((ROOT / "data" / "erosivity").rglob("*.xlsx"))
    frames = xlsx_sheets(excel)
    hits = []
    for sheet, frame in frames.items():
        text = frame.astype(str)
        mask = text.apply(lambda column: column.str.contains("Jharkhand|Hazaribagh|Chatra|Koderma|East|Northeast|India", case=False, na=False)).any(axis=1)
        selected = frame.loc[mask].head(40)
        for _index, row in selected.iterrows():
            hits.append({"sheet": sheet, "row": " | ".join(str(item) for item in row.tolist() if str(item).strip())})
    pd.DataFrame(checks).to_csv(OUT / "ired_point_checks.csv", index=False)
    pd.DataFrame(hits).to_csv(OUT / "ired_table_hits.csv", index=False)
    print(window.to_string(index=False))
    print(pd.DataFrame(test_rows).to_string(index=False))
    print(pd.DataFrame(ratio_rows).to_string(index=False))
    print(pd.DataFrame(class_rows).to_string(index=False))
    print("lookup mean", lookup_mean)
    print(pd.DataFrame(checks).to_string(index=False))
    print("excel hits", len(hits))


if __name__ == "__main__":
    main()
