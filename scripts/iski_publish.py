"""Daily İSKİ publish, run by a Windows scheduled task on the author's machine.

Reads today's figures from İSKİ's occupancy page (scripts/iski_harvest.py),
rewrites results/iski_series.csv (one figure per reservoir and day after İBB's
series ends), rebuilds the page and pushes the two if they changed. The push
touches site/, so GitHub Pages redeploys. The raw page reads stay in data/iski/.

It only publishes from a clean main that matches origin/main, so it never
pushes or discards the author's own work.

    uv run --extra harvest python scripts/iski_publish.py
    uv run python scripts/iski_publish.py --no-harvest --no-push
"""

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from baraj_aynasi import ibb
from baraj_aynasi.iski import load_collected, series

IN = Path("data/iski")
OUT = Path("results/iski_series.csv")
PUBLISHED = ["results/iski_series.csv", "site"]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def write_series() -> None:
    out = series(load_collected(IN), ibb.END)
    out["date"] = out.date.dt.strftime("%Y-%m-%d")
    out.to_csv(OUT, index=False, lineterminator="\n")
    print(f"wrote {OUT} ({len(out)} rows, last {out.date.max()})")


def build() -> None:
    write_series()
    subprocess.run([sys.executable, "scripts/build_site.py"], check=True)


def ready_to_publish() -> bool:
    if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        print("not on main, not publishing")
        return False
    if git("status", "--porcelain").stdout.strip():
        print("working tree has changes, not publishing")
        return False
    git("pull", "--ff-only")
    if git("rev-list", "--count", "origin/main..HEAD").stdout.strip() != "0":
        print("local commits not on origin/main, not publishing")
        return False
    return True


def commit_and_push() -> bool:
    """Commit the published files if they changed; True when nothing is left to push."""
    if not git("status", "--porcelain", "--", *PUBLISHED).stdout.strip():
        print("nothing new to publish")
        return True
    git("add", "--", *PUBLISHED)
    git("commit", "-m", f"Add İSKİ figures for {date.today():%Y-%m-%d}")
    pushed = git("push", check=False)
    if pushed.returncode == 0:
        print("pushed")
        return True
    print(f"push failed: {pushed.stderr.strip()}")
    # Only this script's commit sits on top of origin/main (checked above).
    git("fetch")
    git("reset", "--hard", "origin/main")
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-harvest", action="store_true", help="use the files already in data/iski")
    ap.add_argument("--no-push", action="store_true", help="rebuild locally, do not commit or push")
    args = ap.parse_args()
    print(f"--- {date.today()}")
    if not args.no_push and not ready_to_publish():
        sys.exit(1)
    harvest_failed = False
    if not args.no_harvest:
        harvest_failed = subprocess.run([sys.executable, "scripts/iski_harvest.py"]).returncode != 0
    build()
    if not args.no_push:
        # A daily update run may have pushed in between; rebuild on top of it once.
        if not commit_and_push():
            build()
            if not commit_and_push():
                sys.exit(1)
    if harvest_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
