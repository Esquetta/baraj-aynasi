"""Train the U-Net on reviewed training patches.

Labels: for each patch, the candidate mask chosen in labels/review.csv
(rejected patches are left out). Clouds, shadow and no-data pixels are ignored
in the loss. 15% of training scenes are held back for validation: the epoch
with the lowest validation loss is kept, and training stops after 30 epochs
without improvement (or at 200). Test patches are not touched here.

    uv run python scripts/train_unet.py
    uv run python scripts/unet_seeds.py      # several seeds, see that script
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

from baraj_aynasi.patches import CANDIDATES
from baraj_aynasi.unet import UNet, masked_loss

PATCHES = Path("data/unet/patches")
MODEL = Path("data/unet/model.pt")
EPOCHS = 200
PATIENCE = 30
SEED = 0


def load(split: str) -> pd.DataFrame:
    table = pd.read_csv("labels/patches.csv").merge(pd.read_csv("labels/review.csv"), on="pid")
    return table[(table.split == split) & (table.choice != "reject")].reset_index(drop=True)


def tensors(rows: pd.DataFrame):
    xs, ys, igs = [], [], []
    for r in rows.itertuples():
        z = np.load(PATCHES / f"{r.pid}.npz")
        xs.append(z["x"])
        ys.append(z["candidates"][CANDIDATES.index(r.choice)][None].astype(np.float32))
        igs.append(z["ignore"][None])
    return torch.from_numpy(np.stack(xs)), torch.from_numpy(np.stack(ys)), torch.from_numpy(np.stack(igs))


def augment(x, y, ig):
    """Random 90-degree rotations and flips (water has no preferred direction)."""
    k = int(torch.randint(4, (1,)))
    x, y, ig = (torch.rot90(t, k, dims=(2, 3)) for t in (x, y, ig))
    if torch.rand(1) < 0.5:
        x, y, ig = (torch.flip(t, dims=(3,)) for t in (x, y, ig))
    return x, y, ig


def train(seed: int, model_path: Path) -> list[dict]:
    """Train one model, save the best epoch to model_path and return the loss history."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rows = load("train")
    scenes = rows.item_id.unique()
    val_scenes = set(rng.choice(scenes, size=max(1, int(0.15 * len(scenes))), replace=False))
    val = rows.item_id.isin(val_scenes)
    train_ds = TensorDataset(*tensors(rows[~val]))
    xv, yv, iv = (t.to(device) for t in tensors(rows[val]))
    loader = DataLoader(train_ds, batch_size=16, shuffle=True, generator=torch.Generator().manual_seed(seed))

    model = UNet().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best, best_epoch, history = np.inf, 0, []
    for epoch in range(EPOCHS):
        model.train()
        total = 0.0
        for x, y, ig in loader:
            x, y, ig = augment(*(t.to(device) for t in (x, y, ig)))
            loss = masked_loss(model(x), y, ig)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(x)
        model.eval()
        with torch.no_grad():
            val_loss = masked_loss(model(xv), yv, iv).item()
        history.append({"epoch": epoch, "train_loss": total / len(train_ds), "val_loss": val_loss})
        if val_loss < best:
            best, best_epoch = val_loss, epoch
            model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), model_path)
        if epoch - best_epoch >= PATIENCE:
            break
    print(f"device {device}; {len(train_ds)} train / {int(val.sum())} val patches; best val loss {best:.4f} at epoch {best_epoch}")
    return history


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    history = train(args.seed, MODEL)
    Path("results/unet").mkdir(parents=True, exist_ok=True)
    Path("results/unet/training_history.json").write_text(json.dumps(history), encoding="utf-8")


if __name__ == "__main__":
    main()
