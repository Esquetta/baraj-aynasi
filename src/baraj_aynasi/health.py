"""Checks behind the daily health report (scripts/health.py).

Each check returns {issue title: issue body}; an empty dict means healthy. Titles
stay the same from day to day, so one open issue tracks one problem.
"""

import pandas as pd

STOP_LINE = 10.0  # occupancy points, the project's stop rule on held-out error
RECENT_PAIRS = 5
MAX_AGE_DAYS = 2
RADAR_MAX_AGE_DAYS = 21
PAGE_TITLE = "Live page differs from main"


def iski_stale(series: pd.DataFrame, today: pd.Timestamp) -> dict[str, str]:
    """İSKİ figures come from a task on the author's machine; each missed day loses its ten-year window."""
    last = series.groupby("dam").date.max().min()
    if (today - last).days <= MAX_AGE_DAYS:
        return {}
    return {
        "İSKİ figures have stopped updating": (
            f"At least one reservoir's last figure in results/iski_series.csv is from {last:%Y-%m-%d}. "
            "Check the scheduled task and data/iski/harvest.log on the author's machine."
        )
    }


def update_unhealthy(run: dict | None, today: pd.Timestamp) -> dict[str, str]:
    """`run` is the latest run of the daily satellite update, as `gh run list --json` gives it."""
    title = "Daily satellite update is not running"
    if run is None:
        return {title: "The workflow has no runs."}
    if run["conclusion"] not in ("success", ""):  # "" while it is still running
        return {title: f"The latest run ended with {run['conclusion']}: {run['url']}"}
    created = pd.Timestamp(run["createdAt"]).tz_localize(None).normalize()
    if (today - created).days > MAX_AGE_DAYS:
        return {title: f"The latest run started on {created:%Y-%m-%d}: {run['url']}"}
    return {}


def page_differs(url: str, live: bytes, built: bytes) -> dict[str, str]:
    if live.replace(b"\r\n", b"\n") == built.replace(b"\r\n", b"\n"):
        return {}
    return {f"{PAGE_TITLE}: {url}": "The last deploy may have failed. Check the Deploy site workflow."}


def radar_stale(estimates: pd.DataFrame, names: dict[str, str], today: pd.Timestamp) -> dict[str, str]:
    """Radar passes come every five or six days and the radar step may fail without failing the update."""
    last = estimates[estimates.dam.isin(names)].groupby("dam").date.max().min()
    if (today - last).days <= RADAR_MAX_AGE_DAYS:
        return {}
    return {
        "Radar estimates have stopped updating": (
            f"At least one offered reservoir's last radar estimate is from {last:%Y-%m-%d}. "
            "Check the radar step in the Update estimates workflow."
        )
    }


def recent_error(pairs: pd.DataFrame, names: dict[str, str], label: str = "Recent error") -> dict[str, str]:
    """Offered reservoirs (key -> name) whose latest pairs with İSKİ miss by more than the stop line."""
    out = {}
    for key, name in names.items():
        title = f"{label} above the stop line: {name}"
        last = pairs[pairs.dam == key].sort_values("iski_date").tail(RECENT_PAIRS)
        if last.empty:
            out[title] = "This reservoir has no comparisons with İSKİ, so its error cannot be checked."
            continue
        mae = (last.estimate_pct - last.iski_pct).abs().mean()
        if mae > STOP_LINE:
            out[title] = (
                f"The last {len(last)} comparisons with İSKİ ({last.iski_date.iloc[0]} to {last.iski_date.iloc[-1]}) "
                f"miss by {mae:.1f} points on average; the stop line is {STOP_LINE:.0f}. "
                "Review whether this reservoir should still be offered."
            )
    return out


def plan(problems: dict[str, str], open_issues: list[dict], unchecked: tuple[str, ...] = ()) -> tuple[list[str], list[int]]:
    """Titles to open and issue numbers to close. Issues whose title starts with an `unchecked` prefix
    stay open: that check did not run, so their problem may still be there."""
    titles = {i["title"] for i in open_issues}
    to_close = [i["number"] for i in open_issues if i["title"] not in problems and not i["title"].startswith(unchecked)]
    return [t for t in problems if t not in titles], to_close
