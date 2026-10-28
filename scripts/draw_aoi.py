"""Draw each reservoir's AOI polygon from its high-water extent.

1. Pick the clearest scenes on the days İBB reported the highest occupancy, using
   only the training period (2017 to 2022-06-30) so held-out labels stay unseen.
2. Water frequency per pixel over those scenes (NDWI > 0, cloud-free pixels only).
3. Keep the connected water body that contains the hand-picked seed points in dams.py.
4. Grow it by MARGIN_M and remove other water bodies the margin touches.
5. Vectorise, simplify and write aoi/reservoirs.geojson; save review plots under aoi/review/.

    uv run python scripts/draw_aoi.py --preview   # frequency maps with a lon/lat grid, to pick seeds
    uv run python scripts/draw_aoi.py             # write the polygons
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio.features
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from baraj_aynasi import ibb
from baraj_aynasi.aoi import aoi_mask, reservoir_mask
from baraj_aynasi.chips import CRS
from baraj_aynasi.dams import DAMS
from baraj_aynasi.measure import load_grid, load_masks, to_wgs84
from baraj_aynasi.stac import DAM_TILE

CHIPS = Path("data/chips")
OUT = Path("aoi/reservoirs.geojson")
REVIEW = Path("aoi/review")
TRAIN_END = pd.Timestamp("2022-06-30")  # same split as scripts/fit.py
N_SCENES = 12
MIN_CLEAR = 0.95
MARGIN_M = 200
ATTRIBUTION = "Contains modified Copernicus Sentinel data 2017-2022."
SIMPLIFY_M = 10


def high_water_scenes(dam) -> pd.DataFrame:
    idx = pd.read_csv(CHIPS / f"index_{DAM_TILE[dam.key]}.csv")
    idx = idx[(idx.dam == dam.key) & idx.saved & (idx.clear_box >= MIN_CLEAR)].copy()
    idx["date"] = pd.to_datetime(idx.datetime.str[:10])
    gt = ibb.load()
    gt = gt[(gt.ibb_column == dam.ibb_column) & (gt.date <= TRAIN_END)][["date", "occupancy_pct"]]
    idx = idx.merge(gt, on="date").sort_values("occupancy_pct", ascending=False)
    # At most one scene per month, so a single wet spell does not dominate.
    idx["month"] = idx.date.dt.to_period("M")
    return idx.drop_duplicates("month").head(N_SCENES)


def frequency(dam, scenes: pd.DataFrame) -> list[np.ndarray]:
    wet = clear = None
    for item_id in scenes.item_id:
        masks = load_masks(CHIPS / dam.key / f"{item_id}.npz")
        if wet is None:
            wet = [np.zeros(m[0].shape) for m in masks]
            clear = [np.zeros(m[0].shape) for m in masks]
        for j, (_, c, w) in enumerate(masks):
            wet[j] += w
            clear[j] += c
    with np.errstate(invalid="ignore", divide="ignore"):
        return [np.where(c > 0, w / c, 0.0) for w, c in zip(wet, clear)]


def lonlat_to_pixel(g: dict, lon: float, lat: float) -> tuple[int, int]:
    x, y = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(lon, lat)
    col, row = ~g["transform"] * (x, y)
    return int(row), int(col)


def lonlat_grid(ax, g: dict) -> None:
    """Label a pixel-space image with lon/lat ticks."""
    to_ll = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    h, w = g["shape"]
    t = g["transform"]
    cols = np.linspace(0, w - 1, 6)
    rows = np.linspace(0, h - 1, 6)
    ax.set_xticks(cols, [f"{to_ll.transform(*(t * (c, h / 2)))[0]:.3f}" for c in cols], fontsize=7)
    ax.set_yticks(rows, [f"{to_ll.transform(*(t * (w / 2, r)))[1]:.3f}" for r in rows], fontsize=7)
    ax.grid(color="k", lw=0.3, alpha=0.5)


def print_components(freq: np.ndarray, g: dict, box: int, top: int = 6) -> None:
    """Largest high-water components with one interior lon/lat each, as seed candidates."""
    labels, n = ndimage.label(freq >= 0.5, structure=np.ones((3, 3), bool))
    sizes = np.bincount(labels.ravel())[1:]
    to_ll = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    for i in np.argsort(sizes)[::-1][:top]:
        rr, cc = np.nonzero(labels == i + 1)
        k = len(rr) // 2
        lon, lat = to_ll.transform(*(g["transform"] * (cc[k] + 0.5, rr[k] + 0.5)))
        print(f"  box {box}: {sizes[i] / 1e4:.3f} km2, interior point ({lon:.4f}, {lat:.4f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--dam", action="append")
    args = ap.parse_args()
    REVIEW.mkdir(parents=True, exist_ok=True)
    features = []
    if OUT.exists() and args.dam:
        features = [f for f in json.loads(OUT.read_text(encoding="utf-8"))["features"] if f["properties"]["dam"] not in args.dam]
    for dam in DAMS:
        if args.dam and dam.key not in args.dam:
            continue
        scenes = high_water_scenes(dam)
        grid = load_grid(CHIPS, dam.key)
        freq = frequency(dam, scenes)
        print(f"{dam.key}: {len(scenes)} scenes, occupancy {scenes.occupancy_pct.min():.1f}-{scenes.occupancy_pct.max():.1f}%")
        if args.preview:
            fig, axs = plt.subplots(1, len(freq), figsize=(9 * len(freq), 9), squeeze=False)
            for j, (f, g) in enumerate(zip(freq, grid)):
                axs[0, j].imshow(f, cmap="Blues", vmin=0, vmax=1)
                lonlat_grid(axs[0, j], g)
                print_components(f, g, j)
            fig.suptitle(f"{dam.name}: high-water frequency")
            fig.text(0.01, 0.01, ATTRIBUTION, fontsize=7)
            fig.savefig(REVIEW / f"{dam.key}_freq.png", dpi=60, bbox_inches="tight")
            plt.close(fig)
            continue
        polys = []
        fig, axs = plt.subplots(1, len(freq), figsize=(9 * len(freq), 9), squeeze=False)
        for j, (f, g) in enumerate(zip(freq, grid)):
            seeds = [lonlat_to_pixel(g, *s) for s in dam.seeds[j]]
            try:
                res = reservoir_mask(f, seeds)
            except ValueError as exc:
                raise SystemExit(f"{dam.key} box {j}: {exc}; seeds {dam.seeds[j]}") from exc
            aoi = aoi_mask(res, other_water=f >= 0.5, margin_px=MARGIN_M // 10)
            shapes = [shape(s) for s, v in rasterio.features.shapes(aoi.astype("uint8"), mask=aoi, transform=g["transform"]) if v]
            polys.append(unary_union(shapes).simplify(SIMPLIFY_M))
            axs[0, j].imshow(f, cmap="Blues", vmin=0, vmax=1)
            axs[0, j].contour(aoi, levels=[0.5], colors="red", linewidths=0.8)
            axs[0, j].plot([c for _, c in seeds], [r for r, _ in seeds], "y*", ms=12)
            lonlat_grid(axs[0, j], g)
        fig.suptitle(f"{dam.name}: AOI (red) on high-water frequency")
        fig.text(0.01, 0.01, ATTRIBUTION, fontsize=7)
        fig.savefig(REVIEW / f"{dam.key}_aoi.png", dpi=60, bbox_inches="tight")
        plt.close(fig)
        geom = to_wgs84(unary_union(polys))
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "dam": dam.key,
                    "name": dam.name,
                    "method": f"high-water NDWI>0 frequency>=0.5 over {len(scenes)} Sentinel-2 L2A scenes, "
                    f"seeded component, +{MARGIN_M} m margin, simplified {SIMPLIFY_M} m",
                    "scenes": sorted(scenes.item_id.tolist()),
                },
                "geometry": mapping(geom),
            }
        )
    if not args.preview:
        features.sort(key=lambda f: [d.key for d in DAMS].index(f["properties"]["dam"]))
        OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
