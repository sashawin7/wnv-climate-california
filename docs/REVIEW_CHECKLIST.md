# Pipeline Review Checklist

Known and suspected sources of error in retrieving and processing the data. Each item names the
file and function involved and what to check.

As of this writing, the pipeline has only run on made-up test data. The code's assumptions about
column names, units and formats were written from documentation, not checked against the real
files, so the "Retrieval" items are untested.

Mark each item checked, and note what you found (confirmed bug, fixed, not a problem).

## Most likely real problems

- [ ] **False zeros after the last WNV report.** `build_dataset.build`
  Weather sets the rows, and county-weeks missing from the WNV file get 0 cases. Weather runs to
  the present, but CDPH's file lags (it was last updated August 2026), so every week after CDPH's
  latest report becomes 0 instead of "not reported yet". The same happens to pre-2006 weeks if
  weather is downloaded with `--start` before 2006.
  *Check:* the latest WNV week vs the latest output week. *Likely fix:* keep only weeks between
  the WNV file's first and last week.

- [ ] **CDPH weeks may not be MMWR weeks.** `build_dataset.load_wnv`, `build`
  The CDPH file has week-53 rows in years with no MMWR week 53 (e.g. 2010, 2013, 2017–2019),
  which suggests CDPH numbers weeks differently (e.g. from January 1, or ISO weeks). If so, cases
  could sit up to a week off from their weather, and the year-end rows set aside as "unmatched"
  are really a numbering mismatch.
  *Check:* CDPH's data dictionary for how it defines a week, and which years have week 53 rows.

- [ ] **Rows silently dropped if `fips` has blanks.** `build_dataset.weekly_weather`
  If the weather data has a `fips` column, it's used as a `groupby` key. Pandas drops rows with a
  blank group key by default (`dropna=True`). If one county appears with two FIPS formats (int vs
  zero-padded string), it splits into two rows per week, and the lag merge then duplicates rows.
  *Check:* blank or mixed-format FIPS in the raw weather file; that each county-week appears
  exactly once in the output.

- [ ] **gridMET cells could be matched to the wrong counties.** `download_gridmet.county_means`
  Each variable is flattened with `.reshape(len(times), -1)`, which lines up with the cell-to-county
  list from `cell_county_index` only if the array's dimensions are ordered (time, lat, lon). If
  PyGridMET or the clipping step returns (time, lon, lat), cells go to the wrong counties with no
  error.
  *Check:* `ds[v].dims` on a real download. *Likely fix:* `ds[v].transpose("time", "lat", "lon")`
  before reshaping.

- [ ] **Missing days undercount precipitation.** `build_dataset.weekly_weather`
  A blank daily `prcp` counts as 0 in the weekly sum, while temperature means skip blanks. Partial
  weeks at the ends of the series have the same problem. `n_days` records days present, but
  nothing excludes or adjusts weeks with fewer than 7.
  *Check:* blank `prcp` values and how many weeks have `n_days < 7`.

## Retrieval: all sources

- [ ] **No retries.** None of the download scripts retry, so a brief network failure stops the run
  or leaves a gap.
- [ ] **Wrong content could be saved.** A site returning an error page with a success status would
  be saved as data. `download_wnv` never checks what it got.
- [ ] **No record of download dates.** CDPH revises past weeks, NOAA finalizes preliminary months,
  and gridMET's recent months are provisional. Nothing records when each file was pulled, so
  reruns can quietly produce different data.
- [ ] **Column guesses are unverified.** Every assumption about real column names should be
  checked against the first rows of each real raw file.

## Retrieval and processing by source

### WNV cases (`download_wnv.py`, `build_dataset.load_wnv`)

- [ ] The case column is the first whose name contains "case". With more than one such column, it
  could pick the wrong one.
- [ ] Renaming expects columns named exactly `year`, `week` and `county` (case-insensitive).
  Another header, like "Week Reported", causes a crash.
- [ ] Entries that aren't real counties (e.g. "Unknown") go to the unmatched file and drop out.
- [ ] Unclear whether `year` is the MMWR year or the calendar year. Early-January reports could
  land in the wrong year.

### NOAA weather (`download_weather.py`)

- [ ] **Missing months reported as "not available yet".** `fetch_month` treats any non-200 response
  (including 403 or 500) that way and skips it, leaving lasting gaps. Those weeks then disappear
  from the output, because weather defines the rows, and their WNV cases go to the unmatched file
  with a message that blames week mismatches.
