"""Download clipped Sentinel-1 RTC chips (VV, VH) for each dam from Planetary Computer.

Chips go to data/radar/chips/<dam>/<first item id>.npz and aren't committed. Finished
chips are skipped, so a stopped run can be restarted.

    uv run python scripts/radar_download.py                       # every pass, 2017 on
    uv run python scripts/radar_download.py --sample 40 --until 2022-06-30

--sample keeps N passes per dam, evenly spaced across İBB occupancy, for a pilot.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import product, repeat
from pathlib import Path

import numpy as np
import pandas as pd
import pystac_client
import rasterio

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS, search_box
from baraj_aynasi.measure import load_grid
from baraj_aynasi.radar import (
    BANDS,
    GDAL,
    encode_db,
    group_passes,
    read_band,
    search_cached,
)
from baraj_aynasi.stac import STAC_URL

ROOT = Path("data/radar")
CHIPS = Path("data/chips")
WORKERS = 8


def dam_passes(dam, client, until: pd.Timestamp) -> list[list[dict]]:
    months = [(y, m) for y, m in product(range(2017, until.year + 1), range(1, 13)) if (y, m) <= (until.year, until.month)]
    box = search_box(dam)
    with ThreadPoolExecutor(WORKERS) as pool:
        found = pool.map(lambda ym: search_cached(ROOT / "stac" / dam.key, client, box, *ym), months)
    items = [it for month in found for it in month if it["properties"]["datetime"][:10] <= f"{until:%Y-%m-%d}"]
    return group_passes(items)


def sample_by_occupancy(passes: list[list[dict]], ibb_column: str, n: int) -> list[list[dict]]:
    gt = ibb.load()
    gt = gt[gt.ibb_column == ibb_column].set_index("date").occupancy_pct
    dated = [(gt.get(pd.Timestamp(p[0]["properties"]["datetime"][:10])), p) for p in passes]
    dated = sorted([d for d in dated if d[0] is not None], key=lambda d: d[0])
    return [dated[i][1] for i in np.linspace(0, len(dated) - 1, min(n, len(dated))).astype(int)]


def fetch(dam, items: list[dict], grids: list[dict]) -> bool:
    path = ROOT / "chips" / dam.key / f"{items[0]['id']}.npz"
    if path.exists():
        return False
    arrays = {"datetime": items[0]["properties"]["datetime"], "orbit": items[0]["properties"]["sat:relative_orbit"]}
    for attempt in range(3):
        try:
            with rasterio.Env(**GDAL):
                for band in BANDS:
                    for j, grid in enumerate(grids):
                        arrays[f"{band}_{j}"] = encode_db(read_band(items, band, grid))
            break
        except rasterio.errors.RasterioIOError as exc:
            print(f"  {items[0]['id']}: attempt {attempt + 1}: {str(exc)[:80]}", flush=True)
    else:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, help="passes per dam, evenly spaced across occupancy")
    ap.add_argument("--until", default=None, help="last date, default today")
    args = ap.parse_args()
    until = pd.Timestamp(args.until) if args.until else pd.Timestamp.now().normalize()
    client = pystac_client.Client.open(STAC_URL)
    for dam in DAMS:
        passes = dam_passes(dam, client, until)
        if args.sample:
            passes = sample_by_occupancy(passes, dam.ibb_column, args.sample)
        grids = load_grid(CHIPS, dam.key)
        with ThreadPoolExecutor(WORKERS) as pool:
            done = sum(pool.map(fetch, repeat(dam), passes, repeat(grids)))
        print(f"{dam.key}: {len(passes)} passes, {done} new", flush=True)


if __name__ == "__main__":
    main()
