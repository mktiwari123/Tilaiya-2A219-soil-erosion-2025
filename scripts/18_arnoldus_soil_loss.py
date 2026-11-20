"""Reported soil-loss maps using the corrected Arnoldus erosivity equation.

Annual R is the corrected Arnoldus (1977) equation stated by Chen et al.
(2023). Each month receives a share proportional to Pm^2, so the twelve
months sum to that annual total.

July and August cover in the primary maps is interpolated from the June
and September optical cover factors. Radar cover is written as a
sensitivity case. The stored SoilLoss and Erosivity rasters are not
replaced. Renard and Freimund (1994) is an annual comparison only.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tilaiya.factors import (  # noqa: E402
    arnoldus_monthly_erosivity,
    corrected_arnoldus_annual,
    renard_freimund_annual,
)
from tilaiya.rasters import read_band, write_band  # noqa: E402

OUT = ROOT / "output" / "tables"
SOIL = ROOT / "output" / "rasters" / "SoilLoss"
EROSIVITY = ROOT / "output" / "rasters" / "Erosivity"
STACK = ROOT / "data" / "aligned"
DEST = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
FIG = ROOT / "output" / "figures" / "maps"
SDR_PATH = ROOT / "output" / "connectivity" / "SDR.tif"
HA = 12.5 * 12.5 / 10000.0
DENSITY = 1.45

# Study annual sums used only to identify which IMD cell a pixel belongs to.
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
LONLAT = {
    1: (85.25, 24.00),
    2: (85.50, 24.00),
    3: (85.25, 24.25),
    4: (85.50, 24.25),
    5: (85.25, 24.50),
}


def finite_clean(values):
    out = values.astype(np.float64, copy=True)
    out[out < 0] = np.nan
    return out


def summarise(values):
    data = values[np.isfinite(values)]
    if data.size == 0:
        return {"n": 0, "mean": np.nan, "median": np.nan, "p95": np.nan}
    return {
        "n": int(data.size),
        "mean": float(data.mean()),
        "median": float(np.median(data)),
        "p95": float(np.percentile(data, 95)),
    }


def class_code(annual):
    classes = np.zeros(annual.shape, dtype=np.uint8)
    valid = np.isfinite(annual)
    classes[valid & (annual <= 5)] = 1
    classes[valid & (annual > 5) & (annual <= 15)] = 2
    classes[valid & (annual > 15) & (annual <= 30)] = 3
    classes[valid & (annual > 30) & (annual <= 50)] = 4
    classes[valid & (annual > 50) & (annual <= 100)] = 5
    classes[valid & (annual > 100)] = 6
    return classes


def cell_raster(annual_r):
    keys = np.array(sorted(STUDY), dtype=float)
    nearest = np.full(annual_r.shape, np.nan)
    finite = np.isfinite(annual_r)
    flat = annual_r[finite]
    index = np.abs(flat[:, None] - keys[None, :]).argmin(axis=1)
    chosen = keys[index]
    nearest[finite] = chosen
    far = int(np.sum(np.abs(flat - chosen) > 5))
    print("erosivity cells unmatched", far, "of", int(finite.sum()))
    cells = np.full(annual_r.shape, -1, dtype=np.int16)
    for value, cell in STUDY.items():
        cells[np.isclose(nearest, value)] = cell
    return cells


def cover(month):
    values, _profile = read_band(STACK / f"Tilaiya_2025_{month:02d}.tif", band=9)
    return finite_clean(values)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)

    monthly_r = {cell: arnoldus_monthly_erosivity(rain) for cell, rain in RAINFALL.items()}
    annual_r = {cell: corrected_arnoldus_annual(rain) for cell, rain in RAINFALL.items()}
    freimund = {cell: renard_freimund_annual(rain) for cell, rain in RAINFALL.items()}

    stored_annual, profile = read_band(EROSIVITY / "Erosivity_annual.tif")
    cells = cell_raster(stored_annual)
    known = cells > 0

    ratio_to_freimund = np.ones(cells.shape, dtype=np.float64)
    for cell in range(1, 6):
        ratio_to_freimund[cells == cell] = freimund[cell] / annual_r[cell]

    cm_june = cover(6)
    cm_sep = cover(9)
    cm_july = (2.0 / 3.0) * cm_june + (1.0 / 3.0) * cm_sep
    cm_august = (1.0 / 3.0) * cm_june + (2.0 / 3.0) * cm_sep
    interpolated = {7: cm_july, 8: cm_august}

    ls, _ls_profile = read_band(ROOT / "output" / "rasters" / "LS" / "LS.tif")
    sdr, _sdr_profile = read_band(SDR_PATH)

    primary_annual = np.zeros(cells.shape, dtype=np.float64)
    radar_annual = np.zeros(cells.shape, dtype=np.float64)
    primary_valid = np.ones(cells.shape, dtype=bool)
    radar_valid = np.ones(cells.shape, dtype=bool)
    month_rows = []
    kept = {}

    for month in range(1, 13):
        soil, _profile = read_band(SOIL / f"SoilLoss_{month:02d}.tif")
        soil = finite_clean(soil)
        old_r, _r_profile = read_band(EROSIVITY / f"Erosivity_{month:02d}.tif")
        new_r = np.full(cells.shape, np.nan)
        for cell in range(1, 6):
            new_r[cells == cell] = monthly_r[cell][month - 1]

        scale = np.ones(cells.shape, dtype=np.float64)
        can_scale = known & np.isfinite(old_r) & (old_r > 0) & np.isfinite(new_r)
        scale[can_scale] = new_r[can_scale] / old_r[can_scale]
        radar = soil * scale
        radar[~known] = np.nan
        dry = known & np.isfinite(new_r) & (new_r == 0)
        radar[dry] = 0.0

        primary = radar.copy()
        cm_used = cover(month) if month not in interpolated else interpolated[month]
        if month in interpolated:
            old_cm = cover(month)
            ok = np.isfinite(primary) & np.isfinite(cm_used) & np.isfinite(old_cm) & (old_cm > 0)
            primary[ok] = radar[ok] * (cm_used[ok] / old_cm[ok])
            primary[~ok] = np.nan

        write_band(DEST / f"SoilLoss_{month:02d}.tif", primary, profile)
        primary_valid &= np.isfinite(primary)
        radar_valid &= np.isfinite(radar)
        primary_annual += np.where(np.isfinite(primary), primary, 0.0)
        radar_annual += np.where(np.isfinite(radar), radar, 0.0)

        month_stats = summarise(primary)
        cm_on = cm_used[np.isfinite(primary)]
        r_on = new_r[np.isfinite(primary)]
        month_rows.append(
            {
                "month": month,
                "n": month_stats["n"],
                "mean_A": month_stats["mean"],
                "median_A": month_stats["median"],
                "p95_A": month_stats["p95"],
                "mean_Cm": float(np.mean(cm_on)) if cm_on.size else np.nan,
                "median_Cm": float(np.median(cm_on)) if cm_on.size else np.nan,
                "share_Cm_floor": float(np.mean(np.isclose(cm_on, 0.001, atol=1e-6))) if cm_on.size else np.nan,
                "share_Cm_below_0.15": float(np.mean(cm_on < 0.15)) if cm_on.size else np.nan,
                "mean_Rm": float(np.mean(r_on)) if r_on.size else np.nan,
                "max_R_scale": float(np.nanmax(scale[can_scale])) if can_scale.any() else np.nan,
            }
        )
        if month in (6, 7):
            kept[month] = (primary, cm_used)
        print(
            f"month {month:02d} mean {month_stats['mean']:.4f} "
            f"median {month_stats['median']:.4f} Rm {month_rows[-1]['mean_Rm']:.2f}"
        )

    primary_annual = np.where(primary_valid, primary_annual, np.nan)
    radar_annual = np.where(radar_valid, radar_annual, np.nan)
    freimund_annual = np.where(primary_valid, primary_annual * ratio_to_freimund, np.nan)
    write_band(DEST / "SoilLoss_annual.tif", primary_annual, profile)
    classes = class_code(primary_annual).astype(np.float32)
    classes[~np.isfinite(primary_annual)] = np.nan
    write_band(DEST / "SoilLoss_annual_class.tif", classes, profile)

    def mass(values):
        data = values[np.isfinite(values)]
        gross_t = float(data.sum() * HA)
        return {
            "n": int(data.size),
            "mean_t_ha": float(data.mean()) if data.size else np.nan,
            "median_t_ha": float(np.median(data)) if data.size else np.nan,
            "gross_t": gross_t,
            "gross_m3": gross_t / DENSITY,
        }

    annual_rows = []
    for name, values in (
        ("interpolated optical, Arnoldus", primary_annual),
        ("radar cover, Arnoldus", radar_annual),
        ("interpolated optical, Renard-Freimund", freimund_annual),
    ):
        row = mass(values)
        row["case"] = name
        both = np.isfinite(values) & np.isfinite(sdr)
        gross = float(np.sum(values[both]) * HA)
        delivered = float(np.sum(values[both] * sdr[both]) * HA)
        row["sdr_pixels"] = int(both.sum())
        row["gross_t_on_sdr"] = gross
        row["yield_t"] = delivered
        row["yield_m3"] = delivered / DENSITY
        row["delivery_fraction"] = delivered / gross if gross else np.nan
        row["mean_sdr"] = float(np.mean(sdr[both])) if both.any() else np.nan
        annual_rows.append(row)
        print(name, {key: row[key] for key in ("n", "mean_t_ha", "gross_m3", "yield_t", "yield_m3")})

    class_names = {1: "0-5", 2: "5-15", 3: "15-30", 4: "30-50", 5: "50-100", 6: ">100"}
    valid_class = classes[np.isfinite(primary_annual)].astype(int)
    class_rows = []
    for code, label in class_names.items():
        count = int(np.sum(valid_class == code))
        class_rows.append(
            {
                "class": label,
                "pixels": count,
                "percent": 100.0 * count / valid_class.size,
            }
        )

    a6, cm6 = kept[6]
    a7, cm7 = kept[7]
    shared = np.isfinite(a6) & np.isfinite(a7) & np.isfinite(ls) & np.isfinite(cm7)
    n_shared = int(shared.sum())
    zero_ls = shared & np.isclose(ls, 0.0, atol=1e-8)
    compare = pd.DataFrame(
        [
            {"quantity": "shared pixels", "value": n_shared},
            {"quantity": "share June A < 0.01", "value": float(np.mean(a6[shared] < 0.01))},
            {"quantity": "share July A < 0.01", "value": float(np.mean(a7[shared] < 0.01))},
            {"quantity": "share LS exactly 0", "value": float(np.mean(zero_ls[shared]))},
            {"quantity": "June median", "value": float(np.median(a6[shared]))},
            {"quantity": "July median", "value": float(np.median(a7[shared]))},
            {"quantity": "June mean", "value": float(np.mean(a6[shared]))},
            {"quantity": "July mean", "value": float(np.mean(a7[shared]))},
        ]
    )

    bins = [
        ("0.001", np.isclose(cm7, 0.001, atol=1e-6)),
        ("0.001 to 0.05", (cm7 > 0.001) & (cm7 <= 0.05)),
        ("0.05 to 0.15", (cm7 > 0.05) & (cm7 <= 0.15)),
        ("0.15 to 0.40", (cm7 > 0.15) & (cm7 <= 0.40)),
        ("above 0.40", cm7 > 0.40),
    ]
    bin_rows = []
    for label, mask in bins:
        group = shared & mask
        count = int(group.sum())
        if count == 0:
            bin_rows.append(
                {
                    "july_cover": label,
                    "n": 0,
                    "share": 0.0,
                    "share_below_0.01": np.nan,
                    "median_july": np.nan,
                    "median_june": np.nan,
                    "median_LS": np.nan,
                }
            )
            continue
        bin_rows.append(
            {
                "july_cover": label,
                "n": count,
                "share": count / n_shared,
                "share_below_0.01": float(np.mean(a7[group] < 0.01)),
                "median_july": float(np.median(a7[group])),
                "median_june": float(np.median(a6[group])),
                "median_LS": float(np.median(ls[group])),
            }
        )

    cell_rows = []
    for cell, rain in RAINFALL.items():
        rain = np.asarray(rain, dtype=float)
        count = int(np.sum(cells == cell))
        peak = int(np.argmax(monthly_r[cell]) + 1)
        lon, lat = LONLAT[cell]
        cell_rows.append(
            {
                "cell": cell,
                "longitude": lon,
                "latitude": lat,
                "pixels": count,
                "annual_rainfall_mm": float(rain.sum()),
                "arnoldus_annual_R": annual_r[cell],
                "renard_freimund_annual_R": freimund[cell],
                "june_Rm": float(monthly_r[cell][5]),
                "july_Rm": float(monthly_r[cell][6]),
                "peak_month": peak,
                "july_share": float(monthly_r[cell][6] / annual_r[cell]),
            }
        )

    pd.DataFrame(month_rows).to_csv(OUT / "arnoldus_monthly_soil_loss.csv", index=False)
    pd.DataFrame(annual_rows).to_csv(OUT / "arnoldus_annual_summary.csv", index=False)
    pd.DataFrame(class_rows).to_csv(OUT / "arnoldus_annual_classes.csv", index=False)
    compare.to_csv(OUT / "arnoldus_june_july.csv", index=False)
    pd.DataFrame(bin_rows).to_csv(OUT / "arnoldus_july_cover_bins.csv", index=False)
    pd.DataFrame(cell_rows).to_csv(OUT / "arnoldus_cell_erosivity.csv", index=False)
    print(compare.to_string(index=False))
    print(pd.DataFrame(bin_rows).to_string(index=False))
    print(pd.DataFrame(cell_rows).to_string(index=False))
    print(pd.DataFrame(class_rows).to_string(index=False))

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "presentation_maps", ROOT / "scripts" / "09_presentation_maps.py"
    )
    maps = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maps)
    view = maps.prepare_view()
    note = (
        "Corrected Arnoldus erosivity. July and August cover is interpolated "
        "from June and September. Grey inside the boundary is NoData."
    )
    maps.draw_one(
        DEST / "SoilLoss_annual_class.tif",
        FIG / "SoilLoss_Arnoldus_annual_class_2025.png",
        view,
        "Annual soil loss, 2025",
        "Soil loss (t/ha/yr)",
        "classes",
        interpolation="nearest",
        note=note,
    )
    maps.draw_year(
        [DEST / f"SoilLoss_{month:02d}.tif" for month in range(1, 13)],
        FIG / "SoilLoss_Arnoldus_monthly_2025.png",
        view,
        "Monthly soil loss, 2025",
        "t/ha/month",
        "warm",
        note=(
            "Corrected Arnoldus erosivity. July and August cover is interpolated "
            "from June and September. Colour scale is 0 to the 98th percentile."
        ),
    )


if __name__ == "__main__":
    main()
