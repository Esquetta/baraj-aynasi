"""Sentinel-1 RTC on Planetary Computer: search, clipped reads and water masks.

Radar sees through cloud, so it can fill the gaps in the optical series. One pass
of the satellite can span two overlapping catalogue items, so a scene here is all
the items of one pass, read together.
"""

import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer
import pystac
import rasterio
from pystac_client.exceptions import APIError
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from scipy.ndimage import median_filter

from .chips import CRS, GDAL_ENV

COLLECTION = "sentinel-1-rtc"
BANDS = ("vv",)  # VH was clearly worse in the pilot, see results/radar/README.md
GDAL = {**GDAL_ENV, "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff"}  # RTC files end in .tiff
DB_MIN, DB_STEP, DB_NODATA = -40.0, 0.2, 255
HIST_EDGES = DB_MIN - DB_STEP / 2 + DB_STEP * np.arange(DB_NODATA + 1)


def search_month(client, box: tuple, year: int, month: int, retries: int = 8) -> list[dict]:
    start = f"{year:04d}-{month:02d}-01T00:00:00Z"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    for attempt in range(retries):
        try:
            found = client.search(collections=[COLLECTION], bbox=box, datetime=f"{start}/{ny:04d}-{nm:02d}-01T00:00:00Z", limit=100)
            return [it.to_dict() for it in found.item_collection()]
        except (APIError, OSError) as exc:  # the API returns intermittent 504s
            wait = min(60, 5 * 2**attempt)
            print(f"  {year}-{month:02d}: {type(exc).__name__}, retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"search failed for {box} {year}-{month:02d}")


def search_cached(cache: Path, client, box: tuple, year: int, month: int) -> list[dict]:
    path = cache / f"{year:04d}-{month:02d}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    items = search_month(client, box, year, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items), encoding="utf-8")
    return items


def group_passes(items: list[dict]) -> list[list[dict]]:
    """Items grouped by satellite pass (platform, relative orbit, UTC date), oldest first."""
    groups = defaultdict(list)
    for it in items:
        p = it["properties"]
        groups[(p["datetime"][:10], p["platform"], p["sat:relative_orbit"])].append(it)
    return [sorted(groups[k], key=lambda it: it["id"]) for k in sorted(groups)]


def read_band(items: list[dict], band: str, grid: dict) -> np.ndarray:
    """One polarisation in dB on a dam box's 10 m grid, NaN where no item has data."""
    out = np.full(grid["shape"], np.nan, dtype="float32")
    height, width = grid["shape"]
    for raw in items:
        href = planetary_computer.sign(pystac.Item.from_dict(raw)).assets[band].href
        with rasterio.open(href) as src, WarpedVRT(
            src, crs=CRS, transform=grid["transform"], width=width, height=height, resampling=Resampling.nearest
        ) as vrt:
            a = vrt.read(1)
        fresh = np.isnan(out) & (a > 0)  # no-data is negative
        out[fresh] = 10 * np.log10(a[fresh])
    return out


def encode_db(db: np.ndarray) -> np.ndarray:
    """dB to uint8 in 0.2 dB steps (-40 to +10 dB), for compact local chips."""
    scaled = np.nan_to_num((db - DB_MIN) / DB_STEP, nan=DB_NODATA)
    return np.where(np.isnan(db), DB_NODATA, np.clip(np.round(scaled), 0, DB_NODATA - 1)).astype("uint8")


def decode_db(coded: np.ndarray) -> np.ndarray:
    db = coded.astype("float32") * DB_STEP + DB_MIN
    db[coded == DB_NODATA] = np.nan
    return db


def despeckle(db: np.ndarray) -> np.ndarray:
    """3 x 3 median. No-data counts as bright land, so scene edges don't turn into water."""
    return median_filter(np.where(np.isnan(db), 0.0, db), size=3)


def aoi_values(smooth: list[np.ndarray], valid: list[np.ndarray], aois: list[np.ndarray]) -> np.ndarray:
    """A dam's AOI pixels with data, over all its boxes."""
    return np.concatenate([s[v & a] for s, v, a in zip(smooth, valid, aois)])


def pass_values(coded: list[np.ndarray], aois: list[np.ndarray]) -> tuple[np.ndarray, float]:
    """A pass's despeckled AOI pixels, from encoded boxes, and the share of the AOI it covers."""
    decoded = [decode_db(c) for c in coded]
    values = aoi_values([despeckle(d) for d in decoded], [np.isfinite(d) for d in decoded], aois)
    return values, values.size / sum(np.count_nonzero(a) for a in aois)


def replace_passes(areas: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Add `new` rows at the end. A pass measured again replaces its old row, so items that arrive late count.
    Other rows keep their place: the robust fit samples by row position, so reordering would shift its results."""
    fresh = set(zip(new.dam, new.date, new.orbit))
    old = areas[[k not in fresh for k in zip(areas.dam, areas.date, areas.orbit)]]
    return pd.concat([old, new], ignore_index=True)


def db_histogram(values: np.ndarray) -> np.ndarray:
    """Pixel counts per 0.2 dB level. A 3 x 3 median of decoded chips stays on those levels."""
    return np.histogram(values, bins=HIST_EDGES)[0]


def km2_below(hist: np.ndarray, threshold: float) -> float:
    """Area of the pixels darker than the threshold, at 10 m per pixel."""
    return float(hist[HIST_EDGES[1:] <= threshold + DB_STEP / 2].sum()) * 1e-4
