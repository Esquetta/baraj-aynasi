"""Daily update: measure new Sentinel-2 scenes and turn them into estimates.

Works without the local chip cache, so it can run in GitHub Actions. For each
tile it searches from a few days before the newest measured scene (late
uploads), reads the clipped SCL, B03 and B08 windows straight from Planetary
Computer, measures NDWI water inside the AOIs, appends the rows to
results/areas.csv and rewrites results/estimates_2024_2026.csv with the frozen
curves in results/curves.json. Nothing is refitted.

    uv run python scripts/update.py
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import pystac
import pystac_client
from pystac_client.exceptions import APIError

from baraj_aynasi import ibb
from baraj_aynasi.chips import read_item
from baraj_aynasi.dams import BY_KEY
from baraj_aynasi.measure import area_and_clear, chip_masks, load_aoi, load_grid, rasterize_aoi
from baraj_aynasi.scenes import MIN_CLEAR, estimates
from baraj_aynasi.stac import COLLECTION, DAM_TILE, STAC_URL, TILES, dedupe

AREAS = Path("results/areas.csv")
CURVES = Path("results/curves.json")
ESTIMATES = Path("results/estimates_2024_2026.csv")
AOI = Path("aoi/reservoirs.geojson")
CHIPS = Path("data/chips")
LOOKBACK_DAYS = 5
MIN_CLEAR_BOX = 0.3  # same loose pre-filter as scripts/download.py


def search(client, tile: str, start: str, end: str, retries: int = 6) -> list[pystac.Item]:
    for attempt in range(retries):
        try:
            found = client.search(collections=[COLLECTION], bbox=TILES[tile], datetime=f"{start}/{end}", limit=100)
            raw = [it.to_dict() for it in found.item_collection() if it.properties.get("s2:mgrs_tile") == tile]
            return [pystac.Item.from_dict(d) for d in dedupe(raw)]
        except (APIError, OSError) as exc:  # the API returns intermittent 504s
            wait = min(60, 5 * 2**attempt)
            print(f"  {tile}: {type(exc).__name__}, retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"search failed for {tile}")


def main() -> int:
    areas = pd.read_csv(AREAS, dtype={"baseline": str})
    seen = set(zip(areas.dam, areas.datetime.str[:19]))
    end = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    client = pystac_client.Client.open(STAC_URL)
    new = []
    for tile in TILES:
        dams = [BY_KEY[k] for k, t in DAM_TILE.items() if t == tile]
        aois = {d.key: rasterize_aoi(load_aoi(AOI, d.key), load_grid(CHIPS, d.key)) for d in dams}
        aoi_km2 = {k: sum(int(a.sum()) for a in v) * 100 / 1e6 for k, v in aois.items()}
        last = pd.to_datetime(areas[areas.dam.isin(aois)].datetime).max()
        start = (last - pd.Timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        items = search(client, tile, start, end)
        for item in items:
            todo = [d for d in dams if (d.key, item.properties["datetime"][:19]) not in seen]
            if not todo:
                continue
            _, chips = read_item(item, todo, MIN_CLEAR_BOX)
            for key, chip in chips.items():
                masks = chip_masks(chip)
                if [m[0].shape for m in masks] != [a.shape for a in aois[key]]:
                    print(f"  skipped {item.id} {key}: window does not match the dam grid", flush=True)
                    continue
                water, clear = area_and_clear(masks, aois[key])
                new.append(
                    {
                        "dam": key,
                        "item_id": item.id,
                        "datetime": item.properties["datetime"],
                        "date": item.properties["datetime"][:10],
                        "baseline": f"{float(item.properties['s2:processing_baseline']):05.2f}",
                        "clear_frac": round(clear, 4),
                        "water_km2": round(water, 4),
                        "aoi_km2": round(aoi_km2[key], 4),
                    }
                )
        print(f"{tile}: {len(items)} items since {start[:10]}", flush=True)
    if not new:
        print("no new scenes")
        return 0
    added = pd.DataFrame(new)
    print(f"added {len(added)} dam-scenes, {int((added.clear_frac >= MIN_CLEAR).sum())} clear enough for estimates")
    areas = pd.concat([areas, added], ignore_index=True).sort_values(["dam", "datetime"])
    areas.to_csv(AREAS, index=False)
    areas["date"] = pd.to_datetime(areas.date)
    curves = json.loads(CURVES.read_text(encoding="utf-8"))
    estimates(areas, curves, ibb.END).to_csv(ESTIMATES, index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
