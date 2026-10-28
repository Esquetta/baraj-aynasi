import numpy as np
import pytest

from baraj_aynasi.fit import Curve, fit_curve, metrics, out_of_fold_residuals


def _synthetic(noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    area = np.linspace(10, 20, 60)
    occ = 0.4 * (area - 10) ** 2 + 2 * (area - 10) + 20 + rng.normal(0, noise, area.size)
    groups = np.repeat(np.arange(6), 10)
    return area, occ, groups


def test_fit_curve_recovers_quadratic_and_picks_degree_2():
    area, occ, groups = _synthetic()
    curve, degree = fit_curve(area, occ, groups)
    assert degree == 2
    assert curve.predict(np.array([15.0]))[0] == pytest.approx(0.4 * 25 + 10 + 20)
    assert curve.halfwidth == pytest.approx(0.0, abs=1e-6)


def test_linear_data_prefers_degree_1_when_noisy():
    rng = np.random.default_rng(1)
    area = np.linspace(0, 10, 40)
    occ = 5 * area + 10 + rng.normal(0, 3, area.size)
    _, degree = fit_curve(area, occ, np.repeat(np.arange(8), 5))
    assert degree == 1


def test_out_of_fold_residuals_hold_out_each_group():
    area, occ, groups = _synthetic()
    res = out_of_fold_residuals(area, occ, groups, degree=1)
    assert np.isfinite(res).all()
    # A straight line fitted without a group misses that group's curvature.
    assert np.abs(res).max() > 1.0


def test_halfwidth_covers_most_noise():
    area, occ, groups = _synthetic(noise=2.0)
    curve, _ = fit_curve(area, occ, groups, coverage=0.9)
    lo, hi = curve.interval(area)
    inside = np.mean((occ >= lo) & (occ <= hi))
    assert 0.8 <= inside <= 1.0


def test_predictions_are_clipped_to_percent_range():
    curve = Curve(coef=np.array([10.0, 0.0]), halfwidth=5.0)
    assert curve.predict(np.array([-1.0, 5.0, 20.0])).tolist() == [0.0, 50.0, 100.0]
    lo, hi = curve.interval(np.array([0.0, 20.0]))
    assert lo.tolist() == [0.0, 95.0] and hi.tolist() == [5.0, 100.0]


def test_metrics():
    m = metrics(np.array([10.0, 20.0]), np.array([12.0, 16.0]), np.array([8.0, 17.0]), np.array([14.0, 25.0]))
    assert m["mae"] == pytest.approx(3.0)
    assert m["rmse"] == pytest.approx(np.sqrt(10.0))
    assert m["bias"] == pytest.approx(-1.0)
    assert m["coverage"] == pytest.approx(1.0)
    assert m["n"] == 2


def test_fit_curve_needs_several_groups():
    with pytest.raises(ValueError):
        fit_curve(np.array([1.0, 2.0]), np.array([1.0, 2.0]), np.array([0, 0]))
