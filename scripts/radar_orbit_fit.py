"""Candidate fix for radar's orbit bias: one curve per reservoir and relative orbit.

Each relative orbit sees a reservoir from its own angle, and with one shared curve some
orbits read high and others low. This fits scripts/fit.py's curves separately per orbit
on the VV fixed-threshold areas. An orbit with fewer than MIN_TRAIN training passes keeps
the shared curve. Writes results/radar/vv_fixed_orbit/:

- curves.json: per reservoir and orbit, fitted on all passes up to 2024-02-19 and
  then frozen, like results/radar/vv_fixed/curves.json.
- heldout_metrics.csv: training leave-one-year-out error for the shared curve, a shared
  curve with a per-orbit offset, and per-orbit curves (the choice between the last two
  was made on this), and held-out error for the shared and per-orbit curves.

The candidate is judged on new İSKİ figures by scripts/radar_orbit_check.py, under the
rule in results/radar/README.md.

    uv run python scripts/radar_orbit_fit.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS
from baraj_aynasi.fit import fit_curve, metrics, out_of_fold_residuals
from baraj_aynasi.scenes import clean_scenes

AREAS = Path("results/radar/areas_vv_fixed.csv")
OUT = Path("results/radar/vv_fixed_orbit")
TRAIN_END = pd.Timestamp("2022-06-30")
MIN_TRAIN = 100


def arrays(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return df.water_km2.to_numpy(), df.occupancy_pct.to_numpy(), df.date.dt.year.to_numpy()


def loyo_misses(df: pd.DataFrame) -> pd.Series:
    """Predicted minus observed, each training year held out in turn."""
    _, degree = fit_curve(*arrays(df))
    return pd.Series(-out_of_fold_residuals(*arrays(df), degree), index=df.index)


def main() -> None:
    areas = pd.read_csv(AREAS, parse_dates=["date"])
    gt = ibb.load()
    curves, rows = {}, []
    for dam in DAMS:
        labels = gt[gt.ibb_column == dam.ibb_column][["date", "occupancy_pct"]]
        lab = clean_scenes(areas, dam.key).merge(labels, on="date").dropna(subset=["occupancy_pct"])
        train, test = lab[lab.date <= TRAIN_END], lab[lab.date > TRAIN_END]
        shared_loyo = loyo_misses(train)
        offset_loyo = shared_loyo - shared_loyo.groupby(train.orbit).transform("median")
        shared, _ = fit_curve(*arrays(train))
        pred = pd.Series(shared.predict(test.water_km2.to_numpy()), index=test.index)
        lo, hi = shared.interval(test.water_km2.to_numpy())
        lo, hi = pd.Series(lo, index=test.index), pd.Series(hi, index=test.index)
        orbit_loyo, dam_curves = [], {}
        for orbit, g in train.groupby("orbit"):
            if len(g) < MIN_TRAIN:
                continue
            orbit_loyo.append(loyo_misses(g))
            in_test = test.orbit == orbit
            curve, _ = fit_curve(*arrays(g))
            pred[in_test] = curve.predict(test.water_km2[in_test].to_numpy())
            lo[in_test], hi[in_test] = curve.interval(test.water_km2[in_test].to_numpy())
            final, degree = fit_curve(*arrays(lab[lab.orbit == orbit]))
            dam_curves[str(orbit)] = {
                "degree": degree,
                "coef": final.coef.tolist(),
                "fit_range_km2": [final.lo, final.hi],
                "error_bar_90": final.halfwidth,
                "n_train": len(g),
            }
        curves[dam.key] = dam_curves
        m = metrics(test.occupancy_pct.to_numpy(), pred.to_numpy(), lo.to_numpy(), hi.to_numpy())
        rows.append(
            {
                "dam": dam.key,
                "loyo_train_shared": shared_loyo.abs().mean(),
                "loyo_train_offset": offset_loyo.abs().mean(),
                "loyo_train_orbit": pd.concat(orbit_loyo).abs().mean(),
                "n_test": m["n"],
                "test_mae_shared": np.mean(np.abs(shared.predict(test.water_km2.to_numpy()) - test.occupancy_pct.to_numpy())),
                "test_mae_orbit": m["mae"],
                "test_bias_orbit": m["bias"],
                "test_coverage_90_orbit": m["coverage"],
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "curves.json").write_text(json.dumps(curves, indent=1), encoding="utf-8")
    table = pd.DataFrame(rows).round(2)
    table.to_csv(OUT / "heldout_metrics.csv", index=False)
    print(table.to_string(index=False))
    print("\nmedian:", table.drop(columns=["dam", "n_test"]).median().round(2).to_dict())


if __name__ == "__main__":
    main()
