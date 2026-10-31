# Baraj Aynası

Project page: [esquetta.github.io/baraj-aynasi](https://esquetta.github.io/baraj-aynasi/)
([Türkçe](https://esquetta.github.io/baraj-aynasi/tr/))

Satellite estimates, with error bars, of how full Istanbul's ten supply
reservoirs are. The water surface of each reservoir is measured in Sentinel-2
L2A imagery (2017–2026), and a per-reservoir curve maps surface area to the
occupancy İBB reported daily until 2024-02-19. After that date the curves turn
satellite measurements alone into occupancy estimates.

Status: Phase 1 (data pipeline and NDWI baseline) is done. The project's stop
rule ("if the held-out error for the four largest reservoirs exceeds 10
occupancy points, publish the gap and stop") was met for Terkos, Büyükçekmece
and Darlık; [results/README.md](results/README.md) is that write-up. Continuing
with a narrower scope was a later decision: estimates are offered for Ömerli,
Alibey, Sazlıdere, Pabuçdere and Istrancalar, which missed İSKİ's 2024-2026
figures by 1.6 to 4.8 points on average in an untouched test (4 to 6 comparison
dates each). Kazandere is provisional after 17- and 23-point misses in summer
2026; Terkos is out, and Elmalı is too small.

A small U-Net, trained on 236 patches labelled by AI agents (60 more held out
for testing; 56 of the labels spot-checked by the owner), was tried as an
alternative water mask. It handles the late-spring scenes where NDWI misses
algal water without a hand-made filter: over five training runs Darlık's
held-out error drops from 11.7 to 5.3 on average (4.9–5.7) and its error bar
from ±24 to ±12, while removing those scenes from the NDWI series gives about
the same error. It beats NDWI in every run on Ömerli, Darlık, Terkos,
Istrancalar and Elmalı, is worse in every run on Sazlıdere and Kazandere, and
Terkos and Büyükçekmece still miss the stop line in every run. The served estimates stay on NDWI. See
[results/unet/README.md](results/unet/README.md).

## How it works

1. `scripts/search.py` caches Sentinel-2 L2A STAC items for tiles 35TPF, 35TQF
   and 35TNG from Microsoft Planetary Computer.
2. `scripts/download.py` reads clipped B03, B08 and SCL chips for every reservoir
   and keeps scenes with at least 30% cloud-free pixels in the search box.
3. `scripts/draw_aoi.py` draws each reservoir's area of interest from its
   high-water extent (see [docs/data-sources.md](docs/data-sources.md)).
4. `scripts/areas.py` computes NDWI = (green − NIR) / (green + NIR) and counts
   water pixels (NDWI > 0, cloud-free per SCL) inside the AOI.
5. `scripts/fit.py` fits robust, increasing area-to-occupancy curves on scenes
   up to 2022-06-30, reports error on 2022-07-01 to 2024-02-19, and sizes a 90%
   error bar from leave-one-year-out residuals.

```bash
uv sync                  # add --extra unet for the U-Net (PyTorch, CUDA wheels for Windows and Linux)
uv run pytest
uv run python scripts/search.py
uv run python scripts/download.py
uv run python scripts/draw_aoi.py
uv run python scripts/areas.py
uv run python scripts/fit.py
uv run python scripts/iski_check.py   # needs data/iski/, see docs/data-sources.md
uv run --extra harvest python scripts/iski_harvest.py   # once a day, saves İSKİ's page windows
uv run --extra harvest python scripts/iski_publish.py   # harvest + results/iski_series.csv + page, then push
uv run python scripts/update.py       # new scenes -> results/areas.csv and estimates, frozen curves
```

A GitHub Actions workflow (`.github/workflows/update.yml`) runs `update.py` and
`build_site.py` every morning and commits any new estimates; the page then
redeploys. Estimates appear only when a new scene of a reservoir is at least 98%
cloud-free, so the page can stay unchanged for days in cloudy weather.

The U-Net steps are listed in [results/unet/README.md](results/unet/README.md). `uv run python scripts/build_site.py` builds the static project page in
`site/` from the committed results.

Raw imagery is cached under `data/` (about 30 GB) and is not committed.

## Data and attribution

- Reservoir occupancy: [İBB Açık Veri Portalı](https://data.ibb.gov.tr/dataset/istanbul-barajlari-gunluk-doluluk-oranlari),
  İstanbul Büyükşehir Belediyesi, under the [İBB Open Data License](https://data.ibb.gov.tr/license).
  Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir.
- Imagery: Contains modified Copernicus Sentinel data 2017–2026, accessed through
  the Microsoft Planetary Computer.
- 2024–2026 comparison figures: İSKİ, [iski.istanbul/baraj-doluluk](https://iski.istanbul/baraj-doluluk/).

Details, terms and the AOI drawing method are in
[docs/data-sources.md](docs/data-sources.md). Code is MIT licensed.
