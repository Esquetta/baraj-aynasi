"""Sample U-Net patches, build candidate masks and contact sheets for review.

Train/validation patches come from scenes up to 2022-06-30 and test patches from
2022-07-01 to 2024-02-19, the same split as the occupancy fit. Per reservoir,
training patches are drawn from late-spring scenes (when NDWI misses algal
water), from the lowest-occupancy quarter, and at random.

    uv run python scripts/unet_patches.py
    uv run python scripts/unet_patches.py --resheet   # recompute candidates and sheets only
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_computer
import rasterio
from rasterio.windows import Window

from baraj_aynasi import ibb
from baraj_aynasi.chips import GDAL_ENV, double, extra_path, load_chip, scl_window, upsample2
from baraj_aynasi.dams import BY_KEY, DAMS
from baraj_aynasi.measure import load_aoi, load_grid, rasterize_aoi
from baraj_aynasi.patches import CANDIDATES, PATCH, candidate_masks, input_stack, sample_patch_origins
from baraj_aynasi.stac import DAM_TILE, load_items
from baraj_aynasi.water import boa_offset, clear_mask, reflectance

CHIPS = Path("data/chips")
OUT = Path("data/unet")  # patch arrays and sheets (not committed)
TABLE = Path("labels/patches.csv")  # which scene, box and window each patch is
TRAIN_END = pd.Timestamp("2022-06-30")
PER_STRATUM = 8  # training scenes per stratum and reservoir
TEST_PER_DAM = 6
SHEET_ROWS = 8
SEED = 7


def bands(chip: dict, extra: dict, j: int):
    off = boa_offset(str(chip["baseline"]))
    green = reflectance(chip[f"b03_{j}"], off)
    nir = reflectance(chip[f"b08_{j}"], off)
    red = reflectance(extra[f"b04_{j}"], off)
    swir = upsample2(reflectance(extra[f"b11_{j}"], off))[: green.shape[0], : green.shape[1]]
    ignore = ~clear_mask(upsample2(chip[f"scl_{j}"]))[: green.shape[0], : green.shape[1]]
    return green, red, nir, swir, ignore


def choose_scenes(rng: np.random.Generator) -> pd.DataFrame:
    a = pd.read_csv("results/areas.csv", parse_dates=["date"])
    a = a[(a.clear_frac >= 0.98) & (a.date <= ibb.END)]
    a = a[[extra_path(CHIPS / r.dam / f"{r.item_id}.npz").exists() for r in a.itertuples()]]
    gt = ibb.load()
    gt["dam"] = gt.ibb_column.str.lower()
    a = a.merge(gt[["dam", "date", "occupancy_pct"]], on=["dam", "date"]).drop_duplicates(["dam", "date"])
    picks = []
    for dam in DAMS:
        d = a[a.dam == dam.key]
        train, test = d[d.date <= TRAIN_END], d[d.date > TRAIN_END]
        low = train.occupancy_pct <= train.occupancy_pct.quantile(0.25)
        spring = train.date.dt.month.isin([5, 6])
        used: set[str] = set()
        for stratum, pool in (("late_spring", train[spring]), ("low_water", train[low & ~spring]), ("random", train)):
            pool = pool[~pool.item_id.isin(used)]
            take = pool.sample(min(PER_STRATUM, len(pool)), random_state=int(rng.integers(1 << 31)))
            used |= set(take.item_id)
            picks.append(take.assign(split="train", stratum=stratum))
        take = test.sample(min(TEST_PER_DAM, len(test)), random_state=int(rng.integers(1 << 31)))
        picks.append(take.assign(split="test", stratum="random"))
    return pd.concat(picks, ignore_index=True)


def true_colour(item, box, r0: int, c0: int) -> np.ndarray:
    signed = planetary_computer.sign(item)
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(signed.assets["SCL"].href) as scl:
            w = double(scl_window(box, scl.transform))
        with rasterio.open(signed.assets["visual"].href) as src:
            img = src.read(window=Window(w.col_off + c0, w.row_off + r0, PATCH, PATCH))
    return np.moveaxis(img, 0, -1)


def resheet() -> None:
    """Recompute candidate masks from the saved inputs and redraw the sheets."""
    table = pd.read_csv(TABLE)
    for pid in table.pid:
        path = OUT / "patches" / f"{pid}.npz"
        z = dict(np.load(path))
        green, nir, swir = z["x"][0], z["x"][2], z["x"][3]
        cands = candidate_masks(green, nir, swir)
        z["candidates"] = np.stack([cands[c] for c in CANDIDATES])
        np.savez_compressed(path, **z)
    write_sheets(table)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resheet", action="store_true")
    if ap.parse_args().resheet:
        return resheet()
    rng = np.random.default_rng(SEED)
    (OUT / "patches").mkdir(parents=True, exist_ok=True)
    (OUT / "sheets").mkdir(parents=True, exist_ok=True)
    scenes = choose_scenes(rng)
    items = {}
    for tile in sorted(set(DAM_TILE.values())):
        items.update({it.id: it for it in load_items(Path("data/stac"), tile)})
    rows = []
    for s in scenes.itertuples():
        dam = BY_KEY[s.dam]
        grid = load_grid(CHIPS, dam.key)
        aois = rasterize_aoi(load_aoi(Path("aoi/reservoirs.geojson"), dam.key), grid)
        chip = load_chip(CHIPS / dam.key / f"{s.item_id}.npz")
        extra = load_chip(extra_path(CHIPS / dam.key / f"{s.item_id}.npz"))
        boxes = [j for j in range(len(dam.boxes)) if aois[j].any()]
        j = int(rng.choice(boxes))
        green, red, nir, swir, ignore = bands(chip, extra, j)
        cands = candidate_masks(green, nir, swir)
        origins = sample_patch_origins(aois[j], cands["mndwi"], 1, rng)
        if not origins:
            continue
        r0, c0 = origins[0]
        sl = (slice(r0, r0 + PATCH), slice(c0, c0 + PATCH))
        pid = f"{len(rows):03d}_{dam.key}_{s.date:%Y%m%d}"
        np.savez_compressed(
            OUT / "patches" / f"{pid}.npz",
            x=input_stack(green[sl], red[sl], nir[sl], swir[sl]),
            candidates=np.stack([cands[c][sl] for c in CANDIDATES]),
            ignore=ignore[sl] | ~np.isfinite(green[sl]),
            tci=true_colour(items[s.item_id], dam.boxes[j], r0, c0),
        )
        rows.append(
            {
                "pid": pid, "dam": dam.key, "item_id": s.item_id, "date": s.date.date(), "box": j,
                "r0": r0, "c0": c0, "split": s.split, "stratum": s.stratum, "occupancy_pct": s.occupancy_pct,
            }
        )
        print(pid, flush=True)
    table = pd.DataFrame(rows)
    TABLE.parent.mkdir(exist_ok=True)
    table.to_csv(TABLE, index=False)
    write_sheets(table)


def write_sheets(table: pd.DataFrame) -> None:
    cols = ["true colour", "false colour (NIR, red, green)"] + [f"{c}" for c in CANDIDATES]
    for k in range(0, len(table), SHEET_ROWS):
        part = table.iloc[k : k + SHEET_ROWS]
        fig, axs = plt.subplots(len(part), len(cols), figsize=(2.2 * len(cols), 2.3 * len(part)), squeeze=False)
        for i, r in enumerate(part.itertuples()):
            z = np.load(OUT / "patches" / f"{r.pid}.npz")
            tci = np.clip(z["tci"].astype(float) * 1.6 / 255, 0, 1)
            fc = np.clip(np.stack([z["x"][2], z["x"][1], z["x"][0]], -1) * 3.5, 0, 1)
            panels = [tci, fc] + [tci] * len(CANDIDATES)
            for c, img in enumerate(panels):
                ax = axs[i, c]
                ax.imshow(img)
                if c >= 2:
                    m = z["candidates"][c - 2]
                    ax.imshow(np.ma.masked_where(~m, m), cmap="cool", alpha=0.45, vmin=0, vmax=1)
                    ax.contour(m, levels=[0.5], colors="cyan", linewidths=0.5)
                if z["ignore"].any():
                    ax.contour(z["ignore"], levels=[0.5], colors="red", linewidths=0.6)
                ax.set_xticks([])
                ax.set_yticks([])
                if i == 0:
                    ax.set_title(cols[c], fontsize=8)
            axs[i, 0].set_ylabel(r.pid, fontsize=7)
        fig.text(0.01, 0.002, "Contains modified Copernicus Sentinel data.", fontsize=6)
        fig.tight_layout()
        fig.savefig(OUT / "sheets" / f"sheet_{k // SHEET_ROWS:02d}.png", dpi=75)
        plt.close(fig)


if __name__ == "__main__":
    main()
