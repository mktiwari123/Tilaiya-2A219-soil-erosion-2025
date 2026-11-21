"""Write the methodology record for work completed through 7 November 2026."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(__file__).resolve().parents[1] / "Tilaiya_Advanced_Methodology.docx"


def shade(cell, hex_color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = header
        shade(cell, "1F4E79")
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.size = Pt(10)
                run.font.name = "Calibri"
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = str(value)
            for paragraph in cells[index].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
                    run.font.name = "Calibri"
    doc.add_paragraph()
    return table


def heading(doc, text, level):
    paragraph = doc.add_heading(text, level=level)
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(31, 78, 121)
        run.font.name = "Calibri"
    return paragraph


def para(doc, text, bold=False, italic=False):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(11)
    run.bold = bold
    run.italic = italic
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.08
    return paragraph


def equation(doc, text):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.font.name = "Cambria Math"
    run.font.size = Pt(12)
    run.italic = True
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(8)
    return paragraph


def build():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    styles = doc.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(11)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(
        "Methodology record\nMonthly rainfall erosivity, Sentinel-1/2 factors, "
        "and the Tilaiya advanced soil-erosion project"
    )
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(31, 78, 121)
    run.font.name = "Calibri"

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    srun = sub.add_run(
        "Spatiotemporal Soil Erosion Dynamics and Sediment Connectivity in a Data-Scarce Monsoon Catchment: An Integrated Framework Coupling Sentinel-1 SAR Time-Series, Stacking Ensembles, and Explainable AI\n"
        "Tilaiya Reservoir headwater, sub-watershed 2A219\n"
        "Chota Nagpur Plateau, Eastern India\n"
        "Study lead: Dr. Mukesh Kumar Tiwari\n"
        "Record date: 7 November 2026\n"
        "Project folder: Tilaiya_Advanced"
    )
    srun.font.size = Pt(11)
    srun.font.name = "Calibri"
    srun.italic = True

    para(
        doc,
        "This document records the processing completed in the Tilaiya_Advanced "
        "project and the equations that project uses. It is written so that the "
        "numerical choices, data sources, and file names are not lost. Steps that "
        "have been coded but not yet executed are kept in a separate section and "
        "are not described as results.",
    )

    heading(doc, "1. Relation to the baseline study", 1)
    para(
        doc,
        "The baseline study estimated annual soil loss (A, t/ha/yr) for the "
        "Tilaiya Reservoir headwater with the Revised Universal Soil Loss Equation "
        "and compared multiple linear regression, a multilayer perceptron, and "
        "Random Forest. The study area is about 715 km2. Topography came from the "
        "ALOS PALSAR 12.5 m DEM. Annual rainfall erosivity came from IMD 0.25 degree "
        "daily rainfall. Soil erodibility and texture came from SoilGrids. The "
        "cover factor came from Sentinel-2. A stratified sample of 12,697 points "
        "was drawn from 4,527,896 valid pixels. The Reduced Integrated predictor "
        "set (LS, SOC, C, P, NDVI, K) was the strongest annual scenario.",
    )
    para(
        doc,
        "The advanced project keeps that annual baseline unchanged. New files are "
        "written only inside Tilaiya_Advanced. The extensions specified for the "
        "advanced study are monthly dynamic RUSLE, Sentinel-1 radar vegetation "
        "and moisture, a two-level stacking ensemble, SHAP, and Borselli sediment "
        "connectivity. Of these, the satellite monthly stacks, the point sample, "
        "the dynamic-factor join, the spatial monthly rainfall and erosivity layers, "
        "and the monthly soil-loss maps have been produced. Both stacking "
        "scenarios have been trained: Reduced Integrated and Dynamic Integrated. "
        "TreeSHAP has been run for the XGBoost member of both stacks: "
        "Reduced Integrated and Dynamic Integrated. "
        "Connectivity and sediment yield have been run. No reservoir mask "
        "was available, so flow paths end at the catchment outlet.",
    )

    heading(doc, "2. Common analysis grid", 1)
    para(
        doc,
        "Every new raster is aligned to the baseline DEM "
        "(D:\\A_RKLSCP\\Final_Index\\Actual_Raster\\DEM.tif).",
    )
    add_table(
        doc,
        ["Item", "Value"],
        [
            ["Coordinate system", "WGS 84 / UTM zone 45N, EPSG:32645"],
            ["Cell size", "12.5 m"],
            ["Columns x rows", "2,777 x 2,677"],
            ["Origin (upper left)", "311,579.4375 E, 2,698,245.25 N"],
            ["Pixel area", "156.25 m2 = 0.015625 ha"],
            ["NoData on new rasters", "-9999"],
            ["DEM NoData", "32767"],
            ["Watershed polygon", "Watershed IARI Whole\\watershed.shp"],
            ["Watershed pixels with data", "4,576,196"],
        ],
    )
    para(
        doc,
        "K, LS, C, and P used for any new map are the copies already aligned to "
        "this grid in Aligned_2.tif (K_aligned.tif, LS_aligned.tif, C_aligned.tif, "
        "P_aligned.tif). The original K and P files are not on this grid and are "
        "not used directly. The 11-band predictor stack is "
        "Aligned_Gen_1.tif\\stacked_ANN_input_2025.tif, with bands R, K, LS, C, P, "
        "Clay, Sand, Silt, SOC, Rain, and NDVI. The annual soil-loss target is "
        "Aligned_2.tif\\Annual_Soil_Loss_RUSLE_2025.tif.",
    )

    heading(doc, "3. Sentinel-1 and Sentinel-2 monthly stacks", 1)
    para(
        doc,
        "Monthly stacks for calendar year 2025 were exported from Google Earth "
        "Engine with project id ee-watershed-iari. The export rectangle, "
        "coordinate system, and 12.5 m geotransform are exactly the DEM grid, so "
        "the downloaded GeoTIFFs did not need to be resampled. Twelve files, "
        "Tilaiya_2025_01.tif through Tilaiya_2025_12.tif, are stored in the "
        "project folder gee\\. Each file has nine float32 bands in this order:",
    )
    add_table(
        doc,
        ["Band", "Name", "Source"],
        [
            ["1", "SAVI", "Sentinel-2"],
            ["2", "NDVI", "Sentinel-2"],
            ["3", "NDBI", "Sentinel-2"],
            ["4", "MNDWI", "Sentinel-2"],
            ["5", "Cm_optical", "Sentinel-2 SAVI, every month"],
            ["6", "VV_dB", "Sentinel-1"],
            ["7", "VH_dB", "Sentinel-1"],
            ["8", "RVI", "Sentinel-1, linear power"],
            ["9", "Cm", "SAVI, except July and August, which use RVI"],
        ],
    )

    heading(doc, "3.1 Optical composite", 2)
    para(
        doc,
        "Collection: COPERNICUS/S2_SR_HARMONIZED. Scenes with cloudy-pixel "
        "percentage of 80 or more were excluded. Remaining scenes were masked "
        "with the Scene Classification Layer. Pixels in classes 3 (cloud shadow), "
        "8 (cloud medium probability), 9 (cloud high probability), 10 (thin "
        "cirrus), and 11 (snow or ice) were removed. The monthly value is the "
        "median of the remaining observations. Surface reflectance is stored as "
        "0-10000 and was divided by 10000 before SAVI, because the soil-adjustment "
        "term is defined on reflectance.",
    )
    equation(doc, "SAVI = ((NIR - Red) / (NIR + Red + 0.5)) x 1.5")
    equation(doc, "NDVI = (NIR - Red) / (NIR + Red)")
    equation(doc, "NDBI = (SWIR - NIR) / (SWIR + NIR)")
    equation(doc, "MNDWI = (Green - SWIR) / (Green + SWIR)")
    para(
        doc,
        "Band mapping: Red = B4, Green = B3, NIR = B8, SWIR = B11. The SAVI "
        "soil factor L is 0.5, so the multiplier 1.5 is (1 + L).",
    )

    heading(doc, "3.2 Radar composite and the radar vegetation index", 2)
    para(
        doc,
        "Collection: COPERNICUS/S1_GRD, instrument mode IW, with both VV and VH "
        "present. Ascending and descending passes were combined. The monthly "
        "value is the median of VV and VH in decibels. No additional speckle "
        "filter was applied. Earth Engine stores Sentinel-1 GRD backscatter in "
        "decibels. The dual-polarisation radar vegetation index is defined on "
        "linear power, so the decibel values were converted before RVI.",
    )
    equation(doc, "sigma0 = 10 ^ (dB / 10)")
    equation(doc, "RVI = (4 x VH) / (VV + VH)")
    para(
        doc,
        "Number of scenes retained in each month after these filters:",
    )
    add_table(
        doc,
        ["Month", "Sentinel-2 scenes", "Sentinel-1 scenes"],
        [
            ["January", "12", "11"],
            ["February", "10", "9"],
            ["March", "14", "11"],
            ["April", "15", "9"],
            ["May", "16", "10"],
            ["June", "5", "11"],
            ["July", "2", "9"],
            ["August", "5", "10"],
            ["September", "10", "9"],
            ["October", "10", "11"],
            ["November", "13", "10"],
            ["December", "15", "10"],
        ],
    )
    para(
        doc,
        "July retains 2 Sentinel-2 scenes and August retains 5. The reason those "
        "two months use a different canopy index is set out in Section 4.1.",
    )

    heading(doc, "4. Cover-management factor Cm", 1)
    equation(doc, "Cm = clip(1 - 1.18 x canopy index, 0.001, 1.0)")
    para(
        doc,
        "Cm is the same factor in every month, and the equation does not change. "
        "For January-June and September-December the canopy index is SAVI. For "
        "July and August the canopy index is RVI. RVI can exceed 1 when VH "
        "approaches VV, so RVI was limited to the range 0-1 before this equation. "
        "That limit keeps Cm inside 0.001 to 1. Cm_optical, the SAVI-based cover "
        "factor, is stored for every month, including July and August. The value "
        "used in the soil-loss maps is band 9, named Cm.",
    )

    heading(doc, "4.1 Why July and August use RVI", 2)
    para(
        doc,
        "SAVI is the default canopy index. It is calculated from Sentinel-2 "
        "surface reflectance, and the annual baseline cover factor is also an "
        "optical index of the same family. Outside July and August the monthly "
        "optical median is built from 5 to 16 scenes that passed the cloud "
        "filters. September has 10. The dry-season months have 10 to 16.",
    )
    para(
        doc,
        "July and August are the peak monsoon months in this headwater. After "
        "the same cloud filters, the July optical median rests on 2 scenes and "
        "the August median on 5. A median from so few clear looks does not give "
        "a stable monthly canopy surface, and many pixels stay masked. "
        "Sentinel-1 C-band radar is not blocked by cloud. July still has 9 "
        "Sentinel-1 scenes and August has 10, so the dual-polarisation RVI is "
        "used as the canopy index in those two months only.",
    )
    para(
        doc,
        "The switch is by calendar month, not by a pixel cloud test. A July "
        "pixel that was clear still receives the RVI-based Cm. June also has "
        "only 5 optical scenes, but June stays on SAVI. The method names July "
        "and August. It does not switch every month that falls below a scene "
        "count. September returns to SAVI.",
    )
    para(
        doc,
        "SAVI and RVI enter the same equation, but they are not the same "
        "measurement and they were not scaled to each other. At the 12,697 "
        "sample points the mean SAVI is 0.309 and the mean RVI is 0.693. A "
        "larger canopy index produces a smaller Cm, so the July and August "
        "maps can step down relative to a neighbouring SAVI month. The "
        "SAVI-based Cm_optical band is kept in the monthly stacks so that "
        "step can be inspected. The exported files Cm_01.tif through Cm_12.tif "
        "are the fused factor used in Am.",
    )

    heading(doc, "5. Stratified sample and dynamic factors at the points", 1)
    para(
        doc,
        "The annual master table did not store coordinates, so the original "
        "12,697 points cannot be recovered exactly. The sample was drawn again "
        "from the same predictor stack and the same annual soil-loss raster, "
        "with the same class breaks, the same sample size, and random seed 42. "
        "Row, column, easting, northing, and a 2 km spatial-block id were stored "
        "with every point. Valid pixels: 4,527,896. A pixel was kept when every "
        "predictor and the soil-loss value were finite and soil loss was at least zero.",
    )
    add_table(
        doc,
        ["Class", "Soil loss (t/ha/yr)", "Pixels", "Percent", "Samples"],
        [
            ["E1", "0-5", "2,755,730", "60.86", "7,729"],
            ["E2", "5-15", "1,025,338", "22.64", "2,875"],
            ["E3", "15-30", "463,379", "10.23", "1,299"],
            ["E4", "30-50", "162,746", "3.59", "456"],
            ["E5", "50-100", "88,247", "1.95", "247"],
            ["E6", ">100", "32,456", "0.72", "91"],
            ["Total", "", "4,527,896", "100", "12,697"],
        ],
    )
    para(
        doc,
        "The split is 8,888 training points and 3,809 holdout points, stratified "
        "by erosion class. Files: output\\datasets\\stratified_12697.csv, "
        "training.csv, and testing.csv.",
    )
    heading(doc, "5.1 Moisture-adjusted erodibility at the sample points", 2)
    para(
        doc,
        "Base erodibility Kbase is the aligned annual K raster. For each month, "
        "VV backscatter over the whole monthly raster was stretched to a 0-1 "
        "wetness index. Wetter soil has a higher (less negative) VV value. The "
        "5th and 95th percentiles were used as the lower and upper bounds, and "
        "values outside that range were clipped. This is a relative wetness index. "
        "It is not a field-calibrated dielectric inversion. A calibrated moisture "
        "model can replace this step later without changing the rest of the workflow.",
    )
    equation(doc, "theta = clip((VV - VV_p5) / (VV_p95 - VV_p5), 0, 1)")
    equation(doc, "Km(t) = Kbase x (1 + 0.25 x theta)")
    para(
        doc,
        "Percentile bounds of monthly VV (dB), computed on the full raster:",
    )
    add_table(
        doc,
        ["Month", "5th percentile (dB)", "95th percentile (dB)"],
        [
            ["January", "-16.21", "-7.71"],
            ["February", "-16.13", "-7.63"],
            ["March", "-16.08", "-7.78"],
            ["April", "-15.35", "-7.53"],
            ["May", "-15.02", "-7.17"],
            ["June", "-13.07", "-6.48"],
            ["July", "-12.87", "-5.78"],
            ["August", "-12.87", "-6.24"],
            ["September", "-13.35", "-5.90"],
            ["October", "-13.41", "-6.51"],
            ["November", "-14.13", "-6.81"],
            ["December", "-14.99", "-7.13"],
        ],
    )
    para(
        doc,
        "VV is higher in June-September than in the dry months, which is the "
        "expected monsoon pattern. At each of the 12,697 points, the twelve "
        "monthly values were averaged. No point is missing. Means on the sample: "
        "Cm = 0.577, SAVI = 0.309, RVI = 0.693, Km = 0.040. Ranges: Cm 0.320 to "
        "0.939, SAVI -0.130 to 0.536, RVI 0.199 to 1.162, Km 0.000 to 0.073. "
        "These annual means are columns in the training and testing tables.",
    )

    heading(doc, "6. Monthly rainfall and rainfall erosivity", 1)
    para(
        doc,
        "Daily rainfall is the IMD 0.25 degree gridded product. The year-wise "
        "binary files are in HydroMeteorological Data\\Gridded Rainfall Data\\"
        "Gridded Rainfall Data 2015 to 2024\\rain, named 1995.grd through 2025.grd. "
        "No further download was required. The 2025 file contains 365 daily grids. "
        "Each day is a 129 by 135 array of 32-bit floating-point values. Latitude "
        "starts at 6.5 degrees N and longitude at 66.5 degrees E, with a spacing "
        "of 0.25 degrees. Missing values are coded -999 and were excluded.",
    )
    para(
        doc,
        "Two rainfall summaries were made, and they are not interchangeable.",
    )
    para(
        doc,
        "First, a catchment-mean daily series was written to "
        "data\\rainfall\\imd_daily.csv. It averages the IMD cell centres inside "
        "the expanded study bounding box (latitude 24.0865-24.3875 degrees N, "
        "longitude 85.1429-85.4873 degrees E, expanded by half a cell). That "
        "selection contains six cells. Their 2025 total is 1,307 mm. Monthly "
        "erosivity for this single series is in output\\tables\\Rm_2025.csv. "
        "This file is a catchment time series. It has no spatial variation inside "
        "the watershed.",
    )
    para(
        doc,
        "Second, the maps use only the five IMD cells whose 0.25 degree polygon "
        "intersects watershed.shp. The cell at 85.50 degrees E, 24.50 degrees N "
        "falls in the bounding box but does not intersect the watershed, so it "
        "is not in the maps. Erosivity is calculated separately for each cell, "
        "using that cell's own annual rainfall as Pannual.",
    )
    equation(doc, "MFIm = Pm ^ 2 / Pannual")
    equation(doc, "Rm = 1.8219 x (MFIm ^ 1.211)")
    para(
        doc,
        "Pm and Pannual are in millimetres. Rm is in MJ mm / ha / h / month. "
        "A month with no rain has Rm = 0. The annual erosivity raster is the "
        "sum of the twelve monthly Rm values. The coefficients 1.8219 and 1.211 "
        "are a retired pair. No primary paper was found for 1.8219 and 1.211. "
        "The stored erosivity rasters still use that pair. The reported soil-loss "
        "maps use the corrected Arnoldus equation in Section 21. "
        "This is not the EI30 erosivity equation.",
    )

    heading(doc, "6.1 Values for the five watershed cells, 2025", 2)
    add_table(
        doc,
        ["Cell", "Longitude", "Latitude", "Annual rainfall (mm)", "Annual Rm"],
        [
            ["1", "85.25", "24.00", "1,220", "894"],
            ["2", "85.50", "24.00", "1,399", "1,225"],
            ["3", "85.25", "24.25", "1,090", "786"],
            ["4", "85.50", "24.25", "1,263", "1,046"],
            ["5", "85.25", "24.50", "1,443", "1,292"],
        ],
    )
    para(
        doc,
        "Monthly rainfall (mm) for these cells:",
    )
    add_table(
        doc,
        ["Month", "Cell 1", "Cell 2", "Cell 3", "Cell 4", "Cell 5"],
        [
            ["Jan", "0", "0", "0", "0", "0"],
            ["Feb", "0", "0", "0", "0", "0"],
            ["Mar", "21.6", "23.9", "23.5", "36.5", "16.3"],
            ["Apr", "50.9", "32.8", "46.7", "15.2", "60.4"],
            ["May", "83.2", "88.5", "62.4", "90.5", "56.1"],
            ["Jun", "323.6", "229.4", "217.1", "193.1", "233.7"],
            ["Jul", "272.4", "409.6", "310.1", "397.8", "480.1"],
            ["Aug", "194.9", "340.5", "173.9", "237.7", "243.0"],
            ["Sep", "151.7", "139.4", "117.8", "165.6", "170.0"],
            ["Oct", "109.9", "125.7", "120.9", "106.6", "148.7"],
            ["Nov", "12.0", "9.7", "18.0", "19.9", "34.0"],
            ["Dec", "0", "0", "0", "0", "0"],
        ],
    )
    para(doc, "Monthly erosivity, Rm:")
    add_table(
        doc,
        ["Month", "Cell 1", "Cell 2", "Cell 3", "Cell 4", "Cell 5"],
        [
            ["Jan", "0", "0", "0", "0", "0"],
            ["Feb", "0", "0", "0", "0", "0"],
            ["Mar", "0.6", "0.6", "0.8", "1.9", "0.2"],
            ["Apr", "4.5", "1.3", "4.2", "0.2", "5.6"],
            ["May", "14.9", "14.7", "8.5", "17.5", "4.7"],
            ["Jun", "400.0", "147.2", "174.3", "109.9", "148.6"],
            ["Jul", "263.6", "599.6", "413.5", "632.6", "849.4"],
            ["Aug", "117.2", "383.3", "101.8", "181.8", "163.2"],
            ["Sep", "63.9", "44.1", "39.7", "75.8", "68.7"],
            ["Oct", "29.2", "34.3", "42.2", "26.0", "49.7"],
            ["Nov", "0.1", "0.1", "0.4", "0.4", "1.4"],
            ["Dec", "0", "0", "0", "0", "0"],
        ],
    )
    para(
        doc,
        "Cell 1 is wetter in June than in July. The other four cells peak in "
        "July. July is the peak erosivity month for cells 2, 3, 4, and 5. Cell 1 "
        "peaks in June because its June rainfall (324 mm) is larger than its July "
        "rainfall (272 mm), and Rm depends on the square of monthly rainfall.",
    )

    heading(doc, "6.2 Raster files for watershed calculations", 2)
    para(
        doc,
        "The five cell values were burned onto the 12.5 m DEM grid and then "
        "masked with the watershed polygon and the DEM NoData mask. Pixels "
        "outside the watershed are NoData (-9999). All 4,576,196 watershed "
        "pixels received a value. The raster does not interpolate between IMD "
        "cells. Every 12.5 m pixel carries the value of the 0.25 degree cell "
        "that covers it, so the map is five blocks. That is the spatial resolution "
        "of the IMD rainfall used to calculate erosivity.",
    )
    para(
        doc,
        "On the watershed raster, July rainfall ranges from 272.4 mm to 480.1 mm, "
        "with a pixel-weighted mean of 336.1 mm. July erosivity ranges from 263.6 "
        "to 849.4, with a pixel-weighted mean of 473.8. The pixel-weighted mean "
        "is lower than the unweighted mean of the five cells because the drier "
        "cells cover more of the watershed.",
    )
    add_table(
        doc,
        ["Folder", "Files", "Units"],
        [
            [
                "output\\rasters\\Rainfall",
                "Rainfall_01.tif to Rainfall_12.tif, Rainfall_annual.tif",
                "mm",
            ],
            [
                "output\\rasters\\Erosivity",
                "Erosivity_01.tif to Erosivity_12.tif, Erosivity_annual.tif",
                "MJ mm / ha / h / month, annual file is the sum",
            ],
        ],
    )
    para(
        doc,
        "Polygon copies of the same five cells, for maps that should show the "
        "IMD grid rather than the 12.5 m pixels, are "
        "output\\shapefiles\\IMD_Rainfall_Monthly_2025.shp (fields P_01 to P_12 "
        "and P_annual) and IMD_Erosivity_Monthly_2025.shp (fields Rm_01 to Rm_12 "
        "and Rm_annual). Both shapefiles are in UTM zone 45N. The cell table is "
        "IMD_monthly_cells_2025.csv.",
    )
    para(
        doc,
        "The older annual rainfall map, rain.tif, has a watershed mean near "
        "1,126 mm. That map is one yearly surface from the baseline study. The "
        "1,090-1,443 mm cell totals in this document are the 2025 sums of the "
        "daily IMD grids. They should not be averaged together or treated as "
        "the same layer.",
    )

    heading(doc, "7. Monthly soil loss", 1)
    equation(doc, "Am = Rm x Km(t) x LS x Cm(t) x P")
    para(
        doc,
        "This map was calculated for all twelve months of 2025 by "
        "scripts/03_monthly_soil_loss.py. Rm is the spatial erosivity raster "
        "from Section 6, not the single catchment-mean value. Cm(t) is band 9 "
        "of the monthly Sentinel stack. LS and P are the static aligned "
        "baseline rasters. Watershed-masked copies are stored in the project "
        "by scripts/03c_export_ls_c_p.py: output\\rasters\\LS\\LS.tif and "
        "output\\rasters\\Practice\\P.tif. The annual baseline cover factor is "
        "output\\rasters\\Cover\\C_annual_baseline.tif. The monthly cover "
        "factor used in Am is output\\rasters\\Cover\\Cm_01.tif through "
        "Cm_12.tif. Km(t) uses the same equation as Section 5.1, but "
        "the VV percentiles for the maps were calculated on watershed pixels "
        "only. The earlier point-table Km used percentiles of the full monthly "
        "raster, so those point values are not identical to the map pixels.",
    )
    para(
        doc,
        "A pixel is left as NoData when K, LS, P, Cm, VV, or Rm is missing, or "
        "when the result is negative. The annual raster is the sum of the twelve "
        "months only where all twelve months are valid. Pixels missing any month "
        "stay NoData, so a gap is not treated as zero erosion. About 30,208 "
        "watershed pixels are missing in every month because K, LS, or P is "
        "missing. June has 111,194 missing pixels and September has 347,762, "
        "from gaps in the monthly satellite cover or radar layer.",
    )
    add_table(
        doc,
        ["Month", "Mean Am (t/ha)", "Median (t/ha)", "95th percentile (t/ha)"],
        [
            ["January", "0", "0", "0"],
            ["February", "0", "0", "0"],
            ["March", "0.027", "0.003", "0.113"],
            ["April", "0.063", "0.002", "0.263"],
            ["May", "0.223", "0.030", "0.918"],
            ["June", "2.988", "0.479", "11.54"],
            ["July", "3.536", "0.005", "16.26"],
            ["August", "1.123", "0.002", "5.10"],
            ["September", "0.780", "0.097", "3.19"],
            ["October", "0.588", "0.091", "2.27"],
            ["November", "0.008", "0.001", "0.031"],
            ["December", "0", "0", "0"],
        ],
    )
    para(
        doc,
        "Where all twelve months are valid (4,154,545 pixels), the annual mean "
        "is 9.30 t/ha/yr. July is the peak month. The distribution is strongly "
        "skewed: the July median is about 0.005 t/ha while the July mean is "
        "3.54 t/ha, because steep LS pixels dominate the mean. The annual class "
        "raster uses the baseline breaks: 1 = 0-5, 2 = 5-15, 3 = 15-30, "
        "4 = 30-50, 5 = 50-100, and 6 = above 100 t/ha/yr.",
    )
    add_table(
        doc,
        ["Content", "Path"],
        [
            ["Monthly soil loss", "output\\rasters\\SoilLoss\\SoilLoss_01.tif to SoilLoss_12.tif"],
            ["Annual soil loss", "output\\rasters\\SoilLoss\\SoilLoss_annual.tif"],
            ["Annual class", "output\\rasters\\SoilLoss\\SoilLoss_annual_class.tif"],
            ["Valid-month count", "output\\rasters\\SoilLoss\\SoilLoss_month_count.tif"],
            ["Monthly Km", "output\\rasters\\Erodibility\\Km_01.tif to Km_12.tif"],
            ["Watershed means", "output\\shapefiles\\SoilLoss_Monthly_Means_2025.shp"],
            ["Statistics", "output\\tables\\monthly_soil_loss_2025.csv"],
        ],
    )
    para(
        doc,
        "The soil-loss surface is stored as a raster. The shapefile is the "
        "watershed boundary with the monthly mean soil loss stored as attributes "
        "Am_01 to Am_12 and A_annual. It is not a polygon for every pixel.",
    )

    heading(doc, "8. Stacking ensemble", 1)
    para(
        doc,
        "The Reduced Integrated scenario was trained by scripts/05_stacking_ensemble.py "
        "on 7 November 2026. Predictors are LS, SOC, C, P, NDVI, and K. The target "
        "is the baseline annual RUSLE soil loss at the sample points, not the new "
        "monthly soil-loss sum. Level-0 models are XGBoost (500 trees, maximum depth "
        "6, learning rate 0.03, subsample 0.8), CatBoost (600 iterations, depth 6, "
        "learning rate 0.04, L2 leaf regularisation 3), Random Forest (300 trees, "
        "maximum features sqrt, minimum samples to split 4), and an MLP with hidden "
        "layers (100, 50), ReLU, Adam, and L2 penalty 0.001. MLP inputs are "
        "standardised, and MLP training uses early stopping. Level-1 is Ridge with "
        "alpha 1.0 and an intercept, fit only to out-of-fold Level-0 predictions. "
        "Those folds are five GroupKFold splits on the 2 km blocks inside the "
        "8,888 training points. The 3,809-point holdout stays the stratified random "
        "split. R2 and NSE are the same number under the sum-of-squares definition.",
    )
    add_table(
        doc,
        ["Model", "Set", "n", "R2", "RMSE", "MAE"],
        [
            ["Stack, out of fold", "Training blocks", "8888", "0.983", "2.96", "0.71"],
            ["Stack", "Holdout", "3809", "0.832", "22.19", "1.02"],
            ["MLP", "Holdout", "3809", "0.920", "15.33", "1.01"],
            ["CatBoost", "Holdout", "3809", "0.548", "36.35", "1.47"],
            ["XGBoost", "Holdout", "3809", "0.451", "40.08", "1.76"],
            ["Random Forest", "Holdout", "3809", "0.443", "40.34", "1.94"],
        ],
    )
    para(
        doc,
        "Units of RMSE and MAE are t/ha/yr. NSE equals R2 in each row. Ridge "
        "weights on the holdout blend are CatBoost 0.702, MLP 0.567, XGBoost "
        "-0.085, and Random Forest -0.167, with intercept -0.097. The MLP alone "
        "has a higher holdout R2 and a lower RMSE than the stacked blend. The "
        "negative weights on XGBoost and Random Forest pull the blend away from "
        "the MLP.",
    )
    para(
        doc,
        "Holdout MAE is 1.02 t/ha/yr, so a typical point is close to the RUSLE "
        "value. Holdout RMSE is 22.19 because the test set contains the extreme "
        "tail. The largest training soil loss is 909 t/ha/yr. The largest holdout "
        "soil loss is 2,769 t/ha/yr. Three holdout points exceed 500 t/ha/yr, and "
        "the stack underpredicts those points. The observed-versus-predicted "
        "figure is output\\figures\\Reduced_Integrated\\observed_vs_predicted.png. "
        "The saved model is output\\models\\Reduced_Integrated\\stack.joblib.",
    )
    para(
        doc,
        "Dynamic Integrated was trained on the same points and the same target "
        "by scripts/05b_stacking_dynamic_integrated.py. Predictors are LS, R, "
        "Km, Cm, P, RVI, SAVI, and SOC. Km, Cm, RVI, and SAVI are the annual "
        "means of the monthly factors at each sample point. The point-table Km "
        "uses Sentinel-1 percentiles of the full monthly raster, not the "
        "watershed-only percentiles used in the soil-loss maps. The model "
        "settings, the five spatial-block folds, and the stratified holdout "
        "are the same as Reduced Integrated.",
    )
    add_table(
        doc,
        ["Model", "Set", "n", "R2", "RMSE", "MAE"],
        [
            ["Stack, out of fold", "Training blocks", "8888", "0.964", "4.31", "1.20"],
            ["Stack", "Holdout", "3809", "0.702", "29.49", "1.77"],
            ["MLP", "Holdout", "3809", "0.878", "18.90", "2.01"],
            ["CatBoost", "Holdout", "3809", "0.466", "39.52", "1.65"],
            ["XGBoost", "Holdout", "3809", "0.411", "41.51", "1.86"],
            ["Random Forest", "Holdout", "3809", "0.390", "42.22", "2.55"],
        ],
    )
    para(
        doc,
        "Ridge weights are CatBoost 0.903, MLP 0.389, XGBoost 0.042, and "
        "Random Forest -0.282, with intercept -0.295. Again the MLP alone "
        "beats the stacked blend on the holdout. Dynamic Integrated is weaker "
        "than Reduced Integrated on the same holdout: stack R2 0.702 against "
        "0.832, and MAE 1.77 against 1.02. The target is the baseline annual "
        "soil loss, which was calculated with the annual K and C. Dynamic "
        "Integrated replaces those with Km and Cm and adds R, RVI, and SAVI, "
        "so it is not using the exact factors that produced the target. "
        "The figure is output\\figures\\Dynamic_Integrated\\observed_vs_predicted.png. "
        "The saved model is output\\models\\Dynamic_Integrated\\stack.joblib.",
    )

    heading(doc, "9. Explainable AI", 1)
    para(
        doc,
        "TreeSHAP was run by scripts/06_shap_xai.py on the XGBoost member of "
        "the Reduced Integrated stack. The explanation uses the 3,809 holdout "
        "points. It explains that XGBoost model, whose holdout R2 is 0.451, "
        "not the Ridge blend (holdout R2 0.832) and not the MLP (holdout R2 "
        "0.920). Mean absolute SHAP value, in predicted t/ha/yr, ranks the "
        "predictors as follows.",
    )
    add_table(
        doc,
        ["Feature", "Mean absolute SHAP"],
        [
            ["LS", "10.33"],
            ["P", "2.69"],
            ["SOC", "2.35"],
            ["K", "0.98"],
            ["C", "0.49"],
            ["NDVI", "0.11"],
        ],
    )
    para(
        doc,
        "A value above the holdout median increases predicted soil loss for "
        "LS, P, C, and K. A value above the median decreases predicted soil "
        "loss for SOC. NDVI has little effect. High LS is the dominant push "
        "toward large predicted soil loss. The summary plot and the LS and C "
        "dependence plots are in output\\figures\\Reduced_Integrated\\shap\\.",
    )
    para(
        doc,
        "The cover-threshold table was calculated. No holdout point has C "
        "below 0.15. The lowest holdout C is 0.410, and the mean C is 0.686. "
        "The comparison of bare cover against the rest of the holdout "
        "therefore has no low-cover group.",
    )
    para(
        doc,
        "TreeSHAP was then run for the XGBoost member of Dynamic Integrated "
        "by scripts/06b_shap_dynamic_integrated.py, on the same 3,809 holdout "
        "points. It explains that XGBoost model, whose holdout R2 is 0.411, "
        "not the Dynamic ridge blend (holdout R2 0.702) and not its MLP "
        "(holdout R2 0.878). This step has been run. Mean absolute SHAP, "
        "in predicted t/ha/yr, ranks the eight predictors as follows.",
    )
    add_table(
        doc,
        ["Feature", "Mean absolute SHAP"],
        [
            ["LS", "10.33"],
            ["P", "2.59"],
            ["Km", "2.04"],
            ["SOC", "1.44"],
            ["SAVI", "0.37"],
            ["Cm", "0.22"],
            ["R", "0.07"],
            ["RVI", "0.06"],
        ],
    )
    para(
        doc,
        "A value above the holdout median increases predicted soil loss for "
        "LS, P, Km, and Cm. A value above the median decreases predicted soil "
        "loss for SOC and SAVI. R and RVI have mean absolute contributions "
        "below 0.08 t/ha/yr. No holdout point has Cm below 0.15 (n = 0; "
        "mean holdout Cm is 0.577). The plots are in "
        "output\\figures\\Dynamic_Integrated\\shap\\.",
    )

    heading(doc, "10. Connectivity and reservoir siltation", 1)
    para(
        doc,
        "Borselli's index of connectivity is specified on the 12.5 m DEM. The "
        "weighting factor is the RUSLE cover factor, or the mean monthly Cm when "
        "that layer exists. Depressions are filled by priority-flood. Flow is "
        "steepest-descent D8. Minimum weight and minimum slope are 0.001, so the "
        "downslope term stays finite.",
    )
    equation(doc, "IC = log10(D_up / D_down)")
    equation(doc, "D_up = C_bar x S_bar x sqrt(A_up)")
    equation(doc, "D_down = sum of [d_i / (C_i x S_i)] along the flow path")
    equation(doc, "SDR = 0.8 / (1 + exp((0.5 - IC) / 1.2))")
    equation(doc, "SY = sum(A x SDR x 0.015625)")
    equation(doc, "Volume (m3/yr) = SY / 1.45")
    para(
        doc,
        "SY is tonnes per year. The bulk density 1.45 t/m3 is 1.45 g/cm3. "
        "Until a reservoir mask is supplied as data\\reservoir_mask.tif, with "
        "value 1 on Tilaiya Reservoir, flow paths end at the catchment outlet "
        "rather than at the reservoir shoreline. The first IC and SDR grids "
        "from 7 November 2026 drew parallel stripes across the northern "
        "plateau. The elevation there is stored in whole metres, so many "
        "neighbours are equal. Filling those flats with a microscopic "
        "gradient sent them all in one direction. That flow is no longer "
        "used. Flat cells are now routed only toward a cell that already "
        "drains and that is at the same elevation or lower, using a smoothed "
        "elevation to choose the exit. All 4,576,196 watershed cells receive "
        "a finite index. The weight is the mean monthly Cm. No reservoir "
        "mask was present, so paths end at the catchment outlet. "
        "The corrected index has mean -7.73 and median -7.66 "
        "(5th to 95th percentile -9.62 to -6.63). The delivery ratio has "
        "mean 0.00105 and median 0.000891. Delivered yield is about 0.17 "
        "percent of hillslope erosion. A min-to-max colour stretch still "
        "paints the map nearly one colour, because a few cells reach -10.2 "
        "and -0.95. The plates for the paper use the 2nd to 98th percentile "
        "and are output\\figures\\maps\\IC_2025.png and SDR_2025.png.",
    )
    add_table(
        doc,
        ["Soil-loss map", "Pixels", "Gross erosion (t/yr)", "Sediment yield (t/yr)", "Volume (m3/yr)"],
        [
            ["Baseline annual RUSLE", "4527896", "633485", "1064.9", "734.4"],
            ["Dynamic annual sum", "4154545", "603597", "1000.8", "690.2"],
        ],
    )
    para(
        doc,
        "scripts/07b_sediment_yield_by_source.py applies the corrected SDR "
        "to both annual soil-loss maps. The dynamic sum is the soil-loss "
        "raster used by scripts/07_connectivity_sediment_yield.py. "
        "IC and SDR are output\\connectivity\\IC.tif and SDR.tif.",
    )

    heading(doc, "11. Decisions that must stay with the results", 1)
    para(
        doc,
        "Sentinel-2 digital numbers were converted to reflectance before SAVI. "
        "Sentinel-1 decibels were converted to linear power before RVI. July and "
        "August use RVI for Cm because those peak monsoon months have only 2 and "
        "5 clear Sentinel-2 scenes. The other ten months use SAVI. The equation "
        "is the same in every month. SAVI and RVI were not scaled to each other, "
        "and the SAVI-based Cm is retained as Cm_optical for comparison. The moisture term "
        "in Km is a percentile stretch of VV, with alpha = 0.25, not a calibrated "
        "soil-moisture retrieval. The map Km uses VV percentiles inside the "
        "watershed. The point-table Km used percentiles of the full monthly "
        "raster. Erosivity uses the Modified Fournier equation above, calculated "
        "per IMD cell with that cell's own annual rainfall. "
        "The 12.5 m erosivity rasters repeat the 0.25 degree cell value. They "
        "do not add rainfall detail. The six-cell catchment CSV and the five-cell "
        "watershed rasters are different spatial supports. The 12,697 points "
        "follow the baseline sampling design. They are not the identical point "
        "list from the annual master table. Both stacks predict that baseline "
        "annual soil loss. The holdout contains soil-loss values above the "
        "training maximum, and those points dominate RMSE. On that holdout, "
        "Reduced Integrated (R2 0.832) is stronger than Dynamic Integrated "
        "(R2 0.702). Annual soil loss is reported only "
        "where all twelve monthly maps are valid. The annual baseline rasters "
        "and the SoilProperties scripts were not modified.",
    )

    heading(doc, "12. Where the files are", 1)
    add_table(
        doc,
        ["Content", "Path inside Tilaiya_Advanced"],
        [
            ["Monthly Sentinel stacks", "gee\\Tilaiya_2025_01.tif to Tilaiya_2025_12.tif"],
            ["Catchment-mean daily rainfall", "data\\rainfall\\imd_daily.csv"],
            ["Catchment-mean monthly Rm", "output\\tables\\Rm_2025.csv"],
            ["Sample and splits", "output\\datasets\\"],
            ["Five-cell rainfall polygons", "output\\shapefiles\\IMD_Rainfall_Monthly_2025.shp"],
            ["Five-cell erosivity polygons", "output\\shapefiles\\IMD_Erosivity_Monthly_2025.shp"],
            ["Cell table", "output\\shapefiles\\IMD_monthly_cells_2025.csv"],
            ["12.5 m rainfall rasters", "output\\rasters\\Rainfall\\"],
            ["12.5 m erosivity rasters", "output\\rasters\\Erosivity\\"],
            ["Monthly Km", "output\\rasters\\Erodibility\\"],
            ["Monthly and annual soil loss", "output\\rasters\\SoilLoss\\"],
            ["LS factor", "output\\rasters\\LS\\LS.tif"],
            ["Support-practice factor P", "output\\rasters\\Practice\\P.tif"],
            ["Annual baseline C and monthly Cm", "output\\rasters\\Cover\\"],
            ["Soil-loss means", "output\\shapefiles\\SoilLoss_Monthly_Means_2025.shp"],
            ["Reduced Integrated stack", "output\\models\\Reduced_Integrated\\stack.joblib"],
            ["Dynamic Integrated stack", "output\\models\\Dynamic_Integrated\\stack.joblib"],
            ["Reduced Integrated SHAP", "output\\figures\\Reduced_Integrated\\shap\\"],
            ["Dynamic Integrated SHAP", "output\\figures\\Dynamic_Integrated\\shap\\"],
            ["Holdout error by class", "output\\tables\\holdout_error_by_class.csv"],
            ["Erosivity equation comparison", "output\\tables\\erosivity_equation_comparison.csv"],
            ["Valid-pixel fractions", "output\\tables\\valid_pixel_fractions.csv"],
            ["SDR parameter check", "output\\tables\\sdr_parameter_sensitivity.csv"],
            ["Connectivity index and SDR", "output\\connectivity\\IC.tif and SDR.tif"],
            ["Sediment yield by soil-loss map", "output\\tables\\sediment_yield_by_source.csv"],
            ["Stack scores and ridge weights", "output\\tables\\Reduced_Integrated_scores.csv and Dynamic_Integrated_scores.csv"],
            ["Holdout observed and predicted", "output\\tables\\Reduced_Integrated_holdout_predictions.csv"],
            ["Monthly soil-loss script", "scripts\\03_monthly_soil_loss.py"],
            ["Equation constants", "tilaiya\\constants.py"],
            ["Earth Engine export", "gee\\export_monthly_factors.py"],
            ["Presentation maps", "output\\figures\\maps\\"],
            ["Map script", "scripts\\09_presentation_maps.py"],
        ],
    )
    para(
        doc,
        "Earth Engine account: project ee-watershed-iari. IMD daily grids: "
        "D:\\Downloads MKT\\HydroMeteorological Data\\Gridded Rainfall Data\\"
        "Gridded Rainfall Data 2015 to 2024\\rain\\2025.grd and the companion "
        "yearly files from 1995 onward.",
    )

    heading(doc, "13. Presentation maps", 1)
    para(
        doc,
        "The maps for the paper and for slides are drawn in Python by "
        "scripts/09_presentation_maps.py, using tilaiya/maps.py. ArcGIS and "
        "QGIS are not required for these figures. In Visual Studio Code the "
        "run configuration is named 09 Presentation maps. The plates are "
        "written to output\\figures\\maps at 300 dpi.",
    )
    para(
        doc,
        "Each plate is cropped to the watershed with a small margin. A shaded "
        "relief from the ALOS PALSAR DEM lies under the colour. The watershed "
        "outline is drawn on top. The frame is WGS 84 / UTM zone 45N, with a "
        "0.1 degree graticule, a kilometre scale bar, and a grid-north arrow. "
        "Classified soil loss uses the six annual classes: 0-5, 5-15, 15-30, "
        "30-50, 50-100, and greater than 100 t/ha/yr, coloured green to dark "
        "red. The continuous annual map is stretched from the 2nd to the 98th "
        "percentile so the long LS tail does not flatten the colours; the "
        "legend states that stretch. Monthly panels for one variable share a "
        "single legend. Monthly soil loss uses one scale from zero to the 98th "
        "percentile of the monthly values, so the extreme tail does not flatten "
        "the other months. Cover is drawn from 0 to 1. Rainfall, erosivity, and "
        "Km share a scale from zero to the maximum of the twelve months. "
        "Rainfall and erosivity repeat the IMD 0.25 degree cell value on the "
        "12.5 m grid, so the colour changes in "
        "blocks. Display is nearest-neighbour for classes, rainfall, and "
        "erosivity, so the renderer does not invent a gradient at those edges. "
        "The index of connectivity and the sediment delivery ratio use the "
        "same plate. Both are stretched from the 2nd to the 98th percentile, "
        "so a few extreme cells do not turn the catchment one dark colour. "
        "Those two plates are output\\figures\\maps\\IC_2025.png and "
        "SDR_2025.png. This step has been run.",
    )

    heading(doc, "14. Assumption checks for the manuscript", 1)
    para(
        doc,
        "scripts/10_assumption_checks.py was run after the maps, stacks, SHAP, "
        "and connectivity. It does not replace those results. It reads the "
        "completed tables and applies two published annual erosivity equations "
        "to the same five-cell monthly rainfall, splits the holdout errors by "
        "erosion class, records the fraction of watershed pixels that are valid "
        "in each month, and evaluates the delivery-ratio sigmoid at the median "
        "connectivity. This step has been run.",
    )
    para(
        doc,
        "On the five watershed cells, the sum of monthly Rm used in this study "
        "is 786 to 1,292. The corrected Arnoldus (1977) annual equation, "
        "R = 17.02 x 10^(1.50 x log10(sum of Pm^2 / P) - 0.8188), gives "
        "6,854 to 12,083 on the same rainfall. The Renard and Freimund (1994) "
        "equations give 16,451 to 35,708. Those equations were not fitted in "
        "this catchment. The comparison shows that the absolute erosivity, and "
        "therefore the absolute soil loss, depends on the coefficient pair. "
        "The monthly maps were not recalculated.",
    )
    para(
        doc,
        "Of 4,576,196 watershed pixels, 4,545,988 (99.3 percent) are valid in "
        "the ten months other than June and September. June is valid on 97.6 "
        "percent and September on 92.4 percent. The annual sum is valid on "
        "4,154,545 pixels, 90.8 percent of the watershed. Monthly means use "
        "each month's own valid pixels. The annual mean uses only the "
        "twelve-month intersection. No imputation was applied.",
    )
    para(
        doc,
        "Reduced Integrated holdout errors by class are small from E1 to E5 "
        "(MAE 0.37 to 2.46 t/ha/yr) and large in E6 (n = 27, MAE 74.0, "
        "RMSE 263). The same pattern holds for Dynamic Integrated, with E6 "
        "MAE 113. At the median IC of -7.66, the study sigmoid (IC0 = 0.5, "
        "k = 1.2, SDRmax = 0.8) gives SDR 0.000891. The same IC0 and SDRmax "
        "with k = 2 give SDR 0.0133 at that one cell. The connectivity raster "
        "was not recomputed. The 1,001 t/yr yield is 834 m3/yr at 1.20 t/m3 "
        "and 626 m3/yr at 1.60 t/m3.",
    )

    heading(doc, "15. Literature benchmark in the manuscript", 1)
    para(
        doc,
        "The journal manuscript now contains a literature review that places "
        "these calculations against published work. The benchmark papers are "
        "annual RUSLE for the Barakar (Biswas and Pani, 2015) and the Damodar "
        "(Ghosh et al., 2025), USLE sediment yield at Karso in Hazaribagh "
        "(Pandey et al., 2007), SWAT inflow to Tilaiya (Sardar et al., 2014; "
        "Dutta et al., 2017), the Indian USLE-factor review of Majhi et al. "
        "(2021), the erosivity-equation review of Chen et al. (2023), and the "
        "connectivity reviews of Walling (1983), Heckmann et al. (2018), and "
        "Hamel et al. (2015). Sardar et al. report a calibrated Tilaiya "
        "sedimentation rate of 0.76 million m3/yr. The primary structural "
        "yield on the Arnoldus maps is 10,257 m3/yr at the mask boundary "
        "(Section 21). An earlier structural yield of 690 m3/yr belongs to "
        "the retired erosivity maps and is not the reported figure. "
        "Manuscript Section 6.6 and Table 15 compare the reported mean "
        "(136 t/ha/yr), the median (21.7), the 33 percent of area above "
        "100 t/ha/yr, the July mean (65.4), and the gross volume "
        "(6.08 million m3/yr) with Ghosh et al. (2025), Biswas and Pani "
        "(2015), Borrelli et al. (2021), Sardar et al. (2014), Central Water "
        "Commission (2021), and Pandey et al. (2007). No raster was "
        "recalculated for that comparison. The abstract, Section 6.6, and "
        "the conclusions state the three findings of this study: the monthly "
        "split, with July equal to 65.4 of the annual mean of 136 t/ha; the "
        "median of 21.7 against a mean lifted by 33 percent of the area above "
        "100 t/ha/yr; and a gross volume above the reservoir rates with a "
        "structural yield of 10,257 m3/yr. The manuscript text is written by "
        "scripts/write_manuscript_docx.py.",
    )

    heading(doc, "16. Review diagnostics", 1)
    para(
        doc,
        "scripts/11_review_diagnostics.py was run after the literature revision. "
        "It reads completed rasters and tables. It does not redraw soil-loss "
        "maps, refit the stacks, replace the erosivity equation, cross-calibrate "
        "RVI to SAVI, or calibrate the delivery sigmoid. This step has been run.",
    )
    para(
        doc,
        "July Cm is at the 0.001 floor on 22.5 percent of finite pixels. August "
        "is at the floor on 16.3 percent. June has no pixel at the floor. The "
        "July median Cm is 0.208 and the June median Cm is 0.650. The aligned "
        "annual C layer has a minimum of 0.284 and no pixel below 0.15. Mean Km "
        "in the monthly table stays between 0.0393 and 0.0398 because each month "
        "is percentile-stretched on its own. On the five IMD cells, exponents "
        "1, 1.211, 1.5, and 2 leave the peak month unchanged, while the July "
        "share on the wettest cell rises from 0.57 to 0.87. Reduced and Dynamic "
        "XGBoost mean absolute SHAP for LS are 10.326 and 10.329, from separate "
        "files. The 27 holdout points above 100 t/ha/yr supply 99.5 percent of "
        "reduced-stack squared error. On 4,139,550 overlapping pixels the dynamic "
        "annual sum and the static annual map have means 9.32 and 8.94 t/ha/yr "
        "and Pearson correlation 0.93. Gross dynamic erosion of 603,597 t/yr is "
        "416,000 m3/yr at 1.45 t/m3. That volume is below the 0.76 million m3/yr "
        "Tilaiya rate in Sardar et al. (2014), including after a proportional "
        "extension from 715 km2 to the 984 km2 DVC catchment. The manuscript "
        "states that the sigmoid cannot be calibrated to that rate while the "
        "adopted erosivity pair is retained.",
    )

    heading(doc, "17. July median, rank correlation, and radar-cover scaling", 1)
    para(
        doc,
        "scripts/12_july_median_debug.py and scripts/13_rvi_savi_scaling.py "
        "were run. Neither script replaces SoilLoss rasters, the connectivity "
        "grids, or the trained stacks. This step has been run.",
    )
    para(
        doc,
        "On 4,465,002 pixels valid in both June and July, A_July/A_June equals "
        "(R_July/R_June) times (Km_July/Km_June) times (Cm_July/Cm_June) at every "
        "pixel. The median of that ratio is 0.889. Where July Cm exceeds 0.15 "
        "(2,628,051 shared pixels) the July median is 0.612 t/ha and the June "
        "median on those pixels is 0.455 t/ha. On the shared pixels, 52.4 percent "
        "of July values are below 0.01 t/ha. On the July cover-floor pixels the "
        "June median is 0.470 t/ha and the July median is 0.002 t/ha. The "
        "watershed-wide July median of 0.005 t/ha is that near-zero mass, not a "
        "broken product.",
    )
    para(
        doc,
        "On 4,139,550 pixels where the dynamic annual sum and the static annual "
        "map are both finite, Pearson r is 0.931, Spearman r is 0.989, and "
        "Pearson r of log10 soil loss is 0.941 (2,148,282 pixels above zero).",
    )
    para(
        doc,
        "SAVI was regressed on RVI using 80,000 pixels in each of January-June "
        "and September-December (800,000 pixels, seed 42). The fit is SAVI = "
        "0.235 + 0.098 RVI, with R2 = 0.033. Applying the line and the same "
        "cover equation raises the July median from 0.005 to 1.405 t/ha and the "
        "July mean from 3.54 to 10.17 t/ha, and the August median from 0.0017 "
        "to 0.372 t/ha. The July cover floor disappears under that line. The "
        "official maps were not replaced, because RVI does not predict SAVI in "
        "the months where both indices exist. Tables are "
        "output/tables/july_june_pixel_ratios.csv, "
        "july_june_same_pixel_summary.csv, annual_map_rank_correlation.csv, "
        "rvi_savi_fit.csv, and rvi_savi_cover_scaling.csv.",
    )

    heading(doc, "18. Cover classes, cover treatments, and the storage bulletin", 1)
    para(
        doc,
        "scripts/14_cover_bins_and_treatments.py was run. It does not replace "
        "the soil-loss rasters or the connectivity grids. This step has been run.",
    )
    para(
        doc,
        "On 4,465,002 shared June-July pixels, the pixels with July soil loss "
        "below 0.01 t/ha have median LS of 0 and median June soil loss of 0. "
        "Pixels at or above 0.01 t/ha have median LS of 1.44 and median June "
        "soil loss of 3.46 t/ha. The cover-floor class changes from a June "
        "median of 0.469 t/ha to a July median of 0.002 t/ha. Table "
        "output/tables/july_cover_bins.csv gives the five July-cover classes.",
    )
    para(
        doc,
        "On the 4,154,545 pixels with all twelve months valid, the annual mean "
        "is 9.30 t/ha/yr with unscaled RVI in July and August, 15.28 t/ha/yr "
        "if July and August cover is interpolated between June and September "
        "SAVI cover, and 17.72 t/ha/yr if the SAVI-on-RVI line is applied. "
        "July SAVI cover is finite on 114,325 of those pixels. August SAVI "
        "cover is finite on 2,859,576. The official maps were not replaced. "
        "Tables are output/tables/annual_mean_cover_treatments.csv and "
        "monthly_cover_treatments.csv.",
    )
    para(
        doc,
        "The CWC bulletin for 7 October 2021 lists Tilaiya live capacity at "
        "full reservoir level as 0.142 BCM and that day's live storage as "
        "0.142 BCM. It does not list 131.235 MCM. The manuscript therefore "
        "cites 131.235 MCM as the 2021 live capacity in Central Water "
        "Commission publication CWC/2021/147, and it no longer describes that "
        "figure as a weekly storage reading.",
    )

    heading(doc, "19. Near-zero share, zero LS, and the uncertainty envelope", 1)
    para(
        doc,
        "scripts/15_zero_ls_and_uncertainty.py was run. It does not replace "
        "the soil-loss rasters or the connectivity grids. The monthly maps "
        "on disk remain the radar-cover case. The primary numbers in the "
        "manuscript are the interpolated-optical means. This step has been run.",
    )
    para(
        doc,
        "On 4,465,002 pixels valid in both June and July, 48.2 percent have "
        "June soil loss below 0.01 t/ha and 52.4 percent have July soil loss "
        "below 0.01 t/ha. The June median is 0.479 t/ha and the July median "
        "is 0.005 t/ha. The LS factor is exactly zero on 44.3 percent of those "
        "pixels. LS is the combined slope-length and steepness factor in "
        "LS_aligned.tif, not the length factor L alone. The exact zeros are "
        "an artefact of whole-metre elevations. A continuous elevation model "
        "(Copernicus GLO-30 or FABDEM), a minimum slope in LS, routing to a "
        "Sentinel-1 shoreline, and calibration of the delivery sigmoid to the "
        "CWC live-storage loss were identified and not run in that script. "
        "The Copernicus and static-K cases were run later and are recorded below.",
    )
    para(
        doc,
        "The July cover class above 0.40 contains 909,368 shared pixels. "
        "Half of them have soil loss of exactly zero in both June and July. "
        "Of those zeros, 89 percent have LS exactly zero and 21 percent have "
        "P exactly zero. Median MNDWI in the class is -0.15, so the class is "
        "not open water. Median P is 0.50.",
    )
    para(
        doc,
        "On the 4,154,545 twelve-month pixels, cell-wise ratios to the "
        "corrected Arnoldus and Renard-Freimund annual equations give the "
        "means in output/tables/cover_by_erosivity_envelope.csv. The primary "
        "interpolated-optical mean is 15.28 t/ha/yr at the study erosivity "
        "(gross 0.684 million m3/yr at 1.45 t/m3), 136 t/ha/yr at Arnoldus "
        "(6.09 million m3/yr), and 347 t/ha/yr at Renard-Freimund "
        "(15.5 million m3/yr). The radar sensitivity is 9.30, 82.8, and "
        "211 t/ha/yr. The fitted line, from months other than July and "
        "August, is 17.7, 158, and 404 t/ha/yr.",
    )

    heading(doc, "20. Watershed boundaries", 1)
    para(
        doc,
        "scripts/17_tilaiya_watershed_boundaries.py was run. It does not "
        "replace soil-loss or connectivity rasters. This step has been run.",
    )
    para(
        doc,
        "The study mask is the single polygon in Watershed IARI Whole\\"
        "watershed_edited.shp. Its area is 715.02 km2. The script writes "
        "that polygon to output/shapefiles/Tilaiya_2A219_study_mask.shp, "
        "in WGS 84 / UTM zone 45N. This is the boundary used by the monthly "
        "maps. It is sub-watershed 2A219. This polygon is the final analysis "
        "boundary. The HydroBASINS catchment was drawn for comparison and "
        "is not used for soil loss, connectivity, or the reported areas.",
    )
    para(
        doc,
        "No Damodar Valley Corporation polygon for the 984 km2 Tilaiya "
        "catchment is stored in the project. The script dissolves the "
        "HydroBASINS v1c level-12 units that drain to HYBAS_ID 4120944082, "
        "the unit that contains Tilaiya Dam at 24 degrees 19 minutes 26 "
        "seconds N, 85 degrees 31 minutes 16 seconds E. Fifteen units are "
        "included. Their SUB_AREA values sum to 954.7 km2. The dissolved "
        "polygon measures 952.47 km2. The HydroBASINS UP_AREA stored on "
        "that outlet is 970.7 km2. The result is "
        "output/shapefiles/Tilaiya_dam_catchment_HydroBASINS.shp. Of the "
        "study mask, 702.54 km2 lies inside this polygon. The comparison "
        "map is output/figures/maps/Tilaiya_watershed_boundaries.png. "
        "The manuscript figure of the study area alone is "
        "output/figures/maps/Tilaiya_2A219_study_area.png. "
        "The table is output/tables/tilaiya_watershed_boundaries.csv.",
    )

    heading(doc, "21. Corrected Arnoldus soil loss", 1)
    para(
        doc,
        "scripts/18_arnoldus_soil_loss.py was run. It does not replace the "
        "stored SoilLoss or Erosivity rasters. Those rasters still use "
        "Rm = 1.8219 x (MFIm ^ 1.211). No primary paper was found for that "
        "pair, so it is not used for the reported results. This step has been run.",
    )
    para(
        doc,
        "The reported annual erosivity is the corrected Arnoldus (1977) "
        "equation stated by Chen et al. (2023): "
        "R = 17.02 x 10^(1.50 x log10(sum of Pm^2 / P) - 0.8188), "
        "in MJ mm / ha / h / year. The equation was estimated for Morocco. "
        "It was not fitted to Tilaiya storms, and it is not storm EI30. "
        "Each month receives Rm = R x (Pm^2 / sum of Pm^2). The twelve "
        "months sum to R. A dry month is zero. This split is not a second "
        "regression. Renard and Freimund (1994) is calculated as a second "
        "published annual total. It was fitted in the United States and is "
        "not used to draw the monthly maps.",
    )
    para(
        doc,
        "July and August cover in the reported maps is interpolated from "
        "the June and September optical cover factors: July = (2/3) June + "
        "(1/3) September, and August = (1/3) June + (2/3) September. "
        "Stored monthly soil loss is multiplied by the ratio of the new "
        "monthly erosivity to the stored erosivity. July and August are "
        "also multiplied by the ratio of interpolated cover to radar cover. "
        "The new rasters are output/rasters/SoilLoss_Arnoldus. "
        "The class map is output/figures/maps/SoilLoss_Arnoldus_annual_class_2025.png. "
        "The monthly plate is output/figures/maps/SoilLoss_Arnoldus_monthly_2025.png.",
    )
    para(
        doc,
        "On the five IMD cells, corrected Arnoldus annual R is 8,133, "
        "11,610, 6,854, 9,504, and 12,083. Cell 1 peaks in June. The other "
        "cells peak in July. On 4,154,545 pixels with all twelve months "
        "valid, the interpolated-cover mean is 135.86 t/ha/yr (median 21.7; "
        "gross 8.82 million t/yr; 6.08 million m3/yr at 1.45 t/m3). "
        "Radar cover on the same erosivity gives 87.17 t/ha/yr and "
        "3.90 million m3/yr. The Renard-Freimund annual total on the "
        "interpolated cover gives 346 t/ha/yr and 15.5 million m3/yr. "
        "Tables are output/tables/arnoldus_monthly_soil_loss.csv, "
        "arnoldus_annual_summary.csv, arnoldus_cell_erosivity.csv, "
        "arnoldus_june_july.csv, and arnoldus_july_cover_bins.csv.",
    )
    para(
        doc,
        "On the same 4,154,545 pixels, 48.2 percent are below 0.01 t/ha in "
        "both June and July. The June median is 4.65 t/ha and the July "
        "median is 9.92 t/ha. The LS factor is exactly zero on 44.4 percent "
        "of the pixels. Interpolated July cover has no pixels below 0.15. "
        "The existing SDR grid, which was not rebuilt, gives a primary yield "
        "of 14,873 t/yr (10,257 m3/yr). The delivery fraction is 0.00169. "
        "Matching 0.76 million m3/yr would need a mean delivery ratio near "
        "0.13. The mean of the SDR grid on these pixels is 0.00104.",
    )

    heading(doc, "22. Cited literature files", 1)
    para(
        doc,
        "scripts/19_download_cited_literature.py was run. It reads the "
        "reference list in scripts/write_manuscript_docx.py and asks "
        "Unpaywall for a legal open-access file. Closed papers were not "
        "downloaded from other sites. Thirteen PDFs were saved in "
        "literature/cited. The de Vente et al. (2013) repository file was a "
        "one-page corrigendum and was removed. MDPI and Springer returned a "
        "block page to the script, so those gold open-access papers were not "
        "saved even though they can be opened in a browser from the DOI. "
        "The USDA handbooks and the FAO bulletin were not at the public URLs "
        "that were tried. The status tables are "
        "output/tables/cited_literature_downloads.csv and "
        "output/tables/cited_literature_retry.csv. This step does not change "
        "any soil-loss, connectivity, or model result.",
    )
    heading(doc, "23. Static K, Copernicus GLO-30, and the annual-support comparison", 1)
    para(
        doc,
        "scripts/20_dem_k_sensitivity.py was run after the wording revision. "
        "It does not replace the Arnoldus soil-loss rasters or the connectivity "
        "grids. Static K, on the 4,138,768 pixels where K and Km are both "
        "finite, changes the mean from 136 to 119 t/ha/yr and the median from "
        "22.8 to 20.4. Gross volume changes from 6.08 to 5.32 million m3/yr, "
        "and the structural yield from 10,257 to 9,043 m3/yr. Copernicus "
        "GLO-30 tile N24 E085 was downloaded and bilinearly aligned to the "
        "12.5 m grid. The LS equation with the highest correlation against "
        "the published LS raster is USLE length with a slope-dependent "
        "exponent and the McCool steepness factor, using D8 accumulation, "
        "then scaled by 1.124. Pearson r is 0.771. That equation gives an "
        "annual mean of 103 t/ha/yr on the integer-metre DEM and 119 on "
        "Copernicus, with medians 64 and 62. Copernicus leaves 1.2 percent "
        "of LS values at exactly zero, against 44 percent in the published "
        "raster. Of the published zeros, 88 percent have a Copernicus slope "
        "steeper than 0.5 degrees. The excluded 421,649 watershed pixels "
        "have mean elevation 411 m against 388 m in the annual set, with "
        "nearly the same D8 flat share, October NDVI, and annual C. The "
        "support map is output/figures/maps/annual_support_mask.png. "
        "FABDEM, a spatially blocked holdout, and a public deposit were not "
        "run. The ALOS tiles on disk are int16. This step has been run.",
    )
    para(
        doc,
        "The manuscript prose in scripts/write_manuscript_docx.py was "
        "revised again after those runs. The title "
        "is unchanged. Spatiotemporal soil erosion dynamics is defined as the "
        "intra-annual and spatial variation of RUSLE-estimated soil loss "
        "during 2025. The abstract still opens with the need for the study "
        "and closes with the contribution, and it now states that plot, "
        "gauge, and bathymetry records were unavailable. Stacking is described "
        "as emulation of the annual RUSLE surface, and SHAP as an explanation "
        "of the XGBoost member and of that model-derived target. The delivery "
        "volume is called a structural scenario. The Arnoldus monthly factor "
        "is described as an empirical allocation by squared rainfall, and Km "
        "and the July–August cover as uncalibrated scenarios. Section 6.7 "
        "now reports the static-K and Copernicus scenarios, and Table 16 "
        "gives the calculated envelope. A spatially blocked holdout and a "
        "public data deposit were still not carried out. The reported "
        "Arnoldus rasters were not replaced.",
    )

    para(
        doc,
        "A later wording pass corrected the 6.08 million m3 figure so that it "
        "is the 8.82 million t soil-loss mass divided by 1.45 t/m3. Table 16 "
        "is described as a sensitivity comparison because the rows do not share "
        "one pixel support. The Copernicus structural yields are stated to use "
        "the existing delivery grid. The Sardar et al. (2014) publisher abstract "
        "still prints mm3/year. The typeset PDF was not opened, so the manuscript "
        "reads that string as million cubic metres per year and marks the reading "
        "as provisional. The stacking scores are called surrogate-model diagnostics. "
        "The data-availability statement says the files have not been deposited "
        "and that the paper is not a public reproduction package. No raster was recalculated.",
    )

    para(
        doc,
        "The Sardar et al. (2014) numerical comparison was removed. The "
        "publisher abstract still prints mm3/year, and the typeset PDF was "
        "not opened. The reservoir-volume comparison that remains uses the "
        "Central Water Commission live-storage loss of 1.01 million m3/yr. "
        "The statement that Table 16 rows do not share one pixel support was "
        "kept, as was the statement that the stacking holdout was not "
        "spatially blocked. A public repository was not created. The "
        "data-availability section does not describe the computing environment. "
        "It states that the scripts, tables, rasters, metadata, and checksum "
        "inventory have not yet been deposited and are available from the "
        "corresponding author. The statements on the absence of plot, gauge, "
        "and bathymetry observations, and on the absence of a spatially blocked "
        "holdout, were left in place. The checksum inventory remains "
        "output/tables/reproduction_manifest.csv. No soil-loss raster was recalculated.",
    )
    para(
        doc,
        "A public repository was then created at "
        "https://github.com/mktiwari123/Tilaiya-2A219-soil-erosion-2025. "
        "The data-availability section and the closing paragraph cite that "
        "address. They do not describe the computing environment. The "
        "statements on the absence of plot, gauge, and bathymetry observations, "
        "and on the absence of a spatially blocked holdout, remain. The "
        "checksum script omits Python bytecode. The deposited inventory is "
        "output/tables/reproduction_manifest.csv. No soil-loss raster was recalculated.",
    )
    para(
        doc,
        "A later wording pass restated the manuscript in direct sentences. "
        "Each definition now says what was calculated. Plot, gauge, and "
        "bathymetry observations remain unavailable, and the stacking holdout "
        "remains a random stratified split, with spatial blocks used inside "
        "training. No soil-loss raster was recalculated.",
    )
    para(
        doc,
        "Eight highlights were added to the manuscript after the keywords. "
        "They restate results already calculated: the 2025 monthly maps, "
        "Arnoldus erosivity, interpolated July and August cover, the reported "
        "mean and median, the whole-metre LS zeros, the soil-loss mass and "
        "structural yield, the scenario envelope against the Central Water "
        "Commission live-storage loss, and the stacking emulation. No "
        "soil-loss raster was recalculated.",
    )
    para(
        doc,
        "The manuscript now presents sub-watershed 2A219 as ungauged for "
        "sediment. Erosion plots, a sediment station on this mask, and a 2025 "
        "bathymetric survey are unavailable. Published sediment records are "
        "stated to describe Karso, Banha, earlier Tilaiya streamflow, or "
        "live-storage change for the whole dam. The 2025 load of the 715 km2 "
        "mask is therefore estimated from rainfall, satellite cover, soil "
        "grids, and elevation. No soil-loss raster was recalculated.",
    )
    para(
        doc,
        "Chen et al. (2023), literature/cited/13_Chen_2023.pdf, was read. "
        "The manuscript equation uses 17.02 and -0.8188. Chen et al. defend "
        "that SI conversion and list 1.735 and -0.08188 among the incorrect "
        "copies. Replacing 17.02 with 1.735 would lower R by a factor of 9.8. "
        "The mapped mean of 136 t/ha/yr was kept as one scenario and was set "
        "against Damodar means near 12 t/ha/yr, the 44 percent zero-LS cells, "
        "July cover near 0.58, and a 14 percent change when K is held static. "
        "The reservoir loss of 1.01 million m3/yr is 10.3 t/ha/yr at 1.0 t/m3 "
        "and 14.9 t/ha/yr at 1.45 t/m3 over 98,420 ha. The structural yield was "
        "removed from the title, abstract, highlights, and conclusions. "
        "Connectivity was not rebuilt and was not calibrated to the storage "
        "survey. The title is now a scenario title. Stacking and SHAP were "
        "moved to a supplement. The 7 October 2021 bulletin sentence was "
        "removed. No soil-loss raster was recalculated.",
    )
    para(
        doc,
        "scripts/22_cover_erosivity_budget.py was run. It does not replace "
        "the Arnoldus soil-loss rasters. Monthly soil loss was rescaled by "
        "van der Knijff cover, C = exp(-2 * NDVI / (1 - NDVI)), with July "
        "and August NDVI interpolated from June and September. The mean falls "
        "from 136 to 27.6 t/ha/yr, and the area above 100 t/ha/yr falls from "
        "33 percent to 5.8 percent. Erosivity-weighted cover is 0.579 linear "
        "and 0.167 exponential. The Raj et al. (2022) IRED R-factor, Zenodo "
        "10.5281/zenodo.6505510, was sampled on the annual pixels. Its mean "
        "is 772 MJ mm/ha/h/yr, against an Arnoldus mean of 7,783. Substituting "
        "that magnitude lowers the linear-cover mean to 12.9. Both replacements "
        "give 2.88. Das et al. (2025) grids are available on request and were "
        "not sampled. The aligned P grid is 0, 0.5, and 1. The annual-project "
        "land-cover table (built-up 0.002, cropland 0.28, vegetation 0.005, "
        "water 0, barren 1) is not that grid. The LS equation is not recorded "
        "in either project's scripts. Mean LS on the annual support is 1.38. "
        "Delivery was moved to a supplement. Sections were renumbered 6.1-6.5 "
        "and 7.1-7.2. The live-storage loss is described as a lower bound on "
        "sediment retained in the reservoir. This step has been run.",
    )
    para(
        doc,
        "scripts/23_delivery_window.py was run. It leaves the Arnoldus "
        "soil-loss rasters in place. Area curves stated by Lim et al. (2005) "
        "were evaluated at 715 km2 and at the official 984 km2 catchment: "
        "Vanoni (1975) SDR = 0.4724 A^(-0.125), USDA (1972) "
        "SDR = 0.5656 A^(-0.11), and Boyce (1975) SDR = 0.3750 A^(-0.2382). "
        "None is calibrated at Tilaiya. On 984 km2 the Vanoni ratio is 0.20 "
        "and the gross rate that would supply the live-storage loss of "
        "10.3-14.9 t/ha/yr is 51-75 t/ha/yr. USDA gives 39-56 and Boyce gives "
        "141-205. Every cover and erosivity mean was tested against that "
        "yield and against the Vanoni band. Linear cover with Arnoldus R "
        "(136) sits above the band, with an implied delivery ratio of "
        "0.076-0.11. Exponential NDVI cover (27.6) and the land-cover lookup "
        "used as cover (28.8 on all 4,154,545 annual pixels, nearest class) "
        "exceed the yield and sit below the band, with implied ratios near "
        "0.4-0.5. Linear cover with the India-grid magnitude (12.9) implies "
        "a ratio of 0.79-1.15 and falls short of the 14.9 t/ha/yr bound. "
        "Both replacements (2.88) lie below the yield. The sentence that "
        "12.9 meets the reservoir rate was removed. The erosivity-weighted "
        "cover ratio is 3.56; weighting by R times LS raises it to 4.70, and "
        "the soil-loss mean ratio is 4.92, so the extra drop is mostly "
        "covariance with LS. On the nearest class, cropland is P = 0.5, "
        "vegetation and barren land are P = 1, and built-up is P = 0. "
        "The small land-cover table values were the lookup cover. "
        "The IRED workbook gives Hazaribagh district 690, Jharkhand state "
        "1,198, and the Jharkhand subdivision 1,224. The mask sample is 772. "
        "A Cherrapunji cell on the same grid is 10,206. Raj et al. "
        "(EGU22-152) report 3,312 for East and Northeast India. Das et al. "
        "(2025) monthly maps were not obtained; they are available from the "
        "corresponding author on request, so the Pm^2 monthly split was not "
        "tested. Ghosh et al. (2025) use R = 0.363 P + 79 (R about 507-983). "
        "Biswas and Pani (2015) use the Renard-Freimund monthly average. "
        "Their soil-loss means are therefore not a check on the Arnoldus "
        "equation. The van der Knijff coefficient is the European value and "
        "is uncalibrated here; July-August NDVI is interpolated, with clear "
        "July data on 2.8 percent of annual pixels, before the exponential. "
        "The reasoned window is the Vanoni band of 51-75 t/ha/yr, widened "
        "to about 39-205 by the USDA and Boyce curves. No calculated row "
        "falls inside 51-75. The rainfall factor is left as the bracket "
        "772-7,783. This step has been run.",
    )
    para(
        doc,
        "scripts/24_class_share_and_practice.py was run. It leaves the "
        "Arnoldus soil-loss rasters in place. Setting P to 1 wherever the "
        "current practice factor is positive raises the linear-cover mean "
        "from 136 to 182 t/ha/yr (median 34.3; 40 percent of the area above "
        "100). Pixels with P = 0 stay at zero. Cropland mean loss rises from "
        "90 to 174. On the linear-cover map, vegetation is 40 percent of the "
        "area and 60 percent of the mass, and barren land is 2.2 percent of "
        "the area and 3.2 percent of the mass. Under the exponential cover, "
        "barren land is 8.2 percent of the mass. Under the five-class lookup, "
        "barren land is 23 percent of the mass and vegetation is 2.9 percent. "
        "The land-cover source grid is LULC_2025_RF_v2, uint8, EPSG:4326, "
        "0.00009 degrees (about 10 m), five classes. The aligned copy is "
        "12.5 m float32. No classifier, training sample, satellite input, or "
        "accuracy is stored with the raster or in the project scripts. "
        "Vegetation is one class. The India-grid value of 772 is described "
        "as a low-biased floor. The Jharkhand average in the IRED workbook, "
        "1,198, is the comparison. The East and Northeast abstract value of "
        "3,312 was removed from the highlights and from the comparison. "
        "Das et al. (2025) monthly maps were not obtained; they remain the "
        "test of the Pm^2 allocation. July is about half the annual mean, "
        "and an HLS or relaxed-cloud composite was not calculated. The "
        "connectivity supplement was dropped. The grid mean delivery ratio "
        "of 0.00105 is about 200 times the Vanoni ratio of 0.20, and the "
        "grid was not calibrated. The reservoir curves do not choose between "
        "the means near 28 and the means from 136 to 182. This step has been "
        "run.",
    )
    para(
        doc,
        "The manuscript discussion was rewritten after a reading of "
        "Tilaiya_Manuscript_Draft. No new raster was calculated. Section 7 "
        "now says the monthly maps time the July peak and do not size the "
        "load, that the mean of 136 is a zero-LS class plus a high tail, and "
        "that class shares rank the cover scenarios more sharply than the "
        "reservoir curves. The Km stretch is described as seasonally null, "
        "so the seasonal pattern that remains is rainfall. The two "
        "measurements named as further work are the Das et al. (2025) "
        "monthly erosivity surfaces, which were not obtained, and an "
        "observed July-August NDVI from HLS or a relaxed-cloud composite, "
        "which was not calculated. Repeated local literature was cut to the "
        "telling in Section 2. The unverified Sardar et al. (2014) rate of "
        "0.76 mm3/year is stated once and is not used as a benchmark. "
        "Sentences that still promised a structural yield were aligned with "
        "the decision to set the connectivity grid aside. The stacking "
        "holdout R2 is described as recovery of the RUSLE surface from its "
        "own factors. Main-text tables that followed Table 8 were numbered "
        "9 to 15 in reading order, the supplement tables were numbered S1 to "
        "S5, Figure 25 became Figure 13, and the supplement figures became "
        "Figures 14 to 23. This revision has been written into the manuscript "
        "generator and regenerated. It has been run as a document revision, "
        "not as a new calculation.",
    )
    para(
        doc,
        "scripts/25_zero_ls_provenance.py was run. It does not replace the "
        "published LS raster or the Arnoldus soil-loss rasters. On the "
        "4,154,545 annual pixels, published LS is exactly zero on 1,842,858 "
        "pixels (44.4 percent). Of those zeros, water is 2.7 percent. Cells "
        "with no D8 drop and an accumulation of one cell, excluding water, "
        "are 40.4 percent. Cells with no D8 drop that still receive flow are "
        "1.2 percent, and their median accumulation is two cells. Cells with "
        "a positive D8 drop are 55.7 percent. Their median integer slope is "
        "8 percent, a one-metre step across 12.5 m, and 95.3 percent of them "
        "have an accumulation of one cell. Copernicus D8 slope exceeds 0.5 "
        "degrees on 88.6 percent of the zeros, with a median slope of 3.2 "
        "percent. The published raster does not record a routing tool, so it "
        "is not assigned to Desmet and Govers, Hickey, or Wischmeier and "
        "Smith. The equations scored in script 20 remain steepest-descent "
        "D8. USLE length with the McCool steepness factor correlates at "
        "0.77. The Moore and Burch contributing-area form correlates at "
        "0.76. The Hickey cumulative-length cutoff was not calculated. In "
        "the D8 equation, LS is zero only where the steepest descent is "
        "zero. This step has been run.",
    )
    para(
        doc,
        "scripts/26_ic0_recentering.py was run. It leaves the stored IC "
        "raster and the default SDR raster in place. The sigmoid remains "
        "SDR = 0.8 / (1 + exp((IC0 - IC) / 1.2)). On 4,576,196 pixels the "
        "mean IC is -7.73 and the median is -7.66. With IC0 = 0.5 the mean "
        "SDR is 0.00105 and the median is 0.000891, and the mass-weighted "
        "ratio on the linear-cover map is 0.00169, which recovers the "
        "earlier delivered mass of 14,873 t/yr. Setting IC0 to the median "
        "IC gives a median SDR of 0.40, a mean of 0.392, and a mass-weighted "
        "ratio of 0.471. Setting IC0 to the mean IC gives a mean SDR of "
        "0.403. Forcing the unweighted mean to 0.15, 0.20, and 0.25 requires "
        "IC0 of -5.82, -6.29, and -6.69. The mass-weighted ratios are then "
        "0.206, 0.265, and 0.322. Those three thresholds are chosen to match "
        "the area-curve window. They are not the median IC. The comparison "
        "in the manuscript keeps the area curves. A sensitivity raster, "
        "output/rasters/sensitivity/SDR_IC0_at_median.tif, stores the "
        "median-centered ratio. This step has been run.",
    )
    para(
        doc,
        "scripts/27_km_annual_range.py was run. It leaves the stored monthly "
        "Km rasters and the Arnoldus soil-loss rasters in place. Km remains "
        "K times (1 + 0.25 times theta). Mean VV on the map pixels is -11.1 dB "
        "in January and -8.76 dB in July. The literal annual minimum and "
        "maximum are -33.89 and 16.42 dB. On that range, mean Km is 0.0392 "
        "in January and 0.0399 in July, and the annual mean on 4,138,768 "
        "pixels is 134.3 t/ha/yr (median 22.9; 33.2 percent above 100). The "
        "pooled 5th and 95th percentiles are -14.17 and -6.63 dB. With those "
        "bounds, mean Km is 0.0387 in January and 0.0416 in July, the July "
        "mean is 68.1 t/ha, and the annual mean is 140.5 t/ha/yr (median "
        "23.6; 34.0 percent above 100). Each pixel's own annual minimum and "
        "maximum gives an annual mean of 140.5 t/ha/yr, with mean Km of "
        "0.0379 in January and 0.0423 in July. The 0.25 coefficient still "
        "caps the monthly increase at 25 percent of base K. The reported "
        "maps keep the within-month stretch. Sensitivity rasters are "
        "output/rasters/sensitivity/SoilLoss_annual_Km_annual_minmax.tif and "
        "SoilLoss_annual_Km_annual_p5p95.tif. This step has been run.",
    )
    para(
        doc,
        "scripts/28_cover_benchmarks.py was run. It leaves the soil-loss "
        "rasters and the cover layers in place. Erosivity-weighted cover "
        "was accumulated by nearest land-cover class for the linear factor "
        "and for the van der Knijff exponential of NDVI, using the same "
        "June-September interpolation for July and August as the reported "
        "maps. On the annual support the linear class means are built-up "
        "0.709, cropland 0.607, vegetation 0.508, water 0.711, and barren "
        "land 0.664. The exponential class means are 0.359, 0.201, 0.071, "
        "0.392, and 0.329. July means by class stay within 0.02 of those "
        "annual values. These means are written to "
        "output/tables/cover_by_class_versus_benchmarks.csv. They were set "
        "beside the Karso handbook assignments of Jain and Kothyari (2000), "
        "the Barakar assignments of Biswas and Pani (2015), and the "
        "CSWCRTI Dehradun plot values of Narain et al. (2001). No Chota "
        "Nagpur runoff-plot table was obtained, and the mapped linear cover "
        "was not replaced. This step has been run.",
    )
    para(
        doc,
        "A submission pass restated three calculated sensitivities and did "
        "not write a new raster. The aligned Sentinel-1 stack is the twelve "
        "months of 2025, so the Km bounds in scripts/27_km_annual_range.py "
        "are the full extremes available here. Literal annual minimum and "
        "maximum leave mean Km at 0.0392 in January and 0.0399 in July. "
        "The published LS raster still records no flow-accumulation tool, "
        "length equation, or sink-filling threshold. The comparison equation "
        "in scripts/20_dem_k_sensitivity.py is D8 steepest descent on the "
        "stored whole-metre DEM with no depression fill: LS = (lambda / "
        "22.13)^m times the McCool S, multiplied by 1.12, and LS is zero "
        "where the steepest descent is zero. Priority-flood filling belongs "
        "to the connectivity index, not to that LS test. scripts/26_ic0_recentering.py "
        "already stores the median-centered case: mass-weighted SDR 0.471, "
        "delivered 4.16 million t/yr, or 2.87 million m3/yr at 1.45 t/m3. "
        "That ratio sits above the Vanoni ratio of 0.20 and the Boyce ratio "
        "of 0.073. The stored SDR raster remains at IC0 = 0.5, and the "
        "manuscript comparison keeps the area curves. This pass has been "
        "written into the manuscript. No new raster was calculated.",
    )
    para(
        doc,
        "Three scripts were added for Visual Studio and have not been run. "
        "scripts/29_ls_sinkfill_mfd.py fills closed pits on the stored "
        "whole-metre DEM by priority-flood and recalculates D8 USLE-McCool "
        "length and a multiple-flow Desmet-Govers length. It does not "
        "replace output/rasters/LS/LS.tif. Equal-metre plateaus stay flat "
        "after a pit fill. Copernicus GLO-30 already lowered the zero share "
        "to 1.2 percent and left the annual mean at 119. "
        "scripts/30_sdr_vanoni_threshold.py writes "
        "output/rasters/sensitivity/SDR_IC0_vanoni_0.20.tif at IC0 = -6.2868, "
        "the threshold whose unweighted mean SDR is 0.20. The stored SDR "
        "raster stays at IC0 = 0.5. The mass-weighted ratio at that threshold "
        "is 0.265 and the delivered volume is 1.61 million m3/yr. Paths end "
        "at the catchment outlet. scripts/31_km_multiyear_envelope.py "
        "inventories Tilaiya_2020 through Tilaiya_2025 monthly stacks. Only "
        "2025 is present, so a multi-year Km envelope cannot be calculated "
        "until those years are aligned. These three scripts are coded and "
        "have not been run. The manuscript planning range of 51-75 t/ha/yr "
        "uses the Vanoni ratio and the live-storage loss already calculated. "
        "It is not a new RUSLE raster.",
    )
    para(
        doc,
        "scripts/30_sdr_vanoni_threshold.py was run. It writes "
        "output/rasters/sensitivity/SDR_IC0_vanoni_0.20.tif at IC0 = -6.2868. "
        "On 4,576,196 pixels the unweighted mean SDR is 0.200 and the median "
        "is 0.193. On the published linear-cover map the mass-weighted ratio "
        "is 0.265 and the delivered volume is 1.61 million m3/yr. The stored "
        "SDR raster was not replaced. scripts/32_copernicus_vanoni_delivery.py "
        "was run. It multiplies output/rasters/sensitivity/SoilLoss_annual_copernicus_LS.tif "
        "by that ratio. On 4,138,768 pixels the Copernicus gross mean is "
        "118.8 t/ha/yr and the median is 62.4. The mass-weighted ratio is "
        "0.214. Delivered volume is 1.14 million m3/yr. The delivered grid is "
        "output/rasters/sensitivity/Delivered_copernicus_LS_IC0_vanoni.tif. "
        "The Copernicus LS grid itself was calculated earlier by "
        "scripts/20_dem_k_sensitivity.py and was not recalculated in this "
        "pass. The manuscript calls 51-75 t/ha/yr the hydrologically "
        "reconciled consensus because that is the gross rate implied by the "
        "live-storage loss at SDR 0.20, and the Copernicus median falls "
        "inside it. This step has been run.",
    )
    para(
        doc,
        "scripts/33_copernicus_mfd_ls.py was run. It leaves the published "
        "LS raster and the Arnoldus soil-loss rasters in place. Copernicus "
        "GLO-30 on the 12.5 m grid is routed by slope-proportional multiple "
        "flow. LS = 1.4 * (A_s / 22.13)^0.4 * (sin beta / 0.0896)^1.3, "
        "with A_s the contributing area per unit width. LS is zero only "
        "where every neighbour is level or higher. On 4,154,545 annual "
        "pixels the zero share is 1.04 percent, the soil-loss median is "
        "71.9 t/ha/yr, and the mean is 139.6. The 0-5 class is 10.7 percent "
        "and the class above 100 is 40.6 percent. Outputs are "
        "output/rasters/sensitivity/LS_copernicus_mfd_desmet.tif, "
        "SoilLoss_annual_copernicus_mfd.tif, and "
        "output/tables/copernicus_mfd_desmet.csv. This step has been run.",
    )
    para(
        doc,
        "scripts/34_sdr_vanoni_spatial.py was run. It leaves the stored "
        "SDR raster at IC0 = 0.5. The routing map is "
        "output/rasters/sensitivity/SDR_IC0_vanoni_0.20.tif, with IC0 = "
        "-6.29. On the multiple-flow Copernicus soil-loss grid the "
        "unweighted mean ratio is 0.200, the mass-weighted ratio is 0.215, "
        "and the delivered volume is 1.35 million m3/yr. The highest fifth "
        "of the ratio carries 37.7 percent of that mass. Rainfall cell 4 "
        "carries 44.6 percent and cell 3 carries 46.9 percent. The map is "
        "output/figures/maps/SDR_IC0_vanoni.png. Paths end at the catchment "
        "outlet. This step has been run.",
    )
    para(
        doc,
        "scripts/31_km_multiyear_envelope.py was run. It inventories "
        "data/aligned/Tilaiya_YYYY_MM.tif for 2020 through 2025 and writes "
        "output/tables/km_multiyear_availability.csv. Twelve of 72 months "
        "are present, all of them 2025. The first missing file is "
        "Tilaiya_2020_01.tif, and 60 months are missing. No multi-year Km "
        "was calculated, and the stored Km rasters were not replaced. The "
        "2025 envelope, already calculated by scripts/27_km_annual_range.py, "
        "leaves January and July mean Km at 0.0392 and 0.0399 under the "
        "literal annual minimum and maximum. This step has been run.",
    )
    para(
        doc,
        "The manuscript now states the three roles of the cover spread. "
        "Linear cover, 136 t/ha/yr, is the uncalibrated upper bound: the "
        "adopted SAVI coefficient 1.18 leaves cropland at 0.61 and vegetation "
        "at 0.51, above the published factors. Exponential cover, 27.6 t/ha/yr, "
        "is the lower bound from the European van der Knijff coefficient, "
        "which was not fitted at Tilaiya. The band 51-75 t/ha/yr is the "
        "planning target implied by the live-storage loss at SDR 0.20. No "
        "new raster was calculated. This restatement has been written into "
        "the manuscript.",
    )
    para(
        doc,
        "Section 6.6 of the manuscript now states the holdout comparison "
        "in the main text. On 3,809 points the Reduced Integrated perceptron "
        "has R2 0.920, XGBoost 0.451, and Random Forest 0.443. Class E6, "
        "27 points above 100 t/ha/yr, has stack RMSE 263. The largest "
        "training soil loss is 909 and the largest holdout value is 2,769. "
        "A tree returns a leaf value and cannot pass that training maximum. "
        "The perceptron is continuous and can follow the RUSLE product past "
        "it. No model was retrained, and the maps were not changed. This "
        "restatement has been written into the manuscript.",
    )
    para(
        doc,
        "Figures 11 and 13 were redrawn so the patterns can be read in the "
        "manuscript. July Km uses the 2nd to 98th percentile of that month. "
        "The monthly soil-loss plate uses a shared scale of 0 to 50 t/ha/month, "
        "with higher values saturated. Figure 12 is the existing annual class "
        "map. Images are flattened onto a white background before they are "
        "placed in the Word file. No soil-loss raster was recalculated.",
    )
    para(
        doc,
        "The manuscript introduction now states the Central Water Commission "
        "live-storage loss of 1.01 million m3/yr as the reason for mapping "
        "sub-watershed 2A219. Section 5.6 presents IC0 = -6.29 as a "
        "calibration of the literature default 0.5, not as a discarded grid. "
        "Table 17 in the main text reports the holdout member scores. "
        "Figure 14 is a logarithmic cumulative distribution of the annual "
        "Arnoldus map, and Figure 15 places that class map beside the "
        "calibrated delivery ratio. No new soil-loss raster was calculated. "
        "This restatement has been written into the manuscript.",
    )
    para(
        doc,
        "scripts/35_dem_satellite_ls.py was run. It conditions three "
        "satellite elevations with the same sequence and does not replace "
        "the published LS raster or the Arnoldus soil-loss maps. ALOS PALSAR "
        "is the stored whole-metre L-band DEM. Copernicus GLO-30 is the "
        "aligned TanDEM-X grid. SRTM is the C-band 1-arc-second tile "
        "N24E085 from elevation-tiles-prod, written as data/dem/SRTM_N24E085.tif "
        "and bilinearly warped to output/rasters/sensitivity/SRTM_GL1_12m5.tif. "
        "ASTER GDEM was not retrieved because e4ftl01.gsfc.nasa.gov did not "
        "resolve. Each surface is filled by a Barnes priority flood from "
        "the mask boundary. Remaining level cells rise by 1 mm per cell "
        "away from a draining neighbour. LS then uses the Desmet-Govers "
        "multiple-flow form in scripts/33_copernicus_mfd_ls.py, with no "
        "1.12 scale. On 4,154,545 pixels, ALOS is flat on 38.5 percent of "
        "cells before and after the fill, the pit share is zero, and after "
        "the millimetre step the LS zero share is 13.6 percent, the soil-loss "
        "median is 93.8 t/ha/yr, and the mean is 144.3. Copernicus is flat "
        "on 1.04 percent before the fill and 5.39 percent after it, with a "
        "pit share of 4.80 percent; after the millimetre step the zero share "
        "is 3.30 percent, the median is 67.8, and the mean is 136.3. SRTM is "
        "flat on 2.51 percent before the fill and 15.1 percent after it, "
        "with a pit share of 13.3 percent; after the millimetre step the "
        "zero share is 7.71 percent, the median is 77.1, and the mean is "
        "136.4. Cells gentler than 0.5 degrees are 38.5, 13.7, and 18.8 "
        "percent. The unfilled Copernicus multiple-flow grid from script 33 "
        "remains the corrected terrain. Outputs are "
        "output/rasters/sensitivity/LS_alos_filled_mfd.tif, "
        "LS_copernicus_filled_mfd.tif, LS_srtm_filled_mfd.tif, the matching "
        "conditioned DEM and annual soil-loss grids, and "
        "output/tables/dem_satellite_ls.csv. This step has been run.",
    )
    para(
        doc,
        "scripts/35_dem_satellite_ls.py was run again for ASTER only. "
        "ALOS, Copernicus, and SRTM were not recalculated. The elevation "
        "file is data/dem/ASTGTMV003_N24E085_dem.tif, the ASTER GDEM v3 "
        "tile for 24-25 N and 85-86 E. ASTER GDEM is a Terra optical stereo "
        "surface, not radar. The companion stack-count file "
        "ASTGTMV003_N24E085_num.tif was not used as elevation. Neighbouring "
        "tiles are on disk, and the reference grid lies inside N24E085, so "
        "they were not mosaicked. The elevation band was bilinearly warped "
        "to output/rasters/sensitivity/ASTER_GDEM_12m5.tif. The same Barnes "
        "priority flood from the mask boundary, the 1 mm drainage step, and "
        "the Desmet-Govers multiple-flow form in scripts/33_copernicus_mfd_ls.py "
        "were applied, with no 1.12 scale. This step has been run. On "
        "4,154,545 pixels, ASTER is flat on 1.24 percent of cells before "
        "the fill and on 23.7 percent after it, so the fill increases the "
        "flat share. The pit share is 23.3 percent. After the millimetre "
        "step the LS zero share is 10.5 percent, 25.4 percent of cells are "
        "gentler than 0.5 degrees, the soil-loss median is 116.7 t/ha/yr, "
        "and the mean is 219.9. The 0-5 class is 30.2 percent and the class "
        "above 100 is 53.2 percent. The median of 116.7 does not lie in "
        "the 51-75 band. The mean of 219.9 is not the planning consensus. "
        "The planning target of 51-75 remains the Vanoni gross rate. The "
        "unfilled Copernicus multiple-flow grid from script 33 remains the "
        "corrected terrain. Outputs are "
        "output/rasters/sensitivity/LS_aster_filled_mfd.tif, "
        "DEM_aster_conditioned.tif, SoilLoss_annual_aster_filled_mfd.tif, "
        "and the aster row of output/tables/dem_satellite_ls.csv. The "
        "published LS raster and the Arnoldus soil-loss maps were not "
        "replaced.",
    )
    para(
        doc,
        "After the later DEM edits, the manuscript was read again for "
        "sentences that still set the connectivity grid aside. The "
        "discussion opening still said that Section 6.4 tests the scenarios "
        "against the yield and the area curves. That sentence now keeps "
        "the calibrated map at IC0 = -6.29 (Figure 2) as the routing map "
        "and the Vanoni, USDA, and Boyce curves as the lumped check. "
        "Section 5.6 already points to that map, to the highest fifth of "
        "the ratio, and to rainfall cells 3 and 4, and it keeps the paths "
        "at the outlet of sub-watershed 2A219. No new raster was written. "
        "This restatement has been written into the manuscript.",
    )
    para(
        doc,
        "This prose pass records that the unfilled Copernicus multiple-flow "
        "grid is the primary terrain result in the manuscript, no new raster "
        "was written, and the published LS raster was not replaced.",
    )
    para(
        doc,
        "The introduction now opens on three results already calculated. "
        "Replacing erosivity moves the annual mean by about a factor of ten, "
        "and replacing cover moves it by about a factor of five. July "
        "contains about half of the linear-cover annual mean. The Central "
        "Water Commission live-storage loss of 1.01 million m3/yr, at a "
        "Vanoni delivery ratio of 0.20, is the benchmark that sets the "
        "51-75 planning band. No new raster was calculated. This "
        "restatement has been written into the manuscript.",
    )
    para(
        doc,
        "Section 6.5 now leads with the topographic result. Whole-metre "
        "storage forces LS to zero on 44.36 percent of annual-support pixels "
        "and holds the median at 21.7 t/ha/yr. The unfilled Copernicus "
        "multiple-flow grid brings the zero share to 1.0 percent and the "
        "median to 72, with the mean remaining 140 because 41 percent of "
        "the area exceeds 100. The monthly series holds the legacy grid "
        "fixed so that July is a timing result. No new raster was calculated.",
    )
    para(
        doc,
        "Section 5.6 now leads with the connectivity calibration. On this "
        "plateau the default threshold IC0 = 0.5 returns a mean delivery "
        "ratio of 0.00105, and the Vanoni ratio of 0.20 is about 190 times "
        "that mean. Moving only the threshold to -6.29 sets the unweighted "
        "mean ratio to 0.20. On the multiple-flow Copernicus soil-loss grid "
        "that ratio carries 1.35 million m3/yr to the outlet of sub-watershed "
        "2A219. The shoreline remains outside the mask. No new raster was "
        "calculated.",
    )
    para(
        doc,
        "A wording pass restated the legacy slope-length comparison, the "
        "monthly baseline, the three cover formulations, and the unused "
        "radar-to-optical fit as design choices, and recast the study-area "
        "prose. This pass has been written into the manuscript, and no new "
        "raster was calculated.",
    )
    para(
        doc,
        "The manuscript was revised against the suggestions in "
        "C:\\Users\\tiwar\\Desktop\\revisions.docx. The abstract separates "
        "seasonal timing from the size of the annual load. Section 6.4 "
        "opens on the Central Water Commission 68-year live-storage survey "
        "as the benchmark for the 51-75 band. Section 6.6 states that the "
        "perceptron reproduces the multiplicative surface and that RMSE 263 "
        "on the class above 100 is the stack. Section 7.2 pairs the "
        "integer-metre zero class with the Copernicus multiple-flow median "
        "of 72 and mean of 140. Mediterranean scrub, elevations of 364 to "
        "628 m, Archean gneiss, and a Sentinel-2 accuracy test of the class "
        "map were not added. Flow paths still end at the catchment outlet. "
        "No new raster was calculated.",
    )
    para(
        doc,
        "The listed revisions in C:\\Users\\tiwar\\Desktop\\revisions.docx "
        "were written into the manuscript. The abstract opens on the "
        "separation of seasonal timing from annual size. The study area "
        "states the measured ALOS range, 312 to 670 m, rather than "
        "364 to 628 m. The class map is compared with Sentinel-2 SAVI. "
        "No classifier accuracy score was calculated. Section 5.6 "
        "recalibrates IC0 from 0.5 to -6.29 and carries 1.35 million "
        "m3/yr to the 2A219 outlet. Section 6.1 states that July times "
        "the pulse while Arnoldus erosivity on the five cells runs from "
        "6854 to 12083. Section 6.4 opens on the 68-year live-storage "
        "benchmark. Section 6.6 opens on the perceptron against the trees. "
        "The shoreline, Mediterranean scrub, Archean gneiss, and the "
        "span 2827 to 12083 were not inserted. No new raster was calculated.",
    )
    para(
        doc,
        "The abstract cadence for the Copernicus result was rewritten. "
        "Unfilled multiple-flow Desmet-Govers routing on Copernicus GLO-30 "
        "reduces the zero slope-length class from 44.36 percent to 1.0 "
        "percent. The median of 72 t/ha/yr lies in the 51-75 planning band "
        "and the mean of 140 does not, with 41 percent of the map still "
        "above 100. The monthly series holds one slope-length grid, and "
        "July accounts for about half the linear-cover annual detachment. "
        "The phrase that the median directly matches the planning target "
        "was not used. No new raster was calculated.",
    )
    para(
        doc,
        "Section 6 now states why both terrain grids are reported. The "
        "legacy ALOS slope-length grid is kept for the twelve-month series "
        "so month-to-month differences are erosivity and cover. The unfilled "
        "Copernicus GLO-30 multiple-flow grid is the annual terrain result. "
        "It reduces the zero class from 44.36 percent to 1.0 percent. Its "
        "median of 72 t/ha/yr lies in the 51-75 band implied by the "
        "live-storage loss at a Vanoni ratio of 0.20. Its mean of 140 does "
        "not, so the text does not say that gross erosion is reconciled "
        "with the reservoir sedimentation record. No new raster was calculated.",
    )
    para(
        doc,
        "The analysis code is prepared for the GitHub repository "
        "mktiwari123/Tilaiya-2A219-soil-erosion-2025. That deposit holds "
        "scripts/, tilaiya/, tests/, and output/tables/. The project folder "
        "keeps the DEM tiles, the soil-loss and sensitivity rasters, the "
        "map figures, and the manuscript. The reproduction manifest lists "
        "checksums for the code, tables, figures, rasters, and DEM tiles. "
        "Large rasters are not part of the code deposit. No new raster "
        "was calculated.",
    )
    para(
        doc,
        "The public repository "
        "mktiwari123/Tilaiya-2A219-soil-erosion-2025 now receives the "
        "analysis rasters and the DEM tiles with the scripts and the "
        "checksum inventory. The aligned monthly stacks remain in the "
        "project folder because each file exceeds the 100 MB GitHub limit. "
        "Displayed equations italicize single-letter variables and leave "
        "LS, SDR, and IC upright. The abstract states IC0 = -6.29. "
        "No new raster was calculated.",
    )

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
