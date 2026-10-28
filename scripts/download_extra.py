"""Download red (B04) and SWIR (B11) for scenes the occupancy fit uses
(at least 98% of the AOI cloud-free in results/areas.csv). Inputs for the U-Net.

    uv run python scripts/download_extra.py [--workers 8]
"""

import argparse
import concurrent.futures as cf
from pathlib import Path

import pandas as pd

from baraj_aynasi.chips import extra_path, fetch_extra
from baraj_aynasi.dams import BY_KEY
from baraj_aynasi.stac import DAM_TILE, load_items

CHIPS = Path("data/chips")
MIN_CLEAR = 0.98


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    areas = pd.read_csv("results/areas.csv")
    areas = areas[areas.clear_frac >= MIN_CLEAR]
    jobs = []
    for tile in sorted(set(DAM_TILE.values())):
        items = {it.id: it for it in load_items(Path("data/stac"), tile)}
        need = areas[areas.dam.map(DAM_TILE) == tile]
        for item_id, g in need.groupby("item_id"):
            dams = [BY_KEY[k] for k in g.dam if not extra_path(CHIPS / k / f"{item_id}.npz").exists()]
            if dams:
                jobs.append((items[item_id], dams))
    print(f"{len(jobs)} items to fetch ({sum(len(d) for _, d in jobs)} chips)", flush=True)
    failed = 0
    with cf.ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(fetch_extra, it, dams, CHIPS): it for it, dams in jobs}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            try:
                fut.result()
            except Exception as exc:  # network errors: rerun picks them up
                failed += 1
                print(f"  failed {futures[fut].id}: {type(exc).__name__}: {exc}", flush=True)
            if n % 100 == 0:
                print(f"  {n}/{len(jobs)} done, {failed} failed", flush=True)
    print(f"finished, {failed} failed", flush=True)


if __name__ == "__main__":
    main()
