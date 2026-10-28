"""Before/after crops: true colour plus the NDWI water outline on a high- and a low-water date.

    uv run python scripts/crops.py --dam omerli --dam darlik
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio

from baraj_aynasi import ibb
from baraj_aynasi.chips import GDAL_ENV, double, scl_window
from baraj_aynasi.dams import BY_KEY
from baraj_aynasi.measure import load_aoi, load_grid, load_masks, rasterize_aoi
from baraj_aynasi.stac import STAC_URL

CHIPS = Path("data/chips")
AOI = Path("aoi/reservoirs.geojson")
OUT = Path("results/figures")


def pick_dates(dam) -> pd.DataFrame:
    """Clearest full-cover scenes at the highest and lowest İBB occupancy."""
    a = pd.read_csv("results/areas.csv", parse_dates=["date"])
    a = a[(a.dam == dam.key) & (a.clear_frac >= 0.995)]
    gt = ibb.load()
    a = a.merge(gt[gt.ibb_column == dam.ibb_column][["date", "occupancy_pct"]], on="date")
    a = a.sort_values("occupancy_pct")
    return pd.concat([a.tail(1), a.head(1)])


def true_colour(item_id: str, dam) -> np.ndarray:
    client = pystac_client.Client.open(STAC_URL)
    item = next(client.search(collections=["sentinel-2-l2a"], ids=[item_id]).items())
    signed = planetary_computer.sign(item)
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(signed.assets["SCL"].href) as scl:
            win = double(scl_window(dam.boxes[0], scl.transform))
        with rasterio.open(signed.assets["visual"].href) as src:
            return np.moveaxis(src.read(window=win), 0, -1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dam", action="append", required=True)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for key in args.dam:
        dam = BY_KEY[key]
        aoi = rasterize_aoi(load_aoi(AOI, key), load_grid(CHIPS, key))[0]
        rows, cols = np.nonzero(aoi)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        fig, axs = plt.subplots(1, 2, figsize=(12, 6.5))
        for ax, (_, s) in zip(axs, pick_dates(dam).iterrows()):
            rgb = true_colour(s.item_id, dam)[r0:r1, c0:c1]
            water = load_masks(CHIPS / key / f"{s.item_id}.npz")[0][2][r0:r1, c0:c1] & aoi[r0:r1, c0:c1]
            ax.imshow(np.clip(rgb.astype(float) * 1.6 / 255, 0, 1))
            ax.contour(water, levels=[0.5], colors="cyan", linewidths=0.6)
            ax.set_title(f"{s.date:%Y-%m-%d}: İBB {s.occupancy_pct:.0f}%, NDWI water {s.water_km2:.2f} km²", fontsize=10)
            ax.axis("off")
        fig.suptitle(f"{dam.name}: high vs low water (cyan = NDWI > 0 inside AOI)")
        fig.text(0.01, 0.01, "Contains modified Copernicus Sentinel data 2017-2026. Occupancy: İBB Open Data.", fontsize=7)
        fig.tight_layout()
        fig.savefig(OUT / f"crops_{key}.png", dpi=80)
        plt.close(fig)
        print(f"wrote crops_{key}.png")


if __name__ == "__main__":
    main()
