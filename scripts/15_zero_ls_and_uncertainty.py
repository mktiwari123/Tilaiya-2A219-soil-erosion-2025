"""June near-zero share, zero LS, the high-cover class, and the uncertainty envelope.

Official soil-loss rasters are not replaced.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config

OUT = ROOT / "output" / "tables"
STACK = ROOT / "data" / "aligned"
SOIL = ROOT / "output" / "rasters" / "SoilLoss"
EROSIVITY = ROOT / "output" / "rasters" / "Erosivity"
NODATA = -9999.0
HA = 12.5 * 12.5 / 10000.0
DENSITY = 1.45

# Study annual sums used to label the five IMD cells, then published scales.
STUDY = {
    894.0: 1,
    1225.0: 2,
    786.0: 3,
    1046.0: 4,
    1292.0: 5,
}
RAINFALL = {
    1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
    2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
    3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
    4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
    5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
}


def read_raster(path, band=1):
    with rasterio.open(path) as src:
        values = src.read(band).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        values[np.isclose(values, nodata)] = np.nan
    values[np.isclose(values, NODATA)] = np.nan
    return values


def soil(month):
    values = read_raster(SOIL / f"SoilLoss_{month:02d}.tif")
    values[values < 0] = np.nan
    return values


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = Path(__file__).with_name("10_assumption_checks.py")
    # Import the published-equation helpers without running that script's main.
    import importlib.util

    spec = importlib.util.spec_from_file_location("assumption_checks", checks)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)

    ls = read_raster(config.LS_FACTOR)
    p = read_raster(config.P_FACTOR)
    a6 = soil(6)
    a7 = soil(7)
    cm7 = read_raster(STACK / "Tilaiya_2025_07.tif", band=9)
    mndwi = read_raster(STACK / "Tilaiya_2025_07.tif", band=4)
    shared = np.isfinite(a6) & np.isfinite(a7) & np.isfinite(ls)
    n = int(shared.sum())
    low_june = shared & (a6 < 0.01)
    low_july = shared & (a7 < 0.01)
    zero_ls = shared & np.isclose(ls, 0.0, atol=1e-8)
    summary = pd.DataFrame(
        [
            {"quantity": "shared pixels", "value": n},
            {"quantity": "share June A < 0.01", "value": float(low_june.sum() / n)},
            {"quantity": "share July A < 0.01", "value": float(low_july.sum() / n)},
            {"quantity": "share LS exactly 0", "value": float(zero_ls.sum() / n)},
            {"quantity": "share LS < 0.001", "value": float((shared & (ls < 0.001)).sum() / n)},
            {"quantity": "June median", "value": float(np.median(a6[shared]))},
            {"quantity": "July median", "value": float(np.median(a7[shared]))},
        ]
    )
    summary.to_csv(OUT / "june_july_near_zero_and_ls.csv", index=False)
    print(summary.to_string(index=False))

    high = shared & np.isfinite(cm7) & (cm7 > 0.40)
    nh = int(high.sum())
    zero_a = high & np.isclose(a7, 0.0, atol=1e-12)
    detail = {
        "n": nh,
        "share_of_shared": nh / n,
        "fraction_July_A_exactly_0": float(np.mean(np.isclose(a7[high], 0.0, atol=1e-12))),
        "fraction_June_A_exactly_0": float(np.mean(np.isclose(a6[high], 0.0, atol=1e-12))),
        "fraction_LS_exactly_0": float(np.mean(np.isclose(ls[high], 0.0, atol=1e-8))),
        "fraction_P_exactly_0": float(np.mean(np.isclose(p[high], 0.0, atol=1e-8))) if np.isfinite(p[high]).any() else np.nan,
        "median_LS": float(np.median(ls[high])),
        "median_P": float(np.nanmedian(p[high])),
        "median_MNDWI": float(np.nanmedian(mndwi[high])),
        "median_MNDWI_where_July_A_is_0": float(np.nanmedian(mndwi[zero_a])) if zero_a.any() else np.nan,
        "fraction_of_zero_A_with_LS_0": float(np.mean(np.isclose(ls[zero_a], 0.0, atol=1e-8))) if zero_a.any() else np.nan,
        "fraction_of_zero_A_with_P_0": float(np.mean(np.isclose(p[zero_a], 0.0, atol=1e-8))) if zero_a.any() else np.nan,
        "median_LS_where_July_A_positive": float(np.median(ls[high & (a7 > 0)])),
    }
    pd.DataFrame([detail]).to_csv(OUT / "july_high_cover_class.csv", index=False)
    print(pd.DataFrame([detail]).T.to_string(header=False))

    ratios = {}
    for value, cell in STUDY.items():
        _annual, mfi, arnoldus = helpers.arnoldus_annual(RAINFALL[cell])
        freimund = helpers.renard_freimund_annual(mfi)
        ratios[value] = {
            "study": 1.0,
            "arnoldus": arnoldus / value,
            "renard_freimund": freimund / value,
        }
    annual_r = read_raster(EROSIVITY / "Erosivity_annual.tif")
    nearest = np.full(annual_r.shape, np.nan)
    keys = np.array(list(STUDY), dtype=float)
    finite_r = np.isfinite(annual_r)
    if finite_r.any():
        flat = annual_r[finite_r]
        index = np.abs(flat[:, None] - keys[None, :]).argmin(axis=1)
        nearest_flat = keys[index]
        nearest[finite_r] = nearest_flat
        far = np.abs(flat - nearest_flat) > 5
        print("erosivity cells unmatched", int(far.sum()), "of", int(finite_r.sum()))

    months = {month: soil(month) for month in range(1, 13)}
    valid = np.ones(a7.shape, dtype=bool)
    for values in months.values():
        valid &= np.isfinite(values)
    official = np.zeros(a7.shape, dtype=np.float64)
    for values in months.values():
        official += np.where(valid, values, 0.0)

    def rescale(month, new_cm):
        old = read_raster(STACK / f"Tilaiya_2025_{month:02d}.tif", band=9)
        out = months[month].copy()
        ok = valid & np.isfinite(new_cm) & np.isfinite(old) & (old > 0)
        out[ok] = months[month][ok] * (new_cm[ok] / old[ok])
        return out

    cm_june = read_raster(STACK / "Tilaiya_2025_06.tif", band=9)
    cm_sep = read_raster(STACK / "Tilaiya_2025_09.tif", band=9)
    gap = official.copy()
    line = official.copy()
    intercept, slope = 0.23487652445509008, 0.09754669155761421
    for month, weight_june in ((7, 2 / 3), (8, 1 / 3)):
        gap_cm = weight_june * cm_june + (1 - weight_june) * cm_sep
        rvi = read_raster(STACK / f"Tilaiya_2025_{month:02d}.tif", band=8)
        savi_hat = np.clip(intercept + slope * rvi, 0, 1)
        cm_line = np.clip(1 - 1.18 * savi_hat, 0.001, 1)
        cm_line[~np.isfinite(rvi)] = np.nan
        gap += rescale(month, gap_cm) - months[month]
        line += rescale(month, cm_line) - months[month]
    official = np.where(valid, official, np.nan)
    gap = np.where(valid, gap, np.nan)
    line = np.where(valid, line, np.nan)

    rows = []
    cell_ok = valid & np.isfinite(nearest)
    for name, annual in (
        ("interpolated optical cover", gap),
        ("radar cover", official),
        ("fitted SAVI-on-RVI line", line),
    ):
        for scale in ("study", "arnoldus", "renard_freimund"):
            factor = np.ones(annual.shape, dtype=np.float64)
            for value, cell_ratios in ratios.items():
                factor[np.isclose(nearest, value)] = cell_ratios[scale]
            scaled = np.where(cell_ok, annual * factor, np.nan)
            data = scaled[np.isfinite(scaled)]
            gross_t = float(data.sum() * HA)
            rows.append(
                {
                    "cover": name,
                    "erosivity": scale,
                    "n": int(data.size),
                    "mean_t_ha": float(data.mean()),
                    "gross_t": gross_t,
                    "gross_m3_at_1.45": gross_t / DENSITY,
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "cover_by_erosivity_envelope.csv", index=False)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
