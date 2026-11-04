# Sentinel-1 radar: can it fill the cloudy gaps?

Optical estimates need a cloud-free scene, and in autumn and winter that can leave a
reservoir's latest estimate two months old. Radar sees through cloud. This folder
tests whether Sentinel-1 water area can carry an occupancy estimate. Satellite
estimates with error bars, not official figures.

## Decision rule, set before any scoring

Everything after the mask is the pipeline in [../README.md](../README.md): the same
AOIs, scene filter, robust monotone curves, split (train to 2022-06-30, held out to
2024-02-19) and error bars. `clear_frac` is the share of the AOI the radar pass
covers.

1. **Pilot, training years only.** 40 passes per reservoir, evenly spaced across İBB
   occupancy, all up to 2022-06-30. If leave-one-year-out error is above 10 points on
   three or more of the five offered reservoirs (Ömerli, Sazlıdere, Pabuçdere, Alibey,
   Istrancalar) for every candidate mask, stop here and write up the result.
2. **One mask, chosen on training years only.** Candidates: VV or VH, split per scene
   (Otsu) or at a fixed per-dam threshold set from training scenes. The mask with the
   lowest median leave-one-year-out error across the ten reservoirs is used for all of
   them, and no other mask is scored on the held-out years.
3. **A reservoir's radar estimates may go on the page only if** its held-out error is
   at most 10 points (the project's stop line) **and** its error against İSKİ's
   2024–2026 figures, with frozen curves and at least 10 pairs, is at most 10 points.
   Radar estimates stay a separate, labelled series with their own error bars; they
   are never merged into the optical one.
4. A reservoir not offered today (Terkos, Darlık, Büyükçekmece, Elmalı, Kazandere) that
   passes rule 3 is reported here, and being offered from radar is a separate decision
   by the author.

## Pilot result

Leave-one-year-out error in occupancy points, training years only. NDWI uses all its
clean training scenes, the radar masks about 40 passes each. "–" means no increasing
curve could be fitted.

| Reservoir | VV, per scene | VV, fixed | VH, per scene | VH, fixed | NDWI |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Ömerli** | 5.7 | 10.4 | 13.9 | 18.2 | 7.8 |
| **Sazlıdere** | 2.8 | 5.0 | 8.1 | 15.1 | 2.3 |
| **Pabuçdere** | 4.9 | 6.4 | 21.7 | 16.1 | 3.6 |
| **Alibey** | 9.3 | 8.9 | 20.7 | 15.6 | 4.9 |
| **Istrancalar** | 11.2 | 6.3 | 8.5 | 10.0 | 5.8 |
| Darlık | 20.5 | 9.9 | 22.8 | 26.9 | 11.1 |
| Terkos | 10.0 | 13.3 | 9.1 | 11.6 | 11.7 |
| Büyükçekmece | 10.8 | 21.7 | 17.6 | 20.3 | 10.9 |
| Kazandere | 19.0 | 9.9 | 25.1 | 17.6 | 10.8 |
| Elmalı | 35.8 | 15.3 | – | 30.9 | 15.0 |
| Median | 10.4 | 9.9 | 17.6 | 16.8 | |

Rule 1 is met: each VV mask misses 10 points on one offered reservoir, so the work
continues. VH is clearly worse on these years and is dropped, which also halves the
download. The two VV medians are too close to separate on 40 passes, so rule 2 is
applied to all training-year passes.

## Mask choice

Same measure on all clean training-year passes, from
[`scripts/radar_pick_mask.py`](../../scripts/radar_pick_mask.py), recorded here before
any held-out year was scored. Per-pass areas are in `areas_vv_otsu.csv` and
`areas_vv_fixed.csv`, thresholds in `thresholds.json`.

| Reservoir | VV, per scene | VV, fixed |
| --- | ---: | ---: |
| **Ömerli** | 4.7 | 6.2 |
| **Sazlıdere** | 3.5 | 4.3 |
| **Pabuçdere** | 6.5 | 7.3 |
| **Alibey** | 7.9 | 8.5 |
| **Istrancalar** | 9.6 | 6.5 |
| Darlık | 9.4 | 10.2 |
| Terkos | 10.1 | 11.5 |
| Büyükçekmece | 10.3 | 13.1 |
| Kazandere | 16.9 | 12.0 |
| Elmalı | 28.3 | 9.9 |
| Median | 9.47 | 9.20 |

**VV with a fixed per-dam threshold is the mask.** Per-scene VV wins on seven of the
ten reservoirs and loses the median by 0.27 points, so this is a narrow call made by the
rule, not a clear win. Per-scene VV isn't scored on the held-out years.

## Data

Sentinel-1 RTC from Microsoft Planetary Computer, processed by Catalyst (CC BY 4.0).
Contains modified Copernicus Sentinel data. Chips stay in `data/radar/` and aren't
committed.
