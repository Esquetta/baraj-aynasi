"""Guesses made without imagery, scored next to each satellite series on its own dates.

The rule is in results/baselines/README.md. Writes results/baselines/heldout.csv and
results/baselines/iski.csv: the average miss in occupancy points per reservoir, series
and guess. The fading-gap column was added after the rule and isn't part of its
verdict. Needs the İBB file in data/ibb/, see docs/data-sources.md.

    uv run python scripts/baselines.py
"""

import io
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS
from baraj_aynasi.fit import fit_curve
from baraj_aynasi.scenes import clean_scenes

OUT = Path("results/baselines")
# Areas as committed when each series' held-out errors were published: the robust fit
# samples by row position and its scene filter scales with the whole file, so later
# rows would shift the held-out numbers slightly.
SERIES = {
    "ndwi": ("b88fc36c1a24c6469dd12bc9bb6ff521ac12e27e", "results/areas.csv", Path("results/iski_check.csv")),
    "radar": ("c1740745708628d4b6e441c6c8051f1957e97c28", "results/radar/areas_vv_fixed.csv", Path("results/radar/vv_fixed/iski_check.csv")),
    "unet": ("07706007c8999c525f2abcfbe951be2e80fb422f", "results/unet/areas_unet.csv", Path("results/unet/unet/iski_check.csv")),
}
TRAIN_END = pd.Timestamp("2022-06-30")
WINDOW_DAYS = 7
LAST_YEAR_SLACK = 1
FADE_DAYS = 365


def git_show(commit: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{commit}:{path}"], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def anniversary(d: pd.Timestamp, year: int) -> pd.Timestamp:
    return pd.Timestamp(year, d.month, 28 if (d.month, d.day) == (2, 29) and not pd.Timestamp(year, 1, 1).is_leap_year else d.day)


def season(history: pd.Series, cutoff: pd.Timestamp, dates: pd.Series) -> np.ndarray:
    """Mean figure within WINDOW_DAYS calendar days of an anniversary of each date, over the history up to cutoff."""
    h = history[history.index <= cutoff]
    out = []
    for d in pd.DatetimeIndex(dates):
        years = range(h.index.year.min() - 1, h.index.year.max() + 2)
        anchors = pd.DatetimeIndex([anniversary(d, y) for y in years]).to_numpy()
        days = h.index.to_numpy()
        gap = np.abs((days[:, None] - anchors[None, :]) / np.timedelta64(1, "D")).min(axis=1)
        out.append(h.to_numpy()[gap <= WINDOW_DAYS].mean())
    return np.array(out)


def fading_gap(history: pd.Series, cutoff: pd.Timestamp, dates: pd.Series) -> np.ndarray:
    """Added after the rule: the season guess plus the last figure's gap from it, fading over FADE_DAYS."""
    last = history[history.index <= cutoff]
    gap = last.iloc[-1] - season(history, cutoff, pd.Series([last.index[-1]]))[0]
    age = (pd.DatetimeIndex(dates) - cutoff).days.to_numpy()
    return np.clip(season(history, cutoff, dates) + gap * np.exp(-age / FADE_DAYS), 0, 100)


def last_year(reported: pd.Series, dates: pd.Series) -> np.ndarray:
    """The figure a year before each date, within LAST_YEAR_SLACK days; NaN when there is none."""
    known = reported.sort_index()
    out = []
    for d in pd.DatetimeIndex(dates):
        target = d - pd.DateOffset(years=1)
        near = known[(known.index >= target - pd.Timedelta(days=LAST_YEAR_SLACK)) & (known.index <= target + pd.Timedelta(days=LAST_YEAR_SLACK))]
        out.append(near.iloc[np.argmin(np.abs((near.index - target).days))] if len(near) else np.nan)
    return np.array(out, dtype=float)


def unchanged(history: pd.Series, cutoff: pd.Timestamp, n: int) -> np.ndarray:
    return np.full(n, history[history.index <= cutoff].iloc[-1])


def scores(dam: str, series: str, dates: pd.Series, truth: np.ndarray, estimate: np.ndarray, history: pd.Series, reported: pd.Series, cutoff: pd.Timestamp) -> dict:
    miss = lambda guess: np.abs(guess - truth)  # noqa: E731
    ly = last_year(reported, dates)
    has_ly = np.isfinite(ly)
    by_season = season(history, cutoff, dates)
    row = {
        "dam": dam,
        "series": series,
        "n": len(truth),
        "mae_series": miss(estimate).mean(),
        "mae_season": miss(by_season).mean(),
        "closer_than_season": int((miss(estimate) < miss(by_season)).sum()),
        "mae_unchanged": miss(unchanged(history, cutoff, len(truth))).mean(),
        "n_last_year": int(has_ly.sum()),
        "mae_series_last_year_dates": miss(estimate)[has_ly].mean() if has_ly.any() else np.nan,
        "mae_last_year": miss(ly)[has_ly].mean() if has_ly.any() else np.nan,
    }
    row["beats_guesses"] = bool(
        row["mae_series"] < row["mae_season"]
        and row["mae_series"] < row["mae_unchanged"]
        and (not has_ly.any() or row["mae_series_last_year_dates"] < row["mae_last_year"])
    )
    row["mae_extra_fading_gap"] = miss(fading_gap(history, cutoff, dates)).mean()  # not in the rule, not in the flag
    return row


def main() -> None:
    gt = ibb.load()
    iski = pd.read_csv("results/iski_series.csv", parse_dates=["date"])
    held, against_iski = [], []
    for name, (commit, areas_path, pairs_path) in SERIES.items():
        areas = pd.read_csv(io.StringIO(git_show(commit, areas_path)), parse_dates=["date"])
        pairs = pd.read_csv(pairs_path, parse_dates=["iski_date"])
        for dam in DAMS:
            labels = gt[gt.ibb_column == dam.ibb_column][["date", "occupancy_pct"]].dropna()
            history = labels.set_index("date").occupancy_pct.sort_index()
            lab = clean_scenes(areas, dam.key).merge(labels, on="date")
            train, test = lab[lab.date <= TRAIN_END], lab[lab.date > TRAIN_END]
            curve, _ = fit_curve(train.water_km2.to_numpy(), train.occupancy_pct.to_numpy(), train.date.dt.year.to_numpy())
            held.append(scores(dam.key, name, test.date, test.occupancy_pct.to_numpy(), curve.predict(test.water_km2.to_numpy()), history, history, TRAIN_END))
            p = pairs[pairs.dam == dam.key]
            if p.empty:
                continue
            later = iski[iski.dam == dam.key].set_index("date").occupancy_pct
            reported = pd.concat([history, later[later.index > ibb.END]])
            against_iski.append(scores(dam.key, name, p.iski_date, p.iski_pct.to_numpy(), p.estimate_pct.to_numpy(), history, reported, ibb.END))
    OUT.mkdir(parents=True, exist_ok=True)
    for file, rows in (("heldout.csv", held), ("iski.csv", against_iski)):
        table = pd.DataFrame(rows).round(2)
        table.to_csv(OUT / file, index=False)
        print(file)
        print(table.to_string(index=False), "\n")


if __name__ == "__main__":
    main()
