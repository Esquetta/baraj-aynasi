# U-Net water masks vs NDWI and MNDWI

A small U-Net is tried as the water mask in place of the NDWI threshold;
everything after the mask (AOIs, cloud filter, robust monotone curves, split,
error bars) is the same pipeline as in [../README.md](../README.md). Satellite
estimates with error bars, not official figures. The served estimates stay on
NDWI; the U-Net is an alternative under test.

## What was trained

- **Inputs** (6 channels, 10 m): green (B03), red (B04), near infrared (B08),
  short-wave infrared (B11, resampled from 20 m), NDWI and MNDWI.
- **Patches**: 300 patches of 96 × 96 pixels (about 1 km): 240 from
  training-period scenes (up to 2022-06-30) and 60 from the held-out period.
  Training patches were drawn per reservoir from late-spring scenes, from the
  lowest-occupancy quarter and at random, centred on the shoreline where
  possible ([`../../labels/patches.csv`](../../labels/patches.csv)). All 60 test
  patches are random draws, so none is from a late-spring scene by design.
- **Labels**: for each patch, five candidate masks (NDWI > 0, MNDWI > 0, their
  union and intersection, and an Otsu split of near infrared within the patch)
  were shown next to true- and false-colour images. Two independent passes
  picked the best candidate or rejected the patch, and agreed on 276 of 300. A
  third pass decided the 24 disagreements. Because the first two passes misread
  some patch ids, the third pass also looked at 24 rows where the passes turned
  out to agree once ids were matched; there the agreed pick was kept. **The
  reviewers were AI agents reading the images, not people.** The owner then
  did a quick visual spot-check (about five minutes) of 56 labels: every
  non-NDWI or disputed label used for training or testing, plus 15 random NDWI
  picks. Asked only whether the picked mask covers the water, the owner judged
  49 correct, 6 unsure and 1 wrong (a narrow Darlık arm the mask misses); see
  [`../../labels/owner_check.csv`](../../labels/owner_check.csv). That patch
  was then rejected and the model retrained. Picks: NDWI 268, near-infrared
  split 18, union 10, rejected 4 ([`../../labels/review.csv`](../../labels/review.csv)). The
  near-infrared candidate was added after the first sheet showed a late-spring
  Ömerli patch where every index mask missed most of the water.
