"""Static-K and continuous-DEM sensitivity for the 2025 RUSLE scenarios.

The reported Arnoldus soil-loss rasters are not replaced. Copernicus
GLO-30 is bilinearly placed on the 12.5 m grid. The LS equation is the
standard form, among those tried, that most closely follows the published
LS raster on the integer-metre DEM. Original ALOS tiles on this machine
are stored in whole metres, so they are not a second continuous surface.
"""

from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from tilaiya.rasters import align_to_reference, read_band, watershed_mask, write_band

HA = 12.5 * 12.5 / 10000.0
DENSITY = 1.45
CELL = 12.5
DEM_NODATA = 32767.0
DEST = ROOT / "output" / "rasters" / "sensitivity"
TABLES = ROOT / "output" / "tables"
ARNOLDUS = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus"
KM_DIR = ROOT / "output" / "rasters" / "Erodibility"
COPERNICUS = ROOT / "data" / "dem" / "Copernicus_GLO30_N24_E085.tif"
COPERNICUS_GRID = DEST / "Copernicus_GLO30_12m5.tif"
STACK = ROOT / "data" / "aligned"


def load_arnoldus():
    path = ROOT / "scripts" / "18_arnoldus_soil_loss.py"
    spec = importlib.util.spec_from_file_location("arnoldus_soil_loss", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean(values):
    out = np.asarray(values, dtype=np.float64)
    out[~np.isfinite(out)] = np.nan
    out[np.isclose(out, -9999.0)] = np.nan
    return out


def mass(values, sdr=None):
    data = values[np.isfinite(values)]
    gross_t = float(data.sum() * HA) if data.size else np.nan
    row = {
        "n": int(data.size),
        "mean_t_ha": float(data.mean()) if data.size else np.nan,
        "median_t_ha": float(np.median(data)) if data.size else np.nan,
        "gross_t": gross_t,
        "gross_m3": gross_t / DENSITY if data.size else np.nan,
    }
    if sdr is not None:
        both = np.isfinite(values) & np.isfinite(sdr)
        gross = float(np.sum(values[both]) * HA)
        delivered = float(np.sum(values[both] * sdr[both]) * HA)
        row["yield_t"] = delivered
        row["yield_m3"] = delivered / DENSITY if both.any() else np.nan
        row["mean_sdr"] = float(np.mean(sdr[both])) if both.any() else np.nan
    return row


def class_shares(values):
    data = values[np.isfinite(values)]
    breaks = [0, 5, 15, 30, 50, 100, np.inf]
    labels = ["0-5", "5-15", "15-30", "30-50", "50-100", ">100"]
    rows = []
    for label, low, high in zip(labels, breaks[:-1], breaks[1:]):
        count = int(np.sum((data > low) & (data <= high))) if label != "0-5" else int(np.sum(data <= 5))
        rows.append({"class": label, "pixels": count, "percent": 100.0 * count / data.size if data.size else np.nan})
    return rows


def d8_slope_and_receiver(dem):
    """Steepest-descent slope (rise/run) and flat receiver index, or -1."""
    z = np.where(np.isfinite(dem), dem.astype(np.float64), np.nan)
    height, width = z.shape
    padded = np.pad(z, 1, constant_values=np.nan)
    offsets = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    distances = CELL * np.array([np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)])
    slopes = np.empty((8, height, width), dtype=np.float32)
    for index, ((row_shift, col_shift), distance) in enumerate(zip(offsets, distances)):
        neighbour = padded[1 + row_shift : 1 + row_shift + height, 1 + col_shift : 1 + col_shift + width]
        drop = (z - neighbour) / distance
        slopes[index] = np.where(np.isfinite(drop) & (drop > 0), drop, 0.0).astype(np.float32)
    best = np.argmax(slopes, axis=0)
    max_slope = np.take_along_axis(slopes, best[np.newaxis], axis=0)[0]
    di = np.array([-1, -1, -1, 0, 0, 1, 1, 1], dtype=np.int32)
    dj = np.array([-1, 0, 1, -1, 1, -1, 0, 1], dtype=np.int32)
    rows = np.arange(height, dtype=np.int32)[:, None]
    cols = np.arange(width, dtype=np.int32)[None, :]
    receiver_row = rows + di[best]
    receiver_col = cols + dj[best]
    receiver = np.full(height * width, -1, dtype=np.int32)
    has_exit = max_slope.ravel() > 0
    receiver[has_exit] = (receiver_row * width + receiver_col).ravel()[has_exit]
    return max_slope.astype(np.float64), receiver


