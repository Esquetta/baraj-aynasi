"""Which scenes count, and the satellite-only estimates made from them (pure functions)."""

import numpy as np
import pandas as pd

from .fit import Curve, hampel_outliers

MIN_CLEAR = 0.98  # share of the AOI that must be cloud-free
OUTLIER_WINDOW_DAYS = 20
OUTLIER_FLOOR = 0.03  # of the dam's 95th-percentile area


def clean_scenes(areas: pd.DataFrame, dam_key: str) -> pd.DataFrame:
    """A dam's mostly cloud-free scenes, sorted by date, without the ones whose
    water area jumps away from their neighbours (see hampel_outliers)."""
    a = areas[(areas.dam == dam_key) & (areas.clear_frac >= MIN_CLEAR)].sort_values("date")
    if a.empty:
        return a
    days = (a.date - a.date.min()).dt.days.to_numpy()
    floor = OUTLIER_FLOOR * np.quantile(a.water_km2, 0.95)
    return a[~hampel_outliers(days, a.water_km2.to_numpy(), OUTLIER_WINDOW_DAYS, floor=floor)]


def curve_from_json(entry: dict) -> Curve:
    return Curve(np.array(entry["coef"]), entry["error_bar_90"], *entry["fit_range_km2"])


def estimates(areas: pd.DataFrame, curves: dict, after: pd.Timestamp) -> pd.DataFrame:
    """Occupancy estimates with 90% bars for every clean scene after `after`,
    from frozen curves (curves.json): nothing is refitted."""
    frames = []
    for key, entry in curves.items():
        curve = curve_from_json(entry)
        new = clean_scenes(areas, key)
        new = new[new.date > after]
        lo, hi = curve.interval(new.water_km2.to_numpy())
        frames.append(
            pd.DataFrame(
                {
                    "dam": key,
                    "date": new.date.dt.date,
                    "item_id": new.item_id,
                    "water_km2": new.water_km2,
                    "occupancy_est": curve.predict(new.water_km2.to_numpy()).round(1),
                    "lower_90": lo.round(1),
                    "upper_90": hi.round(1),
                    "heldout_passed": entry["heldout_passed"],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
