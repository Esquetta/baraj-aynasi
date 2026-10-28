"""Pixel-level test on the reviewed test patches (2022-07-01 to 2024-02-19).

Each label is one of the candidates (NDWI, MNDWI, their union or intersection,
or the near-infrared Otsu split) picked by eye, so a fixed index scores 1.0
wherever it was the pick. The U-Net has to match the right choice per patch to do well.

    uv run python scripts/eval_unet.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch

from baraj_aynasi.patches import CANDIDATES
from baraj_aynasi.unet import UNet, iou_f1, predict

PATCHES = Path("data/unet/patches")
MODEL = Path("data/unet/model.pt")
OUT = Path("results/unet")


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = UNet().to(device)
    model.load_state_dict(torch.load(MODEL, map_location=device))
    table = pd.read_csv("labels/patches.csv").merge(pd.read_csv("labels/review.csv"), on="pid")
    test = table[(table.split == "test") & (table.choice != "reject")]
    rows = []
    for r in test.itertuples():
        z = np.load(PATCHES / f"{r.pid}.npz")
        label = z["candidates"][CANDIDATES.index(r.choice)]
        preds = {
            "ndwi": z["candidates"][CANDIDATES.index("ndwi")],
            "mndwi": z["candidates"][CANDIDATES.index("mndwi")],
            "unet": predict(model, z["x"], device) > 0.5,
        }
        for method, pred in preds.items():
            iou, f1 = iou_f1(pred, label, z["ignore"])
            rows.append({"pid": r.pid, "dam": r.dam, "label": r.choice, "method": method, "iou": iou, "f1": f1})
    res = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "pixel_test.csv", index=False)
    summary = res.groupby("method")[["iou", "f1"]].mean().round(3)
    summary["patches"] = res.groupby("method").size()
    print(summary.to_string())
    print(res.groupby(["label", "method"]).iou.mean().unstack().round(3).to_string())


if __name__ == "__main__":
    main()
