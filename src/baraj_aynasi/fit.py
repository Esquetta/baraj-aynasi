"""Area-to-occupancy curves, held-out metrics and conformal error bars (pure functions)."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Curve:
    coef: np.ndarray  # numpy.polyfit order, highest power first
    halfwidth: float  # error-bar half width in occupancy points

    def predict(self, area_km2: np.ndarray) -> np.ndarray:
        """Occupancy (%) for the given areas, clipped to the physical 0..100 range."""
        return np.clip(np.polyval(self.coef, area_km2), 0.0, 100.0)

    def interval(self, area_km2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        p = self.predict(area_km2)
        return np.clip(p - self.halfwidth, 0.0, 100.0), np.clip(p + self.halfwidth, 0.0, 100.0)


def fit_poly(area: np.ndarray, occ: np.ndarray, degree: int) -> np.ndarray:
    return np.polyfit(np.asarray(area, float), np.asarray(occ, float), degree)


def out_of_fold_residuals(area: np.ndarray, occ: np.ndarray, groups: np.ndarray, degree: int) -> np.ndarray:
    """Residuals (observed - predicted) with each group (e.g. a year) held out in turn."""
    res = np.full(len(occ), np.nan)
    for g in np.unique(groups):
        test = groups == g
        if np.count_nonzero(~test) <= degree + 1:
            continue
        coef = fit_poly(area[~test], occ[~test], degree)
        res[test] = occ[test] - np.clip(np.polyval(coef, area[test]), 0.0, 100.0)
    return res


def fit_curve(
    area: np.ndarray,
    occ: np.ndarray,
    groups: np.ndarray,
    degrees: tuple[int, ...] = (1, 2),
    coverage: float = 0.9,
) -> tuple[Curve, int]:
    """Pick the polynomial degree by grouped cross-validation MAE, then refit on all data.

    The error bar is the `coverage` quantile of the absolute out-of-fold
    residuals (split-conformal style), so it reflects error on unseen years.
    """
    best = None
    for deg in degrees:
        res = out_of_fold_residuals(area, occ, groups, deg)
        res = res[np.isfinite(res)]
        if res.size == 0:
            continue
        mae = float(np.mean(np.abs(res)))
        if best is None or mae < best[0]:
            best = (mae, deg, res)
    if best is None:
        raise ValueError("not enough groups to cross-validate")
    _, deg, res = best
    halfwidth = float(np.quantile(np.abs(res), coverage))
    return Curve(fit_poly(area, occ, deg), halfwidth), deg


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
