# Tilaiya sub-watershed 2A219

Analysis code for the 2025 monthly RUSLE study of sub-watershed 2A219 (715 km² mask). This GitHub repository holds the scripts, the shared `tilaiya` package, and the result tables. The project folder on disk also holds the elevation tiles, soil-loss rasters, map figures, and the manuscript.

The outputs are scenario results for an ungauged headwater. Sub-watershed 2A219 has no erosion plots, no sediment station, and no 2025 bathymetric survey. Neighbouring records describe Karso, Banha, earlier Tilaiya streamflow, or reservoir storage for the whole dam.

## What stays in the project folder

- `scripts/` — numbered analysis scripts and the manuscript generators
- `tilaiya/` — shared factor, raster, and connectivity functions
- `output/tables/` — scenario tables
- `output/figures/maps/` — map figures
- `output/rasters/` — monthly soil-loss rasters and the sensitivity grids, including the unfilled Copernicus multiple-flow result
- `data/dem/` — Copernicus GLO-30, SRTM, and ASTER tiles used for the terrain comparison
- `Tilaiya_Manuscript_Draft.docx` and `Tilaiya_Advanced_Methodology.docx`

The elevation tiles, rasters, and figures remain in that folder. They are not part of this code deposit. Sentinel-1, Sentinel-2, IMD rainfall, and SoilGrids remain in their public collections. The annual baseline rasters and the SoilProperties project are left unchanged.

## Reported monthly maps

The monthly soil-loss rasters in `output/rasters/SoilLoss_Arnoldus` were built from stored monthly products. Each stored monthly soil-loss value was multiplied by the ratio of the corrected Arnoldus monthly erosivity to the stored monthly erosivity. July and August were also multiplied by the ratio of interpolated optical cover to radar cover. The original `output/rasters/SoilLoss` rasters were left in place. The annual equation is

R = 17.02 × 10^(1.50 × log10(Σ Pm² / P) − 0.8188).

Chen et al. (2023) defend 17.02 as the SI conversion and −0.8188 as the intercept. Copies that use 1.735 or −0.08188 are the widespread errors reviewed in that paper. The twelve monthly maps keep the legacy slope-length grid, so month-to-month differences are erosivity and cover.

The annual terrain result is the unfilled Copernicus GLO-30 multiple-flow Desmet–Govers grid (`output/rasters/sensitivity/LS_copernicus_mfd_desmet.tif`). The routing map uses IC₀ = −6.29 so the unweighted mean delivery ratio is 0.20. The default grid at IC₀ = 0.5 remains `output/connectivity/SDR.tif`.

Checksums of the code, tables, figures, rasters, and DEM tiles are listed in `output/tables/reproduction_manifest.csv`.
