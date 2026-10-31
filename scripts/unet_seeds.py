"""Train the U-Net with several seeds and report the spread of its occupancy error.

One run is not enough to rank the U-Net against NDWI closely: GPU training is
not deterministic and the seed changes the validation scenes, batch order and
starting weights. Each seed is trained on the same labels, measured on the same
scenes as results/unet/areas_unet.csv, fitted and scored like the single run
(scripts/fit.py, scripts/iski_check.py). Per-seed outputs stay in
data/unet/seeds/; the summary goes to results/unet/seeds.csv.

    uv run python scripts/unet_seeds.py
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import torch

from baraj_aynasi.dams import DAMS
from baraj_aynasi.measure import load_aoi, load_grid, rasterize_aoi
from baraj_aynasi.patches import input_stack
from baraj_aynasi.unet import UNet, predict
from baraj_aynasi.water import water_area_km2

sys.path.insert(0, str(Path(__file__).parent))
from areas_methods import AOI, CHIPS, scene_bands  # noqa: E402
from train_unet import train  # noqa: E402

SEEDS = range(5)
ROOT = Path("data/unet/seeds")
SCENES = Path("results/unet/areas_unet.csv")
OUT = Path("results/unet/seeds.csv")


def measure(folders: list[Path]) -> None:
    """Water area per scene for every seed's model, in one pass over the chips."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    models = []
    for f in folders:
        m = UNet().to(device)
        m.load_state_dict(torch.load(f / "model.pt", map_location=device))
        models.append(m)
    base = pd.read_csv(SCENES)
    out = [[] for _ in models]
    for dam in DAMS:
        aois = rasterize_aoi(load_aoi(AOI, dam.key), load_grid(CHIPS, dam.key))
        rows = base[base.dam == dam.key]
        for r in rows.itertuples(index=False):
            area = [0.0] * len(models)
            for aoi, green, red, nir, swir, clear in scene_bands(dam.key, r.item_id, aois):
                x = input_stack(green, red, nir, swir)
                for k, m in enumerate(models):
                    area[k] += water_area_km2((predict(m, x, device) > 0.5) & clear, aoi)
            for k, km2 in enumerate(area):
                out[k].append({**r._asdict(), "water_km2": round(km2, 4)})
        print(f"{dam.key}: {len(rows)} scenes", flush=True)
    for f, rows in zip(folders, out):
        pd.DataFrame(rows).to_csv(f / "areas.csv", index=False)


def main() -> None:
    folders = [ROOT / f"seed_{s}" for s in SEEDS]
    for seed, f in zip(SEEDS, folders):
        if not (f / "model.pt").exists():
            print(f"seed {seed}: ", end="", flush=True)
            train(seed, f / "model.pt")
    if not all((f / "areas.csv").exists() for f in folders):
        measure(folders)
    rows = []
    for seed, f in zip(SEEDS, folders):
        if not (f / "iski_metrics.csv").exists():
            subprocess.run([sys.executable, "scripts/fit.py", "--areas", str(f / "areas.csv"), "--out", str(f)], check=True)
            subprocess.run([sys.executable, "scripts/iski_check.py", "--results", str(f)], check=True)
        held = pd.read_csv(f / "heldout_metrics.csv")[["dam", "test_mae", "loyo_mae_2017_2024", "error_bar_90", "test_coverage_90"]]
        iski = pd.read_csv(f / "iski_metrics.csv")[["dam", "mae"]].rename(columns={"mae": "iski_mae"})
        rows.append(held.merge(iski, on="dam").assign(seed=seed))
    table = pd.concat(rows)[["seed", "dam", "test_mae", "loyo_mae_2017_2024", "error_bar_90", "test_coverage_90", "iski_mae"]]
    table.round(2).to_csv(OUT, index=False)
    summary = table.groupby("dam", sort=False).test_mae.agg(["mean", "std", "min", "max"]).round(2)
    print("\nHeld-out MAE over seeds:")
    print(summary.to_string())


if __name__ == "__main__":
    main()
