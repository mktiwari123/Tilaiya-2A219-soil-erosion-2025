"""Sediment delivery ratio and Tilaiya reservoir siltation volume."""

import numpy as np

from tilaiya.constants import BULK_DENSITY_T_M3, IC_0, K_IC, PIXEL_AREA_HA, SDR_MAX


def sediment_delivery_ratio(connectivity, sdr_max=SDR_MAX, ic_0=IC_0, k_ic=K_IC):
    """SDR = SDR_max / (1 + exp((IC_0 - IC) / k_ic))."""
    ic = np.asarray(connectivity, dtype=np.float64)
    ratio = sdr_max / (1.0 + np.exp((ic_0 - ic) / k_ic))
    return np.where(np.isfinite(ic), ratio, np.nan)


def sediment_mass_tonnes(soil_loss_t_ha_yr, delivery_ratio, pixel_area_ha=PIXEL_AREA_HA):
    """SY = sum(A * SDR * pixel area in hectares), in tonnes per year."""
    soil_loss = np.asarray(soil_loss_t_ha_yr, dtype=np.float64)
    ratio = np.asarray(delivery_ratio, dtype=np.float64)
    delivered = soil_loss * ratio * pixel_area_ha
    delivered = delivered[np.isfinite(delivered)]
    return float(np.sum(delivered))


def siltation_volume_m3(mass_tonnes, bulk_density_t_m3=BULK_DENSITY_T_M3):
    """Convert delivered dry mass to bulked volume.

    bulk_density_t_m3 of 1.45 corresponds to 1.45 g/cm3.
    """
    if bulk_density_t_m3 <= 0:
        raise ValueError("Bulk density must be positive.")
    return float(mass_tonnes) / float(bulk_density_t_m3)
