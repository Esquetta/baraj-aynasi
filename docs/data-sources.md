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

Not yet collected. İSKİ's [baraj doluluk page](https://iski.istanbul/baraj-doluluk/)
shows the current day, rolling windows and the same calendar day for the past ten
years; Wayback Machine snapshots of its JSON exist for 14 dates in 2024-2025;
news articles repeat the daily figures with occasional transcription errors.
How this comparison set is gathered will be decided before it is used.