- **Training**: U-Net with 4 levels and 16 base channels (1.9 M parameters) on
  236 training-period patches (204 train, 32 validation by scene). Loss is binary
  cross-entropy plus Dice, skipping cloud and no-data pixels; flips and 90°
  rotations; AdamW; the epoch with the lowest validation loss (197 of 200) is
  kept. About 1.5 minutes on an RTX 4070 Ti. The table below is from one
  run after the owner's correction; the model was not changed after testing.
  Five more runs with different seeds follow in [Run-to-run spread](#run-to-run-spread).

## Pixel test (60 held-out patches)

| Method | IoU | F1 |
| --- | ---: | ---: |
| NDWI > 0 | 0.991 | 0.995 |
| U-Net | 0.981 | 0.990 |
| MNDWI > 0 | 0.900 | 0.945 |

58 of the 60 test labels are the NDWI candidate itself, so this test mostly
checks that the U-Net reproduces NDWI where NDWI is right; it does, slightly
less exactly. On the two other test patches the U-Net output stays close to
NDWI's (IoU 0.68 and 0.85 against the label), so there is **no pixel-level
evidence yet that it fixes NDWI failures**.

## Occupancy error by water mask

Mean absolute error in occupancy points. Held-out: 2022-07-01 to 2024-02-19.
LOYO: each labelled year 2017–2024 held out in turn. İSKİ: the 2024–2026
comparison (not used for training, but already looked at in Phase 1; 2 to 8
pairs per reservoir). Each method is scored on its own scenes after the
outlier filter, so scene counts differ slightly; see [comparison.csv](comparison.csv).

| Reservoir | Held-out NDWI | MNDWI | U-Net | 90% bar NDWI → U-Net | Bar coverage NDWI → U-Net | LOYO NDWI → U-Net | İSKİ NDWI → U-Net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Ömerli** | 5.33 | 9.56 | 4.65 | ±11.7 → ±8.5 | 98% → 96% | 6.92 → 4.28 | 4.77 → 3.20 |
| **Darlık** | 11.71 | 9.14 | 5.08 | ±24.3 → ±13.6 | 83% → 100% | 9.06 → 5.43 | 3.99 → 4.98 |
| **Terkos** | 22.98 | 24.57 | 15.00 | ±28.8 → ±25.2 | 82% → 86% | 13.01 → 11.24 | 20.04 → 17.64 |
| **Büyükçekmece** | 11.50 | 10.59 | 11.17 | ±21.6 → ±17.8 | 85% → 78% | 14.86 → 13.95 | 6.94 → 5.91 |
| Alibey | 3.16 | 6.76 | 2.61 | ±10.8 → ±11.5 | 100% → 100% | 4.38 → 3.90 | 2.97 → 2.85 |
| Sazlıdere | 1.14 | 2.45 | 1.91 | ±4.6 → ±4.3 | 100% → 87% | 1.68 → 1.76 | 1.63 → 1.99 |
| Kazandere | 5.61 | 5.57 | 5.86 | ±21.2 → ±17.5 | 100% → 100% | 11.46 → 9.84 | 12.00 → 10.60 |
| Pabuçdere | 1.34 | 1.53 | 1.50 | ±8.3 → ±6.5 | 100% → 97% | 3.01 → 2.51 | 2.50 → 2.00 |
| Istrancalar | 5.18 | 4.49 | 3.42 | ±12.3 → ±10.3 | 96% → 100% | 5.50 → 4.65 | 2.59 → 2.97 |
| Elmalı | 16.95 | 15.05 | 13.01 | ±33.1 → ±19.1 | 100% → 83% | 10.88 → 8.63 | 6.17 → 4.31 |

## What it shows

- **Darlık gains the most, and the gain comes from training-period scenes.**
  Eleven Darlık training scenes (mostly April–July) have NDWI areas far below
  the U-Net's, the late-spring dropouts seen in Phase 1. With them, the
  NDWI curve bends; without them, it is a straight line. On the held-out scenes
  the two masks give almost the same areas (median difference 0.03 km²).
  NDWI with those eleven scenes removed reaches a held-out MAE of 5.1 (bar
  ±14.5), about the same as the U-Net's 5.1 (±13.6). So the U-Net's value here
  is that it handles these scenes on its own, without labels or a hand-made
  filter, not that it measures normal scenes better.
- **One run is not enough to rank the methods closely.** The first U-Net run
  (237 patches) and this one (236, one label removed) differ by more than the
  label change explains: Terkos's held-out error went from 22.9 to 15.0,
  Ömerli's from 4.1 to 4.7, Elmalı's from 13.7 to 13.0. The five-seed runs
  below measure that spread.
- Ömerli, Alibey, Istrancalar and Elmalı also improve on held-out error;
  Elmalı stays out because it is too small.
- **The U-Net is slightly worse on some reservoirs**: held-out error on
  Sazlıdere, Pabuçdere and Kazandere, and İSKİ error on Darlık, Sazlıdere and
  Istrancalar, by under one point in each case.
- **Narrower bars are not always better.** The U-Net's bars are narrower on
  nine of ten reservoirs (Alibey's is slightly wider), but on Büyükçekmece
  (78%), Elmalı (83%), Terkos (86%) and Sazlıdere (87%) they cover fewer
  held-out scenes than the nominal 90%.
- **Terkos and Büyükçekmece stay above the stop line.** Their gap is likely the
  extrapolation into the 2023 record low plus reservoir geometry (Büyükçekmece's
  shallow lagoon) and reed beds (Terkos), which a better mask does not address.
- **MNDWI alone is mixed**: better than NDWI on five reservoirs' held-out error
  and worse on five, much worse on Ömerli (9.6 vs 5.3) and Alibey (6.8 vs 3.2).
  A likely reason is the 20 m SWIR band blurring narrow arms; this was not
  tested.
- The İSKİ column has very few pairs per reservoir; differences of one or two
  points there are noise.

## Run-to-run spread

`scripts/unet_seeds.py` trains the same U-Net five more times (seeds 0–4: the
seed sets the validation scenes, batch order and starting weights; GPU
training adds its own noise), measures the same scenes as the single run and
scores each run the same way. Mean, standard deviation and range of the
held-out MAE over the five runs, next to NDWI:

| Reservoir | NDWI | U-Net mean ± sd | U-Net range | U-Net beats NDWI |
| --- | ---: | ---: | ---: | --- |
| **Ömerli** | 5.33 | 3.88 ± 0.47 | 3.29–4.50 | every run |
| **Darlık** | 11.71 | 5.28 ± 0.33 | 4.87–5.67 | every run |
| **Terkos** | 22.98 | 16.39 ± 2.92 | 14.40–21.51 | every run |
| **Büyükçekmece** | 11.50 | 11.10 ± 0.06 | 11.03–11.19 | every run, by under 0.5 |
| Alibey | 3.16 | 2.97 ± 0.35 | 2.45–3.39 | 4 of 5 |
| Sazlıdere | 1.14 | 1.96 ± 0.10 | 1.86–2.08 | never |
| Kazandere | 5.61 | 6.16 ± 0.25 | 5.90–6.53 | never |
| Pabuçdere | 1.34 | 1.37 ± 0.22 | 1.13–1.61 | 3 of 5 |
| Istrancalar | 5.18 | 3.58 ± 0.27 | 3.34–3.96 | every run |
| Elmalı | 16.95 | 13.78 ± 1.29 | 12.51–15.60 | every run |

- The Darlık and Ömerli gains hold in every run; Terkos moves the most
  (14.4 to 21.5), so the single run's 15.0 was near its best case.
- Sazlıdere and Kazandere are worse than NDWI in every run, by 0.3 to 0.9
  points.
- The 90% bar is narrower than NDWI's in every run on all ten reservoirs, but
  it still covers fewer held-out scenes than nominal on Büyükçekmece (78% in
  every run), Terkos (83% on average), Sazlıdere (86%) and Elmalı (86%).
- Against İSKİ the spread is large where there are few pairs: Kazandere
  3.3–12.2 and Istrancalar 1.2–11.4 points over the five runs, so those
  columns say little.

Per-run numbers: [seeds.csv](seeds.csv). The page's U-Net column shows the
five-run mean.

## Kill rule with U-Net masks

The four-largest stop line (held-out MAE above 10 points) is still met for
**Terkos (15.0) and Büyükçekmece (11.2)**; Darlık (5.1) and Ömerli (4.7) pass.
The same holds in each of the five seed runs (Terkos at least 14.4,
Büyükçekmece at least 11.0).
The rule was set for the project, not per mask, so the outcome in
[../README.md](../README.md) stands.

## Reproduce

```bash
uv sync --extra unet                     # PyTorch with CUDA
uv run python scripts/download_extra.py
uv run python scripts/unet_patches.py
uv run python scripts/train_unet.py      # needs labels/review.csv
uv run python scripts/eval_unet.py
uv run python scripts/areas_methods.py
uv run python scripts/fit.py --areas results/unet/areas_unet.csv --out results/unet/unet
uv run python scripts/fit.py --areas results/unet/areas_mndwi.csv --out results/unet/mndwi
uv run python scripts/iski_check.py --results results/unet/unet
uv run python scripts/iski_check.py --results results/unet/mndwi
uv run python scripts/compare_methods.py
uv run python scripts/unet_seeds.py      # five more runs -> seeds.csv
```

GPU training is not bit-for-bit deterministic, so a retrained model can differ
by a few points per reservoir (see above). Patch arrays, sheets and model weights stay in `data/unet/`.

Contains modified Copernicus Sentinel data 2017–2026. Occupancy: İBB Açık Veri
Portalı, İBB Open Data License; after 2024-02-19, İSKİ (iski.istanbul).
