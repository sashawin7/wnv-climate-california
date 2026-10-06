# Pipeline Review Checklist

Known and suspected sources of error in retrieving and processing the data. Each item names the
file and function involved and what to check.

In October 2026 the code was run against the real downloads. Every item is now marked with what
was found: **fixed** (a code error, corrected), **checked** (not a problem on the real data),
**open** (needs research or a decision, see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)), or
**unchanged** (still worth knowing, nothing to fix).

## Found on the real data

- [x] **County names never matched (fixed).** `build_dataset.county_key`
  NOAA names counties `"CA: Kern County"`. The `"CA: "` prefix wasn't removed, so no weather row
  matched any WNV, drought or population row: every county-week would have had 0 cases. The
  prefix is now removed, and `main` warns about any name in any source that isn't one of the 58
  counties in `config.CA_COUNTIES`.

- [x] **Weather source stopped in February 2026 (fixed).** `download_weather`
  The EpiNOAA parquet copies stopped updating after 2026-02, which would have dropped every 2026
  case. The script now reads NOAA's own county files (`access/averages/`), which run to the
  present. Values are identical to EpiNOAA where both exist (checked for July 2020).

- [x] **gridMET requests always failed (fixed).** `download_gridmet.fetch_year`
  PyGridMET treats any blank cell as a failed download. California's bounding box always contains
  blank ocean cells, so every request failed, whatever its size. It also saved every download to
  a `cache/` folder in the project root. The script now requests the gridMET server directly
  (~35 s a year), and PyGridMET is no longer needed.

## Most likely real problems

- [x] **False zeros after the last WNV report (fixed).** `build_dataset.build`
  The output now ends at the latest real week in the CDPH file (`latest_wnv_week`), and starts at
  2006 week 1. How many recent weeks to treat as incomplete is **open** (B1, A6).

- [ ] **CDPH weeks may not be MMWR weeks (open, A1, A2).** Week 53 appears in 2010, 2012, 2013 and
  2017–2019, none of which has an MMWR week 53. The data dictionary only says "Week reported".

- [x] **Rows silently dropped if `fips` has blanks (fixed).** `build_dataset.weekly_weather`
  `fips` is no longer a grouping key; it's filled from `config.CA_COUNTIES`. Every county-week is
  checked to appear once (`build` raises otherwise).

- [x] **gridMET cells could be matched to the wrong counties (checked; guarded).** The server
  returns (day, lat, lon); `county_means` now transposes to (time, lat, lon) before reshaping
  anyway.

- [x] **Missing days undercount precipitation (partly fixed).** A week with no precipitation values
  now gets a blank total instead of 0. A week missing only some days still sums what's there:
  **open** (B8). The real NOAA files had no blank days except the ones NOAA hasn't processed yet.

## Retrieval: all sources

- [x] **No retries (fixed).** `src/fetch.py` retries connection errors and 429/5xx responses with
  backoff, for every download.
- [x] **Wrong content could be saved (fixed).** `download_wnv` checks the header before saving;
  `download_drought` checks its columns; NOAA files are parsed before caching.
- [x] **No record of download dates (fixed).** Every download is logged to
  `data/raw/download_log.csv`.
- [x] **Column guesses are unverified (checked).** Checked against the first rows of each real
  file. Tests in `tests/test_real_formats.py` use the real layouts.

## Retrieval and processing by source

### WNV cases (`download_wnv.py`, `build_dataset.load_wnv`)

- [x] The case column (fixed): `load_wnv` now raises if there isn't exactly one. Real file:
  `Reported Positive Cases`.
- [x] Renaming (checked): real header is `Year, Week, County, Reported Positive Cases`. A `Week
  Reported` header is also accepted now.
- [x] Non-county entries (checked): all 50 county names in the file are real counties. Anything
  else would be reported and set aside in the unmatched file.
- [ ] MMWR year vs calendar year (open, A1, A3).

### NOAA weather (`download_weather.py`)

- [x] **Missing months reported as "not available yet" (fixed).** Only a 403/404 counts as "not
  published"; other errors stop the run. A month missing for any reason now leaves its weeks in
  the output with blank weather, rather than dropping the rows and their cases.
- [x] **California filter (fixed).** Rewritten for the real files: California is NCEI state code
  `04`, and FIPS is built as `06` + county code.
- [x] **County column (fixed):** fixed position in the real files, no guessing.
- [x] **Units (checked):** °C and mm (Kern, July 2020: mean daily max 35.7 °C).
- [x] **`tavg` (checked):** present in the real files.

### gridMET (`download_gridmet.py`)

- [x] **Request size (fixed).** The failures were blank ocean cells, not size. A full year over
  California is one ~40 MB request per variable and works.
- [ ] **Unweighted cell averages (open, B6).**
- [x] **Fallback for empty counties (checked).** All 58 counties get values; none blank in 2021.
- [x] **Version requirements (checked).** Works with geopandas 1.2.

### Drought Monitor (`download_drought.py`, `build_dataset.weekly_drought`)

- [x] **Form detection (fixed).** Now decided row by row: a categorical row adds up to 100, and a
  cumulative row only does when D1–D4 are 0, where both readings agree. The real API returns
  cumulative values (Kern, 2021-07-27: D0–D3 = 100, D4 = 89.41). Still worth comparing one
  county-week against the Drought Monitor website.
- [x] **Empty responses (fixed).** The API returns an empty 200 when no maps match; the year is
  now skipped.
- [x] **Large requests (checked).** A full year of all California counties works.
- [ ] **Timing choice (open, B10).**

### Census population (`download_population.py`, `build_dataset.population_by_year`)

- [ ] **Jump in 2020 (open, B7).**
- [ ] **Population changes in steps (open, B7).**
- [x] **Years after 2025 reuse 2025 (unchanged).** Flagged in `pop_carried_forward`.
- [x] **Encoding (checked).** All 58 counties read correctly.

## Processing logic and code

- [x] **Joins use county names (fixed).** Names from every source are checked against the 58
  counties, and `report_coverage` lists any county with no data at all from a source.
- [x] **Weather defines which rows exist (fixed).** Rows are now every county × every MMWR week in
  the period. A week missing from a source has blanks.
- [x] **Blank lags at the start (fixed).** Downloads start in 2005, and lags are computed before
  the output is cut to 2006 onward.
- [x] **Duplicate rows would multiply (fixed).** `build` raises if a county-week appears twice.
- [x] **Python version (fixed).** README says Python 3.10+.

## Interpretation

These aren't code errors, but they limit what the data can show. See OPEN_QUESTIONS.md for the
related decisions.

- [ ] **Week reported, not onset.** (A5, B3)
- [ ] **County of residence.** Cases are assigned to where the patient lives, not where they were
  bitten.
- [ ] **Recent weeks are incomplete.** (A6, B1)
- [ ] **Small counts.** (B5)
- [ ] **County averages smooth over local conditions.** (B6)

## Tests

- [x] **Only made-up data (improved).** `tests/test_real_formats.py` uses rows copied from the
  real files' formats.
- [x] **Untested code (improved).** The NOAA parser, county names, CDPH header, drought forms,
  empty drought responses and period trimming are now tested. The network calls themselves are
  not.
- [ ] **Real-data checks.** Run after each full download: 58 counties in every source; each
  county-week appears once (enforced by `build`); statewide annual totals match CDPH's published
  totals (A4); weekly temperature and drought plausible for a few known county-weeks.
