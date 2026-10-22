# Open Questions, Issues and Limitations

Everything known to be uncertain, undecided or limited about the dataset, with ideas for what to
do about each. Code errors that have been fixed are in [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md),
not here. The walkthrough notebook
[notebooks/01_data_pipeline_explained.ipynb](../notebooks/01_data_pipeline_explained.ipynb) shows
most of these issues in the real data.

Facts about the data were checked in October 2026 (CDPH file updated 2026-10-05).

**How to read an item**

- **Type**
  - **Question**: needs facts from documentation or from the data's publishers.
  - **Decision**: an analysis choice the team has to make.
  - **Limitation**: built into the data. It can be reduced or acknowledged, not fully fixed.
- **Priority** is a suggestion, based on how much the item could change results.
  - **High**: could change the main findings.
  - **Medium**: affects some results or some counties.
  - **Low**: minor, or easy to handle.
- **Now** is what the pipeline currently does, so a decision can be put into code easily.
- **Ways forward** lists concrete next steps, roughly cheapest first.

The codes A1–B11 are kept from earlier versions (A = question, B = decision) because
REVIEW_CHECKLIST.md and the notebook refer to them. Limitations are numbered L1–L8.

## At a glance

| ID | Item | Type | Priority | Status | First step |
|---|---|---|---|---|---|
| **Case data** | | | | | |
| A1 | CDPH weeks may not be MMWR weeks | Question | High | Open | Compare against CDPH bulletins; ask CDPH |
| A2 | Large year-end (week 52/53) counts | Question | High | Open | Compare against onset-month counts in CDPH annual reports |
| B2 | What to do with year-end catch-up cases | Decision | High | Kept as is | Depends on A2; try a sensitivity analysis |
| A2b | Weekly counts look batched | Question | Medium | Open | Compare weekly vs monthly noise |
| A2c | One duplicated row | Question | Low | Summed | Ask CDPH along with A1 |
| A3 | Cases reported well before the season | Question | Low | Kept | Check bulletins for those weeks |
| A4 | Do yearly totals match CDPH's published counts? | Question | Medium | Unchecked | Table of yearly totals vs annual reports |
| A6 | How long until recent weeks are complete? | Question | Medium | Open | Keep dated copies of the CDPH file |
| B1 | Where the analysis period ends | Decision | Medium | Partly handled | Decide after A6 |
| L1 | Cases are by county of residence, not exposure | Limitation | Medium | Accepted | Sensitivity analysis without commuter counties |
| L2 | Only reported disease cases: a small, uneven share of infections | Limitation | Medium | Accepted | Use neuroinvasive cases if available |
| **Timing and lags** | | | | | |
| A5 | Is there an onset-date version of the cases? | Question | High | Open | Data request to CDPH |
| B3 | Which lags of weather and drought to use | Decision | High | 1–8 weeks | Extend lags; try a distributed lag model |
| B4 | Weekly or monthly analysis | Decision | High | Weekly | Build a monthly table and compare |
| B10 | Which week's drought map goes with which week | Decision | Low | Same week | Use the previous week's map |
| **Weather, humidity and drought** | | | | | |
| B6 | Area-averaged weather vs where people live | Decision | Medium | Area average | Population-weighted averages |
| L3 | gridMET county averages use only cells centered in the county | Limitation | Low | Accepted | Weight cells by overlap with the county |
| B8 | Partial weeks at the end of the series | Decision | Low | Sums the days present | Blank weeks with `n_days < 7` |
| B9 | Preliminary weather data | Decision | Low | Used | Flag or drop preliminary weeks |
| L4 | Temperature and humidity come from different gridded products | Limitation | Low | Accepted | Compare with gridMET temperature |
| L5 | The Drought Monitor is a judged, stepwise product | Limitation | Low | Accepted | Add a measured index (SPI/SPEI) |
| **Population** | | | | | |
| B7 | Jump at 2019→2020; yearly steps | Decision | Medium | Accepted | Build totals from the intercensal file |
| L6 | 2026 reuses the 2025 population | Limitation | Low | Flagged | Update when Vintage 2026 is out |
| **Scope, model and missing variables** | | | | | |
| B5 | Which weeks of the year and which counties | Decision | High | All of them | Try a season-only, high-burden version |
| B11 | Which statistical model | Decision | High | Not started | Decide after B4 and B5 |
| A7 | Mosquito and bird surveillance (VectorSurv) | Question | Medium | Not added | Ask about access and terms |
| L7 | Important drivers aren't in the data | Limitation | Medium | Accepted | Year and county effects; add what's available |
| L8 | County-level associations, not individual risk | Limitation | Medium | Accepted | Word conclusions as county-level |

