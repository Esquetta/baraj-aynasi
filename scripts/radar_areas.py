"""Water area per reservoir and radar pass, for each candidate mask.

Candidates: each band in radar.BANDS, split per scene (Otsu) or at one fixed threshold per dam,
the median of that dam's per-scene splits up to TRAIN_END, so the held-out years
don't set it. Writes <out>/areas_<mask>.csv with the columns scripts/fit.py reads.
clear_frac here is the share of the AOI the radar pass covers.

    uv run python scripts/radar_areas.py
    uv run python scripts/radar_areas.py --out data/radar/pilot
"""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from baraj_aynasi.dams import DAMS
from baraj_aynasi.measure import load_aoi, load_grid, rasterize_aoi
from baraj_aynasi.patches import otsu_threshold
from baraj_aynasi.radar import BANDS, db_histogram, km2_below, pass_values
from baraj_aynasi.scenes import MIN_CLEAR
from baraj_aynasi.water import water_area_km2

CHIPS = Path("data/radar/chips")
OPTICAL_CHIPS = Path("data/chips")
AOI = Path("aoi/reservoirs.geojson")
TRAIN_END = "2022-06-30"


def measure(dam) -> tuple[list[dict], float]:
    """One row per scene (pass details, AOI coverage, each band's Otsu split and histogram), and the AOI's km²."""
    aois = rasterize_aoi(load_aoi(AOI, dam.key), load_grid(OPTICAL_CHIPS, dam.key))
    scenes = []
    for path in sorted((CHIPS / dam.key).glob("*.npz")):
        z = np.load(path)
        stamp = str(z["datetime"])
        scene = {"item_id": path.stem, "datetime": stamp, "date": stamp[:10], "orbit": int(z["orbit"])}
        for b in BANDS:
            values, scene["clear_frac"] = pass_values([z[f"{b}_{j}"] for j in range(len(aois))], aois)
            scene[f"t_{b}"] = otsu_threshold(values) if values.size else np.nan
            scene[f"hist_{b}"] = db_histogram(values)
        scenes.append(scene)
    return scenes, sum(water_area_km2(a, a) for a in aois)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("results/radar"))
    args = ap.parse_args()
    rows = {f"{b}_{mode}": [] for b in BANDS for mode in ("otsu", "fixed")}
    thresholds = {}
    with ProcessPoolExecutor() as pool:
        for dam, (scenes, aoi_km2) in zip(DAMS, pool.map(measure, DAMS)):
            train = [s for s in scenes if s["date"] <= TRAIN_END and s["clear_frac"] >= MIN_CLEAR]
            fixed = {b: float(np.median([s[f"t_{b}"] for s in train])) for b in BANDS}
            thresholds[dam.key] = fixed  # unrounded: scripts/radar_update.py must split at the same level
            for s in scenes:
                base = {"dam": dam.key, **{k: s[k] for k in ("item_id", "datetime", "date", "orbit")}, "clear_frac": round(s["clear_frac"], 4)}
                for b in BANDS:
                    for mode, t in (("otsu", s[f"t_{b}"]), ("fixed", fixed[b])):
                        km2 = km2_below(s[f"hist_{b}"], t) if np.isfinite(t) else 0.0
                        rows[f"{b}_{mode}"].append({**base, "water_km2": round(km2, 4), "aoi_km2": round(aoi_km2, 4)})
            print(f"{dam.key}: {len(scenes)} scenes, fixed split {fixed}", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, r in rows.items():
        pd.DataFrame(r).to_csv(args.out / f"areas_{name}.csv", index=False)
    (args.out / "thresholds.json").write_text(json.dumps(thresholds, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