- [ ] **California filter rests on guesses.** `keep_california` guesses the state or FIPS column
  from a list of names; the generic `code` could match the wrong column. A FIPS code stored as a
  decimal like "6001.0" won't pad to "06001", so California would match nothing.
- [ ] **County column could be the wrong one.** `standardize`'s candidate list includes the generic
  `name`. If no county column is found, it crashes.
- [ ] **Units unchecked.** The code assumes °C and mm. °F or inches would be off with no error.
- [ ] **`tavg` may not exist** in the source, which would crash the build.

### gridMET (`download_gridmet.py`)

- [ ] **Request size.** A full year of four variables over California may exceed what the gridMET
  server returns in one request; nothing splits it into smaller requests.
- [ ] **Unweighted cell averages.** Each cell counts fully toward the county containing its center,
  with no weighting by overlap. Small or coastal counties rest on few cells, and ocean cells are
  blank.
- [ ] **Fallback for empty counties.** A county with no cell center gets the cell nearest its
  interior point. Untested on real shapes.
- [ ] **Version requirements.** `union_all()` needs geopandas 1.0+, and the `index_right` column
  name from `sjoin` depends on the geopandas version.

### Drought Monitor (`download_drought.py`, `build_dataset.weekly_drought`)

- [ ] **Form detection is all-or-nothing.** It decides cumulative vs per-category by checking
  whether every row adds up to 100 (within 0.5). A few rows with larger rounding errors would get
  the whole dataset treated as cumulative and converted wrongly.
  *Check:* a county and week known to be in drought (e.g. Kern, summer 2021) against the Drought
  Monitor website.
- [ ] **Empty responses crash.** A year with no maps yet (e.g. early January) returns nothing, and
  `pd.read_csv` raises an error.
- [ ] **No splitting of large requests.** A whole year per request may hit size limits or time out.
- [ ] **Timing choice.** Each map describes conditions as of Tuesday morning and is assigned to the
  MMWR week containing that Tuesday. Reasonable, but worth confirming.

### Census population (`download_population.py`, `build_dataset.population_by_year`)

- [ ] **Jump in 2020.** 2000–2009 are intercensal, 2010–2019 come from the Vintage 2020 release
  (not revised to the 2020 census), and 2020 onward comes from Vintage 2025. Incidence will show an
  artificial step between 2019 and 2020.
- [ ] **Population changes in steps.** A July 1 estimate applies to every week of its year, so
  population jumps at each new year. Interpolation would be smoother.
- [ ] **Years after 2025 reuse 2025.** Flagged in `pop_carried_forward`.
- [ ] **Encoding.** Files are read as latin-1. UTF-8 files would garble accented names, though no
  California county has one.

## Processing logic and code

- [ ] **Joins use county names, not FIPS.** All sources are joined by name after removing "County",
  trimming spaces and title-casing (`county_key`). A spelling difference drops that county's data.
  `build_dataset.main` prints a note only when more than 1% of county-weeks lack a source, so a
  single missing county falls below that threshold.
- [ ] **Weather defines which rows exist.** A week missing from the weather data is missing from the
  whole output, even if other sources have it.
- [ ] **Blank lags at the start.** Weather starts in 2006, the same year as WNV, so the first 8
  weeks of 2006 have blank lags. Downloading weather from 2005 would fill them.
- [ ] **Duplicate rows would multiply.** Two weather rows for one county-week would be multiplied by
  the date-based lag merge in `add_lags`.
- [ ] **Python version.** The code uses Python 3.10+ syntax; the README doesn't say so.

## Interpretation

These aren't code errors, but they limit what the data can show.

- [ ] **Week reported, not onset.** Cases are dated when reported, weeks after infection, and the
  delay varies over the season and between years.
- [ ] **County of residence.** Cases are assigned to where the patient lives, not where they were
  bitten.
- [ ] **Recent weeks are incomplete.** Late reports add cases to recent weeks, so they read low until
  CDPH catches up.
- [ ] **Small counts.** Many county-weeks have zero or very few cases, so incidence in small counties
  swings widely.
- [ ] **County averages smooth over local conditions.** Weather averaged over large counties like Kern
  or San Bernardino blends mountain and desert climates.

## Tests

- [ ] **Only made-up data.** All tests use synthetic data shaped by the same assumptions as the code,
  so they can't catch a wrong assumption about a real file.
- [ ] **Untested code.** No test covers `keep_california`, `standardize`, or the download functions.
- [ ] **No real-data checks.** Suggested checks after a real run: 58 counties in every source; each
  county-week appears exactly once; statewide annual case totals match CDPH's published totals;
  weekly temperature and drought values are plausible for a few known county-weeks.
