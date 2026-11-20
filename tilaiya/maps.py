"""Publication maps from the Tilaiya rasters.

The layout follows the pieces used in a GIS layout view: watershed
mask, shaded relief, colour layer, graticule, scale bar, grid north,
and a legend. Coordinates stay in WGS 84 / UTM zone 45N. Display uses
nearest-neighbour for classified and blocky layers so colours are not
smoothed across class or rainfall-cell edges.
"""

from pathlib import Path

import numpy as np
import rasterio
from matplotlib import colors
from matplotlib.patches import Patch
from rasterio.warp import transform as warp_transform

from tilaiya.constants import CELL_SIZE_M
from tilaiya.rasters import read_band

CLASS_BREAKS = (0, 5, 15, 30, 50, 100)
CLASS_LABELS = ("0–5", "5–15", "15–30", "30–50", "50–100", ">100")
CLASS_COLORS = ("#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027", "#67001f")
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def hillshade(elevation, cell_m=CELL_SIZE_M, azimuth=315.0, altitude=45.0):
    """Shaded relief. Invalid elevations stay NoData."""
    z = np.asarray(elevation, dtype=np.float64)
    invalid = ~np.isfinite(z)
    filled = np.where(invalid, 0.0, z)
    dz_east, dz_south = np.gradient(filled, cell_m, cell_m)
    slope = np.pi / 2.0 - np.arctan(np.hypot(dz_east, dz_south))
    aspect = np.arctan2(-dz_east, dz_south)
    azimuth_rad = np.deg2rad(360.0 - azimuth + 90.0)
    altitude_rad = np.deg2rad(altitude)
    shaded = np.sin(altitude_rad) * np.sin(slope) + np.cos(altitude_rad) * np.cos(slope) * np.cos(
        azimuth_rad - aspect
    )
    finite = np.isfinite(shaded) & ~invalid
    if finite.any():
        low = float(np.percentile(shaded[finite], 2))
        high = float(np.percentile(shaded[finite], 98))
        shaded = (shaded - low) / (high - low + 1e-9)
    shaded = np.clip(shaded, 0.0, 1.0)
    shaded[invalid] = np.nan
    return shaded.astype(np.float32)


def view_window(transform, shape, bounds, pad_m):
    """Pixel slice and map extent (west, east, south, north) around bounds."""
    height, width = shape
    west, south, east, north = bounds
    west -= pad_m
    south -= pad_m
    east += pad_m
    north += pad_m
    row_north, col_west = rasterio.transform.rowcol(transform, west, north)
    row_south, col_east = rasterio.transform.rowcol(transform, east, south)
    row0 = int(np.clip(min(row_north, row_south), 0, height - 1))
    row1 = int(np.clip(max(row_north, row_south), 0, height - 1))
    col0 = int(np.clip(min(col_west, col_east), 0, width - 1))
    col1 = int(np.clip(max(col_west, col_east), 0, width - 1))
    window = (slice(row0, row1 + 1), slice(col0, col1 + 1))
    left = transform.c + col0 * transform.a
    right = transform.c + (col1 + 1) * transform.a
    top = transform.f + row0 * transform.e
    bottom = transform.f + (row1 + 1) * transform.e
    return window, (left, right, bottom, top)


def load_layer(path, window):
    array, profile = read_band(path)
    return array[window].astype(np.float32), profile


def stretch_limits(array, low=2.0, high=98.0):
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return 0.0, 1.0
    vmin = float(np.percentile(finite, low))
    vmax = float(np.percentile(finite, high))
    if vmax <= vmin:
        vmax = vmin + 1.0
    return vmin, vmax


def nice_scale_m(width_m):
    """A round scale-bar length, about a fifth of the map width."""
    target = width_m * 0.22
    chosen = 1000.0
    for candidate in (1000, 2000, 5000, 10000, 20000):
        if candidate <= target:
            chosen = float(candidate)
    return chosen