---

## 1. Case data (the outcome)

### A1 · Does CDPH number its weeks the way we assume?
`Question` · Priority **High** · **Open**

**In short:** The CDPH file has week 53 in years that have no MMWR week 53. That suggests its weeks
aren't plain MMWR weeks, which could put cases up to a week out of line with the weather.

**Details:**
- The data dictionary only says "Week reported".
- Week 53 appears in 2010, 2012, 2013, 2017, 2018 and 2019, none of which has an MMWR week 53.
  That is 38 rows and 91 cases, 52 of them in 2017.
- Possible explanations:
  - (a) Week 53 is a year-end bucket for late or undated reports, and everything else is MMWR.
  - (b) CDPH counts weeks from January 1, which would shift *every* case by up to six days.
  - (c) CDPH uses ISO weeks. This doesn't fit: ISO 53-week years are 2009, 2015, 2020 and 2026,
    not the years above.

**Now:** Weeks are read as MMWR weeks. The 38 impossible rows are saved to
`data/processed/wnv_unmatched_rows.csv` and are not in the dataset.

**Why it matters:** Under (a), only 91 cases are affected. Under (b), every case is misaligned by up
to a week, which blurs the short lags.

**Ways forward:**
- [ ] Pick 3–4 county-weeks with cases and check them against CDPH's weekly arbovirus bulletins
  on westnile.ca.gov, which state the dates each report covers.
- [ ] Email the CDPH Vector-Borne Disease Section (the dataset contact on the CHHS portal). Ask
  about week numbering, week 53, the week-52 spikes (A2) and the duplicate row (A2c) in one
  message.
- [ ] If (b) is confirmed, change `bd.add_mmwr` / `load_wnv` to map CDPH weeks to dates using
  CDPH's rule.

### A2 · What are the large year-end counts?
`Question` · Priority **High** · **Open**

**In short:** In some years a fifth to a quarter of all cases are reported in week 52 or 53. These
are almost certainly earlier cases being caught up at year end, not December infections.

**Details:**
- The share of a year's cases reported in week 52 or 53 is 18% in 2020, 24% in 2022 and 17% in
  2023. In most other years it is 2–9%.
- 2020 has a real week 53, which alone holds 39 cases (17% of the year).
- In 2022, week 52 holds 50 cases (24%).
- Weeks 46–49 also carry a long tail of cases (115 in 2015).

**Why it matters:** These cases get paired with December weather, which pulls any
temperature–case association toward zero.

**Ways forward:**
- [ ] Compare against CDPH annual reports, which give cases by month of onset. If December onsets
  are rare, the week-52 cases are catch-up reports.
- [ ] Ask CDPH whether week 52 is used to close out the year (same email as A1).
- [ ] Then decide B2.

### B2 · What to do with year-end catch-up cases
`Decision` · Priority **High** · **Kept as is for now**

**In short:** Keep, drop, redistribute or aggregate away the week-52/53 excess.

**Now:** Week 52, and week 53 in 2020 (a real 53-week year), are kept as reported. Impossible
week-53 rows are set aside (A1).

**Options:**
| Option | Pro | Con |
|---|---|---|
| Keep as reported | Honest to the source | Summer infections paired with winter weather |
| Drop weeks 52–53 | Simple | Loses up to 24% of a year's cases; undercounts those years |
| Redistribute each county's week-52 excess over that season, in proportion to its other weeks | Keeps totals and roughly right timing | An assumption; adds made-up timing |
| Analyze monthly or by season (B4) | Problem mostly disappears | Loses weekly detail |
| Restrict to transmission season (B5) | Removes the issue with winter weeks | Same loss as dropping |

