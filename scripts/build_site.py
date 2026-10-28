"""Build the static project page in site/ from the committed results.

    uv run python scripts/build_site.py
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import fit as fitscript  # noqa: E402  (reuses the exact scene filter of the occupancy fit)

from baraj_aynasi import ibb
from baraj_aynasi.dams import DAMS
from baraj_aynasi.fit import Curve

SITE = Path("site")
TEMPLATE = Path("scripts/site_template.html")
STATUS = {
    "omerli": "offered", "alibey": "offered", "sazlidere": "offered", "pabucdere": "offered", "istrancalar": "offered",
    "kazandere": "provisional", "darlik": "failed", "buyukcekmece": "failed", "terkos": "out", "elmali": "out",
}
NOTES = {
    "kazandere": "Passed the held-out test, but overestimated two summer 2026 scenes by 17 and 23 points.",
    "darlik": "Missed the stop line at the 2023 record low (11.7 points); a U-Net water mask brings it to 5.5.",
    "buyukcekmece": "A shallow former lagoon: at 4% it still holds about half its full-water surface.",
    "terkos": "Surface area barely moves between 40% and 95%, likely because of reed beds; misses by about 20 points.",
    "elmali": "Under 1 km² of water: too small for 10 m pixels.",
}


def main() -> None:
    curves = json.loads(Path("results/curves.json").read_text(encoding="utf-8"))
    held = pd.read_csv("results/heldout_metrics.csv").set_index("dam")
    iski_m = pd.read_csv("results/iski_metrics.csv").set_index("dam")
    iski_pairs = pd.read_csv("results/iski_check.csv", parse_dates=["iski_date"])
    unet = pd.read_csv("results/unet/comparison.csv").set_index("dam")
    gt = ibb.load()
    dams = []
    for dam in DAMS:
        c = curves[dam.key]
        curve = Curve(np.array(c["coef"]), c["error_bar_90"], *c["fit_range_km2"])
        df = fitscript.labelled(dam)
        est = curve.predict(df.water_km2.to_numpy())
        sat = [[d.strftime("%Y-%m-%d"), round(float(e), 1)] for d, e in zip(df.date, est)]
        g = gt[(gt.ibb_column == dam.ibb_column) & (gt.date >= "2017-01-01")].set_index("date").occupancy_pct
        weekly = g.resample("7D").mean().dropna()
        reported = [[d.strftime("%Y-%m-%d"), round(float(v), 1)] for d, v in weekly.items()]
        p = iski_pairs[iski_pairs.dam == dam.key]
        iski = [[d.strftime("%Y-%m-%d"), round(float(v), 1)] for d, v in zip(p.iski_date, p.iski_pct)]
        last = df.iloc[-1]
        dams.append(
            {
                "key": dam.key,
                "name": dam.name,
                "capacity": dam.capacity_mcm,
                "status": STATUS[dam.key],
                "note": NOTES.get(dam.key, ""),
                "bar": round(curve.halfwidth, 1),
                "heldout_mae": round(float(held.loc[dam.key, "test_mae"]), 1),
                "iski_mae": round(float(iski_m.loc[dam.key, "mae"]), 1),
                "iski_n": int(iski_m.loc[dam.key, "n"]),
                "unet_mae": round(float(unet.loc[dam.key, "test_mae_unet"]), 1),
                "latest": {"date": last.date.strftime("%Y-%m-%d"), "pct": round(float(est[-1]), 1)},
                "sat": sat,
                "reported": reported,
                "iski": iski,
            }
        )
    SITE.mkdir(exist_ok=True)
    (SITE / "img").mkdir(exist_ok=True)
    for key in ("buyukcekmece", "darlik"):
        shutil.copy(f"results/figures/crops_{key}.png", SITE / "img" / f"crops_{key}.png")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", json.dumps({"dams": dams, "ibb_end": str(ibb.END.date())}))
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
        + html
        + "</body></html>"
    )
    (SITE / "index.html").write_text(page, encoding="utf-8")
    # The same page without the document shell, for a private claude.ai preview.
    Path("data/site_preview.html").write_text(html, encoding="utf-8")
    print(f"wrote {SITE / 'index.html'} ({(SITE / 'index.html').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
