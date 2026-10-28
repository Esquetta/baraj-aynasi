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
  reviewers were AI agents reading the images, not people, and no person has
  spot-checked them yet.** Picks: NDWI 268, near-infrared split 18, union 11,
  rejected 3 ([`../../labels/review.csv`](../../labels/review.csv)). The
  near-infrared candidate was added after the first sheet showed a late-spring
  Ömerli patch where every index mask missed most of the water.
- **Training**: U-Net with 4 levels and 16 base channels (1.9 M parameters) on
  237 training-period patches (206 train, 31 validation by scene). Loss is binary
  cross-entropy plus Dice, skipping cloud and no-data pixels; flips and 90°
  rotations; AdamW; the epoch with the lowest validation loss (182 of 200) is
  kept. About 1.5 minutes on an RTX 4070 Ti. One run; the model was not
  changed after testing.

## Pixel test (60 held-out patches)

| Method | IoU | F1 |
| --- | ---: | ---: |
| NDWI > 0 | 0.991 | 0.995 |
| U-Net | 0.981 | 0.990 |
| MNDWI > 0 | 0.900 | 0.945 |

58 of the 60 test labels are the NDWI candidate itself, so this test mostly
checks that the U-Net reproduces NDWI where NDWI is right; it does, slightly
less exactly. On the two other test patches the U-Net output stays close to
NDWI's (IoU 0.68 and 0.81 against the label), so there is **no pixel-level
evidence yet that it fixes NDWI failures**.

## Occupancy error by water mask

Mean absolute error in occupancy points. Held-out: 2022-07-01 to 2024-02-19.
LOYO: each labelled year 2017–2024 held out in turn. İSKİ: the 2024–2026
comparison (not used for training, but already looked at in Phase 1; 2 to 8
pairs per reservoir). Each method is scored on its own scenes after the
outlier filter, so scene counts differ slightly; see [comparison.csv](comparison.csv).

| Reservoir | Held-out NDWI | MNDWI | U-Net | 90% bar NDWI → U-Net | Bar coverage NDWI → U-Net | LOYO NDWI → U-Net | İSKİ NDWI → U-Net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Ömerli** | 5.33 | 9.56 | 4.13 | ±11.7 → ±10.6 | 98% → 96% | 6.92 → 4.40 | 4.77 → 4.73 |
| **Darlık** | 11.71 | 9.14 | 5.46 | ±24.3 → ±12.3 | 83% → 95% | 9.06 → 5.61 | 3.99 → 4.58 |
| **Terkos** | 22.98 | 24.57 | 22.87 | ±28.8 → ±26.2 | 82% → 64% | 13.01 → 12.05 | 20.04 → 14.49 |
| **Büyükçekmece** | 11.50 | 10.59 | 11.12 | ±21.7 → ±18.0 | 85% → 78% | 14.86 → 13.28 | 6.94 → 4.47 |
| Alibey | 3.16 | 6.76 | 3.48 | ±10.8 → ±8.5 | 100% → 96% | 4.38 → 4.35 | 2.97 → 3.46 |
| Sazlıdere | 1.14 | 2.45 | 1.96 | ±4.6 → ±4.3 | 100% → 85% | 1.68 → 1.78 | 1.63 → 1.85 |
| Kazandere | 5.61 | 5.57 | 5.82 | ±21.2 → ±18.3 | 100% → 100% | 11.46 → 9.72 | 12.00 → 4.17 |
| Pabuçdere | 1.34 | 1.53 | 1.26 | ±8.3 → ±6.0 | 100% → 97% | 3.01 → 2.26 | 2.50 → 2.00 |
| Istrancalar | 5.18 | 4.49 | 3.96 | ±12.3 → ±11.3 | 96% → 100% | 5.50 → 4.27 | 2.59 → 3.10 |
| Elmalı | 16.95 | 15.05 | 13.69 | ±33.1 → ±20.9 | 100% → 93% | 10.88 → 9.10 | 6.17 → 4.72 |

## What it shows

- **Darlık gains the most, and the gain comes from training-period scenes.**
  Eleven Darlık training scenes (mostly April–July) have NDWI areas far below
  the U-Net's, the late-spring dropouts seen in Phase 1. With them, the
  NDWI curve bends; without them, it is a straight line. On the held-out scenes
  the two masks give almost the same areas (median difference 0.03 km²).
  NDWI with those eleven scenes removed reaches a held-out MAE of 5.1 (bar
  ±14.5), close to the U-Net's 5.5 (±12.3). So the U-Net's value here is that
  it handles these scenes on its own, without labels or a hand-made filter, not
  that it measures normal scenes better.
- Elmalı and Ömerli also improve on held-out error; Elmalı stays out because it
  is too small.
- **The U-Net is slightly worse on some reservoirs**: held-out error on Alibey,
  Sazlıdere and Kazandere, and İSKİ error on Darlık, Alibey, Sazlıdere and
  Istrancalar, by under one point in each case.
- **Narrower bars are not always better.** The U-Net's bars are narrower on all
  ten reservoirs, but on Terkos (64%), Büyükçekmece (78%) and Sazlıdere (85%)
  they cover fewer held-out scenes than the nominal 90%.
- **Terkos and Büyükçekmece barely change.** Their gap is likely the
  extrapolation into the 2023 record low plus reservoir geometry (Büyükçekmece's
  shallow lagoon) and reed beds (Terkos), which a better mask does not address.
- **MNDWI alone is mixed**: better than NDWI on five reservoirs' held-out error
  and worse on five, much worse on Ömerli (9.6 vs 5.3) and Alibey (6.8 vs 3.2).
  A likely reason is the 20 m SWIR band blurring narrow arms; this was not
  tested.
- The İSKİ column has very few pairs per reservoir; differences of one or two
  points there are noise.

## Kill rule with U-Net masks

The four-largest stop line (held-out MAE above 10 points) is still met for
**Terkos (22.9) and Büyükçekmece (11.1)**; Darlık (5.5) and Ömerli (4.1) pass.
The rule was set for the project, not per mask, so the outcome in
[../README.md](../README.md) stands.

## Reproduce

```bash
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
```

GPU training is not bit-for-bit deterministic, so a retrained model can differ
slightly. Patch arrays, sheets and model weights stay in `data/unet/`.

Contains modified Copernicus Sentinel data 2017–2026. Occupancy: İBB Açık Veri
Portalı, İBB Open Data License; after 2024-02-19, İSKİ (iski.istanbul).
