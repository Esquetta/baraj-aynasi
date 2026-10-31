"""Turn a cached chip into water / clear masks on the dam's 10 m grid."""

import json
from pathlib import Path

import numpy as np
import rasterio.features
from affine import Affine
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform as shp_transform

from .chips import CRS, load_chip, upsample2
from .water import boa_offset, clear_mask, ndwi, reflectance, water_area_km2, water_mask

GRIDS = Path("aoi/grids.json")  # committed copy of every dam's grid, for runs without the chip cache


def load_grid(chips_root: Path, dam_key: str) -> list[dict]:
    path = chips_root / dam_key / "grid.json"
    if path.exists():
        grid = json.loads(path.read_text(encoding="utf-8"))
    else:
        grid = json.loads(GRIDS.read_text(encoding="utf-8"))[dam_key]
    return [{"transform": Affine(*g["transform"]), "shape": (g["height"], g["width"])} for g in grid["boxes"]]


def area_and_clear(masks: list, aois: list[np.ndarray]) -> tuple[float, float]:
    """Water area (km2) inside the AOI and the AOI's cloud-free share, over all boxes."""
    water = sum(water_area_km2(w, a) for (_, _, w), a in zip(masks, aois))
    clear_px = sum(np.count_nonzero(c & a) for (_, c, _), a in zip(masks, aois))
    return water, clear_px / sum(np.count_nonzero(a) for a in aois)


def chip_masks(chip: dict, threshold: float = 0.0) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per box: (ndwi, clear, water). Clear excludes clouds, shadow, snow and no-data pixels."""
    off = boa_offset(str(chip["baseline"]))
    out = []
    j = 0
    while f"b03_{j}" in chip:
        green = reflectance(chip[f"b03_{j}"], off)
        nir = reflectance(chip[f"b08_{j}"], off)
        idx = ndwi(green, nir)
        clear = clear_mask(upsample2(chip[f"scl_{j}"]))[: idx.shape[0], : idx.shape[1]] & np.isfinite(idx)
        out.append((idx, clear, water_mask(idx, threshold) & clear))
        j += 1
    return out


def load_masks(path: Path, threshold: float = 0.0):
    return chip_masks(load_chip(path), threshold)


def to_wgs84(geom):
    return shp_transform(Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform, geom)


def to_utm(geom):
    return shp_transform(Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform, geom)


def rasterize_aoi(features: list[dict], grid: list[dict]) -> list[np.ndarray]:
    """AOI polygons (WGS84 GeoJSON features) burned onto each box grid."""
    geoms = [mapping(to_utm(shape(f["geometry"]))) for f in features]
    return [
        rasterio.features.rasterize(geoms, out_shape=g["shape"], transform=g["transform"], dtype="uint8").astype(bool)
        for g in grid
    ]


def load_aoi(path: Path, dam_key: str) -> list[dict]:
    fc = json.loads(path.read_text(encoding="utf-8"))
    return [f for f in fc["features"] if f["properties"]["dam"] == dam_key]
