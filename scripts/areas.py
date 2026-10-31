"""Measure NDWI water area inside each reservoir AOI for every cached chip.

Writes results/areas.csv (one row per scene and dam). Scenes are not filtered
here; clear_frac lets the fitting step choose its own cloud tolerance.

    uv run python scripts/areas.py
"""

import concurrent.futures as cf
from pathlib import Path

import numpy as np
import pandas as pd

from baraj_aynasi.dams import DAMS
from baraj_aynasi.measure import area_and_clear, load_aoi, load_grid, load_masks, rasterize_aoi
from baraj_aynasi.stac import DAM_TILE

CHIPS = Path("data/chips")
AOI = Path("aoi/reservoirs.geojson")
OUT = Path("results/areas.csv")
THRESHOLD = 0.0


def measure(path: Path, aois: list[np.ndarray]) -> tuple[float, float]:
    return area_and_clear(load_masks(path, THRESHOLD), aois)


def main() -> None:
    rows = []
    with cf.ProcessPoolExecutor() as pool:
        for dam in DAMS:
            features = load_aoi(AOI, dam.key)
            if not features:
                print(f"{dam.key}: no AOI yet, skipped", flush=True)
                continue
            aois = rasterize_aoi(features, load_grid(CHIPS, dam.key))
            aoi_km2 = sum(np.count_nonzero(a) for a in aois) * 100 / 1e6
            idx = pd.read_csv(CHIPS / f"index_{DAM_TILE[dam.key]}.csv")
            idx = idx[(idx.dam == dam.key) & idx.saved].drop_duplicates("item_id")
            paths = [CHIPS / dam.key / f"{i}.npz" for i in idx.item_id]
            results = list(pool.map(measure, paths, [aois] * len(paths), chunksize=8))
            for (_, r), (water, clear) in zip(idx.iterrows(), results):
                rows.append(
                    {
                        "dam": dam.key,
                        "item_id": r.item_id,
                        "datetime": r.datetime,
                        "date": r.datetime[:10],
                        "baseline": f"{float(r.baseline):05.2f}",
                        "clear_frac": round(clear, 4),
                        "water_km2": round(water, 4),
                        "aoi_km2": round(aoi_km2, 4),
                    }
                )
            print(f"{dam.key}: {len(results)} scenes", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values(["dam", "datetime"]).to_csv(OUT, index=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