def horn_slope(dem):
    """Horn slope as rise/run. Invalid cells and flat cells are zero."""
    z = np.where(np.isfinite(dem), dem.astype(np.float64), np.nan)
    padded = np.pad(z, 1, constant_values=np.nan)
    a = padded[:-2, :-2]
    b = padded[:-2, 1:-1]
    c = padded[:-2, 2:]
    d = padded[1:-1, :-2]
    f = padded[1:-1, 2:]
    g = padded[2:, :-2]
    h = padded[2:, 1:-1]
    i = padded[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * CELL)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * CELL)
    slope = np.hypot(dzdx, dzdy)
    return np.where(np.isfinite(slope), slope, 0.0)


def accumulate(dem, receiver):
    height, width = dem.shape
    elev = np.where(np.isfinite(dem), dem.astype(np.float64), -1.0e30).ravel()
    order = np.argsort(elev, kind="mergesort")[::-1]
    acc = np.ones(height * width, dtype=np.float64)
    for index in order:
        if elev[index] < -1.0e29:
            break
        downstream = int(receiver[index])
        if downstream >= 0:
            acc[downstream] += acc[index]
    return acc.reshape(height, width)


def ls_candidates(acc, slope_tan):
    """Standard sheet-and-rill LS equations. Slope is rise/run."""
    angle = np.arctan(np.clip(slope_tan, 0, None))
    sin_b = np.sin(angle)
    percent = slope_tan * 100.0
    area = acc * CELL
    m_break = np.where(percent >= 5, 0.5, np.where(percent >= 3, 0.4, np.where(percent >= 1, 0.3, 0.2)))
    length = np.maximum(area, CELL)
    unit = np.ones(acc.shape, dtype=np.float64)
    out = {}

    def store(name, values):
        out[name] = np.where(slope_tan > 0, values, 0.0)

    store("Moore-Burch m0.4 n1.3", (area / 22.13) ** 0.4 * (sin_b / 0.0896) ** 1.3)
    store("Moore-Burch with m+1", 1.4 * (area / 22.13) ** 0.4 * (sin_b / 0.0896) ** 1.3)
    store("Moore-Burch m0.6 n1.3", (area / 22.13) ** 0.6 * (sin_b / 0.0896) ** 1.3)
    smith = 65.41 * sin_b**2 + 4.56 * sin_b + 0.065
    store("USLE length and Smith S", (length / 22.13) ** m_break * smith)
    mccool = np.where(percent < 9, 10.8 * sin_b + 0.03, 16.8 * sin_b - 0.50)
    mccool = np.clip(mccool, 0, None)
    store("USLE length and McCool S", (length / 22.13) ** m_break * mccool)
    store("McCool S only", mccool)
    store("Smith S only", smith)
    store("slope percent", percent)
    store("unit", unit)
    return out


def score_formulas(published, formulas):
    rows = []
    positive = np.isfinite(published) & (published > 0)
    for name, values in formulas.items():
        both = positive & np.isfinite(values) & (values > 0)
        if both.sum() < 1000:
            continue
        x = values[both]
        y = published[both]
        ratio = y / x
        corr = float(np.corrcoef(x, y)[0, 1])
        rows.append(
            {
                "formula": name,
                "n": int(both.sum()),
                "pearson": corr,
                "median_published_over_formula": float(np.median(ratio)),
                "p25_ratio": float(np.percentile(ratio, 25)),
                "p75_ratio": float(np.percentile(ratio, 75)),
            }
        )
    frame = pd.DataFrame(rows).dropna(subset=["pearson"]).sort_values("pearson", ascending=False)
    return frame