**Ways forward:**
- [ ] Wait for A2's answer.
- [ ] Run the main model with "keep" and with "drop" as a sensitivity check. If results barely
  change, the choice doesn't matter much.

### A2b · Weekly counts look batched
`Question` · Priority **Medium** · **Open**

**In short:** Statewide weekly counts jump around in a way that looks like reports arriving in
batches, not like transmission changing.

**Details:**
- 2020 weeks 37–41 have 2, 12, 32, 3 and 21 cases statewide.
- 2009 week 33 has 0 cases statewide, in the middle of the season.

**Why it matters:** If reports come in batches, a single week's count carries little signal.
Week-to-week models will mostly fit noise.

**Ways forward:**
- [ ] Compute the autocorrelation of statewide weekly counts within a season. Strong week-to-week
  zig-zags suggest batching.
- [ ] Compare model fit at weekly, 2-week and monthly resolution (B4).
- [ ] Ask CDPH whether some counties report in batches.

### A2c · One duplicated row
`Question` · Priority **Low** · **Summed**

**In short:** Santa Clara, 2021 week 52 appears twice, with 1 case each. Is that 2 cases, or 1
case listed twice?

**Now:** The pipeline sums the rows (2 cases).

**Ways forward:**
- [ ] Ask CDPH (same email as A1). At most it changes the total by one case.

### A3 · Cases reported well before the season
`Question` · Priority **Low** · **Kept**

**In short:** A few cases are reported in late winter or spring, long before transmission
normally starts.

**Details:** There are 3 such rows: 2013 week 9 (Sacramento), 2007 week 16 (Kern) and 2017 week
17 (Kings).

**Possible explanations:** late reports of the previous season, infections acquired while
travelling, or real early cases.

**Ways forward:**
- [ ] Check CDPH bulletins or annual summaries for those weeks.
- [ ] If they are travel or late cases, drop them or move them. With only 3 cases, this is low
  priority.

### A4 · Do yearly totals match CDPH's published counts?
`Question` · Priority **Medium** · **Not yet checked**

**In short:** The file's yearly totals should match CDPH's official year-end counts of human
disease cases. If they don't, the file is missing something.

**Details:**
- The file's totals include 801 in 2014, 782 in 2015 and 252 so far in 2026.
- Possible gaps: cases with an unknown county, or late revisions.
- Asymptomatic blood-donor infections are already known to be excluded.

**Ways forward:**
- [ ] Make a table of file totals vs CDPH annual report totals for 2006–2025, and note any
  differences.
- [ ] Also compare against the CDC ArboNET county counts by year (a second, independent source).

### A6 · How long until recent weeks are complete?
`Question` · Priority **Medium** · **Open**

**In short:** CDPH keeps adding late reports to recent weeks, so the last few weeks undercount.
How many weeks back is the data reliable?

**Details:** The report delay averages about 5 weeks (see A5), so the last 4–8 weeks are probably
incomplete.

**Ways forward:**
- [ ] Keep a dated copy of each CDPH download. Changing `download_wnv.py` to also save
  `wnv_human_cases_YYYY-MM-DD.csv` would do this automatically.
- [ ] After a few downloads, compare the same weeks across copies to see how much they grow and
  for how long.
- [ ] Use the result to set B1.

### B1 · Where the analysis period ends
`Decision` · Priority **Medium** · **Partly handled**

**In short:** The dataset ends at CDPH's latest week. The last few weeks are probably incomplete,
and the current season is unfinished.

**Now:** It runs from 2006 week 1 through the latest week in the CDPH file (2026 week 39). Weeks
after that aren't filled with false zeros.

**Options:**
- Drop the last *k* weeks, with *k* taken from A6.
- Stop at the last complete season (end of 2025) for the main analysis, and use 2026 only to test
  predictions.

