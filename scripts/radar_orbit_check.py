"""Score per-orbit radar curves against the shared ones on İSKİ figures that are new
since the rule was committed (results/radar/README.md, "Orbit correction").

New figures are those in results/iski_series.csv that weren't in it at FREEZE: each
daily read adds that day and the same day in 2024 and 2025. The decision counts the
series as committed by the end of SCORE_DATE (or FALLBACK_DATE, see the rule). Both
curve sets are scored on the same pairs, made like scripts/iski_check.py from the new
figures: a reservoir's clean passes, averaged per day, within a day of a figure.
Before SCORE_DATE the script scores the current file, which isn't a decision.

    uv run python scripts/radar_orbit_check.py
    uv run python scripts/radar_orbit_check.py --since <commit>   # test the script on older figures
"""

import argparse
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import BY_KEY
from baraj_aynasi.fit import Curve
from baraj_aynasi.iski import match_nearest, one_per_scene
from baraj_aynasi.scenes import clean_scenes, curve_from_json

RADAR = Path("results/radar")
SERIES = "results/iski_series.csv"
FREEZE = "aeb7080fee9b632a682e1ca36e0d8ed4458bba29"  # the commit that set the rule
OFFERED = ["omerli", "alibey", "sazlidere", "pabucdere", "istrancalar"]
SCORE_DATE = "2026-12-21"
FALLBACK_DATE = "2027-01-31"
MIN_PAIRS = 15
MIN_GAIN = 0.5
MIN_WINS = 3
STOP_LINE = 10.0
MAX_DAYS = 1


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def series_at(commit: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(git("show", f"{commit}:{SERIES}")))


def last_commit_by(day: str) -> str:
    """The last commit of the İSKİ series by the end of `day`, Istanbul time."""
    return git("log", "-1", "--format=%H", f"--before={day}T23:59:59+03:00", "--", SERIES)


def new_figures(old: pd.DataFrame, now: pd.DataFrame) -> pd.DataFrame:
    seen = set(zip(old.dam, old.date))
    fresh = now[[k not in seen for k in zip(now.dam, now.date)]].copy()
    fresh["date"] = pd.to_datetime(fresh.date)
    return fresh


def predict(passes: pd.DataFrame, shared: Curve, by_orbit: dict) -> pd.Series:
    out = pd.Series(shared.predict(passes.water_km2.to_numpy()), index=passes.index)
    for orbit, entry in by_orbit.items():
        here = passes.orbit == int(orbit)
        out[here] = curve_from_json(entry).predict(passes.water_km2[here].to_numpy())
    return out


def satellites(ids: pd.Series) -> str:
    kinds = set(ids.str[:3])
    return "1A" if kinds == {"S1A"} else "1C/1D" if "S1A" not in kinds else "mixed"


def pairs(areas: pd.DataFrame, figures: pd.DataFrame, shared: dict, orbit: dict) -> pd.DataFrame:
    rows = []
    for key in BY_KEY:
        passes = clean_scenes(areas, key)
        passes = passes[passes.date > ibb.END].copy()
        passes["shared"] = predict(passes, curve_from_json(shared[key]), {})
        passes["orbit_curves"] = predict(passes, curve_from_json(shared[key]), orbit[key])
        days = passes.groupby("date", as_index=False).agg(
            shared=("shared", "mean"), orbit_curves=("orbit_curves", "mean"), satellites=("item_id", satellites)
        )
        obs = figures[figures.dam == key].sort_values("date").reset_index(drop=True)
        for (_, o), j in zip(obs.iterrows(), match_nearest(days.date, obs.date, MAX_DAYS)):
            if j >= 0:
                d = days.iloc[j]
                rows.append({"dam": key, "iski_date": o.date, "iski_pct": o.occupancy_pct, "scene_date": d.date, "satellites": d.satellites, "shared": d.shared, "orbit_curves": d.orbit_curves})
    if not rows:
        return pd.DataFrame(columns=["dam", "iski_pct", "satellites", "miss_shared", "miss_orbit_curves"])
    out = one_per_scene(pd.DataFrame(rows))
    for name in ("shared", "orbit_curves"):
        out[f"miss_{name}"] = (out[name] - out.iski_pct).abs()
    return out


def decide(p: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """The rule's table and verdict; verdict None when fewer than MIN_WINS reservoirs count."""
    p = p[p.dam.isin(OFFERED)]
    table = p.groupby("dam").agg(n=("iski_pct", "size"), mae_shared=("miss_shared", "mean"), mae_orbit=("miss_orbit_curves", "mean"))
    counted = table[table.n >= MIN_PAIRS]
    if len(counted) < MIN_WINS:
        return table, None
    pooled = p[p.dam.isin(counted.index)]
    gain = pooled.miss_shared.mean() - pooled.miss_orbit_curves.mean()
    wins = int((counted.mae_orbit < counted.mae_shared).sum())
    worst = counted.mae_orbit.max()
    adopt = gain >= MIN_GAIN and wins >= MIN_WINS and worst <= STOP_LINE
    return table, f"pooled gain {gain:.2f} points, lower on {wins} of {len(counted)}, worst {worst:.2f}: " + ("adopt orbit curves" if adopt else "keep shared curves")


def score(old: pd.DataFrame, now: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    areas = pd.read_csv(RADAR / "areas_vv_fixed.csv", parse_dates=["date"])
    shared = json.loads((RADAR / "vv_fixed/curves.json").read_text(encoding="utf-8"))
    orbit = json.loads((RADAR / "vv_fixed_orbit/curves.json").read_text(encoding="utf-8"))
    figures = new_figures(old, now)
    p = pairs(areas, figures, shared, orbit)
    print(f"{len(figures)} new İSKİ figures, {len(p)} pairs")
    table, verdict = decide(p)
    return p, table, verdict


def report(p: pd.DataFrame, table: pd.DataFrame) -> None:
    print(table.round(2).to_string())
    offered = p[p.dam.isin(OFFERED)]
    print(offered.groupby("satellites")[["miss_shared", "miss_orbit_curves"]].agg(["size", "mean"]).round(2).to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="commit whose İSKİ series counts as already seen, to test the script (default: FREEZE)")
    args = ap.parse_args()
    if git("rev-parse", "--is-shallow-repository") == "true":
        raise SystemExit("needs the full git history: run `git fetch --unshallow` first")
    old = series_at(args.since or FREEZE)
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    if args.since or today <= SCORE_DATE:
        p, table, verdict = score(old, pd.read_csv(SERIES))
        report(p, table)
        print(f"\nNot a decision (decided after {SCORE_DATE}): {verdict or f'fewer than {MIN_WINS} reservoirs have {MIN_PAIRS}+ new pairs'}")
        return
    p, table, verdict = score(old, series_at(last_commit_by(SCORE_DATE)))
    if verdict is None and today > FALLBACK_DATE:
        p, table, verdict = score(old, series_at(last_commit_by(FALLBACK_DATE)))
        verdict = verdict or "still too few reservoirs with enough pairs: keep shared curves"
    report(p, table)
    print(f"\n{verdict or f'too few reservoirs with enough pairs on {SCORE_DATE}: wait until {FALLBACK_DATE}'}")


if __name__ == "__main__":
    main()
