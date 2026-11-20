"""Checks that bound the interpretation of the 2025 results.

These calculations do not replace the soil-loss, stack, or connectivity
rasters. They read completed tables and apply published alternative
equations so the manuscript can state what is sensitive.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "output" / "tables"
WATERSHED_PIXELS = 4_576_196


def holdout_errors(predictions, testing, scenario):
    merged = predictions.merge(
        testing[["x", "y", "Class"]],
        on=["x", "y"],
        how="inner",
    )
    merged["abs_error"] = (merged["predicted"] - merged["SoilLoss"]).abs()
    merged["sq_error"] = (merged["predicted"] - merged["SoilLoss"]) ** 2
    rows = []
    for label, group in merged.groupby("Class"):
        rows.append(
            {
                "scenario": scenario,
                "class": label,
                "n": int(len(group)),
                "mean_observed": float(group["SoilLoss"].mean()),
                "mean_predicted": float(group["predicted"].mean()),
                "MAE": float(group["abs_error"].mean()),
                "RMSE": float(np.sqrt(group["sq_error"].mean())),
            }
        )
    return pd.DataFrame(rows)


def arnoldus_annual(monthly_mm):
    """Corrected Arnoldus (1977) annual R, MJ mm ha-1 h-1 yr-1.

    R = 17.02 * 10 ** (1.50 * log10(sum(Pm^2) / P) - 0.8188),
    as stated by Chen et al. (2023).
    """
    rainfall = np.asarray(monthly_mm, dtype=float)
    annual = rainfall.sum()
    mfi = np.sum(rainfall**2) / annual
    erosivity = 17.02 * 10 ** (1.50 * np.log10(mfi) - 0.8188)
    return float(annual), float(mfi), float(erosivity)


def renard_freimund_annual(mfi):
    """Renard and Freimund (1994) annual R from the Modified Fournier index."""
    if mfi < 55:
        return float(0.07397 * mfi**1.847)
    return float(95.77 - 6.081 * mfi + 0.4770 * mfi**2)


def sdr(ic, ic0, k_b, sdr_max=0.8):
    return float(sdr_max / (1.0 + np.exp((ic0 - ic) / k_b)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    testing = pd.read_csv(ROOT / "output" / "datasets" / "testing.csv")
    frames = []
    for scenario, name in (
        ("Reduced_Integrated", "Reduced_Integrated_holdout_predictions.csv"),
        ("Dynamic_Integrated", "Dynamic_Integrated_holdout_predictions.csv"),
    ):
        predictions = pd.read_csv(OUT / name)
        frames.append(holdout_errors(predictions, testing, scenario))
    class_errors = pd.concat(frames, ignore_index=True)
    class_errors.to_csv(OUT / "holdout_error_by_class.csv", index=False)

    monthly = pd.read_csv(OUT / "monthly_soil_loss_2025.csv")
    valid = pd.DataFrame(
        {
            "month": monthly["month"],
            "valid_pixels": monthly["valid_pixels"],
            "missing_pixels": monthly["missing_pixels"],
            "valid_fraction_of_watershed": monthly["valid_pixels"] / WATERSHED_PIXELS,
        }
    )
    valid.to_csv(OUT / "valid_pixel_fractions.csv", index=False)

    # Monthly rainfall (mm) for the five watershed IMD cells, Section 6.1.
    rainfall = {
        1: [0, 0, 21.6, 50.9, 83.2, 323.6, 272.4, 194.9, 151.7, 109.9, 12.0, 0],
        2: [0, 0, 23.9, 32.8, 88.5, 229.4, 409.6, 340.5, 139.4, 125.7, 9.7, 0],
        3: [0, 0, 23.5, 46.7, 62.4, 217.1, 310.1, 173.9, 117.8, 120.9, 18.0, 0],
        4: [0, 0, 36.5, 15.2, 90.5, 193.1, 397.8, 237.7, 165.6, 106.6, 19.9, 0],
        5: [0, 0, 16.3, 60.4, 56.1, 233.7, 480.1, 243.0, 170.0, 148.7, 34.0, 0],
    }
    study_annual = {1: 894, 2: 1225, 3: 786, 4: 1046, 5: 1292}
    erosivity_rows = []
    for cell, monthly_mm in rainfall.items():
        annual, mfi, arnoldus = arnoldus_annual(monthly_mm)
        freimund = renard_freimund_annual(mfi)
        erosivity_rows.append(
            {
                "cell": cell,
                "annual_rainfall_mm": annual,
                "MFI_mm": mfi,
                "study_sum_of_monthly_Rm": study_annual[cell],
                "arnoldus_1977_corrected_annual_R": arnoldus,
                "renard_freimund_1994_annual_R": freimund,
            }
        )
    pd.DataFrame(erosivity_rows).to_csv(OUT / "erosivity_equation_comparison.csv", index=False)

    median_ic = -7.6583404541015625
    sensitivity = []
    for ic0, k_b, note in (
        (0.5, 1.2, "values used in this study"),
        (0.5, 2.0, "k often used with the same IC0 and SDRmax"),
        (0.0, 1.2, "IC0 shifted, k unchanged"),
        (0.5, 0.5, "steeper sigmoid"),
    ):
        sensitivity.append(
            {
                "IC0": ic0,
                "k": k_b,
                "SDRmax": 0.8,
                "median_IC": median_ic,
                "SDR_at_median_IC": sdr(median_ic, ic0, k_b),
                "note": note,
            }
        )
    pd.DataFrame(sensitivity).to_csv(OUT / "sdr_parameter_sensitivity.csv", index=False)
    print(class_errors.to_string(index=False))
    print(valid.to_string(index=False))
    print(pd.DataFrame(erosivity_rows).to_string(index=False))
    print(pd.DataFrame(sensitivity).to_string(index=False))


if __name__ == "__main__":
    main()
