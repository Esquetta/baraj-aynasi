"""Build the spot-check page for the U-Net labels.

One question per patch, no remote-sensing knowledge needed: does the pink
mask (the label the AI review picked) cover the water in the image? Sample:
every non-NDWI or disputed label plus random NDWI picks, shuffled; rejected
patches are skipped because they are not used for training. Three worked
examples come first. Answers go to the artifact's `check` collection.

    uv run python scripts/spotcheck_page.py   # writes data/unet/spotcheck.html
"""

import base64
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from baraj_aynasi.patches import CANDIDATES

PATCHES = Path("data/unet/patches")
OUT = Path("data/unet/spotcheck.html")
TEMPLATE = Path("scripts/spotcheck_template.html")
RANDOM_NDWI = 15
SEED = 11
# (patch, mask shown, right answer, why) -- answers: ok, missed, spill
EXAMPLES = [
    ("004_omerli_20200628", "ndwi", "ok", "Pembe alan, koyu su yüzeyinin tamamını kaplıyor ve ormana taşmıyor. Kıyı çizgisini birkaç piksel kaçırması sorun değil."),
    ("006_omerli_20180609", "ndwi", "missed", "Puslu, alg dolu bir gün. Yalancı renkte su açıkça koyu, ama pembe alan sadece alttaki birkaç beneği kapsıyor; suyun çoğu kaçırılmış."),
    ("066_elmali_20180607", "dark_nir", "spill", "Kanalı kaplıyor ama üst kısımda ve sağ altta ormanı da su saymış. Yalancı renkte o bölgeler parlak kırmızı: bitki, su değil."),
]


def jpeg(rgb: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def bits(mask: np.ndarray) -> str:
    return base64.b64encode(np.packbits(mask.astype(bool).ravel()).tobytes()).decode()


def item(pid: str, mask: str, **extra) -> dict:
    z = np.load(PATCHES / f"{pid}.npz")
    tci = np.clip(z["tci"].astype(float) * 1.6, 0, 255).astype(np.uint8)
    fc = (np.clip(np.stack([z["x"][2], z["x"][1], z["x"][0]], -1) * 3.5, 0, 1) * 255).astype(np.uint8)
    return {
        "pid": pid,
        "dam": pid.split("_")[1],
        "date": f"{pid[-8:-4]}-{pid[-4:-2]}-{pid[-2:]}",
        "tci": jpeg(tci),
        "fc": jpeg(fc),
        "mask": bits(z["candidates"][CANDIDATES.index(mask)]),
        "ignore": bits(z["ignore"]),
        **extra,
    }


def main() -> None:
    table = pd.read_csv("labels/patches.csv").merge(pd.read_csv("labels/review.csv"), on="pid")
    table = table[(table.choice != "reject") & ~table.pid.isin([e[0] for e in EXAMPLES])]
    risky = table[(table.choice != "ndwi") | (table.pass_a != table.pass_b)]
    calm = table.drop(risky.index).sample(RANDOM_NDWI, random_state=SEED)
    sample = pd.concat([risky, calm]).sample(frac=1, random_state=SEED)
    items = [item(r.pid, r.choice, split=r.split) for r in sample.itertuples()]
    examples = [item(pid, mask, answer=ans, why=why) for pid, mask, ans, why in EXAMPLES]
    html = (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("__PATCHES__", json.dumps(items))
        .replace("__EXAMPLES__", json.dumps(examples, ensure_ascii=False))
    )
    OUT.write_text(html, encoding="utf-8")
    print(f"{len(items)} patches ({len(risky)} risky, {RANDOM_NDWI} random NDWI) + {len(examples)} examples -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
