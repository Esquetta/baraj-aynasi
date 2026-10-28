# Phase 1 results: NDWI baseline

Satellite estimates with error bars, not official figures. Occupancy ground
truth is İBB's daily series, which ends on 2024-02-19.

## Setup

- 6,666 reservoir-scene measurements from Sentinel-2 L2A (2017-01 to 2026-10),
  of which scenes with at least 98% of the AOI cloud-free are used.
- Water: NDWI > 0 inside each AOI. Scenes whose area jumps away from their
  neighbours within ±20 days are dropped (label-free filter).
- Curve per reservoir: polynomial of degree 1 or 2, chosen by leave-one-year-out
  error on the training years. The fit starts from a least-median-of-squares
  estimate and drops points more than 3 robust standard deviations off it.
  Curves must not decrease over the observed area range and continue as
  straight lines (tangents) outside it.
- Split: train on scenes up to 2022-06-30, test on 2022-07-01 to 2024-02-19.
  The AOIs are drawn from training-period scenes only.
  The 90% error bar is the 90th percentile of out-of-fold residuals in training.

## Held-out error (occupancy points)

| Reservoir | Test scenes | MAE | RMSE | Bias | LOYO MAE 2017–2024 | 90% bar | Bar coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Ömerli** | 47 | 5.3 | 6.3 | +3.8 | 6.9 | ±11.7 | 98% |
| **Terkos** | 22 | **23.0** | 24.2 | +23.0 | 13.0 | ±28.8 | 82% |
| **Büyükçekmece** | 60 | **11.5** | 13.8 | −5.0 | 14.9 | ±21.6 | 85% |
| **Darlık** | 23 | **11.7** | 14.8 | −3.0 | 9.1 | ±24.3 | 83% |
| Sazlıdere | 55 | 1.1 | 1.4 | +0.0 | 1.7 | ±4.7 | 100% |
| Kazandere | 27 | 5.6 | 6.4 | −3.2 | 11.5 | ±21.2 | 100% |
| Pabuçdere | 30 | 1.3 | 1.7 | +0.4 | 3.0 | ±8.3 | 100% |
| Alibey | 47 | 3.2 | 4.1 | +3.0 | 4.4 | ±10.8 | 100% |
| Istrancalar | 26 | 5.2 | 7.5 | +1.0 | 5.5 | ±12.3 | 96% |
| Elmalı | 48 | 17.0 | 18.1 | +17.0 | 10.9 | ±33.1 | 100% |

Bold rows are the four largest reservoirs by capacity. Bias is predicted minus
reported. Full table:
[heldout_metrics.csv](heldout_metrics.csv). LOYO MAE holds out each labelled
year in turn, so it mostly measures interpolation; the held-out MAE measures
extrapolation forward in time.

## Kill rule

The project card set one stop condition: "If the held-out error for the four
largest reservoirs exceeds 10 occupancy points, publish the gap and stop."
**It is met for Terkos, Büyükçekmece and Darlık.** Only Ömerli passes. This
write-up is the published gap. Going on with a narrower scope (below) is a
separate, later decision by the project owner, not something the rule allows.

## Where the gap comes from

1. **The test period holds the 2023 drought, below anything in training.**
   In İBB's daily series Büyükçekmece fell to 3.6% (minimum before 2022-07:
   16.1%), Terkos to 7.7% (19.9%) and Darlık to 26.6% (32.5%). The curves have
   to extrapolate there.
2. **Reservoir shape.** Büyükçekmece is a former lagoon: at 4% it still holds
   about 12 km² of shallow water, against 24 km² when full, so area keeps
   shrinking while storage barely changes (see
   [crops_buyukcekmece.png](figures/crops_buyukcekmece.png)). Darlık is a steep
   valley reservoir: its surface only goes from 2.9 to 5.4 km² between 29% and
   100%, so 0.1 km² of mask error is worth about 3 points
   ([crops_darlik.png](figures/crops_darlik.png)).
3. **Terkos at high levels.** Between 40% and 95% its NDWI area only moves
   within 28–34 km² and scatters widely, likely because of reed beds on its
   margins and a weir-controlled natural lake. Even interpolation (LOYO) misses by
   13 points. At 100% its north-west arm also reaches the edge of the search box.
4. **NDWI fails on some late-spring scenes.** In May and June, open water in
   Ömerli and Darlık sometimes has NDWI ≤ 0 (likely algal or turbid water), giving
   near-zero areas at 90% occupancy. The robust fit ignores these in training, but
   an estimate made on such a date is wrong. A better water mask (MNDWI with the
   SWIR band, or the planned U-Net) targets this; it does not fix points 1–3.

Elmalı (9.6 million m³, under 1 km² of water) is too small for this method.

## Untouched test: İSKİ figures, 2024-03-25 to 2026-10-22

