# Does the satellite beat a guess made without imagery?

Each satellite series is compared with simple guesses that use no imagery at all, on the
same dates. If a guess does as well, the imagery isn't adding much there. The rule below
was committed before any guess was scored.

## Rule, set before scoring

**Guesses.** Each uses only reported figures from before the date it guesses.

1. **Season:** the reservoir's mean İBB occupancy for that day of the year (±7 days), over
   2000 to the cut-off.
2. **Last year:** the reported figure on the same date a year earlier, from İBB, or from
   İSKİ after 2024-02-19, within a day. It isn't scored where no such figure exists.
3. **Unchanged:** the last İBB figure on or before the cut-off, kept for every later date.

The cut-off is 2022-06-30 for the held-out test and 2024-02-19 for the İSKİ test. Those
are the data the curves saw in each test.

**Series.** NDWI (the page's main estimates), radar VV with the fixed threshold (on the
page for five reservoirs), and the U-Net (one run, for reference only).

**Tests.**

- **Held-out:** July 2022 to February 2024, on each series' own clean scene dates,
  against İBB's daily figures, with curves fitted on training years. These are the
  scenes and curves behind the published held-out errors.
- **İSKİ:** 2024–2026, on each series' pairs in its `iski_check.csv` on the day of the
  run. Each guess is made for the İSKİ figure's date.

Every guess is scored on exactly the dates of the series it is compared with.

**What gets claimed.**

- A series beats the guesses on a reservoir and test only if its average miss is lower
  than every guess's on the same dates. The tables here report the average miss and
  number of dates for every reservoir, series, guess and test.
- The page gets one column: for each reservoir, the held-out error of the best guess on
  the NDWI dates. Its text says where a guess wins.
- Which reservoirs are offered doesn't change on this result.

**Not a guess here.** Yesterday's İSKİ figure carried forward would beat every satellite
series, because İSKİ publishes every day. The point of the satellite is to measure
without the official figure, so that comparison says nothing. "Last year" has a year's
head start that the satellite doesn't, so it is a forecast rather than a like-for-like
measurement. It is kept because it is the obvious thing to try.

## Result, as of 2026-11-08

Average miss in occupancy points; lower is better. Files: `heldout.csv` and `iski.csv`
([`scripts/baselines.py`](../../scripts/baselines.py)). The series errors equal the
published held-out errors exactly: the script reads each series' areas as committed when
those errors were published.

### Held-out years, NDWI and radar

| Reservoir | NDWI | Best guess | Radar | Best guess |
| --- | ---: | ---: | ---: | ---: |
| **Ömerli** | 5.3 | 7.8 season | 6.4 | 11.8 season |
| **Sazlıdere** | 1.1 | 20.5 season | 4.3 | 21.5 season |
| **Pabuçdere** | 1.3 | 38.0 season | 6.8 | 41.1 season |
| **Alibey** | 3.2 | 19.6 season | 6.5 | 24.3 season |
| **Istrancalar** | 5.2 | 25.7 season | 6.1 | 28.0 last year |
| Darlık | 11.7 | 12.9 season | 9.8 | 17.0 season |
| Kazandere | 5.6 | 39.6 season | 10.0 | 42.0 season |
| Büyükçekmece | 11.5 | 25.4 season | 10.9 | 28.0 season |
| Elmalı | 17.0 | 24.4 season | 10.9 | 25.9 season |
| Terkos | 23.0 | 25.5 last year | 11.1 | 25.6 last year |

- **Every series misses less on average than every guess, on all ten reservoirs.** This
  holds for the U-Net too. On most reservoirs the gap is wide: the guesses can't follow
  the 2023 drought, and the satellite can.
- **Two margins are narrow.** NDWI on Darlık beats the season guess by 1.2 points, and is
  closer on only 11 of 23 dates. NDWI on Terkos beats last year by 2.5 points over 22
  dates. Treat both as near ties.

### Against İSKİ, 2024–2026

- **Radar beats every guess on all ten reservoirs**, on 17 to 31 dates each.
  Büyükçekmece is a near tie with the season guess (13.2 against 13.8; radar closer on 10
  of 28 dates). New pairs arrive daily, so that one could flip.
- **NDWI and U-Net have too few dates to say:** 2 to 10 each, and 2 to 5 for the
  last-year guess. On those few dates a guess does better on Terkos (season, 18.8 against
  NDWI's 20.0, 2 dates) and Kazandere (last year, 1.8 against NDWI's 4.2 on 3 dates, and
  2.6 against U-Net's 4.0 on 2).

### A stronger guess, added after the rule

An ML reviewer would ask about a smarter guess, so one was scored as an extra check. It
isn't part of the rule's verdict. **Fading gap** takes the season guess plus the last
figure's gap from it, shrinking with a 365-day time constant. On the held-out years, it
beats the committed guesses on several reservoirs but no satellite series, most
narrowly on Ömerli (NDWI 5.3 against 6.7, U-Net 4.7 against 6.6). Against İSKİ it beats
NDWI and U-Net on Terkos (15.4 against 20.0 and 17.6, 2 dates), and nothing else.

The season guess measures ±7 days around each calendar anniversary of the date (29
February counts as 28 February in other years). A first draft counted days of the year
instead. It was fixed before this write-up, and it moved no number by more than 0.11
points.
