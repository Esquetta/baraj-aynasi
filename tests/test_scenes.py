import numpy as np
import pandas as pd
import pytest

from baraj_aynasi.scenes import clean_scenes, curve_from_json, estimates


def _areas():
    dates = pd.date_range("2024-01-01", periods=12, freq="5D")
    water = np.linspace(10, 12, dates.size)
    water[6] = 2.0  # an isolated NDWI dropout
    clear = np.full(dates.size, 1.0)
    clear[3] = 0.5  # cloudy
    return pd.DataFrame(
        {"dam": "x", "item_id": [f"i{k}" for k in range(dates.size)], "date": dates, "water_km2": water, "clear_frac": clear}
    )


def test_clean_scenes_drops_cloudy_and_isolated_outliers():
    out = clean_scenes(_areas(), "x")
    assert "i3" not in set(out.item_id) and "i6" not in set(out.item_id)
    assert len(out) == 10 and out.date.is_monotonic_increasing


def test_clean_scenes_other_dam_is_empty():
    assert clean_scenes(_areas(), "y").empty


CURVES = {"x": {"degree": 1, "coef": [10.0, -50.0], "fit_range_km2": [10.0, 12.0], "error_bar_90": 5.0, "heldout_passed": True}}


def test_curve_from_json_predicts_with_tangent_outside_range():
    c = curve_from_json(CURVES["x"])
    assert c.predict(np.array([11.0, 14.0])).tolist() == [60.0, 90.0]


def test_estimates_only_after_cutoff_with_bars():
    e = estimates(_areas(), CURVES, pd.Timestamp("2024-01-20"))
    assert (pd.to_datetime(e.date) > pd.Timestamp("2024-01-20")).all()
    assert e.occupancy_est.tolist() == pytest.approx((10 * e.water_km2 - 50).round(1).tolist())
    assert ((e.upper_90 - e.occupancy_est) <= 5.0 + 1e-9).all()
    assert e.heldout_passed.all()
