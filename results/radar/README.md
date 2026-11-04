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

## Result

Average miss in occupancy points, VV with the fixed threshold. Held-out: July 2022 to
February 2024 against İBB, curves fitted on training years. İSKİ: 2024–2026, curves
frozen at 2024-02-19, passes within a day of a figure, as of 2026-11-04. The bar is the
90% error bar of the final curve. Optical is the same held-out test on the NDWI series,
for reference; its scenes fall on different dates.

| Reservoir | Held-out | Vs İSKİ | İSKİ pairs | Bar | Rule 3 | Optical held-out |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| **Ömerli** | 6.4 | 4.8 | 16 | ±12.4 | pass | 5.3 |
| **Sazlıdere** | 4.3 | 3.7 | 27 | ±9.5 | pass | 1.1 |
| **Pabuçdere** | 6.8 | 7.0 | 27 | ±14.6 | pass | 1.3 |
| **Alibey** | 6.5 | 4.4 | 27 | ±17.9 | pass | 3.2 |
| **Istrancalar** | 6.1 | 5.3 | 27 | ±13.6 | pass | 5.2 |
| Darlık | 9.8 | 9.6 | 15 | ±21.1 | pass | 11.7 |
| Kazandere | 10.0 (9.99) | 8.8 | 27 | ±23.3 | pass | 5.6 |
| Büyükçekmece | 10.9 | 13.5 | 26 | ±26.7 | fail | 11.5 |
| Elmalı | 10.9 | 5.3 | 27 | ±23.4 | fail | 17.0 |
| Terkos | 11.1 | 11.9 | 26 | ±21.4 | fail | 23.0 |

- **All five offered reservoirs pass**, so their radar estimates go on the page as a
  separate series with their own bars. Radar is less precise than a clear optical scene
  on all five. Its value is being there when clouds aren't letting optical through.
- **Darlık and Kazandere also pass, narrowly, and stay not offered.** Under rule 4 that
  is the author's separate decision. Bars above ±20 points also make them of little use.
- **Terkos and Büyükçekmece stay above the line.** Radar halves Terkos's held-out error,
  but its last five İSKİ pairs still read about 23 points high. Elmalı fails on held-out
  error alone (10.9); its 5.3 against İSKİ doesn't change that.
- The 90% bars held on the held-out years at 84% to 100%, with Ömerli and Pabuçdere
  lowest at 84%.

### When the optical estimate is old

After the rule, as an exploration: on each day İSKİ published a figure, compare the
latest estimate of each series so far. These are the days when the optical estimate was
more than 14 days old (`freshness.csv`).

| Reservoir | Days | Median age, optical | Median age, radar | Miss, optical | Miss, radar |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ömerli | 12 | 29 | 3.5 | 14.8 | 4.2 |
| Sazlıdere | 21 | 21 | 2 | 8.0 | 4.1 |
| Pabuçdere | 31 | 48 | 2 | 8.6 | 3.7 |
| Alibey | 10 | 36 | 2.5 | 11.0 | 3.8 |
| Istrancalar | 31 | 47 | 2 | 25.9 | 12.0 |

Read this with care. It wasn't part of the rule, and the days aren't independent: many
fall in the same few weeks of autumn 2026. Istrancalar's small stream reservoirs can
move several points a day after rain, so even a two-day-old estimate can lag.

### Known weakness: orbits disagree

Radar sees the same reservoir from different angles, and on the held-out years relative
orbit 138 reads high where orbit 58 doesn't: Ömerli +9.0 against +0.1, Darlık +15.2
against +0.1, Elmalı +17.0 against +0.7 (`orbit_bias.csv`). Passes of the same day are
averaged, as in the optical series, but the dots still scatter. A curve per orbit might
help. The held-out years have now been seen, so that would need new data to judge
fairly, and it hasn't been done.

## Reproduce

```bash
uv run python scripts/radar_download.py      # chips for every pass, about 10 GB
uv run python scripts/radar_areas.py         # areas per pass and thresholds, from the chips only
uv run python scripts/radar_pick_mask.py     # rule 2, training years only
uv run python scripts/fit.py --areas results/radar/areas_vv_fixed.csv --out results/radar/vv_fixed
uv run python scripts/iski_check.py --results results/radar/vv_fixed   # needs data/iski/
uv run python scripts/radar_compare.py       # freshness.csv, orbit_bias.csv
```

`scripts/radar_update.py` runs daily in `.github/workflows/update.yml`. On the 64 recent
passes checked, it gave the same water area as the archive run, and it left all 3,386
estimates unchanged. `vv_fixed/estimates_2024_2026.csv` gets its new passes from it, and
`vv_fixed/iski_check.csv` and `vv_fixed/iski_metrics.csv` are rescored daily by
`scripts/iski_publish.py`, so they will move on from the table above. The curves stay
frozen.

The numbers here were fitted from `areas_vv_fixed.csv` as committed in `c174074`. The
robust fit samples points by row position, so row order matters a little: sorting the
same rows moved held-out errors by up to 0.14 points and training errors by up to 0.1,
and changed no decision. Daily passes are added at the end of the file for this reason.

## Data

Sentinel-1 RTC from Microsoft Planetary Computer, processed by Catalyst (CC BY 4.0).
Contains modified Copernicus Sentinel data 2017–2026. Chips stay in `data/radar/` and
aren't committed. Occupancy: İBB Açık Veri Portalı, İBB Open Data License; after
2024-02-19, İSKİ (iski.istanbul).
