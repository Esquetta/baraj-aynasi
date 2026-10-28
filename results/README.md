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

The project card set one stop condition: held-out error above 10 occupancy
points on the four largest reservoirs. **It is met for Terkos, Büyükçekmece and
Darlık.** Only Ömerli passes.

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

## How the method changed

The first run used plain least-squares polynomials without a monotone
constraint or outlier handling ([heldout_metrics_v1_naive.csv](heldout_metrics_v1_naive.csv),
commit `d88020f`). Its curves bent into U shapes through the NDWI failures and
the kill rule was met for the same three reservoirs. The robust, monotone fit
was added **after** looking at the held-out results, so the held-out numbers
above are somewhat optimistic. The 2024–2026 comparison with İSKİ's reported
figures has not been looked at and is the untouched test.

## Files

- `areas.csv`: water area and cloud-free share per reservoir and scene.
- `curves.json`: final curves fitted on all labelled scenes, with the area range
  they were fitted on (straight-line continuation outside it) and error bars.
- `estimates_2024_2026.csv`: satellite-only estimates after 2024-02-19. Not
  validated against İSKİ yet. Rows with `heldout_passed = False` (Terkos,
  Büyükçekmece, Darlık, Elmalı) failed the 10-point held-out check; do not use them.
- `figures/fit_<dam>.png`: curve, held-out points and time series.
- `figures/crops_<dam>.png`: true colour with the NDWI outline at high and low water.

Contains modified Copernicus Sentinel data 2017–2026. Occupancy: İBB Açık Veri
Portalı, İBB Open Data License.
