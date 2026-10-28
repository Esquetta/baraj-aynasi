import numpy as np
import pytest

from baraj_aynasi.fit import (
    Curve,
    extended_polyval,
    fit_curve,
    fit_poly,
    hampel_outliers,
    is_increasing,
    metrics,
    out_of_fold_residuals,
)


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
    # Only the end years are extrapolated (by tangent), so the error bar stays small.
    assert curve.halfwidth < 1.0


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


def test_fit_poly_ignores_gross_outliers():
    area = np.linspace(10, 20, 40)
    occ = 5 * area - 20
    occ_bad = occ.copy()
    occ_bad[[3, 17, 30]] = [95.0, 99.0, 90.0]  # high occupancy, water missed
    coef, keep = fit_poly(area, occ_bad, 1)
    assert coef == pytest.approx([5.0, -20.0])
    assert keep.sum() == area.size - 3 and not keep[[3, 17, 30]].any()


def test_extended_polyval_continues_with_tangent():
    coef = np.array([1.0, 0.0, 0.0])  # x^2, increasing on [1, 3]
    out = extended_polyval(coef, np.array([0.0, 2.0, 4.0]), lo=1.0, hi=3.0)
    # below: 1 + 2*(0-1) = -1 ; inside: 4 ; above: 9 + 6*(4-3) = 15
    assert out.tolist() == pytest.approx([-1.0, 4.0, 15.0])


def test_is_increasing():
    assert is_increasing(np.array([1.0, 0.0, 0.0]), 0.0, 5.0)
    assert not is_increasing(np.array([1.0, 0.0, 0.0]), -1.0, 5.0)


def test_non_monotone_quadratic_is_rejected():
    # U-shaped data: a quadratic fits better but would map more water to less storage.
    area = np.linspace(0, 10, 50)
    occ = (area - 3) ** 2 + 20
    curve, degree = fit_curve(area, occ, np.repeat(np.arange(5), 10))
    assert degree == 1
    assert is_increasing(curve.coef, 0, 10)


def test_hampel_flags_isolated_drop():
    days = np.arange(0, 100, 5)
    values = np.full(days.size, 17.0) + np.linspace(0, 1, days.size)
    values[8] = 2.0
    flags = hampel_outliers(days, values, window_days=20, floor=0.5)
    assert flags.tolist() == [i == 8 for i in range(days.size)]


def test_hampel_keeps_steady_trend_and_sparse_points():
    days = np.array([0, 5, 10, 15, 20, 200])
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 40.0])
    assert not hampel_outliers(days, values, window_days=20, floor=1.5).any()


def test_predictions_are_clipped_to_percent_range():
    curve = Curve(coef=np.array([10.0, 0.0]), halfwidth=5.0, lo=0.0, hi=20.0)
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


def test_decreasing_line_is_rejected():
    area = np.linspace(0, 10, 30)
    with pytest.raises(ValueError):
        fit_curve(area, 50 - 2 * area, np.repeat(np.arange(5), 6), degrees=(1,))


def test_curve_range_excludes_trimmed_points():
    area = np.r_[0.0, 0.1, np.linspace(3, 5, 40)]
    occ = np.r_[90.0, 92.0, 30 * (np.linspace(3, 5, 40) - 3) + 30]
    curve, _ = fit_curve(area, occ, np.arange(area.size) % 6)
    assert curve.lo == pytest.approx(3.0)


def test_fit_curve_needs_several_groups():
    with pytest.raises(ValueError):
        fit_curve(np.array([1.0, 2.0]), np.array([1.0, 2.0]), np.array([0, 0]))
