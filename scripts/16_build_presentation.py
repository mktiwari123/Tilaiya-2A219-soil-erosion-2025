"""Build the Tilaiya conference presentation from the revised manuscript numbers.

The deck uses the project title and the figures already written under output/figures.
It does not recompute soil loss, connectivity, or the stacking models.
"""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "output" / "figures"
OUT = ROOT / "Tilaiya_Presentation.pptx"

TITLE = (
    "Spatiotemporal Soil Erosion Dynamics and Sediment Connectivity "
    "in a Data-Scarce Monsoon Catchment: An Integrated Framework Coupling "
    "Sentinel-1 SAR Time-Series, Stacking Ensembles, and Explainable AI"
)

FOREST = RGBColor(0x1B, 0x3A, 0x2F)
FOREST_DEEP = RGBColor(0x12, 0x28, 0x22)
CREAM = RGBColor(0xF6, 0xF3, 0xEC)
INK = RGBColor(0x1C, 0x24, 0x28)
MUTED = RGBColor(0x5C, 0x68, 0x66)
SOIL = RGBColor(0xA3, 0x5C, 0x32)
GOLD = RGBColor(0xC4, 0x96, 0x4A)
WHITE = RGBColor(0xFF, 0xFC, 0xF7)
CARD = RGBColor(0xFF, 0xFB, 0xF6)
LINE = RGBColor(0xE4, 0xDD, 0xD2)
PALE = RGBColor(0xE7, 0xF0, 0xEA)

SLIDE_W = 13.333
SLIDE_H = 7.5
TOTAL = 15


def _set_run(run, text, size, bold, color, italic=False, font="Calibri"):
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    # Force Latin typeface so Calibri is used on every run.
    rpr = run._r.get_or_add_rPr()
    for tag in ("latin", "cs", "ea"):
        node = rpr.find(qn(f"a:{tag}"))
        if node is None:
            node = rpr.makeelement(qn(f"a:{tag}"), {})
            rpr.append(node)
        node.set("typeface", font)


def add_text(slide, left, top, width, height, text, size=18, bold=False,
             color=INK, align=PP_ALIGN.LEFT, italic=False, anchor=MSO_ANCHOR.TOP,
             font="Calibri"):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = 0
    frame.margin_bottom = 0
    try:
        frame._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}[anchor])
    except Exception:
        pass
    lines = text.split("\n") if isinstance(text, str) else list(text)
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.alignment = align
        paragraph.space_before = Pt(0)
        paragraph.space_after = Pt(0)
        _set_run(paragraph.add_run(), line, size, bold, color, italic, font)
    return box


def rect(slide, left, top, width, height, fill, line_color=None):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line_color is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(0.75)
    # Drop the default shadow if the template adds one.
    sp_pr = shape._element.spPr
    effect = sp_pr.find(qn("a:effectLst"))
    if effect is not None:
        sp_pr.remove(effect)
    return shape


