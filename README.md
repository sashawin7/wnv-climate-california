# West Nile Virus and Weather in California

County-week analysis of human West Nile virus (WNV) cases and weather in California, 2006–present.
The pipeline builds one dataset with a row per county per MMWR week: WNV case count, weekly
weather averages, and lagged weather.

## Project layout

```
wnv-climate-california/
├── src/
│   ├── config.py            paths, URLs, settings
│   ├── download_wnv.py      CDPH weekly WNV cases → data/raw/
│   ├── download_weather.py  NOAA daily county weather → data/raw/
│   └── build_dataset.py     weekly join → data/processed/
├── tests/                   pytest checks for the join logic
├── notebooks/               exploration and modeling
├── data/raw/                downloaded inputs (not committed)
├── data/processed/          analysis-ready outputs (not committed)
└── outputs/figures/         plots
```

Data files are not committed to git. Anyone can recreate them by running the pipeline.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

In VS Code, pick the `.venv` interpreter (Command Palette → *Python: Select Interpreter*).

## Run the pipeline

From the project root:

```bash
python -m src.download_wnv        # ~1 MB, seconds
python -m src.download_weather    # ~250 monthly files, a few minutes the first time
python -m src.build_dataset
pytest                            # optional: check the join logic
```

Output: `data/processed/ca_wnv_weather_weekly.csv`

| Column | Meaning |
|---|---|
| `county`, `fips`, `mmwr_year`, `mmwr_week`, `week_start` | County and MMWR week (Sunday–Saturday) |
| `n_days` | Days of weather in the week (less than 7 at the ends of the range) |
| `tmax`, `tmin`, `tavg` | Weekly mean of daily max, min, and average temperature (°C) |
| `prcp_total` | Weekly total precipitation (mm) |
| `wnv_cases` | Human WNV disease cases (0 if the county-week isn't in the CDPH file) |
| `<var>_lag<k>` | The weather variable *k* weeks earlier (k = 1, 2, 3, 4, 6, 8) |

## Data sources

| Data | Source | Coverage |
|---|---|---|
| WNV human cases | [CDPH via CHHS Open Data](https://data.chhs.ca.gov/dataset/west-nile-virus-cases-2006-present) | County of residence, week reported, 2006–present |
| Temperature and precipitation | [NOAA nClimGrid-Daily](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily) ([EpiNOAA county files](https://arc.ncics.org/nclimgrid-overview/)) | Daily county averages, 1951–present |

## Caveats

- **Week reported, not onset.** CDPH counts cases by the week they were reported, which lags
  infection by weeks. Test lagged weather rather than same-week weather only.
- **County of residence.** Cases are assigned to where the patient lives, not where they were bitten.
- **Week 52/53 spikes.** The CDPH file has week 53 rows in years with no MMWR week 53
  (e.g. 2010, 2013, 2017–2019) and large week 52 counts, which look like year-end catch-up
  reporting. Rows that don't match a real week are saved to
  `data/processed/wnv_unmatched_rows.csv` for review instead of being dropped silently.
- **Disease cases only.** Asymptomatic positive blood donors aren't included.

## Next steps

- [ ] Add county population (Census estimates) to compute incidence per 100,000
- [ ] Add humidity and vapor pressure deficit from gridMET
- [ ] Add weekly county drought from the US Drought Monitor
- [ ] Exploratory plots and a negative binomial model with a log(population) offset
