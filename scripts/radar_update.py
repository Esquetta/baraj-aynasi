"""Daily radar update: measure recent Sentinel-1 passes and turn them into estimates.

Works without the local chips, so it can run in GitHub Actions. For each reservoir it
reads the VV windows of every pass from a week before the newest measured one (the
items of one pass can arrive on different days) straight from Planetary Computer,
counts the pixels below the reservoir's fixed threshold, updates
results/radar/areas_vv_fixed.csv and rewrites the estimates with the frozen curves.
Nothing is refitted.

    uv run python scripts/radar_update.py
"""

import json
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
from pathlib import Path

import pandas as pd
import pystac_client
import rasterio

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS, search_box
from baraj_aynasi.measure import load_aoi, load_grid, rasterize_aoi
from baraj_aynasi.radar import (
    GDAL,
    db_histogram,
    encode_db,
    group_passes,
    km2_below,
    pass_values,
    read_band,
    replace_passes,
    search_month,
)
from baraj_aynasi.scenes import MIN_CLEAR, estimates
from baraj_aynasi.stac import STAC_URL
from baraj_aynasi.water import water_area_km2

RADAR = Path("results/radar")
AREAS = RADAR / "areas_vv_fixed.csv"
THRESHOLDS = RADAR / "thresholds.json"
CURVES = RADAR / "vv_fixed" / "curves.json"
ESTIMATES = RADAR / "vv_fixed" / "estimates_2024_2026.csv"
AOI = Path("aoi/reservoirs.geojson")
CHIPS = Path("data/chips")
BAND = "vv"
LOOKBACK_DAYS = 7
WORKERS = 8


def recent_passes(client, dam, last: str) -> list[list[dict]]:
    start = pd.Timestamp(last) - pd.Timedelta(days=LOOKBACK_DAYS)
    months = pd.period_range(start, pd.Timestamp.now(), freq="M")
    items = [it for m in months for it in search_month(client, search_box(dam), m.year, m.month)]
    return group_passes([it for it in items if it["properties"]["datetime"][:10] >= f"{start:%Y-%m-%d}"])


def read_coded(items: list[dict], grids: list[dict]) -> list | None:
    for attempt in range(3):
        try:
            with rasterio.Env(**GDAL):
                return [encode_db(read_band(items, BAND, grid)) for grid in grids]
        except rasterio.errors.RasterioIOError as exc:
            print(f"  {items[0]['id']}: attempt {attempt + 1}: {str(exc)[:80]}", flush=True)
    return None


def measure_dam(client, dam, last: str, threshold: float) -> list[dict]:
    grids = load_grid(CHIPS, dam.key)
    aois = rasterize_aoi(load_aoi(AOI, dam.key), grids)
    aoi_km2 = sum(water_area_km2(a, a) for a in aois)
    passes = recent_passes(client, dam, last)
    with ThreadPoolExecutor(WORKERS) as pool:
        read = list(pool.map(read_coded, passes, repeat(grids)))
    rows = []
    for items, coded in zip(passes, read):
        if coded is None:
            continue
        values, clear = pass_values(coded, aois)
        props = items[0]["properties"]
        rows.append(
            {
                "dam": dam.key,
                "item_id": items[0]["id"],
                "datetime": props["datetime"],
                "date": props["datetime"][:10],
                "orbit": props["sat:relative_orbit"],
                "clear_frac": round(clear, 4),
                "water_km2": round(km2_below(db_histogram(values), threshold), 4),
                "aoi_km2": round(aoi_km2, 4),
            }
        )
    return rows


def main() -> None:
    areas = pd.read_csv(AREAS)
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    client = pystac_client.Client.open(STAC_URL)
    new = []
    for dam in DAMS:
        rows = measure_dam(client, dam, areas[areas.dam == dam.key].date.max(), thresholds[dam.key][BAND])
        print(f"{dam.key}: {len(rows)} recent passes", flush=True)
        new += rows
    if not new:
        print("no passes")
        return
    added = pd.DataFrame(new)
    print(f"read {len(added)} dam-passes, {int((added.clear_frac >= MIN_CLEAR).sum())} covering the reservoir")
    areas = replace_passes(areas, added)
    areas.to_csv(AREAS, index=False)
    areas["date"] = pd.to_datetime(areas.date)
    curves = json.loads(CURVES.read_text(encoding="utf-8"))
    estimates(areas, curves, ibb.END).to_csv(ESTIMATES, index=False)


if __name__ == "__main__":
    main()