def paint(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def chrome(slide, title, number):
    paint(slide, CREAM)
    rect(slide, 0, 0, 0.10, SLIDE_H, FOREST)
    add_text(slide, 0.42, 0.22, 11.6, 0.62, title, size=28, bold=True, color=FOREST)
    rect(slide, 0.44, 0.92, 1.7, 0.045, GOLD)
    add_text(
        slide, 0.42, 7.14, 9.4, 0.26,
        "Tiwari and Guru  ·  Tilaiya Reservoir headwater",
        size=12, color=MUTED,
    )
    add_text(
        slide, 10.6, 7.14, 2.3, 0.26, f"{number}   /   {TOTAL}",
        size=12, color=MUTED, align=PP_ALIGN.RIGHT,
    )


def place_image(slide, path, left, top, max_w, max_h):
    with Image.open(path) as image:
        aspect = image.size[0] / image.size[1]
    box_aspect = max_w / max_h
    if aspect > box_aspect:
        width, height = max_w, max_w / aspect
    else:
        height, width = max_h, max_h * aspect
    slide.shapes.add_picture(
        str(path),
        Inches(left + (max_w - width) / 2),
        Inches(top + (max_h - height) / 2),
        Inches(width),
        Inches(height),
    )


def card(slide, left, top, width, height, fill=WHITE):
    return rect(slide, left, top, width, height, fill, LINE)


def build():
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    prs.core_properties.title = TITLE
    prs.core_properties.author = "Mukesh Kumar Tiwari; Prabhat Kumar Guru"
    prs.core_properties.subject = "Tilaiya Reservoir headwater, 2025"
    blank = prs.slide_layouts[6]

    title_slide(prs.slides.add_slide(blank))
    catchment(prs.slides.add_slide(blank))
    framework(prs.slides.add_slide(blank))
    inputs(prs.slides.add_slide(blank))
    cover(prs.slides.add_slide(blank))
    june_july(prs.slides.add_slide(blank))
    high_cover(prs.slides.add_slide(blank))
    monthly_map(prs.slides.add_slide(blank))
    annual(prs.slides.add_slide(blank))
    envelope(prs.slides.add_slide(blank))
    connectivity(prs.slides.add_slide(blank))
    benchmarks(prs.slides.add_slide(blank))
    stack(prs.slides.add_slide(blank))
    open_work(prs.slides.add_slide(blank))
    close(prs.slides.add_slide(blank))

    prs.save(OUT)
    print(OUT)


def title_slide(slide):
    paint(slide, FOREST_DEEP)
    rect(slide, 0, 0, 0.18, SLIDE_H, GOLD)
    add_text(
        slide, 0.7, 0.42, 11.8, 0.34,
        "ICAR–INDIAN AGRICULTURAL RESEARCH INSTITUTE, JHARKHAND",
        size=13, bold=True, color=GOLD,
    )
    add_text(slide, 0.7, 1.35, 11.8, 2.7, TITLE, size=30, bold=True, color=CREAM)
    rect(slide, 0.72, 4.25, 2.1, 0.045, GOLD)
    add_text(
        slide, 0.7, 4.5, 11.5, 0.45,
        "Mukesh Kumar Tiwari    ·    Prabhat Kumar Guru",
        size=20, bold=True, color=WHITE,
    )
    add_text(
        slide, 0.7, 5.05, 11.2, 0.85,
        "School of Natural Resource Management\n"
        "ICAR–IARI Jharkhand, Gauria Karma, Hazaribagh 825405",
        size=16, color=RGBColor(0xD5, 0xE0, 0xD8),
    )
    add_text(
        slide, 0.7, 6.45, 11.5, 0.4,
        "Tilaiya Reservoir headwater  ·  sub-watershed 2A219  ·  eastern India  ·  2025",
        size=15, color=GOLD,
    )
    notes(
        slide,
        "Open with the catchment, not with the model names. The title names the three pieces "
        "that were actually built: a Sentinel-1 monthly series, a stacking ensemble, and SHAP. "
        "The talk then shows what each piece can support.",
    )


def catchment(slide):
    chrome(slide, "A monsoon headwater with a thin observational record", 2)
    facts = [
        ("984 km²", "Official Tilaiya catchment\n(Damodar Valley Corporation)"),
        ("715 km²", "Mask used here\n73 percent of the dam catchment"),
        ("12.5 m", "Common grid\n4.58 million cells, UTM 45N"),
        ("2025", "Twelve monthly composites\nNo storm EI30 in the project"),
    ]
    for i, (value, label) in enumerate(facts):
        left = 0.42 + i * 3.18
        card(slide, left, 1.35, 3.02, 2.15)
        add_text(slide, left + 0.16, 1.5, 2.7, 0.7, value, size=28, bold=True, color=SOIL)
        add_text(slide, left + 0.16, 2.25, 2.7, 1.0, label, size=14, color=INK)
    add_text(
        slide, 0.48, 3.75, 12.3, 1.5,
        "The missing piece is a sediment measurement at the scale of this mask. "
        "Sardar et al. (2014) give a reservoir rate. The Central Water Commission (2021) "
        "gives a live-storage loss. Neither series is a hillslope flux on these 12.5 m cells.",
        size=18, color=INK,
    )
    add_text(
        slide, 0.48, 4.85, 12.3, 1.4,
        "The mask is left at 715 km². The remaining area of the 984 km² catchment is not filled by scaling.",
        size=18, color=INK,
    )
    notes(
        slide,
        "Do not scale the 715 km² results up to 984 km². State the two external numbers only as "
        "reservoir benchmarks, not as observations of this grid.",
    )


def framework(slide):
    chrome(slide, "Three calculations, one grid", 3)
    columns = [
        ("01", "Monthly RUSLE", "Sentinel-1 and Sentinel-2\nenter the cover and the\nwithin-month stretch of K.\nThe year is the sum of the\ntwelve months, and only\nwhere every month is valid."),
        ("02", "Sediment connectivity", "A Borselli index on the\nsame elevation grid, then\na sigmoid delivery ratio.\nPaths end at the edge of\nthe valid mask."),
        ("03", "Stack and SHAP", "A stacking ensemble\nrecovers the annual RUSLE\nlayer from its own factors.\nTreeSHAP attributes that\nrecovery. It is not a test\nagainst measured sediment."),
    ]
    for i, (num, head, body) in enumerate(columns):
        left = 0.42 + i * 4.22
        card(slide, left, 1.35, 4.02, 4.15, WHITE)
        rect(slide, left, 1.35, 4.02, 0.1, GOLD)
        add_text(slide, left + 0.22, 1.6, 3.5, 0.4, num, size=14, bold=True, color=GOLD)
        add_text(slide, left + 0.22, 2.05, 3.55, 0.9, head, size=22, bold=True, color=FOREST)
        add_text(slide, left + 0.22, 3.15, 3.55, 3.1, body, size=16, color=INK)
    notes(
        slide,
        "Keep the three pieces separate. The stack does not deliver the sediment yield, "
        "and the delivery ratio does not validate the monthly soil-loss map.",
    )


def inputs(slide):
    chrome(slide, "What sits on the 12.5 m grid", 4)
    rows = [
        ("Sentinel-2", "Monthly median, cloudy pixels removed", "SAVI in ten months; optical cover"),
        ("Sentinel-1", "Monthly median VV and VH, no incidence correction", "RVI in July and August; the K stretch"),
        ("IMD rainfall", "Five 0.25° cells, repeated onto the fine grid", "Study erosivity, coefficients 1.8219 and 1.211"),
        ("Elevation", "12.5 m product, values stored in whole metres", "LS factor and the flow paths"),
        ("SoilGrids", "250 m texture and carbon, placed on 12.5 m cells", "Base erodibility K"),
        ("Static factors", "Aligned baseline, left unchanged", "LS, support practice P, annual C"),
    ]
    top = 1.25
    for i, (name, what, use) in enumerate(rows):
        y = top + i * 0.9
        fill = WHITE if i % 2 == 0 else PALE
        rect(slide, 0.42, y, 12.45, 0.84, fill)
        add_text(slide, 0.58, y + 0.18, 2.3, 0.5, name, size=16, bold=True, color=FOREST, anchor=MSO_ANCHOR.MIDDLE)
        add_text(slide, 3.0, y + 0.08, 4.7, 0.68, what, size=14, color=INK, anchor=MSO_ANCHOR.MIDDLE)
        add_text(slide, 7.85, y + 0.08, 4.8, 0.68, use, size=14, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    notes(
        slide,
        "Rainfall and soil are coarser than the grid. Sentinel-1 was not corrected for incidence "
        "angle or terrain, so the K stretch can follow slope and aspect.",
    )


def cover(slide):
    chrome(slide, "July and August change the cover measurement", 5)
    add_text(
        slide, 0.48, 1.2, 12.3, 0.7,
        "Cm  =  clip( 1  −  1.18 × canopy index ,  0.001 ,  1 )",
        size=22, bold=True, color=FOREST,
    )
    add_text(
        slide, 0.48, 1.9, 12.3, 0.7,
        "The canopy index is SAVI from January to June and from September to December. It is RVI in July and August. The switch is by calendar month.",
        size=16, color=INK,
    )
    stats = [
        ("0.636", "Mean Cm in June"),
        ("0.224", "Mean Cm in July"),
        ("22.5%", "July pixels on the 0.001 floor"),
        ("0.033", "R² of SAVI on RVI, fit outside July and August"),
    ]
    for i, (value, label) in enumerate(stats):
        left = 0.42 + (i % 4) * 3.18
        card(slide, left, 2.8, 3.02, 1.85)
        add_text(slide, left + 0.16, 2.95, 2.7, 0.6, value, size=26, bold=True, color=SOIL)
        add_text(slide, left + 0.16, 3.6, 2.7, 0.85, label, size=14, color=INK)
    add_text(
        slide, 0.48, 4.9, 12.3, 1.9,
        "RVI does not recover SAVI, so unscaled radar cover is kept as a sensitivity case.\n"
        "The primary annual figure interpolates July and August cover between the June and September optical factors.\n"
        "Two clear July scenes cannot fill the month: optical cover is finite on 114,325 of the annual pixels.",
        size=16, color=INK,
    )
    notes(
        slide,
        "Say explicitly that the R² of 0.033 was measured on the ten SAVI months, not on July and August. "
        "The coefficient 1.18 is an adopted linear form, not a Tilaiya calibration.",
    )


def june_july(slide):
    chrome(slide, "The July median falls with the cover floor", 6)
    pairs = [
        ("0.479", "June median, t ha⁻¹", "2.99 mean"),
        ("0.005", "July median, t ha⁻¹", "3.54 mean"),
        ("48%", "Below 0.01 in June", "same 4.47 million pixels"),
        ("52%", "Below 0.01 in July", "the extra slice is the floor"),
    ]
    for i, (value, label, note) in enumerate(pairs):
        left = 0.42 + i * 3.18
        card(slide, left, 1.28, 3.02, 2.35)
        add_text(slide, left + 0.14, 1.4, 2.74, 0.7, value, size=32, bold=True, color=SOIL)
        add_text(slide, left + 0.14, 2.15, 2.74, 0.7, label, size=15, bold=True, color=FOREST)
        add_text(slide, left + 0.14, 2.85, 2.74, 0.55, note, size=13, color=MUTED)
    add_text(
        slide, 0.48, 3.9, 12.3, 2.8,
        "Fewer than half the shared pixels are near zero in June, so the June median stays at 0.479. "
        "In July, 52 percent are below 0.01, and the 50th percentile falls to 0.005.\n\n"
        "The cover-floor class falls from a June median of 0.47 t ha⁻¹ to a July median of 0.002. "
        "Where July cover exceeds 0.15, the July median is 0.61 t ha⁻¹.\n\n"
        "Separately, 44 percent of the same pixels have an LS factor of exactly zero in every month. "
        "Those structural zeros sit inside the June near-zero share. They do not create the June-to-July change.",
        size=16, color=INK,
    )
    notes(
        slide,
        "Shares are 48.2 percent in June and 52.4 percent in July, on 4,465,002 pixels. "
        "LS exactly zero is 44.3 percent, and those zeros are exact: the share below 0.001 is the same.",
    )


def high_cover(slide):
    chrome(slide, "The class above 0.40 is a mass of zero LS, not open water", 7)
    place_image(slide, FIG / "maps" / "LS_2025.png", 7.15, 1.25, 5.7, 5.55)
    points = [
        ("50%", "of this class is exactly zero in both June and July"),
        ("89%", "of those zeros have LS = 0"),
        ("−0.15", "median MNDWI. Open water would be strongly positive"),
        ("0.50", "median support-practice factor. Ten percent of the class have P = 0"),
        ("LS", "is slope length and steepness together, the single RUSLE term"),
    ]
    y = 1.25
    for value, label in points:
        card(slide, 0.4, y, 6.5, 0.95)
        add_text(slide, 0.55, y + 0.16, 1.5, 0.62, value, size=20, bold=True, color=SOIL, anchor=MSO_ANCHOR.MIDDLE)
        add_text(slide, 2.1, y + 0.12, 4.6, 0.72, label, size=14, color=INK, anchor=MSO_ANCHOR.MIDDLE)
        y += 1.05
    notes(
        slide,
        "The class has 909,368 pixels. Median LS is 0.35 because 45 percent of the class is exactly zero; "
        "where July soil loss is positive, median LS is 1.28. The map on the right is the LS factor.",
    )


def monthly_map(slide):
    chrome(slide, "Monthly soil loss under the stored radar cover", 8)
    place_image(slide, FIG / "maps" / "SoilLoss_monthly_2025.png", 0.4, 1.15, 8.6, 5.75)
    card(slide, 9.15, 1.4, 3.75, 5.2)
    add_text(slide, 9.35, 1.6, 3.4, 0.8, "How to read the year", size=16, bold=True, color=FOREST)
    add_text(
        slide, 9.35, 2.5, 3.4, 3.7,
        "June and July hold the mean.\n\n"
        "November to February are near zero.\n\n"
        "August falls to a mean of 1.12 t ha⁻¹ after the cover switch.\n\n"
        "These panels are the radar case. The primary annual number is the interpolated cover.",
        size=14, color=INK,
    )
    notes(
        slide,
        "July mean 3.54, June mean 2.99, August mean 1.12, all in t ha⁻¹. "
        "The colour stretch is the 98th percentile of the monthly values.",
    )


def annual(slide):
    chrome(slide, "One primary annual mean, two sensitivity cases", 9)
    place_image(slide, FIG / "maps" / "SoilLoss_annual_class_2025.png", 6.85, 1.2, 6.05, 5.6)
    rows = [
        ("15.3", "Primary", "July and August cover interpolated from June and September optical factors"),
        ("9.30", "Sensitivity", "Unscaled radar cover. This is the map on the right, and the rasters on disk"),
        ("17.7", "Fitted line", "SAVI on RVI, fitted outside July and August. R² = 0.033"),
    ]
    y = 1.25
    for value, role, text in rows:
        card(slide, 0.4, y, 6.25, 1.7)
        add_text(slide, 0.55, y + 0.18, 1.7, 0.6, value, size=26, bold=True, color=SOIL)
        add_text(slide, 2.3, y + 0.22, 4.1, 0.4, role, size=14, bold=True, color=FOREST)
        add_text(slide, 2.3, y + 0.65, 4.1, 0.85, text, size=13, color=INK)
        y += 1.82
    notes(
        slide,
        "All three means use the same 4,154,545 pixels with twelve valid months. Units are t ha⁻¹ yr⁻¹. "
        "Grey inside the annual map is NoData, not zero loss.",
    )


def envelope(slide):
    chrome(slide, "Cover treatment crossed with the erosivity scale", 10)
    add_text(
        slide, 0.45, 1.18, 12.4, 0.45,
        "Annual mean soil loss, t ha⁻¹ yr⁻¹, on the 4,154,545 pixels valid in all twelve months.",
        size=15, color=MUTED,
    )
    headers = ["Cover treatment", "Study sum", "Corrected Arnoldus", "Renard–Freimund"]
    data = [
        ["Interpolated optical, primary", "15.3", "136", "347"],
        ["Radar, sensitivity", "9.30", "82.8", "211"],
        ["Fitted SAVI-on-RVI line", "17.7", "158", "404"],
    ]
    table_shape = slide.shapes.add_table(4, 4, Inches(0.45), Inches(1.75), Inches(12.4), Inches(2.7))
    table = table_shape.table
    widths = [4.6, 2.6, 2.6, 2.6]
    for j, width in enumerate(widths):
        table.columns[j].width = Inches(width)
    for j, header in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = ""
        cell.fill.solid()
        cell.fill.fore_color.rgb = FOREST
        paragraph = cell.text_frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.CENTER if j else PP_ALIGN.LEFT
        _set_run(paragraph.add_run(), header, 14, True, WHITE)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, row in enumerate(data):
        for j, value in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = PALE if i == 0 else WHITE
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.CENTER if j else PP_ALIGN.LEFT
            _set_run(paragraph.add_run(), value, 16, i == 0, INK if j else FOREST)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    add_text(
        slide, 0.48, 4.7, 12.3, 2.1,
        "On the primary row, gross volume at 1.45 t m⁻³ is 0.68 million m³ yr⁻¹ at the study erosivity, "
        "6.09 million m³ yr⁻¹ at corrected Arnoldus, and 15.5 million m³ yr⁻¹ at Renard and Freimund.\n\n"
        "The study coefficients are unsourced. On the same rainfall, corrected Arnoldus is about nine times larger, "
        "and Renard and Freimund about 21 to 28 times larger. The maps were not rescaled.",
        size=16, color=INK,
    )
    notes(
        slide,
        "Cell-wise ratios, not a single catchment multiplier. Soil-loss-weighted Arnoldus over the study sum is about 8.9. "
        "Absolute soil loss is linear in the leading erosivity coefficient.",
    )


def connectivity(slide):
    chrome(slide, "Structural delivery sits on the lower limb of the sigmoid", 11)
    place_image(slide, FIG / "maps" / "IC_2025.png", 0.35, 1.2, 6.2, 4.55)
    place_image(slide, FIG / "maps" / "SDR_2025.png", 6.75, 1.2, 6.2, 4.55)
    add_text(slide, 0.45, 5.8, 6.0, 0.35, "Connectivity index, mean −7.73", size=14, bold=True, color=FOREST, align=PP_ALIGN.CENTER)
    add_text(slide, 6.85, 5.8, 6.0, 0.35, "Delivery ratio, mean 0.00105", size=14, bold=True, color=FOREST, align=PP_ALIGN.CENTER)
    add_text(
        slide, 0.45, 6.2, 12.4, 0.8,
        "Slopes and weights are floored at 0.001. Paths end at the mask edge, not at a Sentinel-1 shoreline. "
        "The radar-cover yield to that edge is 1,001 t yr⁻¹, or 690 m³ yr⁻¹.",
        size=14, color=INK,
    )
    notes(
        slide,
        "IC median −7.66. SDR median 0.000891. The 690 m³ yr⁻¹ figure is the stored radar map, "
        "not the primary interpolated cover, and it is not reservoir siltation.",
    )


def benchmarks(slide):
    chrome(slide, "At the adopted erosivity, delivery cannot close the reservoir gap", 12)
    blocks = [
        ("0.68", "Primary gross erosion\nmillion m³ yr⁻¹"),
        ("0.76", "Sardar et al. current rate\nMm³ yr⁻¹"),
        ("1.01", "CWC live-storage loss\nmillion m³ yr⁻¹"),
        ("0.12", "Mean SDR that 6.09 million m³\nwould need, to match 0.76"),
    ]
    for i, (value, label) in enumerate(blocks):
        left = 0.42 + i * 3.18
        card(slide, left, 1.28, 3.02, 2.15)
        add_text(slide, left + 0.12, 1.4, 2.78, 0.7, value, size=32, bold=True, color=SOIL, align=PP_ALIGN.CENTER)
        add_text(slide, left + 0.14, 2.2, 2.74, 1.0, label, size=14, color=INK, align=PP_ALIGN.CENTER)
    add_text(
        slide, 0.48, 3.7, 12.3, 3.0,
        "Both 0.68 and the radar volume of 0.42 million m³ yr⁻¹ sit below the two reservoir figures, "
        "so no delivery ratio between 0 and 1 can match either one while erosivity stays at the adopted pair.\n\n"
        "On the corrected Arnoldus scale the primary gross volume is 6.09 million m³ yr⁻¹. "
        "Matching 0.76 Mm³ yr⁻¹ would need a mean delivery ratio near 0.12, and matching 1.01 would need about 0.17. "
        "The mean ratio on this grid is 0.00105, about 100 times smaller than 0.12.\n\n"
        "Sardar et al. render the unit as mm3/year in the journal abstract. That notation is read here as Mm³ yr⁻¹. "
        "The typeset PDF was not available to re-read. The CWC figure is the 2021 satellite survey of live storage, "
        "not the 7 October 2021 bulletin, which lists Tilaiya as full at 0.142 billion m³.",
        size=15, color=INK,
    )
    notes(
        slide,
        "CWC/2021/147: live capacity 131.235 MCM at full reservoir level against an original 199.89 MCM, "
        "a loss of 68.655 MCM over 68 years. The survey has no ground check. Do not quote the bulletin as that loss.",
    )


def stack(slide):
    chrome(slide, "The stack recovers the annual RUSLE layer", 13)
    place_image(slide, FIG / "Dynamic_Integrated" / "shap" / "shap_importance.png", 7.05, 1.25, 5.85, 5.5)
    stats = [
        ("0.832", "Reduced-stack holdout R²"),
        ("22.19", "Holdout RMSE, t ha⁻¹ yr⁻¹"),
        ("99.5%", "of squared error from 27 points above 100"),
        ("10.33", "SHAP of the LS factor, both files"),
    ]
    for i, (value, label) in enumerate(stats):
        y = 1.25 + i * 1.25
        card(slide, 0.4, y, 6.4, 1.12)
        add_text(slide, 0.55, y + 0.18, 1.7, 0.75, value, size=22, bold=True, color=SOIL, anchor=MSO_ANCHOR.MIDDLE)
        add_text(slide, 2.35, y + 0.18, 4.2, 0.75, label, size=15, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    notes(
        slide,
        "The target is the baseline annual RUSLE product, and the predictors include its factors. "
        "The holdout is a random stratified split, not a spatial block. MAE is 1.02. "
        "Dynamic holdout R² is 0.702. Do not present these scores as erosion skill. "
        "The figure is the dynamic-model importance; LS dominates.",
    )


def open_work(slide):
    chrome(slide, "Four failures were identified and left in place", 14)
    items = [
        ("Whole-metre elevation", "Forty-four percent of shared pixels have LS exactly zero, and the connectivity slopes are floored at 0.001. A continuous DEM, such as Copernicus GLO-30 or FABDEM, was not substituted."),
        ("Paths stop at the mask", "The outlet is the edge of the valid grid. Routing was not rebuilt to a Sentinel-1 shoreline."),
        ("An uncalibrated sigmoid", "IC₀ = 0.5 and k = 1.2 were not fitted to the Central Water Commission live-storage loss."),
        ("No storm erosivity", "The monthly index is not EI30. No IMERG storm series was calculated, and the maps were not rescaled to Arnoldus or Renard–Freimund."),
    ]
    for i, (head, body) in enumerate(items):
        col = i % 2
        row = i // 2
        left = 0.42 + col * 6.4
        top = 1.3 + row * 2.7
        card(slide, left, top, 6.15, 2.5)
        add_text(slide, left + 0.25, top + 0.22, 5.7, 0.5, head, size=18, bold=True, color=FOREST)
        add_text(slide, left + 0.25, top + 0.85, 5.7, 1.4, body, size=15, color=INK)
    notes(
        slide,
        "Say plainly that these were found and not fixed. The official soil-loss rasters and the connectivity grids were not replaced. "
        "A minimum slope in LS belongs with the continuous DEM.",
    )


def close(slide):
    paint(slide, FOREST_DEEP)
    rect(slide, 0, 0, 0.18, SLIDE_H, GOLD)
    add_text(slide, 0.7, 0.4, 11.5, 0.4, "WHAT THE FRAMEWORK SUPPORTS", size=14, bold=True, color=GOLD)
    lines = [
        ("15.3 t/ha/yr", "is the primary 2025 mean, with July and August cover interpolated. Radar cover, at 9.30, is the sensitivity case."),
        ("The July median", "falls to 0.005 because the cover floor pushes the near-zero share from 48 to 52 percent. The zero-LS cells are a separate, year-round feature of the whole-metre DEM."),
        ("The delivery ratio", "of 0.00105 cannot be read as Tilaiya siltation. At the adopted erosivity the gross volume is already below both reservoir benchmarks."),
        ("The stack", "shows that the annual RUSLE layer is recoverable from its factors. It does not test the map against sediment."),
    ]
    y = 1.05
    for head, body in lines:
        add_text(slide, 0.7, y, 11.6, 0.35, head, size=18, bold=True, color=WHITE)
        add_text(slide, 0.7, y + 0.38, 11.6, 0.7, body, size=15, color=RGBColor(0xD5, 0xE0, 0xD8))
        y += 1.2
    add_text(
        slide, 0.7, 6.55, 11.6, 0.45,
        "Mukesh Kumar Tiwari    ·    Mukesh.tiwari1@icar.org.in    ·    Tiwari.iitkgp@gmail.com",
        size=14, color=GOLD,
    )
    notes(
        slide,
        "Stop on these four sentences. Offer the envelope table if the question is about the absolute rate, "
        "and the June–July shares if the question is about the July median.",
    )


if __name__ == "__main__":
    build()
