# Open Questions and Decisions

These can't be settled by fixing code. Part A needs facts about the data, from documentation or
from the data's publishers. Part B needs a decision about the analysis. Each item says where it
shows up in the pipeline and what the code does now, so a decision is easy to put in place.

Facts from the real files were checked in October 2026 (CDPH file updated 2026-10-05).

## A. Research the data

### A1. How does CDPH number its weeks?
The data dictionary only says "Week reported". The file has week 53 in years with no MMWR week
53: 2010, 2012, 2013, 2017, 2018 and 2019 (38 rows, 91 cases; 52 of those cases are in 2017).
Possible explanations: (a) week 53 is a year-end bucket for late or undated reports; (b) CDPH
numbers weeks from January 1 or uses ISO weeks, which would put *every* case up to a week off
its weather. ISO weeks don't fit, though: ISO week-53 years are 2009, 2015, 2020 and 2026, not the
years above.
- *Now:* weeks are read as MMWR weeks. Impossible weeks go to
  `data/processed/wnv_unmatched_rows.csv`.
- *To find out:* ask the CDPH Vector-Borne Disease Section (listed as the dataset contact on the
  CHHS portal), or compare a few counties' weekly counts against the weekly arbovirus bulletins on
  westnile.ca.gov, which state their week dates.

### A2. What are the large week-52 counts?
The share of a year's cases reported in week 52 or 53 is 18% in 2020, 24% in 2022 and 17% in
2023 (2–9% in most other years). These look like year-end catch-up reporting of cases from earlier
in the season.
In 2020, which has a real MMWR week 53, week 53 alone has 39 cases (17% of the year); 2022
week 52 has 50 (24%). Weeks 46–49 also carry a long tail (115 cases in 2015).
- *To find out:* compare to CDPH's annual reports, which give cases by onset month; ask CDPH
  whether week 52 is used to close out the year.
- *Matters for:* B2.

### A2b. Weekly counts look batched
Statewide weekly counts jump around in a way that looks like batch reporting rather than
transmission, e.g. 2020 weeks 37–41: 2, 12, 32, 3, 21; and 2009 week 33 has 0 cases statewide
in the middle of the season. If reports arrive in batches, single-week values carry little
signal. *Matters for:* B4 (weekly vs monthly).

### A2c. One duplicated row
Santa Clara, 2021 week 52 appears twice with 1 case each. The pipeline sums them (2 cases). Is
it two cases or a repeated row? Only CDPH can say; it changes the total by one case.

### A3. What do early-season rows mean?
Some years have cases in weeks well before the season (2013 week 9, 2007 week 16, 2017 week
17). Are these late reports of the previous season's cases, travel cases, or real early cases?
- *To find out:* CDPH annual summaries or the bulletins for those weeks.

### A4. Do the totals match CDPH's published counts?
The file's annual totals (e.g. 801 in 2014, 782 in 2015, 252 so far in 2026) should match CDPH's
year-end summaries of human disease cases. If they don't, find out whether the file leaves
something out (e.g. cases with an unknown county, or the asymptomatic blood donors that are
already known to be excluded).

