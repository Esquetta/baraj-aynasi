"""Link preview images (1200 x 630) for the project page, one per language.

Puts the two Büyükçekmece crops from scripts/crops.py (high and low water)
next to the page title. Writes results/figures/og_en.jpg and og_tr.jpg, which
scripts/build_site.py copies into site/img/.

    uv run python scripts/og_image.py
"""

import json
from pathlib import Path

from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont

FIGS = Path("results/figures")
W, H = 1200, 630
CROP_W = 330  # each crop, centred; leaves 540 px for text
BG, INK, MUTED, ACCENT = (16, 20, 24), (236, 240, 243), (150, 160, 168), (35, 152, 173)
TEXT = {
    "en": {
        "sub": ["Istanbul's reservoirs", "measured from space"],
        "body": ["Sentinel-2 water area turned", "into occupancy estimates,", "with error bars. 2017–2026."],
        "months": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
        "credit": "Contains modified Copernicus Sentinel data 2022–2023",
    },
    "tr": {
        "sub": ["İstanbul'un barajları", "uzaydan ölçülüyor"],
        "body": ["Sentinel-2 su yüzeyinden", "hata paylı doluluk tahmini.", "2017–2026."],
        "months": "Oca Şub Mar Nis May Haz Tem Ağu Eyl Eki Kas Ara".split(),
        "credit": "Değiştirilmiş Copernicus Sentinel verisi içerir, 2022–2023",
    },
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold" if bold else "normal"))
    return ImageFont.truetype(path, size)


def label(meta: dict, months: list[str], lang: str) -> str:
    y, m, _ = meta["date"].split("-")
    pct = round(meta["occupancy_pct"])
    return f"{months[int(m) - 1]} {y} · " + (f"%{pct}" if lang == "tr" else f"{pct}%")


def main() -> None:
    meta = json.loads((FIGS / "crops_meta.json").read_text(encoding="utf-8"))
    for lang, t in TEXT.items():
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        x = W
        for which in ("low", "high"):
            crop = Image.open(FIGS / f"crop_buyukcekmece_{which}.jpg").convert("RGB")
            crop = crop.resize((round(crop.width * H / crop.height), H), Image.LANCZOS)
            left = (crop.width - CROP_W) // 2
            crop = crop.crop((left, 0, left + CROP_W, H))
            x -= crop.width
            img.paste(crop, (x, 0))
            tag = label(meta[f"buyukcekmece_{which}"], t["months"], lang)
            box = d.textbbox((0, 0), tag, font=font(24, True))
            d.rectangle((x + 14, H - 62, x + 30 + box[2], H - 22), fill=BG)
            d.text((x + 22, H - 58), tag, font=font(24, True), fill=INK)
        d.text((56, 64), "Baraj Aynası", font=font(54, True), fill=INK)
        d.rectangle((56, 140, 128, 146), fill=ACCENT)
        for i, line in enumerate(t["sub"]):
            d.text((56, 176 + i * 42), line, font=font(32, True), fill=INK)
        for i, line in enumerate(t["body"]):
            d.text((56, 300 + i * 34), line, font=font(24), fill=MUTED)
        d.text((56, 470), "Büyükçekmece →", font=font(24, True), fill=ACCENT)
        d.text((56, H - 50), t["credit"], font=font(15), fill=MUTED)
        img.save(FIGS / f"og_{lang}.jpg", quality=88)
        print(f"wrote {FIGS / f'og_{lang}.jpg'}")


if __name__ == "__main__":
    main()
