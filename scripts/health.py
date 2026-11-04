"""Daily health report, run by .github/workflows/health.yml.

Opens a GitHub issue (label `health`, assigned to the owner) for each problem it
finds and closes the issue once the problem is gone: İSKİ figures or radar estimates
that stopped updating, a failed or missing satellite update, a live page that differs
from main, and offered reservoirs whose recent error passed the stop line.

    uv run python -X utf8 scripts/health.py --dry-run     # print problems only
    uv run python scripts/health.py --test-alert          # also open a test issue
"""

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from build_site import STATUS, URL

from baraj_aynasi.dams import DAMS
from baraj_aynasi.health import (
    PAGE_TITLE,
    iski_stale,
    page_differs,
    plan,
    radar_stale,
    recent_error,
    update_unhealthy,
)

OWNER = "Esquetta"
LABEL = "health"
PAGES = {"site/index.html": URL, "site/tr/index.html": URL + "tr/"}
DEPLOY_GRACE_S = 3600  # a page pushed within the hour may still be deploying


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def check_pages() -> dict[str, str] | None:
    """Problems with the live pages, or None if a recent commit means they can't be compared yet."""
    if time.time() - int(run("git", "log", "-1", "--format=%ct")) < DEPLOY_GRACE_S:
        print("latest commit is under an hour old, live page not compared")
        return None
    out = {}
    for built, url in PAGES.items():
        try:
            with urlopen(url, timeout=30) as resp:
                out |= page_differs(url, resp.read(), Path(built).read_bytes())
        except OSError as err:
            out[f"{PAGE_TITLE}: {url}"] = f"The page could not be read: {err}"
    return out


def problems() -> tuple[dict[str, str], tuple[str, ...]]:
    """The problems found, and the title prefixes of checks that did not run."""
    today = pd.Timestamp.now().normalize()
    runs = json.loads(run("gh", "run", "list", "--workflow", "update.yml", "-L", "1", "--json", "conclusion,createdAt,url"))
    offered = {d.key: d.name for d in DAMS if STATUS[d.key] == "offered"}
    pages = check_pages()
    found = {
        **iski_stale(pd.read_csv("results/iski_series.csv", parse_dates=["date"]), today),
        **update_unhealthy(runs[0] if runs else None, today),
        **(pages or {}),
        **recent_error(pd.read_csv("results/iski_check.csv"), offered),
        **radar_stale(pd.read_csv("results/radar/vv_fixed/estimates_2024_2026.csv", parse_dates=["date"]), offered, today),
        **recent_error(pd.read_csv("results/radar/vv_fixed/iski_check.csv"), offered, "Recent radar error"),
    }
    return found, (PAGE_TITLE,) if pages is None else ()


def report(found: dict[str, str], unchecked: tuple[str, ...]) -> None:
    run("gh", "label", "create", LABEL, "--force", "--color", "B60205", "--description", "Opened by the daily health check")
    issues = json.loads(run("gh", "issue", "list", "--label", LABEL, "--state", "open", "--json", "number,title"))
    to_open, to_close = plan(found, issues, unchecked)
    for title in to_open:
        print("opened:", run("gh", "issue", "create", "--title", title, "--body", found[title], "--label", LABEL, "--assignee", OWNER).strip())
    for number in to_close:
        run("gh", "issue", "close", str(number), "--comment", "The health check no longer finds this problem.")
        print("closed:", number)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print problems, leave issues alone")
    ap.add_argument("--test-alert", action="store_true", help="add a test problem; the next normal run closes it")
    args = ap.parse_args()
    found, unchecked = problems()
    if args.test_alert:
        found["Health check test"] = "Test of the alert path. The next normal run closes this issue."
    print(f"{len(found)} problem(s)")
    for title, body in found.items():
        print(f"- {title}\n  {body}")
    if not args.dry_run:
        report(found, unchecked)


if __name__ == "__main__":
    main()
