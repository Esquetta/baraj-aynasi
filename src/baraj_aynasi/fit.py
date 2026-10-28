"""Area-to-occupancy curves, held-out metrics and conformal error bars (pure functions)."""

from dataclasses import dataclass

import numpy as np


def extended_polyval(coef: np.ndarray, x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Polynomial inside [lo, hi], continued by its tangent line outside.

    A quadratic fitted on the observed area range can turn back on itself
    beyond that range; the tangent keeps extrapolation monotone.
    """
    x = np.asarray(x, float)
    d = np.polyder(coef)
    out = np.polyval(coef, np.clip(x, lo, hi))
    below, above = x < lo, x > hi
    out[below] += np.polyval(d, lo) * (x[below] - lo)
    out[above] += np.polyval(d, hi) * (x[above] - hi)
    return out


def is_increasing(coef: np.ndarray, lo: float, hi: float) -> bool:
    """True if the polynomial does not decrease anywhere on [lo, hi]."""
    return bool(np.all(np.polyval(np.polyder(coef), np.linspace(lo, hi, 101)) >= 0))


@dataclass(frozen=True)
class Curve:
    coef: np.ndarray  # numpy.polyfit order, highest power first
    halfwidth: float  # error-bar half width in occupancy points
    lo: float  # area range the curve was fitted on (km2)
    hi: float

    def predict(self, area_km2: np.ndarray) -> np.ndarray:
        """Occupancy (%) for the given areas, clipped to the physical 0..100 range."""
        return np.clip(extended_polyval(self.coef, area_km2, self.lo, self.hi), 0.0, 100.0)

    def interval(self, area_km2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = self.predict(area_km2)
        return np.clip(p - self.halfwidth, 0.0, 100.0), np.clip(p + self.halfwidth, 0.0, 100.0)


def lmeds_poly(area: np.ndarray, occ: np.ndarray, degree: int, trials: int = 500, seed: int = 0) -> np.ndarray:
    """Least-median-of-squares polynomial: the exact fit through degree+1 random
    points whose median squared residual over all points is smallest."""
    rng = np.random.default_rng(seed)
    best, best_med = None, np.inf
    for _ in range(trials):
        idx = rng.choice(area.size, degree + 1, replace=False)
        if np.unique(area[idx]).size < degree + 1:
            continue
        coef = np.polyfit(area[idx], occ[idx], degree)
        med = np.median((occ - np.polyval(coef, area)) ** 2)
        if med < best_med:
            best, best_med = coef, med
    return best if best is not None else np.polyfit(area, occ, degree)


def fit_poly(area: np.ndarray, occ: np.ndarray, degree: int, k: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """Least squares on the points within k robust standard deviations of a LMedS fit.

    Scenes where NDWI misses open water (algal or turbid water) sit far off
    the curve, often at the low-area end where they pull hardest; a LMedS start
    is not bent by them, so they can be trimmed before the final fit.
    Returns the coefficients and the mask of points kept.
    """
    area, occ = np.asarray(area, float), np.asarray(occ, float)
    keep = np.ones(area.size, bool)
    if area.size > 2 * (degree + 1):
        res = occ - np.polyval(lmeds_poly(area, occ, degree), area)
        # Rousseeuw's LMedS scale with its small-sample correction.
        scale = 1.4826 * (1 + 5 / (area.size - degree - 1)) * np.sqrt(np.median(res**2))
        trimmed = np.abs(res) <= max(k * scale, 1e-9)
        if trimmed.sum() > degree + 1:
            keep = trimmed
    return np.polyfit(area[keep], occ[keep], degree), keep


def out_of_fold_residuals(area: np.ndarray, occ: np.ndarray, groups: np.ndarray, degree: int) -> np.ndarray:
    """Residuals (observed - predicted) with each group (e.g. a year) held out in turn."""
    res = np.full(len(occ), np.nan)
    for g in np.unique(groups):
        test = groups == g
        if np.count_nonzero(~test) <= degree + 1:
            continue
        a = area[~test]
        coef, keep = fit_poly(a, occ[~test], degree)
        pred = extended_polyval(coef, area[test], a[keep].min(), a[keep].max())
        res[test] = occ[test] - np.clip(pred, 0.0, 100.0)
    return res


def fit_curve(
    area: np.ndarray,
    occ: np.ndarray,
    groups: np.ndarray,
    degrees: tuple[int, ...] = (1, 2),
    coverage: float = 0.9,
) -> tuple[Curve, int]:
    """Pick the polynomial degree by grouped cross-validation MAE, then refit on all data.

    Degrees whose full fit decreases anywhere on the area range it was fitted
    on are skipped, since more water surface cannot mean less stored water.
    The error bar is the `coverage` quantile of the absolute out-of-fold
    residuals (a cross-validation estimate, without a finite-sample
    correction), so it reflects error on unseen years.
    """
    area, occ = np.asarray(area, float), np.asarray(occ, float)
    best = None
    for deg in degrees:
        coef, keep = fit_poly(area, occ, deg)
        lo, hi = float(area[keep].min()), float(area[keep].max())
        if not is_increasing(coef, lo, hi):
            continue
        res = out_of_fold_residuals(area, occ, groups, deg)
        res = res[np.isfinite(res)]
        if res.size == 0:
            continue
        mae = float(np.mean(np.abs(res)))
        if best is None or mae < best[0]:
            best = (mae, deg, res, coef, lo, hi)
    if best is None:
        raise ValueError("no increasing curve, or not enough groups to cross-validate")
    _, deg, res, coef, lo, hi = best
    halfwidth = float(np.quantile(np.abs(res), coverage))
    return Curve(coef, halfwidth, lo, hi), deg


def hampel_outliers(
    days: np.ndarray, values: np.ndarray, window_days: float = 20, k: float = 4.0, floor: float = 0.0
) -> np.ndarray:
    """Flag values far from the median of their neighbours within +-window_days.

    A value is an outlier when it differs from the neighbours' median by more
    than k times their scaled MAD (or `floor`, whichever is larger). Values with
    fewer than three neighbours are never flagged. Uses no labels, so it can be
    applied to scenes after the ground truth ends.
    """
    days, values = np.asarray(days, float), np.asarray(values, float)
    out = np.zeros(values.size, bool)
    for i in range(values.size):
        near = (np.abs(days - days[i]) <= window_days) & (np.arange(values.size) != i)
        if np.count_nonzero(near) < 3:
            continue
        med = np.median(values[near])
        mad = 1.4826 * np.median(np.abs(values[near] - med))
        out[i] = abs(values[i] - med) > max(k * mad, floor)
    return out


def metrics(observed: np.ndarray, predicted: np.ndarray, lower=None, upper=None) -> dict:
    """MAE, RMSE and bias in occupancy points; interval coverage when bounds are given."""
    err = np.asarray(predicted, float) - np.asarray(observed, float)
    out = {
        "n": int(err.size),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "bias": float(np.mean(err)),
    }
    if lower is not None and upper is not None:
        inside = (observed >= lower) & (observed <= upper)
        out["coverage"] = float(np.mean(inside))
    return out