def _lonlat_to_utm(lons, lats):
    xs, ys = warp_transform("EPSG:4326", "EPSG:32645", list(lons), list(lats))
    return np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def _utm_to_lonlat(xs, ys):
    lons, lats = warp_transform("EPSG:32645", "EPSG:4326", list(xs), list(ys))
    return np.asarray(lons, dtype=np.float64), np.asarray(lats, dtype=np.float64)


def add_graticule(ax, extent, step=0.1):
    """Dashed 0.1 degree graticule with labels on the frame."""
    west, east, south, north = extent
    corner_lon, corner_lat = _utm_to_lonlat(
        [west, east, west, east],
        [south, south, north, north],
    )
    lon0 = np.floor(corner_lon.min() / step) * step
    lat0 = np.floor(corner_lat.min() / step) * step
    lons = np.arange(lon0, corner_lon.max() + step * 0.5, step)
    lats = np.arange(lat0, corner_lat.max() + step * 0.5, step)
    lat_line = np.linspace(corner_lat.min() - 0.05, corner_lat.max() + 0.05, 40)
    lon_line = np.linspace(corner_lon.min() - 0.05, corner_lon.max() + 0.05, 40)
    style = dict(color="#4a4a4a", linewidth=0.35, linestyle=(0, (2, 2)), zorder=4)
    for lon in lons:
        xs, ys = _lonlat_to_utm(np.full(lat_line.shape, lon), lat_line)
        ax.plot(xs, ys, **style)
        _label_crossing(ax, xs, ys, north, "horizontal", f"{lon:.1f}°E", extent)
    for lat in lats:
        xs, ys = _lonlat_to_utm(lon_line, np.full(lon_line.shape, lat))
        ax.plot(xs, ys, **style)
        _label_crossing(ax, xs, ys, west, "vertical", f"{lat:.1f}°N", extent)


def _label_crossing(ax, xs, ys, edge, which, text, extent):
    west, east, south, north = extent
    series = ys if which == "horizontal" else xs
    for index in range(len(series) - 1):
        a = series[index]
        b = series[index + 1]
        if (a - edge) * (b - edge) > 0 or a == b:
            continue
        fraction = (edge - a) / (b - a)
        x = xs[index] + fraction * (xs[index + 1] - xs[index])
        y = ys[index] + fraction * (ys[index + 1] - ys[index])
        if which == "horizontal" and west < x < east:
            ax.text(
                x,
                y,
                text,
                ha="center",
                va="bottom",
                fontsize=7,
                color="#222222",
                clip_on=False,
                zorder=6,
            )
        if which == "vertical" and south < y < north:
            ax.text(
                x,
                y,
                text,
                ha="right",
                va="center",
                fontsize=7,
                color="#222222",
                clip_on=False,
                zorder=6,
            )
        break


def add_scalebar(ax, extent):
    west, east, south, north = extent
    length = nice_scale_m(east - west)
    x = west + 0.06 * (east - west)
    y = south + 0.06 * (north - south)
    tick = 0.012 * (north - south)
    ax.plot([x, x + length], [y, y], color="black", linewidth=2.4, solid_capstyle="butt", zorder=7)
    ax.plot([x, x], [y - tick, y + tick], color="black", linewidth=0.8, zorder=7)
    ax.plot([x + length, x + length], [y - tick, y + tick], color="black", linewidth=0.8, zorder=7)
    kilometres = length / 1000.0
    label = f"{kilometres:.0f} km" if kilometres >= 1 else f"{length:.0f} m"
    ax.text(x + length / 2.0, y + tick * 1.8, label, ha="center", va="bottom", fontsize=8, zorder=7)


def add_north_arrow(fig, x=0.84, y=0.78):
    """Grid north in the figure margin, clear of the watershed."""
    from matplotlib.patches import FancyArrowPatch

    arrow = FancyArrowPatch(
        (x, y),
        (x, y + 0.045),
        transform=fig.transFigure,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.15,
        color="black",
        clip_on=False,
    )
    fig.add_artist(arrow)
    fig.text(x, y + 0.05, "N", ha="center", va="bottom", fontsize=11, fontweight="bold", zorder=7)


