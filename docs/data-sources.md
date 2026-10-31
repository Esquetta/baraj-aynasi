# Data sources and terms

This project only publishes derived products: water areas, fitted curves,
estimates and small figures. Raw imagery and downloaded datasets stay in the
local, git-ignored `data/` folder and are not redistributed.

## İBB daily dam occupancy (ground truth)

- Dataset: [İstanbul Barajları Günlük Doluluk Oranları](https://data.ibb.gov.tr/dataset/istanbul-barajlari-gunluk-doluluk-oranlari),
  İstanbul Metropolitan Municipality (İBB) Open Data Portal.
- File: `istanbul-dams-daily-occupancy-rates.xlsx`, 8,520 daily rows from
  2000-10-23 to 2024-02-19, one column per reservoir (Ömerli, Darlık, Elmalı,
  Terkos, Alibey, Büyükçekmece, Sazlıdere, Kazandere, Pabuçdere, Istrancalar).
  The dataset was last modified on 2024-03-01 and has not been extended.
- Quirk handled in `src/baraj_aynasi/ibb.py`: rows from 2023-04-01 to 2023-08-08
  store text dates (`d.m.yyyy`) and percentages; all other rows store dates and
  fractions.
- Licence: [İBB Open Data License](https://data.ibb.gov.tr/license) v1.0. It
  allows copying, distribution and derived works, including commercial use,
  provided the source is attributed and no official endorsement is implied.
  Attribution text suggested by the licence:
  > Atıf 4.0 Uluslararası (CC BY 4.0) kapsamında lisanslanan kamu sektörü bilgilerini içerir.

## Copernicus Sentinel-2 L2A imagery

- Collection `sentinel-2-l2a` on the
  [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a)
  STAC API. Searching needs no account. Reading the image files needs a short-lived
  SAS token from the free anonymous token endpoint, which the `planetary-computer`
  package fetches. No paid key is used.
- Planetary Computer's supplemental terms say tokens are personal and must not
  be shared with third parties, so this project never publishes signed URLs or
  serves imagery to browsers; it only publishes derived results.
- Bands used: B03 (green, 10 m), B08 (near infrared, 10 m), SCL (scene
  classification, 20 m). Tiles: 35TPF, 35TQF and 35TNG (UTM zone 35N).
- Reflectance harmonisation: products with processing baseline 04.00 or later
  store digital numbers with a +1000 offset. The offset is removed by baseline,
  not by date, because the archive holds reprocessed items with mixed baselines
  for the same dates.
- Terms: the [Legal notice on the use of Copernicus Sentinel Data and Service
  Information](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)
  grants free reproduction, distribution and adaptation. Every published figure
  derived from the imagery carries the required wording, and the README files
  next to the derived tables state it:
  > Contains modified Copernicus Sentinel data [years].

## Reservoir areas of interest (AOI)

`aoi/reservoirs.geojson` holds one polygon set per reservoir. They were drawn
from the imagery itself, not traced from another map:

1. For each reservoir, the clearest scenes (at least 95% cloud-free over the
   search box) on the dates İBB reported the highest occupancy between 2017 and
   2022-06-30 (the training period) were selected, at most one per month and
   twelve in total.
2. Per pixel, the share of those scenes with NDWI > 0 was computed.
3. The connected water body containing hand-picked seed points (in
   `src/baraj_aynasi/dams.py`) was kept, grown by 200 m and stripped of any other
   water body inside the margin (for example the Black Sea next to Terkos).
4. The result was vectorised, simplified by 10 m and checked by eye against the
   frequency maps in `aoi/review/`.

Search boxes and seed points were placed with the help of reservoir locations
from OpenStreetMap, Wikidata and İSKİ's "Su Kaynakları" page; no OpenStreetMap
geometry is copied into the polygons. Istrancalar is the sum of five small
stream reservoirs (Düzdere, Kuzuludere, Büyükdere, Sultanbahçedere, Elmalıdere).
Büyükdere is mapped in OpenStreetMap as "Çilingöz Göleti"; that identification
is an inference from İSKİ's basin regulation.

## İSKİ occupancy after 2024-02-19

Used only to score the frozen 2024-2026 estimates (`scripts/iski_check.py`).

- İSKİ's [baraj doluluk page](https://iski.istanbul/baraj-doluluk/) has no
  public download or date-range query. On 2026-10-28 the page was opened in a
  browser like any visitor, each reservoir was selected in its detail tab, and
  the values the page displayed were saved: month ends from 2025-10-31 to
  2026-09-30 plus the current day, the last 14 days, and 28 October of each
  year since 2016. The page's API token was not
  used outside the page.
- From 2026-10-31, `scripts/iski_harvest.py` repeats that page visit once a
  day in a headless browser (Playwright, installed with `uv sync --extra
  harvest`) and saves `data/iski/live_<date>.json`. Because the page shows the
  same calendar day for the past ten years, a year of daily visits fills in
  every day of 2024–2026. Run it once a day after about 09:30 Istanbul time,
  when İSKİ updates the page (for example from a scheduled task or cron).
- Wayback Machine copies of the page's daily summary (`gunlukOzet`) cover 20
  dates from 2024-01-21 to 2025-12-10.
- On the 140 reservoir-days that İBB also covers, İSKİ and İBB agree to 0.01
  points.
- No open licence for İSKİ's figures was found. The raw files stay in
  `data/iski/`; only the figures matched to a satellite scene (52 in
  `results/iski_check.csv`, and the same pairs for the U-Net and MNDWI runs)
  are reproduced, credited to İSKİ, for comparison.
- Not used: news articles. They repeat İSKİ's figures but one checked article
  printed each reservoir's share of total storage as its occupancy.

## U-Net training labels

`labels/patches.csv` lists, for 300 patches of 96 × 96 pixels, the scene, box
and window each was cut from; `labels/review.csv` records which candidate mask
was picked for each (or that it was rejected). The patches themselves are
derived from the Sentinel-2 imagery above and stay in `data/unet/`. The picks
were made by AI agents looking at true- and false-colour images in two
independent passes, with a third pass on the 24 disagreements. The owner
spot-checked 56 of them by eye (`labels/owner_check.csv`); see
`results/unet/README.md`.
