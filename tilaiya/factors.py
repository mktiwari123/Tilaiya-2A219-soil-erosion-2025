"""Monthly RUSLE factor equations.

Am = Rm * Km(t) * LS * Cm(t) * P

Sentinel-1 GRD backscatter is stored in decibels in Earth Engine.
The dual-pol radar vegetation index is defined on linear power, so
VV and VH are converted from dB before RVI is calculated.
"""

import numpy as np

from tilaiya.constants import (
    CM_COEFFICIENT,
    CM_MAX,
    CM_MIN,
    VDK_ALPHA,
    VDK_BETA,
    K_MOISTURE_ALPHA,
    ARNOLDUS_FACTOR,
    ARNOLDUS_LOG_INTERCEPT,
    ARNOLDUS_LOG_SLOPE,
    MFI_COEFFICIENT,
    MFI_EXPONENT,
    SAVI_L,
)


def modified_fournier_index(monthly_precip_mm, annual_precip_mm):
    """MFIm = Pm^2 / Pannual."""
    monthly = np.asarray(monthly_precip_mm, dtype=np.float64)
    annual = np.asarray(annual_precip_mm, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        mfi = np.where(annual > 0, (monthly ** 2) / annual, np.nan)
    return mfi


def monthly_erosivity(monthly_precip_mm, annual_precip_mm):
    """Retired pair: Rm = 1.8219 * (MFIm ** 1.211).

    Kept so the stored SoilLoss rasters can be reproduced.
    Reported results use corrected_arnoldus_annual and
    arnoldus_monthly_erosivity.
    """
    mfi = modified_fournier_index(monthly_precip_mm, annual_precip_mm)
    with np.errstate(invalid="ignore"):
        return MFI_COEFFICIENT * np.power(mfi, MFI_EXPONENT)


def corrected_arnoldus_annual(monthly_precip_mm):
    """Corrected Arnoldus (1977) annual R, MJ mm ha-1 h-1 yr-1.

    R = 17.02 * 10 ** (1.50 * log10(sum(Pm^2) / P) - 0.8188).
    Chen et al. (2023) defend 17.02 as the SI conversion from U.S.
    customary units and identify 1.735 and -0.08188 as incorrect copies.
    The Morocco equation was not fitted at Tilaiya.
    """
    rainfall = np.asarray(monthly_precip_mm, dtype=np.float64)
    annual = float(np.sum(rainfall))
    if annual <= 0:
        return np.nan
    mfi = float(np.sum(rainfall**2) / annual)
    return float(
        ARNOLDUS_FACTOR
        * 10 ** (ARNOLDUS_LOG_SLOPE * np.log10(mfi) - ARNOLDUS_LOG_INTERCEPT)
    )


def arnoldus_monthly_erosivity(monthly_precip_mm):
    """Split the corrected Arnoldus annual total in proportion to Pm^2.

    The twelve monthly values sum to corrected_arnoldus_annual.
    A dry month is zero. This split is not a separate regression.
    """
    rainfall = np.asarray(monthly_precip_mm, dtype=np.float64)
    annual_r = corrected_arnoldus_annual(rainfall)
    squares = rainfall**2
    total = float(np.sum(squares))
    if not np.isfinite(annual_r) or total <= 0:
        return np.zeros(rainfall.shape, dtype=np.float64)
    return annual_r * squares / total


def renard_freimund_annual(monthly_precip_mm):
    """Renard and Freimund (1994) annual R from the Modified Fournier index.

    Fitted for the United States. Used here only as a second published
    annual total, not as the map equation.
    """
    rainfall = np.asarray(monthly_precip_mm, dtype=np.float64)
    annual = float(np.sum(rainfall))
    if annual <= 0:
        return np.nan
    mfi = float(np.sum(rainfall**2) / annual)
    if mfi < 55:
        return float(0.07397 * mfi**1.847)
    return float(95.77 - 6.081 * mfi + 0.4770 * mfi**2)


def savi(nir, red, soil_factor=SAVI_L):
    """SAVIm = ((NIR - Red) / (NIR + Red + L)) * (1 + L)."""
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    denominator = nir + red + soil_factor
    with np.errstate(divide="ignore", invalid="ignore"):
        index = np.where(denominator == 0, np.nan, (nir - red) / denominator)
    return index * (1.0 + soil_factor)


def db_to_linear(backscatter_db):
    """Convert decibel backscatter to linear power."""
    decibels = np.asarray(backscatter_db, dtype=np.float64)
    return np.power(10.0, decibels / 10.0)


def radar_vegetation_index(vv, vh, input_units="linear"):
    """RVI = (4 * VH) / (VV + VH).

    input_units is "linear" or "db".
    """
    if input_units == "db":
        vv = db_to_linear(vv)
        vh = db_to_linear(vh)
    elif input_units != "linear":
        raise ValueError("input_units must be 'linear' or 'db'.")

    vv = np.asarray(vv, dtype=np.float64)
    vh = np.asarray(vh, dtype=np.float64)
    denominator = vv + vh
    with np.errstate(divide="ignore", invalid="ignore"):
        rvi = np.where(denominator <= 0, np.nan, (4.0 * vh) / denominator)
    return rvi


def vander_knijff_cover(ndvi, alpha=VDK_ALPHA, beta=VDK_BETA):
    """C = exp(-alpha * NDVI / (beta - NDVI)), clipped to 0.001-1.

    van der Knijff, Jones and Montanarella (2000) use alpha = 2 and
    beta = 1. NDVI at or above beta is held just below beta. Negative
    NDVI is treated as bare cover.
    """
    index = np.asarray(ndvi, dtype=np.float64)
    capped = np.where(index > 0.0, index, 0.0)
    capped = np.minimum(capped, beta - 1.0e-6)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        cover = np.exp(-alpha * capped / (beta - capped))
    cover = np.where(np.isfinite(index), cover, np.nan)
    return np.clip(cover, CM_MIN, CM_MAX)


def cover_management(canopy_index):
    """Cm = clip(1 - 1.18 * canopy index, 0.001, 1).

    The canopy index is SAVI in optical months. In July and August it
    is the dual-pol RVI used as the cloud-free canopy proxy. RVI is
    limited to 0-1 before the transform so Cm stays inside the
    published bounds when VH approaches VV.
    """
    canopy = np.clip(np.asarray(canopy_index, dtype=np.float64), 0.0, 1.0)
    cm = 1.0 - CM_COEFFICIENT * canopy
    return np.clip(cm, CM_MIN, CM_MAX)


def fuse_cover_management(savi_index, rvi_index, month, monsoon_months=(7, 8)):
    """Use RVI as the canopy index in July and August only.

    Those are the peak monsoon months, when the Sentinel-2 median rests
    on too few clear scenes. The Cm equation is unchanged. SAVI and RVI
    are not scaled to each other.
    """
    if int(month) in monsoon_months:
        return cover_management(rvi_index)
    return cover_management(savi_index)


def relative_moisture(vv_db, low_percentile=5.0, high_percentile=95.0):
    """Stretch VV backscatter to a 0-1 wetness index.

    Wetter soil returns a higher (less negative) VV value. The 5th and
    95th percentiles stand in for theta_min and theta_max until a
    field-calibrated dielectric inversion is supplied. Values outside
    that range are clipped.
    """
    vv = np.asarray(vv_db, dtype=np.float64)
    finite = vv[np.isfinite(vv)]
    if finite.size == 0:
        return np.full(vv.shape, np.nan), np.nan, np.nan

    theta_min = float(np.percentile(finite, low_percentile))
    theta_max = float(np.percentile(finite, high_percentile))
    span = theta_max - theta_min
    if span <= 0:
        return np.zeros(vv.shape, dtype=np.float64), theta_min, theta_max

    theta = np.clip((vv - theta_min) / span, 0.0, 1.0)
    theta = np.where(np.isfinite(vv), theta, np.nan)
    return theta, theta_min, theta_max


def dynamic_erodibility(k_base, theta, alpha=K_MOISTURE_ALPHA):
    """Km(t) = Kbase * (1 + alpha * theta), with theta already 0-1."""
    k_base = np.asarray(k_base, dtype=np.float64)
    moisture = np.clip(np.asarray(theta, dtype=np.float64), 0.0, 1.0)
    return k_base * (1.0 + alpha * moisture)


def monthly_soil_loss(rm, km, ls, cm, p_factor):
    """Am = Rm * Km(t) * LS * Cm(t) * P."""
    with np.errstate(over="ignore", invalid="ignore"):
        return (
            np.asarray(rm, dtype=np.float64)
            * np.asarray(km, dtype=np.float64)
            * np.asarray(ls, dtype=np.float64)
            * np.asarray(cm, dtype=np.float64)
            * np.asarray(p_factor, dtype=np.float64)
        )