def plot_boundary(ax, geometry):
    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    for polygon in polygons:
        x, y = polygon.exterior.xy
        ax.plot(x, y, color="black", linewidth=0.8, zorder=5)
        for ring in polygon.interiors:
            ax.plot(*ring.xy, color="black", linewidth=0.4, zorder=5)


def _colour_setup(style, array, vmin, vmax):
    if style == "classes":
        cmap = colors.ListedColormap(CLASS_COLORS)
        norm = colors.BoundaryNorm([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5], cmap.N)
        return cmap, norm, None
    if style == "class_breaks":
        cmap = colors.ListedColormap(CLASS_COLORS)
        norm = colors.BoundaryNorm([0, 5, 15, 30, 50, 100, 1.0e6], cmap.N)
        return cmap, norm, None
    if style == "unit":
        vmin, vmax = 0.0, 1.0
    elif style == "stretch":
        vmin, vmax = stretch_limits(array)
    elif vmin is None or vmax is None:
        finite = array[np.isfinite(array)]
        vmin = 0.0 if finite.size == 0 else float(np.nanmin(finite))
        vmax = 1.0 if finite.size == 0 else float(np.nanmax(finite))
        if vmax <= vmin:
            vmax = vmin + 1.0
    cmap = colors.LinearSegmentedColormap.from_list(
        "tilaiya",
        ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
        if style == "rain"
        else ["#fff7ec", "#fee8c8", "#fdd49e", "#fc8d59", "#d7301f", "#7f0000"],
    )
    if style not in ("rain", "warm", "stretch", "unit", "fixed"):
        cmap = colors.LinearSegmentedColormap.from_list(
            "tilaiya_warm",
            ["#fff7ec", "#fee8c8", "#fdd49e", "#fc8d59", "#d7301f", "#7f0000"],
        )
    return cmap, colors.Normalize(vmin=vmin, vmax=vmax), (vmin, vmax)


def draw_layer(ax, array, extent, style, interpolation, vmin=None, vmax=None, cmap_name=None):
    cmap, norm, limits = _colour_setup(style, array, vmin, vmax)
    if cmap_name:
        cmap = cmap_name
    shade = np.ma.masked_invalid(array)
    image = ax.imshow(
        shade,
        cmap=cmap,
        norm=norm,
        extent=extent,
        origin="upper",
        interpolation=interpolation,
        alpha=0.9,
        zorder=2,
    )
    return image, limits


def draw_hillshade(ax, shade, extent):
    ax.imshow(
        np.ma.masked_invalid(shade),
        cmap="gray",
        vmin=0.15,
        vmax=0.95,
        extent=extent,
        origin="upper",
        interpolation="bilinear",
        zorder=1,
    )


def finish_axes(ax, extent, geometry, graticule=True):
    west, east, south, north = extent
    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_aspect("equal")
    ax.set_facecolor("#f3f3f3")
    if graticule:
        add_graticule(ax, extent)
    plot_boundary(ax, geometry)
    add_scalebar(ax, extent)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("black")


def add_class_legend(fig, title):
    handles = [
        Patch(facecolor=color, edgecolor="#333333", linewidth=0.3, label=f"{label}  {unit}")
        for color, label, unit in zip(
            CLASS_COLORS,
            ("E1", "E2", "E3", "E4", "E5", "E6"),
            CLASS_LABELS,
        )
    ]
    legend = fig.legend(
        handles=handles,
        title=title,
        loc="center left",
        bbox_to_anchor=(0.76, 0.48),
        frameon=False,
        fontsize=8,
        title_fontsize=8,
        handlelength=1.4,
        handleheight=1.1,
        labelspacing=0.45,
    )
    legend.get_title().set_fontweight("bold")
    return legend


