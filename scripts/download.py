"""Download clipped chips for every cached STAC item and dam.

Run scripts/search.py first. Re-running skips items already in the index.

    uv run python scripts/download.py [--tile 35TPF] [--workers 8]
"""

import argparse
import concurrent.futures as cf
from pathlib import Path

from baraj_aynasi.chips import ChipStore, fetch_item, write_grids
from baraj_aynasi.dams import BY_KEY
from baraj_aynasi.stac import DAM_TILE, TILES, load_items

STAC_CACHE = Path("data/stac")
CHIPS = Path("data/chips")
MIN_CLEAR_BOX = 0.3  # loose pre-filter; the AOI-level filter is applied when measuring areas


def run_tile(tile: str, workers: int) -> None:
    dams = [BY_KEY[k] for k, t in DAM_TILE.items() if t == tile]
    items = load_items(STAC_CACHE, tile)
    store = ChipStore(CHIPS, tile)
    if not all((CHIPS / d.key / "grid.json").exists() for d in dams):
        write_grids(CHIPS, dams, items[-1])
    todo = [it for it in items if it.id not in store.done]
    print(f"{tile}: {len(items)} items, {len(todo)} to fetch", flush=True)
    failed = 0
    with cf.ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(fetch_item, it, dams, store, MIN_CLEAR_BOX): it for it in todo}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            it = futures[fut]
            try:
                store.record(fut.result())
            except Exception as exc:  # network errors: leave out of the index, retry on the next run
                failed += 1
                print(f"  failed {it.id}: {type(exc).__name__}: {exc}", flush=True)
            if n % 50 == 0:
                print(f"  {tile}: {n}/{len(todo)} done, {failed} failed", flush=True)
    print(f"{tile}: finished, {failed} failed", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", choices=list(TILES), action="append")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    for tile in args.tile or list(TILES):
        run_tile(tile, args.workers)


if __name__ == "__main__":
    main()
