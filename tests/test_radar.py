import numpy as np

from baraj_aynasi.radar import (
    aoi_values,
    db_histogram,
    decode_db,
    despeckle,
    encode_db,
    group_passes,
    km2_below,
)


def _item(id_, day, platform="sentinel-1a", orbit=58):
    return {"id": id_, "properties": {"datetime": f"{day}T16:00:00Z", "platform": platform, "sat:relative_orbit": orbit}}


def test_group_passes_joins_slices_of_one_pass_only():
    items = [_item("b", "2021-05-17"), _item("a", "2021-05-17"), _item("c", "2021-05-17", orbit=138), _item("d", "2021-05-17", platform="sentinel-1b"), _item("e", "2021-05-05")]
    groups = group_passes(items)
    assert [[it["id"] for it in g] for g in groups] == [["e"], ["a", "b"], ["c"], ["d"]]


def test_encode_decode_keeps_nodata_and_precision():
    db = np.array([[-20.03, np.nan], [-60.0, 30.0]], dtype="float32")
    out = decode_db(encode_db(db))
    assert abs(out[0, 0] + 20.03) <= 0.1
    assert np.isnan(out[0, 1])
    assert out[1, 0] == -40.0  # clipped, still data
    assert np.isfinite(out[1, 1]) and out[1, 1] <= 10.8


def test_despeckle_removes_lone_dark_pixels_and_treats_nodata_as_land():
    db = np.full((9, 9), -8.0)
    db[4, 4] = -25.0
    assert despeckle(db)[4, 4] == -8.0
    water = np.full((9, 9), -22.0)
    water[:, 0] = np.nan
    assert despeckle(water)[4, 0] >= -22.0 and despeckle(water)[4, 4] == -22.0


def test_aoi_values_skip_invalid_and_outside_aoi_across_boxes():
    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    valid = np.array([[False, True], [True, True]])
    aoi = np.array([[True, True], [True, False]])
    out = aoi_values([a, a * 10], [valid, valid], [aoi, aoi])
    assert sorted(out.tolist()) == [2.0, 3.0, 20.0, 30.0]


def test_km2_below_counts_pixels_darker_than_the_threshold():
    water = decode_db(encode_db(np.full(300, -21.0)))
    land = decode_db(encode_db(np.full(700, -8.0)))
    hist = db_histogram(np.concatenate([water, land]))
    assert hist.sum() == 1000
    assert km2_below(hist, -15.0) == 300 * 1e-4
    assert km2_below(hist, -30.0) == 0.0
    assert km2_below(hist, 0.0) == 1000 * 1e-4
