import numpy as np

from baraj_aynasi.patches import candidate_masks, input_stack, otsu_threshold, sample_patch_origins


def test_input_stack_shape_and_nan():
    g = np.full((4, 4), 0.05, np.float32)
    g[0, 0] = np.nan
    x = input_stack(g, g, g * 0.5, g * 0.2)
    assert x.shape == (6, 4, 4) and x.dtype == np.float32
    assert np.isfinite(x).all() and x[0, 0, 0] == 0.0


def test_candidate_masks_disagree_on_algal_pixel():
    green = np.array([0.06, 0.06, 0.03])
    nir = np.array([0.02, 0.09, 0.25])  # clear water, algal water, vegetation
    swir = np.array([0.01, 0.01, 0.15])
    m = candidate_masks(green, nir, swir)
    assert m["ndwi"].tolist() == [True, False, False]
    assert m["mndwi"].tolist() == [True, True, False]
    assert m["union"].tolist() == [True, True, False]
    assert m["intersection"].tolist() == [True, False, False]


def test_sample_patch_origins_stay_inside_and_prefer_shore():
    aoi = np.zeros((300, 300), bool)
    aoi[50:250, 50:250] = True
    water = np.zeros((300, 300), bool)
    water[:, :150] = True
    origins = sample_patch_origins(aoi, water, n=20, rng=np.random.default_rng(0), size=96)
    assert len(origins) == 20
    for r0, c0 in origins:
        assert 0 <= r0 <= 300 - 96 and 0 <= c0 <= 300 - 96
    mixed = [0.15 <= water[r : r + 96, c : c + 96].mean() <= 0.85 for r, c in origins]
    assert sum(mixed) >= 12


def test_sample_patch_origins_small_chip():
    assert sample_patch_origins(np.ones((50, 50), bool), np.ones((50, 50), bool), 3, np.random.default_rng(0)) == []


def test_otsu_splits_two_groups():
    v = np.r_[np.full(50, 0.02), np.full(50, 0.30)]
    t = otsu_threshold(v)
    assert 0.02 < t < 0.30


def test_dark_nir_finds_algal_water():
    nir = np.r_[np.full(40, 0.09), np.full(60, 0.35)]  # algal water, forest
    green = np.r_[np.full(40, 0.06), np.full(60, 0.05)]
    swir = np.r_[np.full(40, 0.07), np.full(60, 0.15)]
    m = candidate_masks(green, nir, swir)
    assert not m["ndwi"][:40].any() and not m["mndwi"][:40].any()
    assert m["dark_nir"].tolist() == [True] * 40 + [False] * 60
