import numpy as np
import pytest

from baraj_aynasi.aoi import aoi_mask, disk, reservoir_mask


def _scene():
    freq = np.zeros((20, 30))
    freq[5:10, 5:12] = 0.9  # reservoir
    freq[10:12, 11:13] = 0.6  # its diagonal arm, still connected
    freq[2:6, 20:28] = 1.0  # a separate pond
    freq[15:18, 2:5] = 0.3  # seldom-wet land, below the frequency cut
    return freq


def test_reservoir_mask_keeps_only_seeded_component():
    res = reservoir_mask(_scene(), seeds=[(6, 6)])
    assert res[7, 8] and res[11, 12]
    assert not res[3, 22]
    assert not res[16, 3]


def test_reservoir_mask_rejects_any_dry_seed():
    with pytest.raises(ValueError, match=r"\(0, 0\)"):
        reservoir_mask(_scene(), seeds=[(6, 6), (0, 0)], snap_px=2)


def test_seed_snaps_to_nearby_water():
    res = reservoir_mask(_scene(), seeds=[(13, 8)], snap_px=4)  # three pixels below the reservoir
    assert res[7, 8] and not res[3, 22]


def test_reservoir_mask_joins_components_with_several_seeds():
    res = reservoir_mask(_scene(), seeds=[(6, 6), (3, 22)])
    assert res[7, 8] and res[3, 22]


def test_aoi_mask_adds_margin_and_excludes_other_water():
    freq = _scene()
    res = reservoir_mask(freq, seeds=[(6, 6)])
    aoi = aoi_mask(res, other_water=freq >= 0.5, margin_px=2)
    assert aoi[res].all()
    assert aoi[3, 6]  # two pixels above the reservoir edge
    assert not aoi[0, 0]
    assert not aoi[5, 20]  # pond pixel stays out even if the margin reached it


def test_disk():
    d = disk(1)
    assert d.tolist() == [[False, True, False], [True, True, True], [False, True, False]]