def save_map(
    destination,
    array,
    shade,
    extent,
    geometry,
    title,
    subtitle,
    style="warm",
    units="",
    interpolation="bilinear",
    vmin=None,
    vmax=None,
    dpi=300,
    graticule=True,
):
    """Write one map plate. Returns the colour limits actually used."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 9,
            "axes.unicode_minus": False,
            "savefig.facecolor": "white",
        }
    )
    fig = plt.figure(figsize=(8.4, 7.2), dpi=dpi)
    ax = fig.add_axes([0.12, 0.08, 0.62, 0.76])
    draw_hillshade(ax, shade, extent)
    image, limits = draw_layer(ax, array, extent, style, interpolation, vmin, vmax)
    finish_axes(ax, extent, geometry, graticule=graticule)
    add_north_arrow(fig, 0.84, 0.78)
    fig.text(0.12, 0.965, title, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.12, 0.925, subtitle, fontsize=8, ha="left", va="top", color="#333333")
    if style == "classes":
        add_class_legend(fig, units or "t/ha/yr")
    else:
        cax = fig.add_axes([0.78, 0.28, 0.028, 0.40])
        bar = fig.colorbar(image, cax=cax)
        bar.ax.tick_params(labelsize=7, width=0.4, length=2)
        bar.outline.set_linewidth(0.4)
        if units:
            bar.set_label(units, fontsize=8)
        if style == "stretch" and limits is not None:
            cax.set_title("2–98%", fontsize=7, pad=6)
    note = "WGS 84 / UTM zone 45N. Grid north. Shaded relief from the ALOS PALSAR DEM."
    fig.text(0.12, 0.028, note, fontsize=7, color="#444444", ha="left")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=dpi)
    plt.close(fig)
    return limits


def save_panels(
    destination,
    arrays,
    shade,
    extent,
    geometry,
    titles,
    figure_title,
    subtitle,
    style="warm",
    units="",
    interpolation="bilinear",
    vmin=None,
    vmax=None,
    dpi=300,
):
    """Twelve maps with one shared legend."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 8,
            "axes.unicode_minus": False,
            "savefig.facecolor": "white",
        }
    )
    stacked = np.concatenate([item[np.isfinite(item)] for item in arrays if np.isfinite(item).any()])
    cmap, norm, limits = _colour_setup(style, stacked, vmin, vmax)
    fig, axes = plt.subplots(3, 4, figsize=(11.2, 8.6), dpi=dpi)
    image = None
    for ax, array, panel_title in zip(axes.ravel(), arrays, titles):
        draw_hillshade(ax, shade, extent)
        image, _limits = draw_layer(
            ax,
            array,
            extent,
            style,
            interpolation,
            vmin=None if norm is None else norm.vmin,
            vmax=None if norm is None else norm.vmax,
        )
        # draw_layer rebuilds the norm. Re-draw with the shared norm.
        ax.images[-1].set_norm(norm)
        ax.images[-1].set_cmap(cmap)
        west, east, south, north = extent
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_aspect("equal")
        ax.set_facecolor("#f3f3f3")
        plot_boundary(ax, geometry)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(panel_title, fontsize=9, pad=2)
        for spine in ax.spines.values():
            spine.set_linewidth(0.4)
    add_scalebar(axes[2, 0], extent)
    add_north_arrow(fig, 0.955, 0.78)
    fig.subplots_adjust(left=0.04, right=0.90, top=0.88, bottom=0.08, wspace=0.04, hspace=0.16)
    fig.text(0.04, 0.96, figure_title, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.04, 0.925, subtitle, fontsize=8, ha="left", va="top", color="#333333")
    if style in ("classes", "class_breaks"):
        add_class_legend(fig, units or "t/ha")
        fig.legends[-1].set_bbox_to_anchor((0.91, 0.50))
    elif image is not None:
        cax = fig.add_axes([0.92, 0.28, 0.018, 0.46])
        bar = fig.colorbar(image, cax=cax)
        bar.ax.tick_params(labelsize=7, width=0.4, length=2)
        bar.outline.set_linewidth(0.4)
        if units:
            bar.set_label(units, fontsize=8)
    fig.text(
        0.04,
        0.025,
        "Shared legend. WGS 84 / UTM zone 45N. Grid north.",
        fontsize=7,
        color="#444444",
    )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=dpi)
    plt.close(fig)
    return limits