The estimates file was committed (`b88fc36`) before any İSKİ figure after
2024-02-19 was collected, and the curves were not changed afterwards. Each scene
is paired with the İSKİ figure at most one day away; when two scenes of the same
tile exist on one day (two orbits), their estimates are averaged. The ±1-day
window was set before the first scoring run. The rule of one pair per scene was
added after that run, which had counted some scenes several times. İSKİ figures
come from Wayback Machine copies of İSKİ's daily summary (20 dates, 14 after
2024-02-19) and from the windows İSKİ's occupancy page showed on 2026-10-28
(month ends from 2025-10-31 to 2026-09-30, the last 14 days, and 28 October of
each year). On the 140 dam-days
that İBB also covers, the two series agree to 0.01 points, so they are the same
measurements.

| Reservoir | Held-out check | Pairs | MAE | Bias | Inside 90% bar |
| --- | --- | ---: | ---: | ---: | ---: |
| Ömerli | passed | 6 | 4.8 | +1.6 | 6/6 |
| Alibey | passed | 6 | 3.0 | +2.2 | 6/6 |
| Sazlıdere | passed | 5 | 1.6 | −0.3 | 5/5 |
| Pabuçdere | passed | 5 | 2.5 | +2.5 | 5/5 |
| Istrancalar | passed | 4 | 2.6 | +0.6 | 4/4 |
| Kazandere | passed | 4 | 12.0 | +8.0 | 3/4 |
| Darlık | failed | 5 | 4.0 | −1.0 | 5/5 |
| Büyükçekmece | failed | 7 | 6.9 | −6.3 | 7/7 |
| Terkos | failed | 2 | 20.0 | +20.0 | 2/2 |
| Elmalı | failed | 8 | 6.2 | +6.2 | 8/8 |

Pairs per reservoir are few (2 to 8), so these numbers are rough. They agree
with the held-out picture for Ömerli, Alibey, Sazlıdere, Pabuçdere, Istrancalar
and Terkos. Darlık does better here than in the held-out years, which is
consistent with its matched scenes (35–89%) staying above the 2023 record low.
Büyükçekmece's MAE is lower too, but two of its seven pairs miss by 16 points
(2025-12-31) and 20 points (2026-07-31), the second well inside the training
range. Kazandere is worse: its two summer 2026 scenes overestimate by 17 and 23
points. For the reservoirs that failed held-out, the 90% bars are ±20 to ±30
points wide, so a full "inside" count says little about accuracy; one covered
Büyükçekmece pair is an estimate of 0% against 16%. See
[iski_metrics.csv](iski_metrics.csv), [iski_check.csv](iski_check.csv) and
[figures/iski_check.png](figures/iski_check.png).

## Scope after Phase 1

This scope is a post-hoc choice made after the kill rule was met (see above).

- Estimates with error bars are offered for **Ömerli, Alibey, Sazlıdere,
  Pabuçdere and Istrancalar**. Kazandere passed held-out but missed in summer
  2026 on the untouched test; treat it as provisional.
- **Terkos** is out: it fails both tests by about 20 points.
- **Darlık** failed held-out mainly at the 2023 record low; on 5 pairs in
  2024-2026 it stayed within 4 points on average. It stays labelled as failing.
- **Büyükçekmece** failed held-out and still misses by 16 and 20 points on 2 of 7
  pairs in 2024-2026. It stays labelled as failing.
- **Elmalı** is out: under 1 km² of water.

## Later: U-Net water masks

With a U-Net mask (Phase 2), Darlık's held-out error is 5.5 and Terkos and
Büyükçekmece stay above the stop line; see [unet/README.md](unet/README.md).
The Darlık gain shows that point 4 above (late-spring NDWI dropouts, through
their effect on the training curve) explained much of Darlık's gap, more than
point 1 suggested. The scope above was set before that run.

## How the method changed

The first run used plain least-squares polynomials without a monotone
constraint or outlier handling ([heldout_metrics_v1_naive.csv](heldout_metrics_v1_naive.csv),
commit `d88020f`). Its curves bent into U shapes through the NDWI failures and
the kill rule was met for the same three reservoirs. The robust, monotone fit
was added **after** looking at the held-out results, so the held-out numbers
above are somewhat optimistic. The 2024–2026 comparison with İSKİ's reported
figures was run once the estimates were frozen in `b88fc36`; see the
untouched-test section above.

## Files

- `areas.csv`: water area and cloud-free share per reservoir and scene.
- `curves.json`: final curves fitted on all labelled scenes, with the area range
  they were fitted on (straight-line continuation outside it) and error bars.
- `estimates_2024_2026.csv`: satellite-only estimates after 2024-02-19, frozen
  before the İSKİ comparison. Rows with `heldout_passed = False` (Terkos,
  Büyükçekmece, Darlık, Elmalı) failed the 10-point held-out check; do not use them.
- `figures/fit_<dam>.png`: curve, held-out points and time series.
- `figures/crops_<dam>.png`: true colour with the NDWI outline at high and low water.
- `iski_check.csv`, `iski_metrics.csv`, `figures/iski_check.png`: the untouched
  test. Occupancy figures in these files are İSKİ's, cited from iski.istanbul.

Contains modified Copernicus Sentinel data 2017–2026. Occupancy: İBB Açık Veri
Portalı, İBB Open Data License; after 2024-02-19, İSKİ (iski.istanbul).
