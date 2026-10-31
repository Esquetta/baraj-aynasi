"""Score the frozen 2024-2026 satellite estimates against İSKİ's reported occupancy.

The estimates in results/estimates_2024_2026.csv were committed before any İSKİ
figure after 2024-02-19 was collected, so this is an untouched test. Inputs (not
committed): Wayback Machine copies of İSKİ's daily summary in data/iski/wayback/
and the per-dam windows read from İSKİ's occupancy page in data/iski/live_*.json.

    uv run python scripts/iski_check.py
    uv run python scripts/iski_check.py --results results/unet/unet
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS
from baraj_aynasi.fit import metrics
from baraj_aynasi.iski import load_collected, match_nearest, one_per_scene, series

IN = Path("data/iski")
RESULTS = Path("results")
MAX_DAYS = 1  # occupancy can move several points a day after heavy rain


def check_against_ibb(iski: pd.DataFrame) -> None:
    """İSKİ values on dates İBB also covers should be the same series."""
    gt = ibb.load()
    gt["dam"] = gt.ibb_column.str.lower()
    both = iski.merge(gt[["dam", "date", "occupancy_pct"]], on=["dam", "date"], suffixes=("", "_ibb"))
    diff = (both.occupancy_pct - both.occupancy_pct_ibb).abs()
    print(f"ISKI vs IBB on {len(both)} shared dam-days: max |diff| {diff.max():.2f}, median {diff.median():.3f}")


def main() -> None:
    global RESULTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=RESULTS, help="folder with estimates_2024_2026.csv")
    RESULTS = ap.parse_args().results
    iski = load_collected(IN)
    check_against_ibb(iski)
    after = series(iski, ibb.END)

    # Some days have two scenes of the same tile (relative orbits R007 and R107);
    # average them into one measurement per day.
    est = (
        pd.read_csv(RESULTS / "estimates_2024_2026.csv", parse_dates=["date"])
        .groupby(["dam", "date"], as_index=False)
        .agg(
            water_km2=("water_km2", "mean"),
            occupancy_est=("occupancy_est", "mean"),
            lower_90=("lower_90", "mean"),
            upper_90=("upper_90", "mean"),
            heldout_passed=("heldout_passed", "first"),
        )
    )
    rows = []
    for dam in DAMS:
        e = est[est.dam == dam.key].sort_values("date").reset_index(drop=True)
        obs = after[after.dam == dam.key].reset_index(drop=True)
        idx = match_nearest(e.date, obs.date, MAX_DAYS)
        for (_, o), j in zip(obs.iterrows(), idx):
            if j < 0:
                continue
            s = e.iloc[j]
            rows.append(
                {
                    "dam": dam.key,
                    "iski_date": o.date.date(),
                    "iski_pct": o.occupancy_pct,
                    "iski_source": o.source,
                    "scene_date": s.date.date(),
                    "water_km2": s.water_km2,
                    "estimate_pct": s.occupancy_est,
                    "lower_90": s.lower_90,
                    "upper_90": s.upper_90,
                    "heldout_passed": s.heldout_passed,
                }
            )
    pairs = one_per_scene(pd.DataFrame(rows)).round({"water_km2": 4, "estimate_pct": 1, "lower_90": 1, "upper_90": 1})
    pairs.to_csv(RESULTS / "iski_check.csv", index=False)

    summary = []
    for key, g in pairs.groupby("dam", sort=False):
        m = metrics(g.iski_pct.to_numpy(), g.estimate_pct.to_numpy(), g.lower_90.to_numpy(), g.upper_90.to_numpy())
        summary.append(
            {
                "dam": key,
                "heldout_passed": bool(g.heldout_passed.iloc[0]),
                "n": m["n"],
                "mae": m["mae"],
                "rmse": m["rmse"],
                "bias": m["bias"],  # estimate - İSKİ
                "coverage_90": m["coverage"],
                "iski_range": f"{g.iski_pct.min():.0f}-{g.iski_pct.max():.0f}",
                "first": g.iski_date.min(),
                "last": g.iski_date.max(),
            }
        )
    table = pd.DataFrame(summary)
    table.round(2).to_csv(RESULTS / "iski_metrics.csv", index=False)
    print(table.round(2).to_string(index=False))
    print(f"\nPairs: {len(pairs)} (scene within {MAX_DAYS} day of an ISKI figure)")
    plot(est, after, pairs)


def plot(est: pd.DataFrame, after: pd.DataFrame, pairs: pd.DataFrame) -> None:
    fig, axs = plt.subplots(5, 2, figsize=(14, 16), sharex=True)
    for ax, dam in zip(axs.flat, DAMS):
        e = est[est.dam == dam.key]
        o = after[after.dam == dam.key]
        p = pairs[pairs.dam == dam.key]
        ax.errorbar(
            e.date, e.occupancy_est, yerr=[e.occupancy_est - e.lower_90, e.upper_90 - e.occupancy_est],
            fmt=".", ms=2, color="C3", elinewidth=0.3, alpha=0.4, label="satellite estimate ±90% bar",
        )
        ax.plot(o.date, o.occupancy_pct, "o", ms=3, mfc="none", color="C0", label="İSKİ reported")
        ax.plot(pd.to_datetime(p.iski_date), p.iski_pct, "o", ms=3, color="C0", label="İSKİ, matched to a scene")
        status = "passed held-out" if bool(e.heldout_passed.iloc[0]) else "failed held-out"
        ax.set(title=f"{dam.name} ({status})", ylim=(0, 105))
    axs[0, 0].legend(fontsize=7)
    fig.text(0.01, 0.003, "Contains modified Copernicus Sentinel data 2024-2026. Occupancy: İSKİ (iski.istanbul).", fontsize=7)
    fig.tight_layout()
    fig.savefig(RESULTS / "figures" / "iski_check.png", dpi=80)
    plt.close(fig)


if __name__ == "__main__":
    main()
