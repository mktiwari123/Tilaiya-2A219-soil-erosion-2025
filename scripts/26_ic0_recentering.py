"""Recenter the Vigiak threshold on the Tilaiya connectivity grid.

The stored Borselli IC raster and the default SDR raster are left in place.
IC0 = 0.5 and k = 1.2 remain the constants of the stored grid. Setting
IC0 to the median IC recenters the sigmoid. It is not a fit to the
reservoir or to the Vanoni ratio. A second IC0 is solved only to show
what value would force the mean ratio into 0.15-0.25.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tilaiya.rasters import read_band, write_band

IC_PATH = ROOT / "output" / "connectivity" / "IC.tif"
ANNUAL = ROOT / "output" / "rasters" / "SoilLoss_Arnoldus" / "SoilLoss_annual.tif"
OUT = ROOT / "output" / "tables"
SENS = ROOT / "output" / "rasters" / "sensitivity"
HA = 12.5 * 12.5 / 10000.0
SDR_MAX = 0.8
K_IC = 1.2


def clean(values):
    out = np.asarray(values, dtype=np.float64)
    out[~np.isfinite(out)] = np.nan
    out[np.isclose(out, -9999.0)] = np.nan
    return out


def sdr_grid(ic, ic0):
    return SDR_MAX / (1.0 + np.exp((ic0 - ic) / K_IC))


def summarise(name, ic0, ic, soil, note):
    ratio = sdr_grid(ic, ic0)
    finite = np.isfinite(ratio)
    data = ratio[finite]
    both = finite & np.isfinite(soil) & (soil >= 0)
    gross = float(np.sum(soil[both]) * HA)
    delivered = float(np.sum(soil[both] * ratio[both]) * HA)
    return {
        "case": name,
        "IC0": ic0,
        "k": K_IC,
        "SDRmax": SDR_MAX,
        "n": int(data.size),
        "mean_SDR": float(data.mean()),
        "median_SDR": float(np.median(data)),
        "SDR_at_median_IC": float(sdr_grid(np.median(ic[finite]), ic0)),
        "mass_weighted_SDR": delivered / gross if gross else np.nan,
        "delivered_t": delivered,
        "note": note,
    }, ratio


def ic0_for_mean(ic, target):
    low, high = -30.0, 5.0
    for _ in range(60):
        mid = 0.5 * (low + high)
        mean = float(np.mean(sdr_grid(ic, mid)))
        if mean > target:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SENS.mkdir(parents=True, exist_ok=True)
    ic, profile = read_band(IC_PATH)
    ic = clean(ic)
    soil = clean(read_band(ANNUAL)[0])
    finite = np.isfinite(ic)
    values = ic[finite]
    median_ic = float(np.median(values))
    mean_ic = float(np.mean(values))
    print(
        "IC n",
        int(finite.sum()),
        "mean",
        mean_ic,
        "median",
        median_ic,
        "p10",
        float(np.percentile(values, 10)),
        "p90",
        float(np.percentile(values, 90)),
    )

    rows = []
    centered = None
    cases = [
        ("European default", 0.5, "IC0 and k as published for other landscapes"),
        ("IC0 at median IC", median_ic, "sigmoid centered on this mask; median cell is SDRmax/2"),
        ("IC0 at mean IC", mean_ic, "same recentering on the mean"),
    ]
    for target in (0.15, 0.20, 0.25):
        solved = ic0_for_mean(values, target)
        cases.append(
            (
                f"mean SDR forced to {target:.2f}",
                solved,
                "IC0 chosen so the unweighted mean matches the area-curve window",
            )
        )
    for name, ic0, note in cases:
        row, ratio = summarise(name, ic0, ic, soil, note)
        rows.append(row)
        print(name, f"IC0={ic0:.4f}", f"mean={row['mean_SDR']:.4f}", f"mass={row['mass_weighted_SDR']:.4f}")
        if name == "IC0 at median IC":
            centered = np.where(finite, ratio, np.nan)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "ic0_recentering.csv", index=False)
    write_band(SENS / "SDR_IC0_at_median.tif", centered, profile)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
