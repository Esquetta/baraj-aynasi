"""Sentinel-2 L2A item search on Microsoft Planetary Computer, cached per tile and month."""

import json
import time
from pathlib import Path

import pystac
import pystac_client
from pystac_client.exceptions import APIError

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-2-l2a"

# One small probe box per tile; the search keeps only items of that tile.
# Each tile carries the dams listed next to it (see dams.py for their boxes).
TILES = {
    "35TPF": (28.90, 41.12, 28.92, 41.14),  # Ömerli, Elmalı, Terkos, Alibey, Büyükçekmece, Sazlıdere
    "35TQF": (29.57, 41.08, 29.59, 41.10),  # Darlık
    "35TNG": (28.03, 41.61, 28.05, 41.63),  # Kazandere, Pabuçdere, Istrancalar
}
DAM_TILE = {
    "omerli": "35TPF",
    "elmali": "35TPF",
    "terkos": "35TPF",
    "alibey": "35TPF",
    "buyukcekmece": "35TPF",
    "sazlidere": "35TPF",
    "darlik": "35TQF",
    "kazandere": "35TNG",
    "pabucdere": "35TNG",
    "istrancalar": "35TNG",
}


def _search_month(client, tile: str, year: int, month: int, retries: int = 8) -> list[dict]:
    start = f"{year:04d}-{month:02d}-01T00:00:00Z"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{ny:04d}-{nm:02d}-01T00:00:00Z"
    for attempt in range(retries):
        try:
            items = client.search(
                collections=[COLLECTION], bbox=TILES[tile], datetime=f"{start}/{end}", limit=100
            ).item_collection()
            return [it.to_dict() for it in items if it.properties.get("s2:mgrs_tile") == tile]
        except (APIError, OSError) as exc:  # the API returns intermittent 504s
            wait = min(60, 5 * 2**attempt)
            print(f"  {tile} {year}-{month:02d}: {type(exc).__name__}, retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"search failed for {tile} {year}-{month:02d}")


def search_cached(cache_dir: Path, tile: str, year: int, month: int, client=None) -> list[dict]:
    """Items for one tile and month, read from or written to the cache."""
    path = cache_dir / tile / f"{year:04d}-{month:02d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    client = client or pystac_client.Client.open(STAC_URL)
    items = _search_month(client, tile, year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items), encoding="utf-8")
    return items


def dedupe(items: list[dict]) -> list[dict]:
    """Keep one item per acquisition: the highest processing baseline.

    Several satellites can image the same tile on the same day, so the key is
    the sensing time and relative orbit, not the date.
    """
    best: dict[tuple, dict] = {}
    for it in items:
        p = it["properties"]
        key = (p["s2:mgrs_tile"], p["datetime"][:19], p.get("sat:relative_orbit"))
        if key not in best or p["s2:processing_baseline"] > best[key]["properties"]["s2:processing_baseline"]:
            best[key] = it
    return sorted(best.values(), key=lambda it: it["properties"]["datetime"])


def load_items(cache_dir: Path, tile: str) -> list[pystac.Item]:
    """All cached items for a tile, de-duplicated and sorted by time."""
    raw = []
    for path in sorted((cache_dir / tile).glob("*.json")):
        raw.extend(json.loads(path.read_text(encoding="utf-8")))
    return [pystac.Item.from_dict(d) for d in dedupe(raw)]
