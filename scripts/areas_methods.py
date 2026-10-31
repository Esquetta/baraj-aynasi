"""Water areas from MNDWI and from the U-Net, on the scenes the occupancy fit uses.

Writes results/unet/areas_mndwi.csv and results/unet/areas_unet.csv with the
same columns as results/areas.csv (NDWI), so scripts/fit.py can run on either.

    uv run python scripts/areas_methods.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch

from baraj_aynasi.chips import extra_path, load_chip, upsample2
from baraj_aynasi.dams import DAMS
from baraj_aynasi.measure import load_aoi, load_grid, rasterize_aoi
from baraj_aynasi.patches import input_stack
from baraj_aynasi.unet import UNet, predict
from baraj_aynasi.water import boa_offset, clear_mask, mndwi, reflectance, water_area_km2

CHIPS = Path("data/chips")
AOI = Path("aoi/reservoirs.geojson")
MODEL = Path("data/unet/model.pt")
OUT = Path("results/unet")
MIN_CLEAR = 0.98


def scene_bands(dam_key: str, item_id: str, aois: list[np.ndarray]):
    """For each AOI part of one scene: (aoi, green, red, nir, swir, clear) as reflectance at 10 m."""
    chip = load_chip(CHIPS / dam_key / f"{item_id}.npz")
    extra = load_chip(extra_path(CHIPS / dam_key / f"{item_id}.npz"))
    off = boa_offset(str(chip["baseline"]))
    for j, aoi in enumerate(aois):
        if not aoi.any():
            continue
        green = reflectance(chip[f"b03_{j}"], off)
        nir = reflectance(chip[f"b08_{j}"], off)
        red = reflectance(extra[f"b04_{j}"], off)
        swir = upsample2(reflectance(extra[f"b11_{j}"], off))[: green.shape[0], : green.shape[1]]
        clear = clear_mask(upsample2(chip[f"scl_{j}"]))[: green.shape[0], : green.shape[1]] & np.isfinite(green) & np.isfinite(nir)
        yield aoi, green, red, nir, swir, clear


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = UNet().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device))
    base = pd.read_csv("results/areas.csv")
    base = base[base.clear_frac >= MIN_CLEAR]
    out = {"mndwi": [], "unet": []}
    for dam in DAMS:
        aois = rasterize_aoi(load_aoi(AOI, dam.key), load_grid(CHIPS, dam.key))
        rows = base[base.dam == dam.key]
        for r in rows.itertuples():
            area = {"mndwi": 0.0, "unet": 0.0}
            for aoi, green, red, nir, swir, clear in scene_bands(dam.key, r.item_id, aois):
                with np.errstate(invalid="ignore"):
                    area["mndwi"] += water_area_km2((mndwi(green, swir) > 0) & clear, aoi)
                prob = predict(model, input_stack(green, red, nir, swir), device)
                area["unet"] += water_area_km2((prob > 0.5) & clear, aoi)
            for method, km2 in area.items():
                out[method].append({**r._asdict(), "water_km2": round(km2, 4)})
        print(f"{dam.key}: {len(rows)} scenes", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for method, rows in out.items():
        pd.DataFrame(rows).drop(columns="Index").to_csv(OUT / f"areas_{method}.csv", index=False)
    print("wrote", ", ".join(f"areas_{m}.csv" for m in out))


if __name__ == "__main__":
    main()
