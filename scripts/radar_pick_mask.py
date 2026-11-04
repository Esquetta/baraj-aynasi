"""Choose the radar mask on training years only (rule 2 in results/radar/README.md).

Leave-one-year-out error per reservoir for each candidate, over all clean passes up to
TRAIN_END. The lowest median across the ten reservoirs wins; a reservoir where no
increasing curve can be fitted counts as worse than any number. Held-out years aren't
read here.

    uv run python scripts/radar_pick_mask.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS
from baraj_aynasi.fit import fit_curve, out_of_fold_residuals
from baraj_aynasi.radar import BANDS
from baraj_aynasi.scenes import clean_scenes

RESULTS = Path("results/radar")
TRAIN_END = pd.Timestamp("2022-06-30")
MASKS = [f"{b}_{mode}" for b in BANDS for mode in ("otsu", "fixed")]


def training_loyo(areas: pd.DataFrame, dam, gt: pd.DataFrame) -> tuple[float, int]:
    labels = gt[gt.ibb_column == dam.ibb_column][["date", "occupancy_pct"]]
    lab = clean_scenes(areas, dam.key).merge(labels, on="date").dropna(subset=["occupancy_pct"])
    lab = lab[lab.date <= TRAIN_END]
    a, o, y = lab.water_km2.to_numpy(), lab.occupancy_pct.to_numpy(), lab.date.dt.year.to_numpy()
    try:
        _, degree = fit_curve(a, o, y)
    except ValueError:
        return np.inf, len(lab)
    return float(np.nanmean(np.abs(out_of_fold_residuals(a, o, y, degree)))), len(lab)


def main() -> None:
    gt = ibb.load()
    rows = []
    for mask in MASKS:
        areas = pd.read_csv(RESULTS / f"areas_{mask}.csv", parse_dates=["date"])
        for dam in DAMS:
            mae, n = training_loyo(areas, dam, gt)
            rows.append({"mask": mask, "dam": dam.key, "loyo_mae": mae, "n": n})
    table = pd.DataFrame(rows)
    table.round(2).to_csv(RESULTS / "mask_choice.csv", index=False)
    print(table.pivot(index="dam", columns="mask", values="loyo_mae").loc[[d.key for d in DAMS]].round(1).to_string())
    print(table.pivot(index="dam", columns="mask", values="n").loc[[d.key for d in DAMS]].to_string())
    medians = table.groupby("mask").loyo_mae.median()
    print("median:", medians.round(2).to_dict())
    print("chosen:", medians.idxmin())


if __name__ == "__main__":
    main()
