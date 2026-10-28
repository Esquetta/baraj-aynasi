"""Cache Sentinel-2 L2A STAC items for every tile and month, 2017-01 to today.

    uv run python scripts/search.py
"""

import datetime as dt
from pathlib import Path

import pystac_client

from baraj_aynasi.stac import STAC_URL, TILES, search_cached

CACHE = Path("data/stac")


def main() -> None:
    client = pystac_client.Client.open(STAC_URL)
    today = dt.date.today()
    missing = []
    for tile in TILES:
        total = 0
        for year in range(2017, today.year + 1):
            for month in range(1, 13):
                if (year, month) > (today.year, today.month):
                    break
                try:
                    total += len(search_cached(CACHE, tile, year, month, client))
                except RuntimeError as exc:  # not cached; the next run retries it
                    missing.append(str(exc))
        print(f"{tile}: {total} items", flush=True)
    if missing:
        print("Missing months, re-run to retry:\n  " + "\n  ".join(missing), flush=True)


if __name__ == "__main__":
    main()
