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

## Data

Sentinel-1 RTC from Microsoft Planetary Computer, processed by Catalyst (CC BY 4.0).
Contains modified Copernicus Sentinel data. Chips stay in `data/radar/` and aren't
committed.
