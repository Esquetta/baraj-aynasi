# Model card: Baraj Aynası

A one-page summary for reviewers. The details are in [README.md](README.md) and the
write-ups under [results/](results/README.md).

## Task

Estimate how full each of Istanbul's ten supply reservoirs is, as a percentage of
capacity, from satellite imagery alone. Each estimate comes with a 90% error bar. These
are satellite estimates, not official figures; İSKİ publishes the official ones.

## Method

```text
Sentinel-2 L2A ─► NDWI water mask ─┐
                                   ├─► water area inside the reservoir outline
Sentinel-1 RTC ─► VV dark-water mask ┘        │
                                              ▼
                   robust, increasing curve per reservoir: area → occupancy (± 90% bar)
```

- **Training and testing:** the curves are fitted on İBB's daily figures up to
  2022-06-30 and tested on July 2022 to February 2024, which includes the 2023 record
  low.
- **Error bars:** sized from leave-one-year-out misses.
- **After February 2024:** the curves are frozen and scored daily against İSKİ.
- **Radar:** a separate series with its own curves and bars, never blended with the
  optical one.

## Results for the five offered reservoirs

Average miss in occupancy points.

- **Held-out:** the 2022–2024 test, against İBB.
- **Vs İSKİ:** 2024–2026 with frozen curves, as of 2026-11-19, so it moves daily. The
  number of dates follows each value.
- **Best guess:** the best of three guesses that use no imagery, on the NDWI test dates.

| Reservoir | NDWI held-out | NDWI vs İSKİ | NDWI bar | Radar held-out | Radar vs İSKİ | Radar bar | Best guess |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ömerli | 5.3 | 4.0 (8) | ±11.6 | 6.4 | 4.5 (23) | ±12.4 | 7.8 |
| Alibey | 3.2 | 3.7 (7) | ±10.0 | 6.5 | 4.1 (39) | ±17.9 | 19.6 |
| Sazlıdere | 1.1 | 1.6 (6) | ±3.3 | 4.3 | 3.7 (39) | ±9.5 | 20.5 |
| Pabuçdere | 1.3 | 2.2 (7) | ±6.6 | 6.8 | 6.3 (40) | ±14.6 | 38.0 |
| Istrancalar | 5.2 | 2.6 (5) | ±12.3 | 6.1 | 5.2 (40) | ±13.6 | 25.7 |

- **Optical against İSKİ:** the comparison rests on few dates, because a clear scene has
  to fall within a day of a published figure.
- **Radar:** less precise, but it measures through cloud every five or six days.
- **Guesses:** every series beats all three no-imagery guesses on all ten reservoirs in
  the held-out years ([results/baselines/](results/baselines/README.md)).

## What it does not do

- **No city total.** Five of the ten reservoirs are estimated.
- **Terkos, Büyükçekmece and Darlık failed the held-out test.** Their held-out errors
  are 23.0, 11.5 and 11.7. The project's stop line is 10 points on the four largest
  reservoirs.
- **Elmalı is too small:** it has under 1 km² of water.
- **Kazandere was withdrawn** after it read about 20 points above İSKİ in summer 2026.
- **No forecasting.** It only measures what the latest scene shows.
- **Old optical estimates.** In cloudy months the latest optical estimate can be weeks
  old; the page shows its age.

## How it was judged

- **Rules first:** the main tests were written down and committed before scoring. These
  are the stop rule, the radar rule, the no-imagery guesses and the per-orbit radar
  test that is due on 2026-12-22.
- **Changes after looking:** some choices came after seeing results, and the write-ups
  say so. Examples are the robust curve fit, offering five reservoirs after the stop
  rule was met, the one-pair-per-scene rule against İSKİ and the "fading gap" guess.
- **Labels:** the U-Net's training labels were made by AI agents and spot-checked by
  the author. The U-Net is an alternative mask and isn't used for the published
  estimates.

## Reproduce

- **Tests:** `uv sync` then `uv run pytest`. They need no data and run on every push to main and every pull request.
- **Metric tables:** these rebuild from the committed area files, for example
  `uv run python scripts/fit.py --areas results/areas.csv --out <folder>`. That needs
  İBB's daily file in `data/ibb/`, from the İBB Open Data Portal (see
  [docs/data-sources.md](docs/data-sources.md)).
- **Imagery:** rebuilding from imagery means downloading about 40 GB. The README lists
  the steps.

## Data and licences

Occupancy data comes from the İBB Open Data Portal (İBB Open Data License) up to
2024-02-19, and from İSKİ for comparison after that. The imagery contains modified
Copernicus Sentinel data 2017–2026, accessed through the Microsoft Planetary Computer.
The Sentinel-1 RTC data was processed by Catalyst and is used under CC BY 4.0. The code
is MIT.
