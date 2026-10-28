import numpy as np
import pytest

from baraj_aynasi.water import (
    boa_offset,
    clear_fraction,
    clear_mask,
    ndwi,
    reflectance,
    water_area_km2,
    water_mask,
)


@pytest.mark.parametrize(
    ("baseline", "expected"),
    [("02.12", 0), ("03.00", 0), ("04.00", -1000), ("05.13", -1000), ("10.01", -1000)],
)
def test_boa_offset_by_baseline(baseline, expected):
    assert boa_offset(baseline) == expected


def test_reflectance_applies_offset_and_marks_nodata():
    dn = np.array([0, 1000, 1500], dtype=np.uint16)
    out = reflectance(dn, -1000)
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(0.0)
    assert out[2] == pytest.approx(0.05)


def test_ndwi_water_and_land():
    green = np.array([0.08, 0.05])
    nir = np.array([0.02, 0.30])
    out = ndwi(green, nir)
    assert out[0] == pytest.approx(0.6)
    assert out[1] == pytest.approx(-5 / 7)


def test_ndwi_undefined_is_nan():
    out = ndwi(np.array([0.0, np.nan, -0.01]), np.array([0.0, 0.1, 0.0]))
    assert np.isnan(out).all()


def test_harmonised_baselines_give_same_ndwi():
    # The same surface stored under the old and the new baseline.
    old_g, old_n = np.array([800], np.uint16), np.array([200], np.uint16)
    new_g, new_n = old_g + 1000, old_n + 1000
    a = ndwi(reflectance(old_g, boa_offset("02.12")), reflectance(old_n, boa_offset("02.12")))
    b = ndwi(reflectance(new_g, boa_offset("05.10")), reflectance(new_n, boa_offset("05.10")))
    assert a[0] == pytest.approx(b[0])


def test_clear_mask_drops_clouds_shadow_and_nodata():
    scl = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
    assert clear_mask(scl).tolist() == [False, False, True, False, True, True, True, True, False, False, False, False]


def test_water_mask_threshold_and_nan():
    idx = np.array([0.3, 0.0, -0.2, np.nan])
    assert water_mask(idx).tolist() == [True, False, False, False]
    assert water_mask(idx, threshold=-0.3).tolist() == [True, True, True, False]


def test_water_area_counts_only_aoi_pixels():
    water = np.array([[True, True], [True, False]])
    aoi = np.array([[True, False], [True, True]])
    # two 10 m pixels = 200 m2
    assert water_area_km2(water, aoi) == pytest.approx(200 / 1e6)
    assert water_area_km2(water, aoi, pixel_size_m=20) == pytest.approx(800 / 1e6)


def test_clear_fraction():
    valid = np.array([True, False, True, True])
    aoi = np.array([True, True, True, False])
    assert clear_fraction(valid, aoi) == pytest.approx(2 / 3)
    assert clear_fraction(valid, np.zeros(4, bool)) == 0.0
