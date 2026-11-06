"""Score per-orbit radar curves against the shared ones on İSKİ figures that are new
since the rule was committed (results/radar/README.md, "Orbit correction").

New figures are those in results/iski_series.csv that weren't in it at the commit
that added this script: each daily read adds that day and the same day in 2024 and
2025. Both curve sets are scored on the same pairs, made as in scripts/iski_check.py:
a reservoir's clean passes, averaged per day, within a day of a figure. The decision
is taken on SCORE_DATE; runs before it don't count.

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
OFFERED = ["omerli", "alibey", "sazlidere", "pabucdere", "istrancalar"]
SCORE_DATE = "2026-12-21"
MIN_PAIRS = 15
MIN_GAIN = 0.5
MIN_WINS = 3
STOP_LINE = 10.0
MAX_DAYS = 1


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def new_figures(since: str | None) -> pd.DataFrame:
    since = since or git("log", "--diff-filter=A", "-n1", "--format=%H", "--", "scripts/radar_orbit_check.py").strip()
    old = pd.read_csv(io.StringIO(git("show", f"{since}:{SERIES}")))
    now = pd.read_csv(SERIES)
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


def pairs(areas: pd.DataFrame, figures: pd.DataFrame, shared: dict, orbit: dict) -> pd.DataFrame:
    rows = []
    for key in BY_KEY:
        passes = clean_scenes(areas, key)
        passes = passes[passes.date > ibb.END].copy()
        passes["shared"] = predict(passes, curve_from_json(shared[key]), {})
        passes["orbit_curves"] = predict(passes, curve_from_json(shared[key]), orbit[key])
        passes["platforms"] = passes.item_id.str[:3]
        days = passes.groupby("date", as_index=False).agg(
            shared=("shared", "mean"), orbit_curves=("orbit_curves", "mean"), platforms=("platforms", lambda s: "+".join(sorted(set(s))))
        )
        obs = figures[figures.dam == key].sort_values("date").reset_index(drop=True)
        for (_, o), j in zip(obs.iterrows(), match_nearest(days.date, obs.date, MAX_DAYS)):
            if j >= 0:
                d = days.iloc[j]
                rows.append({"dam": key, "iski_date": o.date, "iski_pct": o.occupancy_pct, "scene_date": d.date, "platforms": d.platforms, "shared": d.shared, "orbit_curves": d.orbit_curves})
    out = one_per_scene(pd.DataFrame(rows))
    for name in ("shared", "orbit_curves"):
        out[f"miss_{name}"] = (out[name] - out.iski_pct).abs()
    return out


def decide(p: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    table = p[p.dam.isin(OFFERED)].groupby("dam").agg(n=("iski_pct", "size"), mae_shared=("miss_shared", "mean"), mae_orbit=("miss_orbit_curves", "mean"))
    counted = table[table.n >= MIN_PAIRS]
    if len(counted) < MIN_WINS:
        return table, f"not enough data: {len(counted)} reservoirs have {MIN_PAIRS}+ new pairs"
    pooled = p[p.dam.isin(counted.index)]
    gain = pooled.miss_shared.mean() - pooled.miss_orbit_curves.mean()
    wins = int((counted.mae_orbit < counted.mae_shared).sum())
    worst = counted.mae_orbit.max()
    adopt = gain >= MIN_GAIN and wins >= MIN_WINS and worst <= STOP_LINE
    verdict = f"pooled gain {gain:.2f} points, lower on {wins} of {len(counted)}, worst {worst:.2f}: " + ("adopt orbit curves" if adopt else "keep shared curves")
    return table, verdict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="commit whose İSKİ series counts as already seen (default: the one that added this script)")
    args = ap.parse_args()
    areas = pd.read_csv(RADAR / "areas_vv_fixed.csv", parse_dates=["date"])
    shared = json.loads((RADAR / "vv_fixed/curves.json").read_text(encoding="utf-8"))
    orbit = json.loads((RADAR / "vv_fixed_orbit/curves.json").read_text(encoding="utf-8"))
    figures = new_figures(args.since)
    p = pairs(areas, figures, shared, orbit)
    table, verdict = decide(p)
    print(f"{len(figures)} new İSKİ figures, {len(p)} pairs")
    print(table.round(2).to_string())
    print(p.groupby("platforms")[["miss_shared", "miss_orbit_curves"]].agg(["size", "mean"]).round(2).to_string())
    if pd.Timestamp.now() < pd.Timestamp(SCORE_DATE):
        print(f"\nBefore {SCORE_DATE}: not a decision.")
    print(verdict)


if __name__ == "__main__":
    main()
