"""Build the blind spot-check page for the U-Net labels.

Sample: every patch whose pick was not NDWI or where the two AI passes
disagreed, plus random NDWI picks, shuffled. The page shows the five candidate
masks without the AI's pick; the pick is revealed only after the reviewer
answers. Answers are stored in the artifact's `spotcheck` collection.

    uv run python scripts/spotcheck_page.py   # writes data/unet/spotcheck.html
"""

import base64
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from baraj_aynasi.patches import CANDIDATES

PATCHES = Path("data/unet/patches")
OUT = Path("data/unet/spotcheck.html")
TEMPLATE = Path("scripts/spotcheck_template.html")
RANDOM_NDWI = 15
SEED = 11


def jpeg(rgb: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def bits(mask: np.ndarray) -> str:
    return base64.b64encode(np.packbits(mask.astype(bool).ravel()).tobytes()).decode()


def main() -> None:
    review = pd.read_csv("labels/review.csv")
    table = pd.read_csv("labels/patches.csv").merge(review, on="pid")
    risky = table[(table.choice != "ndwi") | (table.pass_a != table.pass_b)]
    calm = table.drop(risky.index).sample(RANDOM_NDWI, random_state=SEED)
    sample = pd.concat([risky, calm]).sample(frac=1, random_state=SEED)
    items = []
    for r in sample.itertuples():
        z = np.load(PATCHES / f"{r.pid}.npz")
        tci = np.clip(z["tci"].astype(float) * 1.6, 0, 255).astype(np.uint8)
        fc = (np.clip(np.stack([z["x"][2], z["x"][1], z["x"][0]], -1) * 3.5, 0, 1) * 255).astype(np.uint8)
        items.append(
            {
                "pid": r.pid,
                "dam": r.dam,
                "date": r.date,
                "split": r.split,
                "tci": jpeg(tci),
                "fc": jpeg(fc),
                "masks": {c: bits(z["candidates"][i]) for i, c in enumerate(CANDIDATES)},
                "ignore": bits(z["ignore"]),
                "ai": r.choice,
            }
        )
    html = TEMPLATE.read_text(encoding="utf-8").replace("__PATCHES__", json.dumps(items))
    OUT.write_text(html, encoding="utf-8")
    print(f"{len(items)} patches ({len(risky)} risky, {RANDOM_NDWI} random NDWI) -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
