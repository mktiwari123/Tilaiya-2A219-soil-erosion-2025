"""Equation constants from the Tilaiya advanced methodology.

The numerical values below are the ones stated for monthly RUSLE,
SAR-modulated erodibility, and Borselli sediment delivery. They are
kept in one place so the Earth Engine exports and the local Python
steps stay on the same definition.
"""

# Retired pair. No primary paper was found for these two numbers.
# Reported maps use the corrected Arnoldus equation below.
MFI_COEFFICIENT = 1.8219
MFI_EXPONENT = 1.211

# Corrected Arnoldus (1977), as stated by Chen et al. (2023):
# R = 17.02 * 10 ** (1.50 * log10(sum(Pm^2) / P) - 0.8188)
# Units: MJ mm ha-1 h-1 yr-1. Not fitted at Tilaiya.
ARNOLDUS_FACTOR = 17.02
ARNOLDUS_LOG_SLOPE = 1.50
ARNOLDUS_LOG_INTERCEPT = 0.8188

# SAVI with L = 0.5, which is the * 1.5 form in the methodology.
SAVI_L = 0.5

# Cm = 1 - 1.18 * canopy index, then bounded.
CM_COEFFICIENT = 1.18
CM_MIN = 0.001
CM_MAX = 1.0

# July and August use the SAR canopy proxy because optical scenes
# are cloud-saturated in the monsoon.
MONSOON_MONTHS = (7, 8)

# Km(t) = Kbase * (1 + alpha * normalised moisture).
K_MOISTURE_ALPHA = 0.25
MOISTURE_LOW_PERCENTILE = 5.0
MOISTURE_HIGH_PERCENTILE = 95.0

# SDR = SDR_max / (1 + exp((IC_0 - IC) / k_ic)).
SDR_MAX = 0.8
IC_0 = 0.5
K_IC = 1.2

# Local dry bulk density used to convert sediment mass to volume.
# 1.45 g/cm3 is equal to 1.45 t/m3.
BULK_DENSITY_T_M3 = 1.45

# 12.5 m ALOS PALSAR cell. 12.5 * 12.5 m2 = 0.015625 ha.
CELL_SIZE_M = 12.5
PIXEL_AREA_HA = 0.015625

# Small floors so Borselli weights and slopes stay finite.
WEIGHT_MIN = 0.001
SLOPE_MIN = 0.001

NODATA = -9999.0

RANDOM_STATE = 42
N_SAMPLES = 12697
TRAIN_SIZE = 0.70
TRAIN_ROWS = 8888
TEST_ROWS = 3809
N_FOLDS = 5
SPATIAL_BLOCK_M = 2000.0

EROSION_BINS = (0, 5, 15, 30, 50, 100)
EROSION_LABELS = ("E1", "E2", "E3", "E4", "E5", "E6")

# Level-0 and Level-1 settings stated for the meta-stacking pipeline.
XGB_PARAMS = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "objective": "reg:squarederror",
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
}
CAT_PARAMS = {
    "iterations": 600,
    "depth": 6,
    "learning_rate": 0.04,
    "l2_leaf_reg": 3,
    "random_seed": RANDOM_STATE,
    "verbose": 0,
    "allow_writing_files": False,
}
RF_PARAMS = {
    "n_estimators": 300,
    "max_features": "sqrt",
    "min_samples_split": 4,
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
}
MLP_PARAMS = {
    "hidden_layer_sizes": (100, 50),
    "activation": "relu",
    "solver": "adam",
    "alpha": 0.001,
    "max_iter": 500,
    "early_stopping": True,
    "random_state": RANDOM_STATE,
}
RIDGE_ALPHA = 1.0

STACK_BANDS = (
    "R",
    "K",
    "LS",
    "C",
    "P",
    "Clay",
    "Sand",
    "Silt",
    "SOC",
    "Rain",
    "NDVI",
)

SCENARIOS = {
    "Topo_Veg": ("LS", "NDVI"),
    "Soil_Texture": ("K", "SOC", "Sand", "Silt"),
    "Climate_Manage": ("Rain", "P"),
    "Topo_Climate": ("LS", "Rain"),
    "Veg_Soil": ("NDVI", "SOC", "K"),
    "Integrated_All": ("LS", "Rain", "K", "SOC", "Sand", "Silt", "NDVI", "C", "P"),
    "Reduced_Integrated": ("LS", "SOC", "C", "P", "NDVI", "K"),
    # Km, Cm, RVI, and SAVI are annual means of the monthly factors.
    # R is the spatial erosivity grid. Monthly Rm is a catchment value,
    # so it is used in the RUSLE maps rather than as a point predictor.
    "Dynamic_Integrated": ("LS", "R", "Km", "Cm", "P", "RVI", "SAVI", "SOC"),
}

TARGET = "SoilLoss"