def summarise_pair(name, values):
    data = values[np.isfinite(values)]
    return {
        "surface": name,
        "n": int(data.size),
        "mean": float(data.mean()) if data.size else np.nan,
        "median": float(np.median(data)) if data.size else np.nan,
        "p95": float(np.percentile(data, 95)) if data.size else np.nan,
        "share_exactly_zero": float(np.mean(np.isclose(data, 0.0))) if data.size else np.nan,
    }


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    arnoldus = load_arnoldus()
    inside, profile, _watershed = watershed_mask(config.REFERENCE_DEM, config.WATERSHED)
    dem, _dem_profile = read_band(config.REFERENCE_DEM)
    dem = np.where(np.isclose(dem, DEM_NODATA), np.nan, dem)
    published_ls, _ls_profile = read_band(ROOT / "output" / "rasters" / "LS" / "LS.tif")
    published_ls = clean(published_ls)
    k_factor, _k_profile = read_band(config.K_FACTOR)
    k_factor = clean(k_factor)
    sdr, _sdr_profile = read_band(ROOT / "output" / "connectivity" / "SDR.tif")
    sdr = clean(sdr)
    annual_profile = read_band(ARNOLDUS / "SoilLoss_annual.tif")[1]

    print("static K")
    static_annual = np.zeros(dem.shape, dtype=np.float64)
    static_valid = np.ones(dem.shape, dtype=bool)
    primary_annual = np.zeros(dem.shape, dtype=np.float64)
    primary_valid = np.ones(dem.shape, dtype=bool)
    static_months = []
    for month in range(1, 13):
        primary = clean(read_band(ARNOLDUS / f"SoilLoss_{month:02d}.tif")[0])
        km = clean(read_band(KM_DIR / f"Km_{month:02d}.tif")[0])
        static = np.full(dem.shape, np.nan)
        ok = np.isfinite(primary) & np.isfinite(km) & np.isfinite(k_factor) & (km > 0)
        static[ok] = primary[ok] * (k_factor[ok] / km[ok])
        zero = ok & np.isclose(primary, 0.0)
        static[zero] = 0.0
        stats = mass(static)
        static_months.append({"month": month, "n": stats["n"], "mean_t_ha": stats["mean_t_ha"], "median_t_ha": stats["median_t_ha"]})
        static_valid &= np.isfinite(static)
        primary_valid &= np.isfinite(primary)
        static_annual += np.where(np.isfinite(static), static, 0.0)
        primary_annual += np.where(np.isfinite(primary), primary, 0.0)
        print(f"  month {month:02d} static mean {stats['mean_t_ha']:.3f}")
    static_annual = np.where(static_valid, static_annual, np.nan)
    primary_annual = np.where(primary_valid, primary_annual, np.nan)
    common = static_valid & primary_valid & inside
    static_on_common = np.where(common, static_annual, np.nan)
    primary_on_common = np.where(common, primary_annual, np.nan)
    static_summary = pd.DataFrame(
        [
            {"case": "reported Km, integer-metre LS", **mass(primary_on_common, sdr)},
            {"case": "static K, integer-metre LS", **mass(static_on_common, sdr)},
        ]
    )
    static_summary.to_csv(TABLES / "sensitivity_static_k.csv", index=False)
    pd.DataFrame(static_months).to_csv(TABLES / "sensitivity_static_k_monthly.csv", index=False)
    pd.DataFrame(class_shares(static_on_common)).to_csv(TABLES / "sensitivity_static_k_classes.csv", index=False)
    write_band(DEST / "SoilLoss_annual_staticK.tif", static_on_common, annual_profile)
    print(static_summary.to_string(index=False))

    print("missing pixels")
    ndvi = clean(read_band(STACK / "Tilaiya_2025_10.tif", band=2)[0])
    cover = clean(read_band(ROOT / "output" / "rasters" / "Cover" / "C_annual_baseline.tif")[0])
    included = inside & primary_valid
    excluded = inside & ~primary_valid
    slope_int, _receiver_unused = d8_slope_and_receiver(np.where(inside, dem, np.nan))
    missing_rows = []
    for label, mask in (("included in annual sum", included), ("excluded from annual sum", excluded)):
        missing_rows.append(
            {
                "group": label,
                "n": int(mask.sum()),
                "share_of_watershed": float(mask.sum() / inside.sum()),
                "elevation_mean_m": float(np.nanmean(dem[mask])),
                "elevation_median_m": float(np.nanmedian(dem[mask])),
                "share_d8_slope_zero": float(np.mean(np.isclose(slope_int[mask], 0.0))),
                "slope_median_percent": float(np.nanmedian(slope_int[mask] * 100.0)),
                "ndvi_october_median": float(np.nanmedian(ndvi[mask])),
                "annual_C_median": float(np.nanmedian(cover[mask])),
            }
        )
    missing = pd.DataFrame(missing_rows)
    missing.to_csv(TABLES / "missing_pixel_comparison.csv", index=False)
    print(missing.to_string(index=False))

    print("align Copernicus GLO-30")
    if not COPERNICUS_GRID.exists():
        align_to_reference(COPERNICUS, config.REFERENCE_DEM, COPERNICUS_GRID, resampling="bilinear")
    cop = clean(read_band(COPERNICUS_GRID)[0])
    cop_inside = inside & np.isfinite(cop)
    print("copernicus finite share of watershed", float(cop_inside.sum() / inside.sum()))

    print("flow accumulation on integer DEM")
    slope_dem, receiver_dem = d8_slope_and_receiver(np.where(np.isfinite(dem), dem, np.nan))
    acc_dem = accumulate(dem, receiver_dem)
    print("flow accumulation on Copernicus")
    slope_cop, receiver_cop = d8_slope_and_receiver(cop)
    acc_cop = accumulate(np.where(np.isfinite(cop), cop, np.nan), receiver_cop)

    horn_dem = horn_slope(dem)
    horn_cop = horn_slope(cop)
    fit_frames = []
    for slope_name, slope_values in (("D8", slope_dem), ("Horn", horn_dem)):
        formulas = ls_candidates(acc_dem, slope_values)
        scored = score_formulas(np.where(inside, published_ls, np.nan), formulas)
        scored.insert(0, "slope", slope_name)
        fit_frames.append(scored)
        print(scored.head(3).to_string(index=False))
    fit = pd.concat(fit_frames, ignore_index=True).sort_values("pearson", ascending=False)
    fit.to_csv(TABLES / "ls_formula_fit.csv", index=False)
    best = fit.iloc[0]
    formula_name = best["formula"]
    slope_name = best["slope"]
    scale = float(best["median_published_over_formula"])
    print("selected", slope_name, formula_name, "scale", scale, "pearson", float(best["pearson"]))

    slope_for = {"D8": (slope_dem, slope_cop), "Horn": (horn_dem, horn_cop)}
    formula_dem = ls_candidates(acc_dem, slope_for[slope_name][0])[formula_name] * scale
    formula_cop = ls_candidates(acc_cop, slope_for[slope_name][1])[formula_name] * scale
    formula_dem = np.where(inside & np.isfinite(dem), formula_dem, np.nan)
    formula_cop = np.where(cop_inside, formula_cop, np.nan)
    zero_published = inside & np.isfinite(published_ls) & np.isclose(published_ls, 0.0)
    zero_rows = [
        {"quantity": "published LS exactly 0", "value": float(zero_published.sum())},
        {"quantity": "share of those with Copernicus D8 slope above 0.5 degree", "value": float(np.mean(np.degrees(np.arctan(slope_cop[zero_published])) > 0.5))},
        {"quantity": "share of those with Copernicus D8 slope above 2 degrees", "value": float(np.mean(np.degrees(np.arctan(slope_cop[zero_published])) > 2))},
        {"quantity": "median Copernicus D8 slope percent on published LS zeros", "value": float(np.median(slope_cop[zero_published] * 100.0))},
        {"quantity": "share published LS zero and formula LS zero on integer DEM", "value": float(np.mean(np.isclose(formula_dem[zero_published], 0.0)))},
    ]
    pd.DataFrame(zero_rows).to_csv(TABLES / "sensitivity_dem_zero_ls.csv", index=False)
    pd.DataFrame(
        [
            summarise_pair("published LS", np.where(inside, published_ls, np.nan)),
            summarise_pair("scaled formula on integer DEM", formula_dem),
            summarise_pair("scaled formula on Copernicus", formula_cop),
        ]
    ).to_csv(TABLES / "sensitivity_ls_summary.csv", index=False)
    write_band(DEST / "LS_integer_formula.tif", formula_dem, annual_profile)
    write_band(DEST / "LS_copernicus.tif", formula_cop, annual_profile)

    print("rebuild annual soil loss with each LS")
    stored_annual = clean(read_band(ROOT / "output" / "rasters" / "Erosivity" / "Erosivity_annual.tif")[0])
    cells = arnoldus.cell_raster(stored_annual)
    monthly_r = {cell: arnoldus.arnoldus_monthly_erosivity(rain) for cell, rain in arnoldus.RAINFALL.items()}
    cm_june = arnoldus.cover(6)
    cm_sep = arnoldus.cover(9)
    interpolated = {7: (2.0 / 3.0) * cm_june + (1.0 / 3.0) * cm_sep, 8: (1.0 / 3.0) * cm_june + (2.0 / 3.0) * cm_sep}
    p_factor = clean(read_band(ROOT / "output" / "rasters" / "Practice" / "P.tif")[0])

    def annual_from_ls(ls):
        total = np.zeros(dem.shape, dtype=np.float64)
        valid = np.ones(dem.shape, dtype=bool)
        monthly = []
        for month in range(1, 13):
            km = clean(read_band(KM_DIR / f"Km_{month:02d}.tif")[0])
            cm = interpolated[month] if month in interpolated else arnoldus.cover(month)
            rm = np.full(dem.shape, np.nan)
            for cell in range(1, 6):
                rm[cells == cell] = monthly_r[cell][month - 1]
            soil = arnoldus.finite_clean(rm * km * ls * cm * p_factor)
            dry = (cells > 0) & np.isfinite(rm) & (rm == 0) & np.isfinite(km) & np.isfinite(ls) & np.isfinite(cm) & np.isfinite(p_factor)
            soil[dry] = 0.0
            stats = mass(np.where(common, soil, np.nan))
            monthly.append({"month": month, "mean_t_ha": stats["mean_t_ha"], "median_t_ha": stats["median_t_ha"], "n": stats["n"]})
            valid &= np.isfinite(soil)
            total += np.where(np.isfinite(soil), soil, 0.0)
        return np.where(valid, total, np.nan), monthly

    rebuilt_published, _months_published = annual_from_ls(published_ls)
    rebuilt_integer, months_integer = annual_from_ls(formula_dem)
    rebuilt_cop, months_cop = annual_from_ls(formula_cop)
    dem_rows = []
    for name, values in (
        ("reported product on common support", primary_on_common),
        ("rebuilt with published LS", np.where(common, rebuilt_published, np.nan)),
        ("scaled LS formula on integer DEM", np.where(common & np.isfinite(formula_dem), rebuilt_integer, np.nan)),
        ("scaled LS formula on Copernicus GLO-30", np.where(common & np.isfinite(formula_cop), rebuilt_cop, np.nan)),
    ):
        row = {"case": name, **mass(values, sdr)}
        dem_rows.append(row)
        print(name, row["n"], row["mean_t_ha"], row["median_t_ha"], row["gross_m3"], row["yield_m3"])
    dem_summary = pd.DataFrame(dem_rows)
    dem_summary.to_csv(TABLES / "sensitivity_dem_soil_loss.csv", index=False)
    pd.DataFrame(months_integer).assign(surface="integer DEM").to_csv(TABLES / "sensitivity_dem_monthly_integer.csv", index=False)
    pd.DataFrame(months_cop).assign(surface="Copernicus").to_csv(TABLES / "sensitivity_dem_monthly_copernicus.csv", index=False)
    pd.DataFrame(class_shares(np.where(common & np.isfinite(formula_cop), rebuilt_cop, np.nan))).to_csv(
        TABLES / "sensitivity_dem_classes_copernicus.csv", index=False
    )
    write_band(DEST / "SoilLoss_annual_copernicus_LS.tif", np.where(common & np.isfinite(formula_cop), rebuilt_cop, np.nan), annual_profile)
    print("selected formula recorded")
    (TABLES / "sensitivity_dem_formula.txt").write_text(
        f"slope={slope_name}\nformula={formula_name}\nscale={scale}\npearson={float(best['pearson'])}\n",
        encoding="utf-8",
    )