### A5. Is there an onset-date version of the case data?
Week reported trails onset by about 5 weeks on average ([a 2024 PLOS NTD study of 11 California counties](https://pmc.ncbi.nlm.nih.gov/articles/PMC11226093/), using CDPH data),
and the delay varies. Onset-week counts, even only by year or by month, would remove most of the
lag guesswork in B3. Possible sources: a data request to CDPH, or the county-level counts CDC
publishes from ArboNET (by year only).

### A6. When are recent weeks complete?
CDPH keeps adding late reports to recent weeks. How many weeks back from the latest update should
be treated as incomplete? Compare two downloads a few weeks apart (`data/raw/download_log.csv`
now records when each file was pulled; keep a dated copy of the CDPH file to compare).

### A7. Mosquito and bird surveillance (optional new source)
VectorSurv (vectorsurv.org) holds California mosquito pool infection rates and dead-bird
positives by county and week. These are the strongest short-term predictors in most WNV models.
Find out whether access needs a data request and what the terms of use are.

## B. Decide

### B1. Where does the analysis period end?
- *Now:* START_YEAR week 1 through the latest week in the CDPH file (2026 week 39), so weeks
  after CDPH's last report aren't filled with false zeros.
- *Decide:* whether to also drop the last few weeks as incomplete (see A6), and whether to analyze
  the current, unfinished season at all.

### B2. What to do with year-end catch-up cases (week 52/53)?
Options: leave them (they will pair summer infections with December weather); drop them and say
so; spread each county's week-52 excess over that season's weeks in proportion to its other
cases; or model at a coarser time unit (B4) where the problem mostly disappears.
- *Now:* week 52 (and week 53 in 2020, a real 53-week year) is kept as is; impossible week-53
  rows are set aside.

### B3. Which lags?
- *Now:* weather, humidity, VPD and drought lagged 1, 2, 3, 4, 6 and 8 weeks.
- Infection → onset takes 2–14 days, onset → report about 5 weeks, and weather acts on mosquito
  and virus amplification for weeks before infection. Effects may reach 12–16 weeks back, and
  drought effects longer.
- *Options:* extend `LAGS` in `src/build_dataset.py`; add rolling means (e.g. mean temperature
  over the 4 weeks ending k weeks earlier) or degree-days above the ~14 °C threshold for WNV
  replication; or fit a distributed lag model (e.g. `dlnm`-style) instead of picking lags.

### B4. Weekly or monthly?
That study used monthly counts "to remove inconsistent lags in reporting". Weekly
keeps more detail, but much of that detail is reporting noise. The pipeline can aggregate the
weekly table to months if wanted.

### B5. Which weeks of the year and which counties?
- *Now:* every week of the year and all 58 counties. Eight counties have never had a reported
  case (Alpine, Del Norte, Lassen, Mariposa, Plumas, San Benito, Sierra, Trinity).
- 95.7% of county-weeks have 0 cases. Small counties produce extreme weekly incidence (Glenn,
  pop. ~28,000: 4 cases in a week = 14.4 per 100,000; Alpine has ~1,100 people).
- *Options:* restrict to the transmission season (e.g. MMWR weeks 18–48), so winter zeros don't
  dominate (but note the weeks 46–52 reporting tail, A2); restrict to high-burden counties (the 2024 study used 11); or keep everything and
  use a zero-inflated model.

### B6. How to average weather over a county
NOAA and gridMET values are area averages: large counties like San Bernardino, Kern and Riverside
blend mountain, desert and valley. People, and most cases, are in the populated valleys.
- *Options:* keep area averages (simple, standard); population-weighted averages from the gridded
  data (better match to exposure, more work); or use only cells below an elevation cutoff.
- *Also:* gridMET is averaged over cells whose centers fall in the county, unweighted. Weighting
  by area overlap mainly matters for small coastal counties (San Francisco, Santa Cruz, Marin).

### B7. Population
- 2010–2019 comes from Vintage 2020 (based on the 2010 census), 2020 on from Vintage 2025 (based
  on the 2020 census), so there is a step at 2019→2020. Most counties change under 1%, but
  Trinity jumps +30.5% (12,337 → 16,099), Sierra +9.0%, Mono −8.5%, Alpine +6.0% and Inyo,
  Lake, Lassen and Mendocino +5–6%. Options: accept it; or sum the 2010–2020 intercensal
  age/sex/race file to county totals (the code doesn't do this yet), which spreads the census
  correction over the decade.
- Population changes once a year. Options: keep yearly steps, or interpolate between July 1
  estimates.

### B8. Partial weeks and missing days
- *Now:* `n_days` counts days with weather. A week with no precipitation values gets a blank
  total, but a week missing some days sums only the days present.
- *Decide:* drop or blank weeks with `n_days < 7`, or scale the precipitation total up to 7 days.
  This only happens at the ends of the series and where NOAA's preliminary month isn't complete.
  In the current build that is one week: 2026 week 39 has 3 of 7 days (NOAA data through Sep 29).

### B9. Preliminary data
NOAA's latest months are "prelim" and gridMET's latest weeks are provisional; both get revised.
Decide whether to use them for the current season or stop at the last finalized month. The
download log and the `_prelim` cache files show which months are preliminary.

### B10. Drought map timing
- *Now:* each MMWR week gets the Drought Monitor map dated on that week's Tuesday (conditions as
  of Tuesday morning).
- Using the previous week's map instead would ensure the drought value comes before the week's
  cases. With the lags included, the difference is small.

### B11. Model
The README plans a negative binomial model with a log(population) offset. Alternatives used for
California WNV: zero-inflated negative binomial, and negative binomial GEE with an AR(1)
correlation within county (the 2024 study above). Decide after B4 and B5, since the share of
zeros depends on them.
