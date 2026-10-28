"""Fit per-dam area-to-occupancy curves and report held-out error.

Train: scenes up to TRAIN_END. Test: TRAIN_END to 2024-02-19 (end of İBB data).
Within training, years are held out in turn to choose the polynomial degree and
to size the 90% error bar. A final curve refit on all labelled scenes gives the
2024-2026 satellite-only estimates.

    uv run python scripts/fit.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS, LARGEST_FOUR
from baraj_aynasi.fit import fit_curve, metrics

AREAS = Path("results/areas.csv")
RESULTS = Path("results")
FIGS = RESULTS / "figures"
MIN_CLEAR = 0.98
TRAIN_END = pd.Timestamp("2022-06-30")
KILL_MAE = 10.0


def labelled(dam) -> pd.DataFrame:
    a = pd.read_csv(AREAS, parse_dates=["date"])
    a = a[(a.dam == dam.key) & (a.clear_frac >= MIN_CLEAR)]
    gt = ibb.load()
    gt = gt[gt.ibb_column == dam.ibb_column][["date", "occupancy_pct"]]
    return a.merge(gt, on="date", how="left")


def plot(dam, df, curve, test_curve, path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    train = df[df.date <= TRAIN_END]
    test = df[(df.date > TRAIN_END) & df.occupancy_pct.notna()]
    ax1.scatter(train.water_km2, train.occupancy_pct, s=8, label="train (≤2022-06-30)")
    ax1.scatter(test.water_km2, test.occupancy_pct, s=8, label="held-out (2022-07 to 2024-02)")
    x = np.linspace(df.water_km2.min(), df.water_km2.max(), 200)
    lo, hi = test_curve.interval(x)
    ax1.plot(x, test_curve.predict(x), "k-", lw=1, label="curve fitted on train")
    ax1.fill_between(x, lo, hi, color="k", alpha=0.1, label="90% error bar")
    ax1.set(xlabel="NDWI water area (km²)", ylabel="İBB occupancy (%)", title=dam.name)
    ax1.legend(fontsize=8)
    est = curve.predict(df.water_km2.to_numpy())
    ax2.plot(df.date, df.occupancy_pct, ".", ms=3, color="C0", label="İBB reported")
    ax2.errorbar(df.date, est, yerr=curve.halfwidth, fmt=".", ms=3, color="C3", elinewidth=0.4, alpha=0.6, label="satellite estimate ±90% bar")
    ax2.axvline(ibb.END, color="k", lw=0.8, ls="--")
    ax2.set(ylabel="occupancy (%)", ylim=(0, 105), title="Sentinel-2 L2A estimates vs İBB")
    ax2.legend(fontsize=8)
    fig.text(0.01, 0.01, "Contains modified Copernicus Sentinel data 2017-2026. Occupancy: İBB Open Data.", fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)


def main() -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    rows, curves, estimates = [], {}, []
    for dam in DAMS:
        df = labelled(dam)
        if df.empty:
            print(f"{dam.key}: no areas yet, skipped")
            continue
        lab = df[df.occupancy_pct.notna()]
        train = lab[lab.date <= TRAIN_END]
        test = lab[lab.date > TRAIN_END]
        test_curve, deg = fit_curve(train.water_km2.to_numpy(), train.occupancy_pct.to_numpy(), train.date.dt.year.to_numpy())
        lo, hi = test_curve.interval(test.water_km2.to_numpy())
        m = metrics(test.occupancy_pct.to_numpy(), test_curve.predict(test.water_km2.to_numpy()), lo, hi)
        final, final_deg = fit_curve(lab.water_km2.to_numpy(), lab.occupancy_pct.to_numpy(), lab.date.dt.year.to_numpy())
        rows.append(
            {
                "dam": dam.key,
                "name": dam.name,
                "n_train": len(train),
                "n_test": m["n"],
                "degree": deg,
                "test_mae": m["mae"],
                "test_rmse": m["rmse"],
                "test_bias": m["bias"],
                "error_bar_90": test_curve.halfwidth,
                "test_coverage_90": m["coverage"],
                "occ_range_test": f"{test.occupancy_pct.min():.0f}-{test.occupancy_pct.max():.0f}",
                "area_range_km2": f"{lab.water_km2.min():.2f}-{lab.water_km2.max():.2f}",
            }
        )
        curves[dam.key] = {"degree": final_deg, "coef": final.coef.tolist(), "error_bar_90": final.halfwidth}
        new = df[df.date > ibb.END]
        lo, hi = final.interval(new.water_km2.to_numpy())
        estimates.append(
            pd.DataFrame(
                {
                    "dam": dam.key,
                    "date": new.date.dt.date,
                    "item_id": new.item_id,
                    "water_km2": new.water_km2,
                    "occupancy_est": final.predict(new.water_km2.to_numpy()).round(1),
                    "lower_90": lo.round(1),
                    "upper_90": hi.round(1),
                }
            )
        )
        plot(dam, df, final, test_curve, FIGS / f"fit_{dam.key}.png")
    table = pd.DataFrame(rows)
    table.round(2).to_csv(RESULTS / "heldout_metrics.csv", index=False)
    (RESULTS / "curves.json").write_text(json.dumps(curves, indent=1), encoding="utf-8")
    pd.concat(estimates).to_csv(RESULTS / "estimates_2024_2026.csv", index=False)
    print(table.round(2).to_string(index=False))
    big = table[table.dam.isin(LARGEST_FOUR)]
    over = big[big.test_mae > KILL_MAE]
    print(f"\nKill rule (held-out MAE > {KILL_MAE} points on the four largest): " + ("TRIGGERED: " + ", ".join(over.name) if len(over) else "not triggered"))


if __name__ == "__main__":
    main()
