"""Write the Tilaiya study mask and a HydroBASINS catchment to the dam.

The study polygon is the existing 715 km² mask (sub-watershed 2A219).
The dam catchment is the HydroBASINS v1c level-12 tree that drains to the
unit containing Tilaiya Dam. It is not a Damodar Valley Corporation survey
boundary. DVC publishes 984 km² and does not supply a polygon in this project.

This step has been run by executing this script. It does not replace any
soil-loss or connectivity raster.
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shapefile
from matplotlib.colors import to_rgba
from matplotlib.patches import Polygon as MplPolygon
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import orient, transform as transform_geom, unary_union

from tilaiya.maps import add_north_arrow, add_scalebar

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent
STUDY_SRC = PARENT / "watershed_edited.shp"
HYBAS = PARENT.parent / "hybas_lake_as_lev01-12_v1c" / "hybas_lake_as_lev12_v1c.shp"
OUT_DIR = ROOT / "output" / "shapefiles"
FIG = ROOT / "output" / "figures" / "maps" / "Tilaiya_watershed_boundaries.png"
STUDY_FIG = ROOT / "output" / "figures" / "maps" / "Tilaiya_2A219_study_area.png"
TABLE = ROOT / "output" / "tables" / "tilaiya_watershed_boundaries.csv"
PRJ = STUDY_SRC.with_suffix(".prj").read_text(encoding="utf-8")

# Tilaiya Dam, from the published site coordinates 24°19'26" N, 85°31'16" E.
DAM_LON = 85 + 31 / 60 + 16 / 3600
DAM_LAT = 24 + 19 / 60 + 26 / 3600
# HydroBASINS unit whose box contains the dam and whose downstream neighbour
# is the first river reach below the reservoir.
OUTLET_ID = 4120944082

TO_UTM = Transformer.from_crs(4326, 32645, always_xy=True)


def utm(geom):
    return transform_geom(lambda x, y: TO_UTM.transform(x, y), geom)


def clockwise(geom):
    if geom.geom_type == "Polygon":
        return orient(geom, sign=-1.0)
    return unary_union([orient(part, sign=-1.0) for part in geom.geoms])


def rings(geom):
    geom = clockwise(geom)
    parts = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    output = []
    for part in parts:
        output.append(list(part.exterior.coords))
        output.extend(list(ring.coords) for ring in part.interiors)
    return output


def write_polygon(path, geom, fields, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = shapefile.Writer(str(path), shapeType=shapefile.POLYGON)
    for name, kind, size, decimal in fields:
        writer.field(name, kind, size, decimal)
    writer.poly(rings(geom))
    writer.record(*values)
    writer.close()
    path.with_suffix(".prj").write_text(PRJ, encoding="utf-8")
    path.with_suffix(".cpg").write_text("UTF-8", encoding="utf-8")


def load_study():
    reader = shapefile.Reader(str(STUDY_SRC))
    geom = unary_union([shape(s.__geo_interface__) for s in reader.shapes()])
    area = geom.area / 1e6
    return geom, area


def load_dam_catchment():
    reader = shapefile.Reader(str(HYBAS))
    children = defaultdict(list)
    sub_area = {}
    up_area = {}
    for record in reader.iterRecords():
        values = record.as_dict()
        hybas_id = int(values["HYBAS_ID"])
        children[int(values["NEXT_DOWN"])].append(hybas_id)
        sub_area[hybas_id] = float(values["SUB_AREA"])
        up_area[hybas_id] = float(values["UP_AREA"])
    selected = []
    stack = [OUTLET_ID]
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        selected.append(current)
        stack.extend(children.get(current, []))
    reader = shapefile.Reader(str(HYBAS))
    geoms = []
    dam = Point(DAM_LON, DAM_LAT)
    contains_dam = False
    for item in reader.iterShapeRecords():
        values = item.record.as_dict()
        if int(values["HYBAS_ID"]) not in seen:
            continue
        geom = shape(item.shape.__geo_interface__)
        geoms.append(geom)
        if geom.contains(dam) or geom.covers(dam):
            contains_dam = True
    dissolved = utm(unary_union(geoms))
    return dissolved, sum(sub_area[i] for i in seen), up_area[OUTLET_ID], len(seen), contains_dam


def add_poly(ax, geom, face, edge, width, label, alpha=1.0, zorder=2):
    parts = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    first = True
    for part in parts:
        patch = MplPolygon(
            list(part.exterior.coords),
            closed=True,
            facecolor=to_rgba(face, alpha),
            edgecolor=edge,
            linewidth=width,
            label=label if first else None,
            zorder=zorder,
        )
        ax.add_patch(patch)
        first = False
        for ring in part.interiors:
            ax.add_patch(
                MplPolygon(
                    list(ring.coords),
                    closed=True,
                    facecolor="white",
                    edgecolor=edge,
                    linewidth=width * 0.6,
                    zorder=3,
                )
            )


def draw_study(study, study_km2):
    """Map only sub-watershed 2A219, the adopted analysis boundary."""
    STUDY_FIG.parent.mkdir(parents=True, exist_ok=True)
    bounds = study.bounds
    pad_x = 0.04 * (bounds[2] - bounds[0])
    pad_y = 0.04 * (bounds[3] - bounds[1])
    extent = (bounds[0] - pad_x, bounds[2] + pad_x, bounds[1] - pad_y, bounds[3] + pad_y)
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 9,
            "axes.unicode_minus": False,
            "savefig.facecolor": "white",
        }
    )
    fig, ax = plt.subplots(figsize=(8.2, 8.4))
    add_poly(
        ax,
        study,
        "#c47b2b",
        "#8c4a22",
        1.45,
        f"Sub-watershed 2A219, {study_km2:.2f} km²",
        alpha=0.35,
        zorder=3,
    )
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.set_title("Tilaiya study area, sub-watershed 2A219", fontsize=13, pad=8, loc="left", color="#1b3a2f")
    ax.set_xlabel("Easting (m), WGS 84 / UTM zone 45N")
    ax.set_ylabel("Northing (m)")
    add_scalebar(ax, extent)
    add_north_arrow(fig, x=0.86, y=0.78)
    legend = ax.legend(loc="lower right", frameon=True, fontsize=8)
    legend.get_frame().set_linewidth(0.4)
    fig.tight_layout()
    fig.savefig(STUDY_FIG, dpi=200)
    plt.close(fig)


def draw(study, dam_geom, study_km2, hydro_km2, dam_xy):
    FIG.parent.mkdir(parents=True, exist_ok=True)
    bounds = dam_geom.bounds
    pad_x = 0.04 * (bounds[2] - bounds[0])
    pad_y = 0.04 * (bounds[3] - bounds[1])
    extent = (bounds[0] - pad_x, bounds[2] + pad_x, bounds[1] - pad_y, bounds[3] + pad_y)
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 9,
            "axes.unicode_minus": False,
            "savefig.facecolor": "white",
        }
    )
    fig, ax = plt.subplots(figsize=(8.2, 8.4))
    add_poly(ax, dam_geom, "#1b6b4a", "#1b3a2f", 1.15, f"HydroBASINS catchment to the dam, {hydro_km2:.1f} km²", alpha=0.28, zorder=2)
    add_poly(ax, study, "#c47b2b", "#8c4a22", 1.45, f"Study mask, sub-watershed 2A219, {study_km2:.1f} km²", alpha=0.28, zorder=3)
    ax.scatter(
        [dam_xy[0]],
        [dam_xy[1]],
        s=36,
        c="#9b2335",
        marker="^",
        zorder=6,
        label="Tilaiya Dam",
    )
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.set_title("Tilaiya watershed boundaries", fontsize=13, pad=8, loc="left", color="#1b3a2f")
    ax.set_xlabel("Easting (m), WGS 84 / UTM zone 45N")
    ax.set_ylabel("Northing (m)")
    add_scalebar(ax, extent)
    add_north_arrow(fig, x=0.86, y=0.78)
    legend = ax.legend(loc="lower right", frameon=True, fontsize=8)
    legend.get_frame().set_linewidth(0.4)
    fig.text(
        0.08,
        0.012,
        "DVC publishes 984 km². That survey polygon is not in this project.\n"
        "The green polygon measures 952.5 km². HydroBASINS stores 970.7 km² on the outlet.",
        fontsize=7.5,
        color="#333333",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(FIG, dpi=200)
    plt.close(fig)


def main():
    study, study_km2 = load_study()
    dam_geom, sub_sum, up_area, count, contains_dam = load_dam_catchment()
    dam_xy = TO_UTM.transform(DAM_LON, DAM_LAT)
    hydro_km2 = dam_geom.area / 1e6
    write_polygon(
        OUT_DIR / "Tilaiya_2A219_study_mask.shp",
        study,
        [("name", "C", 80, 0), ("area_km2", "F", 12, 2), ("role", "C", 80, 0), ("source", "C", 120, 0)],
        ["Tilaiya sub-watershed 2A219", round(study_km2, 2), "study mask", "watershed_edited.shp"],
    )
    write_polygon(
        OUT_DIR / "Tilaiya_dam_catchment_HydroBASINS.shp",
        dam_geom,
        [("name", "C", 80, 0), ("area_km2", "F", 12, 2), ("up_area", "F", 12, 1), ("outlet_id", "N", 12, 0), ("source", "C", 160, 0)],
        [
            "Tilaiya dam catchment, HydroBASINS",
            round(hydro_km2, 2),
            up_area,
            OUTLET_ID,
            "HydroBASINS v1c level 12, not a DVC survey",
        ],
    )
    overlap = study.intersection(dam_geom).area / 1e6
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(
        "boundary,area_km2,published_area_km2,contains_dam,note\n"
        f"study mask 2A219,{study_km2:.2f},715.0,no,polygon used by the monthly maps\n"
        f"HydroBASINS dam catchment,{hydro_km2:.2f},{up_area:.1f},{'yes' if contains_dam else 'no'},"
        f"{count} level-12 units; sum of SUB_AREA {sub_sum:.1f}; study area inside this polygon {overlap:.2f}; DVC publishes 984\n",
        encoding="utf-8",
    )
    print(f"study_inside_hydro_km2 {overlap:.2f}")
    draw_study(study, study_km2)
    draw(study, dam_geom, study_km2, hydro_km2, dam_xy)
    print(f"study_km2 {study_km2:.2f}")
    print(f"hydro_planar_km2 {hydro_km2:.2f}")
    print(f"hydro_up_area {up_area:.1f}")
    print(f"sub_area_sum {sub_sum:.1f}")
    print(f"units {count}")
    print(f"contains_dam {contains_dam}")
    print(FIG)
    print(OUT_DIR / "Tilaiya_2A219_study_mask.shp")
    print(OUT_DIR / "Tilaiya_dam_catchment_HydroBASINS.shp")


if __name__ == "__main__":
    main()
