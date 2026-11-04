"""After the decision rule: what radar adds next to the optical series.

Exploratory, and not part of the rule in results/radar/README.md. Writes:

- freshness.csv: for each of İSKİ's figures since İBB's series ended, the latest
  estimate of each series on that day, and how far each is from the figure.
- orbit_bias.csv: held-out error per relative orbit, curves fitted on training years.

    uv run python scripts/radar_compare.py
"""

from pathlib import Path

import pandas as pd

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS
from baraj_aynasi.fit import fit_curve
from baraj_aynasi.scenes import clean_scenes

RADAR = Path("results/radar")
TRAIN_END = pd.Timestamp("2022-06-30")
STALE_DAYS = 14


def daily(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"]).groupby(["dam", "date"], as_index=False).occupancy_est.mean()


def latest_on_each_figure(obs: pd.DataFrame, est: pd.DataFrame, name: str) -> pd.DataFrame:
    """Each İSKİ figure with the series' newest estimate up to that day and its age."""
    est = est.rename(columns={"date": "scene", "occupancy_est": name})[["scene", name]]
    out = pd.merge_asof(obs, est, left_on="date", right_on="scene")
    out[f"age_{name}"] = (out.date - out.scene).dt.days
    out[f"err_{name}"] = (out[name] - out.occupancy_pct).abs()
    return out.drop(columns=["scene", name])


def freshness() -> pd.DataFrame:
    iski = pd.read_csv("results/iski_series.csv", parse_dates=["date"])
    optical, radar = daily(Path("results/estimates_2024_2026.csv")), daily(RADAR / "vv_fixed/estimates_2024_2026.csv")
    rows = []
    for dam in DAMS:
        obs = iski[iski.dam == dam.key].sort_values("date")[["date", "occupancy_pct"]]
        t = latest_on_each_figure(obs, optical[optical.dam == dam.key], "optical")
        t = latest_on_each_figure(t, radar[radar.dam == dam.key], "radar").dropna()
        for group, g in (("all figures", t), (f"optical older than {STALE_DAYS} days", t[t.age_optical > STALE_DAYS])):
            rows.append(
                {
                    "dam": dam.key,
                    "group": group,
                    "n": len(g),
                    "median_age_optical": g.age_optical.median(),
                    "median_age_radar": g.age_radar.median(),
                    "mae_optical": g.err_optical.mean(),
                    "mae_radar": g.err_radar.mean(),
                    "radar_closer_share": (g.err_radar < g.err_optical).mean(),
                }
            )
    return pd.DataFrame(rows).round(2)


def orbit_bias() -> pd.DataFrame:
    areas = pd.read_csv(RADAR / "areas_vv_fixed.csv", parse_dates=["date"])
    gt = ibb.load()
    rows = []
    for dam in DAMS:
        labels = gt[gt.ibb_column == dam.ibb_column][["date", "occupancy_pct"]]
        lab = clean_scenes(areas, dam.key).merge(labels, on="date").dropna(subset=["occupancy_pct"])
        train, test = lab[lab.date <= TRAIN_END], lab[lab.date > TRAIN_END].copy()
        curve, _ = fit_curve(train.water_km2.to_numpy(), train.occupancy_pct.to_numpy(), train.date.dt.year.to_numpy())
        test["miss"] = curve.predict(test.water_km2.to_numpy()) - test.occupancy_pct
        for orbit, g in test.groupby("orbit"):
            rows.append({"dam": dam.key, "orbit": orbit, "n": len(g), "mae": g.miss.abs().mean(), "bias": g.miss.mean()})
    return pd.DataFrame(rows).round(2)


def main() -> None:
    for name, table in (("freshness", freshness()), ("orbit_bias", orbit_bias())):
        table.to_csv(RADAR / f"{name}.csv", index=False)
        print(table.to_string(index=False), "\n")


if __name__ == "__main__":
    main()