**Ways forward:**
- [ ] Decide after A6. Stopping at 2025 for model fitting is a safe default.

### L1 · Cases are by county of residence, not of exposure
`Limitation` · Priority **Medium** · **Accepted**

**In short:** Each case is counted where the patient lives, but the infecting bite may have
happened in another county (work, commute, travel).

**Why it matters:** It adds noise, mostly in metro areas where many people commute across county
lines (Bay Area, Los Angeles–Orange–Riverside–San Bernardino, Sacramento region). The
misassignment is probably small in Central Valley counties.

**Ways forward:**
- [ ] Note it as a limitation.
- [ ] Sensitivity analysis: refit without small counties that sit inside a large commuting region,
  or group metro counties into regions.

### L2 · Only reported disease cases: a small and uneven share of infections
`Limitation` · Priority **Medium** · **Accepted**

**In short:** About 80% of WNV infections cause no symptoms, and most mild cases are never tested.
The data only see infections that were diagnosed and reported.

**Details:**
- Neuroinvasive disease (under 1% of infections) is nearly always detected.
- Milder febrile cases are reported much less consistently.
- Testing and reporting practices can differ by county and over time. 2020 is a possible example,
  if COVID-19 changed testing; that is a hypothesis to check.

**Why it matters:** Counts reflect transmission *and* how hard people looked. Changes in testing
can look like changes in risk.

**Ways forward:**
- [ ] Ask CDPH whether a neuroinvasive-only series exists. It is more consistently detected and is
  often the preferred outcome in WNV studies.
- [ ] Include year effects in the model to absorb statewide changes in reporting.

---

## 2. Timing and lags

### A5 · Is there an onset-date version of the case data?
`Question` · Priority **High** · **Open**

**In short:** Cases are dated by the week they were *reported*, about 5 weeks after symptoms
started, with a delay that varies. Counts by date of onset would remove most of this uncertainty.

