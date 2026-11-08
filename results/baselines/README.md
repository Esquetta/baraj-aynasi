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
