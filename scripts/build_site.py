"""Build the static project page in site/ (English) and site/tr/ (Turkish)
from the committed results. Page copy lives in scripts/site_text.py.

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
from site_text import EN, TR  # noqa: E402

SITE = Path("site")
TEMPLATE = Path("scripts/site_template.html")
STATUS = {
    "omerli": "offered", "alibey": "offered", "sazlidere": "offered", "pabucdere": "offered", "istrancalar": "offered",
    "kazandere": "provisional", "darlik": "failed", "buyukcekmece": "failed", "terkos": "out", "elmali": "out",
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
    for old in (SITE / "img").glob("crops_*.png"):
        old.unlink()
    for key in ("buyukcekmece", "darlik"):
        for which in ("high", "low"):
            shutil.copy(f"results/figures/crop_{key}_{which}.jpg", SITE / "img" / f"crop_{key}_{which}.jpg")
    crops = json.loads(Path("results/figures/crops_meta.json").read_text(encoding="utf-8"))
    table = pd.read_csv("labels/patches.csv").merge(pd.read_csv("labels/review.csv"), on="pid")
    numbers = {
        "n_train": int(((table.split == "train") & (table.choice != "reject")).sum()),
        "darlik_ndwi": float(unet.loc["darlik", "test_mae_ndwi"]),
        "darlik_unet": float(unet.loc["darlik", "test_mae_unet"]),
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    for text, folder, img in ((EN, SITE, "img/"), (TR, SITE / "tr", "../img/")):
        folder.mkdir(exist_ok=True)
        html = render(template, text, img, numbers, dams, crops)
        head, body = html.split("</style>", 1)
        page = (
            f'<!doctype html>\n<html lang="{text["lang"]}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            + head
            + "</style>\n</head>\n<body>"
            + body
            + "</body>\n</html>\n"
        )
        (folder / "index.html").write_text(page, encoding="utf-8")
        print(f"wrote {folder / 'index.html'} ({(folder / 'index.html').stat().st_size // 1024} KB)")


def fmt(value: float, text: dict) -> str:
    """One decimal, with the language's decimal mark."""
    s = f"{value:.1f}"
    return s.replace(".", ",") if text["lang"] == "tr" else s


MONTHS = {
    "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
    "tr": "Oca Şub Mar Nis May Haz Tem Ağu Eyl Eki Kas Ara".split(),
}
NAV_IDS = ["estimates", "reservoirs", "method", "limits", "data"]


def panel_label(meta: dict, text: dict) -> str:
    y, m, d = (int(x) for x in meta["date"].split("-"))
    date = f"{d} {MONTHS[text['lang']][m - 1]} {y}"
    pct = round(meta["occupancy_pct"])
    pct = f"%{pct}" if text["lang"] == "tr" else f"{pct}%"
    return text["panel"].format(date=date, pct=pct, km2=fmt(meta["water_km2"], text))


def render(template: str, text: dict, img: str, numbers: dict, dams: list[dict], crops: dict) -> str:
    nums = {k: (fmt(v, text) if isinstance(v, float) else str(v)) for k, v in numbers.items()}
    fill = lambda s: s.format(**nums)  # noqa: E731
    page_dams = [{**d, "note": fill(text["notes"].get(d["key"], ""))} for d in dams]
    keys = {k: v for k, v in text.items() if isinstance(v, str)}
    keys.update(
        img=img,
        other_lang="tr" if text["lang"] == "en" else "en",
        unet_p=fill(text["unet_p"]),
        steps_html="".join(f"<li>{s}</li>" for s in text["steps"]),
        credits_html="\n    ".join(f"<p>{c}</p>" for c in text["credits"]),
        nav_html="".join(f'<a href="#{i}">{label}</a>' for i, label in zip(NAV_IDS, text["nav"])),
        langs_html=(
            '<span aria-current="page">EN</span><a href="tr/" hreflang="tr" lang="tr">TR</a>'
            if text["lang"] == "en"
            else '<a href="../" hreflang="en" lang="en">EN</a><span aria-current="page">TR</span>'
        ),
        bc_high=panel_label(crops["buyukcekmece_high"], text),
        bc_low=panel_label(crops["buyukcekmece_low"], text),
        dk_high=panel_label(crops["darlik_high"], text),
        dk_low=panel_label(crops["darlik_low"], text),
        th_html="".join(('<th class="num">' if i >= 2 else "<th>") + h + "</th>" for i, h in enumerate(text["th"])),
    )
    js = {k: text[k] for k in ("status", "capacity", "f_heldout", "f_iski", "f_dates", "f_bar", "pts", "tip_sat", "tip_rep", "aria", "latest_note", "scene", "locale", "gauge")}
    out = template.replace("__DATA__", json.dumps({"dams": page_dams, "ibb_end": str(ibb.END.date()), "t": js}, ensure_ascii=False))
    for k, v in keys.items():
        out = out.replace("{{" + k + "}}", v)
    if "{{" in out:
        raise ValueError("unfilled placeholder: " + out[out.index("{{") : out.index("{{") + 40])
    return out


if __name__ == "__main__":
    main()
