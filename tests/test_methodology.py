"""Lock the published factor, delivery, and connectivity equations."""

from pathlib import Path

import numpy as np
import pandas as pd

from tilaiya.connectivity import connectivity_index
from tilaiya.constants import MFI_COEFFICIENT, MFI_EXPONENT
from tilaiya.factors import (
    cover_management,
    dynamic_erodibility,
    fuse_cover_management,
    modified_fournier_index,
    monthly_erosivity,
    monthly_soil_loss,
    radar_vegetation_index,
    relative_moisture,
    savi,
)
from tilaiya.metrics import regression_scores
from tilaiya.rainfall import monthly_erosivity_table
from tilaiya.sediment import (
    sediment_delivery_ratio,
    sediment_mass_tonnes,
    siltation_volume_m3,
)
from tilaiya.stacking import fold_splits


def test_monthly_erosivity_matches_the_fournier_equation():
    monthly = np.array([100.0])
    annual = 1000.0
    assert modified_fournier_index(monthly, annual)[0] == 10.0
    expected = MFI_COEFFICIENT * (10.0 ** MFI_EXPONENT)
    assert monthly_erosivity(monthly, annual)[0] == expected


def test_savi_uses_the_half_soil_adjustment():
    # ((0.5 - 0.1) / (0.5 + 0.1 + 0.5)) * 1.5
    assert savi(0.5, 0.1) == (0.4 / 1.1) * 1.5


def test_radar_vegetation_index_converts_decibels():
    # 0 dB is linear power 1, so RVI = 4 / 2.
    assert radar_vegetation_index(0.0, 0.0, input_units="db") == 2.0
    assert radar_vegetation_index(1.0, 1.0, input_units="linear") == 2.0


def test_cover_management_bounds_and_monsoon_switch():
    assert cover_management(0.0) == 1.0
    assert cover_management(1.0) == 0.001
    optical = fuse_cover_management(0.2, 0.8, month=1)
    monsoon = fuse_cover_management(0.2, 0.8, month=7)
    assert optical == cover_management(0.2)
    assert monsoon == cover_management(0.8)


def test_dynamic_erodibility_increases_with_moisture():
    dry = dynamic_erodibility(0.04, 0.0)
    wet = dynamic_erodibility(0.04, 1.0)
    assert dry == 0.04
    assert wet == 0.04 * 1.25
    loss = monthly_soil_loss(10, 0.05, 2, 0.2, 0.5)
    assert loss == 10 * 0.05 * 2 * 0.2 * 0.5


def test_relative_moisture_increases_as_backscatter_increases():
    vv = np.array([-20.0, -12.0, -5.0])
    theta, low, high = relative_moisture(vv, 0, 100)
    assert low == -20.0
    assert high == -5.0
    assert theta[0] == 0.0
    assert theta[-1] == 1.0
    assert theta[1] > theta[0]


def test_scores_are_perfect_when_prediction_matches():
    scores = regression_scores([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert scores["R2"] == 1.0
    assert scores["NSE"] == 1.0
    assert scores["RMSE"] == 0.0


def test_delivery_ratio_is_half_of_maximum_at_the_threshold():
    assert sediment_delivery_ratio(0.5) == 0.4
    mass = sediment_mass_tonnes(np.array([10.0]), np.array([0.4]), pixel_area_ha=0.015625)
    assert mass == 10.0 * 0.4 * 0.015625
    assert siltation_volume_m3(1.45) == 1.0


def test_rainfall_table_aggregates_a_selected_year(tmp_path):
    path = Path(tmp_path) / "rain.csv"
    pd.DataFrame(
        {
            "date": ["2025-01-15", "2025-01-20", "2025-07-01", "2024-07-01"],
            "precip_mm": [10.0, 5.0, 100.0, 999.0],
        }
    ).to_csv(path, index=False)
    table = monthly_erosivity_table(path, 2025)
    assert table.loc[table["month"] == 1, "precip_mm"].item() == 15.0
    assert table.loc[table["month"] == 7, "precip_mm"].item() == 100.0
    assert table["precip_mm"].sum() == 115.0


def test_flat_cells_drain_toward_the_lower_edge():
    elevation = np.full((5, 5), 10.0)
    elevation[-1, :] = 9.0
    weight = np.full(elevation.shape, 0.2)
    result = connectivity_index(elevation, weight, cell_size=10.0, fill_depressions=True)
    assert result["direction"][2, 2] in (3, 4, 5)
    assert np.isfinite(result["ic"][2, 2])


def test_connectivity_increases_toward_the_outlet_on_a_plane():
    elevation = np.array([[5.0, 4.0, 3.0, 2.0, 1.0]])
    weight = np.full(elevation.shape, 0.2)
    result = connectivity_index(elevation, weight, cell_size=10.0, fill_depressions=False)
    assert result["upslope_cells"][0, -1] == 5
    assert result["direction"][0, 0] == 2
    assert result["direction"][0, -1] == -1
    assert result["ic"][0, -1] > result["ic"][0, 0]
    assert np.isfinite(result["ic"]).all()


def test_reservoir_cell_is_excluded_from_connectivity():
    elevation = np.array([[5.0, 4.0, 3.0, 2.0, 1.0]])
    weight = np.full(elevation.shape, 0.2)
    reservoir = np.array([[False, False, False, False, True]])
    result = connectivity_index(
        elevation,
        weight,
        cell_size=10.0,
        reservoir=reservoir,
        fill_depressions=False,
    )
    assert np.isnan(result["ic"][0, -1])
    assert np.isfinite(result["ic"][0, -2])


def test_spatial_blocks_are_used_when_five_groups_exist():
    groups = np.array([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
    _splits, kind = fold_splits(len(groups), groups)
    assert kind == "spatial_block_2km"