def write_support_map():
    """Map of pixels that enter the twelve-month sum."""
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    from tilaiya.maps import add_north_arrow, add_scalebar

    inside, _profile, _watershed = watershed_mask(config.REFERENCE_DEM, config.WATERSHED)
    annual = clean(read_band(ARNOLDUS / "SoilLoss_annual.tif")[0])
    included = inside & np.isfinite(annual)
    excluded = inside & ~included
    show = np.full(inside.shape, np.nan)
    show[included] = 0
    show[excluded] = 1
    write_band(DEST / "annual_support_mask.tif", np.where(inside, show, np.nan), read_band(ARNOLDUS / "SoilLoss_annual.tif")[1])
    with rasterio_open_extent() as extent:
        fig, ax = plt.subplots(figsize=(8.2, 7.2))
        ax.imshow(show, cmap=ListedColormap(["#1a9850", "#d73027"]), vmin=0, vmax=1, interpolation="nearest", extent=extent, origin="upper")
        add_scalebar(ax, extent)
        add_north_arrow(fig)
        ax.legend(handles=[Patch(facecolor="#1a9850", label="In the annual sum"), Patch(facecolor="#d73027", label="Excluded")], loc="upper left", frameon=True)
        ax.set_xlabel("Easting (m)")
        ax.set_ylabel("Northing (m)")
        ax.ticklabel_format(style="plain")
        fig.tight_layout()
        destination = ROOT / "output" / "figures" / "maps" / "annual_support_mask.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(destination, dpi=200)
        plt.close(fig)
        print(destination)


def rasterio_open_extent():
    import rasterio

    class _Extent:
        def __enter__(self):
            self.source = rasterio.open(config.REFERENCE_DEM)
            left, bottom, right, top = self.source.bounds
            return (left, right, bottom, top)

        def __exit__(self, *args):
            self.source.close()

    return _Extent()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--map":
        write_support_map()
    else:
        main()
        write_support_map()
