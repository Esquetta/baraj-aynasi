"""İSKİ reported occupancy after the İBB series ends: parsing and date matching."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

# İSKİ API names -> dams.py keys
DAM_KEYS = {
    "Omerli": "omerli",
    "Darlik": "darlik",
    "Elmali": "elmali",
    "Terkos": "terkos",
    "Alibey": "alibey",
    "BCekmece": "buyukcekmece",
    "Sazlidere": "sazlidere",
    "Kazandere": "kazandere",
    "Pabucdere": "pabucdere",
    "Istrancalar": "istrancalar",
}


def _date(s: str) -> pd.Timestamp:
    return pd.to_datetime(s, format="%d.%m.%Y")


def parse_daily_summary(path: Path) -> pd.DataFrame:
    """One `gunlukOzet` response (all dams, one day), e.g. a Wayback Machine copy."""
    data = json.loads(path.read_text(encoding="utf-8"))["data"]
    return pd.DataFrame(
        {"dam": DAM_KEYS[d["baraj"]], "date": _date(d["tarih"]), "occupancy_pct": float(d["yuzde"]), "source": "daily_summary"}
        for d in data
    )


def parse_page_windows(path: Path) -> pd.DataFrame:
    """Per-dam windows read from the İSKİ occupancy page: month ends, last 14 days,
    and the same calendar day in each of the last ten years."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for name, windows in raw.items():
        for source, key in (("month_end", "ayson"), ("last_14_days", "ondort")):
            rows += [(DAM_KEYS[name], _date(r["tarih"]), float(r["dolulukOrani"]), source) for r in windows[key]]
        rows += [(DAM_KEYS[name], _date(r["tarih"]), float(r["oran"]), "same_day_10y") for r in windows["onyil"]]
    return pd.DataFrame(rows, columns=["dam", "date", "occupancy_pct", "source"])


def pick_by_priority(obs: pd.DataFrame, priority: list[str]) -> pd.DataFrame:
    """One figure per dam and date: the source listed first in `priority` wins."""
    rank = obs.source.map(priority.index)
    return obs.assign(_rank=rank).sort_values(["dam", "date", "_rank"]).drop_duplicates(["dam", "date"]).drop(columns="_rank")


def one_per_scene(pairs: pd.DataFrame) -> pd.DataFrame:
    """Keep, for each dam and scene date, the pair whose İSKİ date is closest
    (earlier İSKİ date on ties), so no measurement is counted twice."""
    gap = (pd.to_datetime(pairs.iski_date) - pd.to_datetime(pairs.scene_date)).dt.days.abs()
    out = pairs.assign(gap_days=gap).sort_values(["dam", "scene_date", "gap_days", "iski_date"], kind="stable")
    return out.drop_duplicates(["dam", "scene_date"])


def match_nearest(scene_dates: pd.Series, obs_dates: pd.Series, max_days: int) -> np.ndarray:
    """For each observation date, the index of the nearest scene date within
    `max_days` (ties go to the earlier scene), or -1 when none is close enough."""
    s = scene_dates.to_numpy(dtype="datetime64[D]").astype(np.int64)
    out = np.full(len(obs_dates), -1)
    for i, d in enumerate(obs_dates.to_numpy(dtype="datetime64[D]").astype(np.int64)):
        if s.size == 0:
            break
        gap = np.abs(s - d)
        j = int(np.argmin(gap))
        if gap[j] <= max_days:
            out[i] = j
    return out