**Details:** The 5-week figure comes from
[a 2024 PLOS NTD study of 11 California counties](https://pmc.ncbi.nlm.nih.gov/articles/PMC11226093/)
that used CDPH data. The delay also varies, which blurs the timing beyond what lags can fix.

**Ways forward:**
- [ ] Data request to CDPH for counts by onset week, or even onset month, by county.
- [ ] CDC ArboNET publishes county counts by year only. That is useful for A4 but not for timing.
- [ ] If neither is available, describe the delay distribution in the write-up and use lags of
  4–8+ weeks (B3).

### B3 · Which lags of weather and drought to use
`Decision` · Priority **High** · **Lags of 1, 2, 3, 4, 6 and 8 weeks**

**In short:** Weather affects mosquitoes and virus build-up weeks before a bite, and the bite comes
weeks before a report. The useful lags may be longer than 8 weeks.

**Details:** The delays add up along the chain:
- weather acts on mosquito breeding and virus amplification for several weeks before a bite;
- infection to symptom onset takes 2–14 days;
- onset to report takes about 5 weeks.

So the relevant weather may be 6–16 weeks before the report week. Drought may act over even longer
periods, through its effects on birds and water sources.

**Now:** `LAGS = [1, 2, 3, 4, 6, 8]` in `src/build_dataset.py` for temperature, precipitation,
humidity, VPD and DSCI.

**Options:**
- Extend `LAGS` to 12 and 16 weeks. This is a one-line change; drought lags need data back to 2005,
  which is already downloaded.
- Rolling means, e.g. mean temperature over the 4 weeks ending k weeks earlier. These are less
  noisy than single-week lags.
- Degree-days above about 14 °C, roughly the temperature at which the virus replicates in
  mosquitoes. This is more biologically meaningful than mean temperature.
- A distributed lag model (DLNM-style), which estimates the whole lag curve instead of choosing
  lags in advance.

**Ways forward:**
- [ ] Extend lags to 16 weeks and add 4-week rolling means. This is cheap and makes the other
  options possible.
- [ ] Plot the correlation between weekly cases and temperature at each lag (statewide and for a
  few high-burden counties), to see where the signal peaks.

### B4 · Weekly or monthly analysis
`Decision` · Priority **High** · **Weekly**

**In short:** Weekly data keep more detail, but much of that detail is reporting noise (A2, A2b, A5).
Monthly counts are steadier.

**Details:** The 2024 study above used monthly counts "to remove inconsistent lags in reporting".

**Ways forward:**
- [ ] Add a monthly table, built from daily weather and weekly cases (weeks assigned to the month
  of their Wednesday), alongside the weekly one.
- [ ] Fit the same model to both and compare. Weekly results only add value if they are more than
  noise.

### B10 · Which week's drought map goes with which week
`Decision` · Priority **Low** · **Same week's map**

**In short:** Each MMWR week gets the Drought Monitor map dated on its Tuesday. That map reflects
conditions up to that Tuesday, so it doesn't strictly come before all of the week's cases.

**Ways forward:**
- [ ] Optional: use the previous week's map, which is the same as using `usdm_dsci_lag1`. With the
  lag columns already in the dataset, this barely matters.

---

## 3. Weather, humidity and drought (the exposures)

### B6 · Area-averaged weather vs where people live
`Decision` · Priority **Medium** · **Area averages**

**In short:** County values average over the whole county, including mountains and desert where
nobody lives. Most people, and most cases, are in valleys and towns.

**Details:** Large, mixed counties are the worst affected: San Bernardino, Kern, Riverside, Inyo,
Fresno and Tulare. Mean temperature in San Bernardino mixes the Mojave Desert with mountain peaks
above 3,000 m.

**Options:**
- Keep area averages. This is simple and standard.
- **Population-weighted averages:** weight each grid cell by the people living in it, using Census
  block populations or a gridded population product. This is the best match to exposure. It is easy
  for gridMET (the cells are already in hand), but NOAA gives only county averages, so temperature
  would have to come from gridMET or from NOAA's gridded files.
- Use only cells below an elevation cutoff (e.g. 1,000 m). This is simpler and gets most of the
  benefit.

**Ways forward:**
- [ ] For 3–4 large counties, compare area-weighted and population-weighted gridMET temperature.
  If they differ a lot, switch.

### L3 · gridMET county averages use only cells centered in the county
`Limitation` · Priority **Low** · **Accepted**

**In short:** A grid cell counts toward a county only if its center is inside the county, and all
counted cells are weighted equally. Cells along the county edges are left out.

**Details:**
- Cells are 1/24°, about 3.7 × 4.6 km (17 km²) at Bay Area latitudes.
- San Francisco (122.5 km² of land) gets 6 cells. Together they cover about 76% of its land.
  Another 15 cells overlap its edges (Ocean Beach, the Presidio, the waterfront, the islands) but
  are left out.
- Large counties have hundreds to thousands of cells (median 234, San Bernardino 2,939), so there
  it makes no practical difference.
- On a test day, SF's edge cells had humidity values in the same range as its six inside cells.

**Ways forward:**
- [ ] Optional: weight each cell by its overlap with the county (`county_means` in
  `src/download_gridmet.py`). This needs the gridMET download to be rerun. It is worth doing if
  B6's population weighting is done, since both change the same function.

### B8 · Partial weeks at the end of the series
`Decision` · Priority **Low** · **Sums the days present**

**In short:** The last week can have fewer than 7 days of weather, which makes its precipitation
total too low.

**Now:** `n_days` counts the days with weather. A week with no precipitation values gets a blank
total, but a week missing some days sums only the days present. In the current build this affects
one week: 2026 week 39 has 3 of 7 days.

**Ways forward:**
- [ ] Blank `prcp_total` (or the whole row's weather) when `n_days < 7`, or scale it up to 7 days.
  This is a few lines in `bd.weekly_weather`. Moot if B1 drops recent weeks.

### B9 · Preliminary weather data
`Decision` · Priority **Low** · **Used**

**In short:** NOAA's latest month is preliminary and gridMET's latest days are provisional. Both
get revised.

**Now:** Used as-is. Preliminary NOAA months are cached as `YYYYMM_prelim.csv` and refetched on
each run until they become final. The download log shows when each file was pulled.

**Ways forward:**
- [ ] Add an `is_prelim` column to the dataset from the cache file names.
- [ ] Or simply stop fitting at the last complete season (B1). The current season's weather then
  only matters for prediction.

### L4 · Temperature and humidity come from different gridded products
`Limitation` · Priority **Low** · **Accepted**

**In short:** Temperature and precipitation come from NOAA nClimGrid, while humidity and VPD come
from gridMET. Both are interpolated from weather stations, but with different methods.

**Details:**
- VPD depends on temperature, so gridMET's VPD reflects gridMET's temperature, not NOAA's.
- In mountains and remote desert, where stations are sparse, both products are less certain.

**Ways forward:**
- [ ] Download gridMET temperature (`tmmx`, `tmmn`; two more variables in the same download) and
  compare it with NOAA for a few counties.
- [ ] If they agree well, consider taking all weather from gridMET. That would also make B6's
  population weighting possible for temperature.

### L5 · The Drought Monitor is a judged, stepwise product
`Limitation` · Priority **Low** · **Accepted**

**In short:** Drought Monitor categories are set each week by authors, who blend several indicators
with local reports. They are not a measurement.

**Details:**
- Values change in steps and can stay flat for months.
- Category lines are drawn at a regional scale, so a county's percentages may not reflect local
  water conditions.
- How the raw values work:
  - Each raw column is cumulative ("this category or worse"), e.g. D1 = % in D1–D4.
  - The pipeline turns these into exact shares (`usdm_d0`–`usdm_d4`), the share in drought
    (`usdm_d1plus`) and the DSCI (0–500).

**Ways forward:**
- [ ] Optional: add a measured drought index such as SPI or SPEI over 3, 6 or 12 months, from
  gridMET precipitation and evaporation. This is smoother and has a clear definition.

---

## 4. Population (the denominator)

### B7 · Jump at 2019→2020; population changes in yearly steps
`Decision` · Priority **Medium** · **Accepted for now**

**In short:** Population for 2010–2019 and for 2020 onward come from estimate series based on
different censuses, so there is an artificial jump between 2019 and 2020. Population also changes
only once a year.

**Details:**
- 2010–2019 comes from Vintage 2020, based on the 2010 census. 2020 onward comes from Vintage 2025,
  based on the 2020 census.
- Most counties change by less than 1–2% between 2019 and 2020 (median 1.2%).
- Most of the counties with large jumps have few or no cases (Trinity, Sierra, Alpine and Lassen
  have none), so the effect on results is small.

Some small counties jump a lot:

| County | Change 2019→2020 |
|---|---|
| Trinity | +30.5% (12,337 → 16,099) |
| Sierra | +9.0% |
| Mono | −8.5% |
| Alpine | +6.0% |
| Inyo, Lake, Lassen, Mendocino | +5–6% |

**Ways forward:**
- [ ] Accept it and note it. Simplest.
- [ ] Or sum the 2010–2020 intercensal age/sex/race file to county totals. This spreads the census
  correction smoothly over 2010–2019. It needs a new step in `download_population.py`.
- [ ] Interpolate between July 1 estimates to remove the steps each January. This matters little
  for a model with a population offset.

### L6 · 2026 reuses the 2025 population
`Limitation` · Priority **Low** · **Flagged**

**In short:** The newest Census estimate is for 2025, so 2026 rows reuse it
(`pop_carried_forward = True`).

**Ways forward:**
- [ ] Add the Vintage 2026 file to `config.CENSUS_POP_URLS` when Census releases it (usually in
  spring), then rerun `download_population`.

---

## 5. Scope, model and missing variables

### B5 · Which weeks of the year and which counties
`Decision` · Priority **High** · **All weeks, all 58 counties**

**In short:** 95.7% of county-weeks have 0 cases. Most of those zeros are winter weeks or counties
that never have cases, and they could dominate the model.

**Details:**
- Eight counties have never had a reported case: Alpine, Del Norte, Lassen, Mariposa, Plumas,
  San Benito, Sierra and Trinity.
- Small counties produce extreme weekly incidence: Glenn (population about 28,000) has 14.4 per
  100,000 from 4 cases in one week, and Alpine has about 1,100 people.

**Options:**
| Option | Pro | Con |
|---|---|---|
| Keep everything, use a zero-inflated model (B11) | No data dropped | Harder to interpret |
| Transmission season only, e.g. MMWR weeks 18–48 | Removes structural winter zeros | Cuts the weeks 46–52 reporting tail (A2) |
| High-burden counties only (the 2024 study used 11) | Stable rates, clear signal | Results don't apply statewide |
| Drop counties with 0 cases ever | Removes counties that can't inform the model | Small loss |

**Ways forward:**
- [ ] Main analysis: season weeks only, counties with at least one case. Sensitivity analysis:
  all weeks and all counties.

### B11 · Which statistical model
`Decision` · Priority **High** · **Not started**

**In short:** The README plans a negative binomial model with a log(population) offset. The right
model depends on B4 and B5.

**Things to account for:**
- the many zeros (B5);
- counts that vary more than a Poisson model allows;
- correlation from week to week within a county;
- differences between counties and between years (L2, L7).

**Options used for California WNV:**
- negative binomial with county and year effects;
- zero-inflated negative binomial;
- negative binomial GEE with AR(1) correlation within county (the 2024 study);
- distributed lag non-linear models (B3).

**Ways forward:**
- [ ] Settle B4 and B5 first.
- [ ] Start with negative binomial + offset + county and year effects + a few chosen lags. Check
  the residuals for leftover autocorrelation before adding complexity.

### A7 · Mosquito and bird surveillance (possible new source)
`Question` · Priority **Medium** · **Not added**

**In short:** Mosquito infection rates and dead-bird positives are usually the strongest short-term
predictors of human WNV, and they sit between weather and human cases in the causal chain.

**Details:** VectorSurv (vectorsurv.org) holds California mosquito pool tests and dead-bird
results by county and week.

**Why it matters:** Adding them changes the question: from "does weather predict cases?" to "does
weather predict cases beyond what surveillance already shows?"

**Ways forward:**
- [ ] Find out whether access needs a data request and what the terms of use are.
- [ ] Decide whether surveillance is an outcome, a predictor, or a mediator (a step in the chain
  between weather and cases) in the analysis.

### L7 · Important drivers aren't in the data
`Limitation` · Priority **Medium** · **Accepted**

**In short:** Many things besides weather change WNV risk, and none of them are in the dataset.

**Examples:**
- **Mosquito control:** abatement district activity, aerial spraying in outbreak years.
- **Bird immunity:** after big outbreak years, more birds are immune, which can damp the following
  years. WNV reached California in 2003–2004.
- **Mosquito habitat:**
  - irrigation and rice fields;
  - urban drainage;
  - neglected swimming pools, e.g. during the 2007–2008 foreclosure wave in Bakersfield.
- **Human behavior and housing:** time outdoors, air conditioning, window screens.
- **Population immunity and age structure:** older people are more likely to get neuroinvasive
  disease.
- **Changes in testing and reporting** (L2).

**Why it matters:** Weather effects estimated without these can be biased when the missing drivers
vary with weather or over time.

**Ways forward:**
- [ ] Include county effects (stable local differences) and year effects (statewide shocks such as
  bird immunity or reporting changes) in the model.
- [ ] Add available proxies if useful: the previous season's case count (immunity), land cover or
  irrigated area, and median age.
- [ ] Name the rest as limitations in any write-up.

### L8 · County-level associations, not individual risk
`Limitation` · Priority **Medium** · **Accepted**

**In short:** The data link county-level weather to county-level case counts. That shows how weather
relates to *how many* cases a county has, not how weather affects any one person's risk.

**Why it matters:** Associations at the county level can differ from those at the individual level
(the ecological fallacy). This is mainly about how conclusions are worded.

**Ways forward:**
- [ ] Phrase results as county-level relationships, e.g. "weeks that are 1 °C warmer are followed
  by X% more reported cases".
