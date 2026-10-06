# West Nile Virus and Weather in California

County-week analysis of human West Nile virus (WNV) cases and weather in California, 2006–present.
The pipeline builds one dataset with a row per county per MMWR week: WNV case count, population and
incidence, weekly temperature, precipitation, humidity, vapor pressure deficit and drought, and
lagged versions of the weather and drought columns.

## Project layout

```
wnv-climate-california/
├── src/
│   ├── config.py            paths, URLs, settings
│   ├── download_wnv.py      CDPH weekly WNV cases → data/raw/
│   ├── download_weather.py  NOAA daily county temperature and precipitation → data/raw/
│   ├── download_gridmet.py  gridMET daily humidity and VPD, averaged to counties → data/raw/
│   ├── download_drought.py  US Drought Monitor weekly county statistics → data/raw/
│   ├── download_population.py  Census annual county population → data/raw/
│   └── build_dataset.py     weekly join → data/processed/
├── tests/                   pytest checks on small made-up data
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
python -m src.download_gridmet    # one fetch per year; the slowest step, cached after the first run
python -m src.download_drought    # one request per year, under a minute
python -m src.download_population # three Census files, seconds
python -m src.build_dataset
pytest                            # optional: check the join logic
```

The gridMET, drought and population steps are optional: `build_dataset` skips any that
haven't been downloaded and says so. The download scripts that fetch by year take
`--start` and `--end` (e.g. `--start 2010 --end 2012`) for a quick test run.

Output: `data/processed/ca_wnv_weather_weekly.csv`

| Column | Meaning |
|---|---|
| `county`, `fips`, `mmwr_year`, `mmwr_week`, `week_start` | County and MMWR week (Sunday–Saturday) |
| `n_days` | Days of weather in the week (less than 7 at the ends of the range) |
| `tmax`, `tmin`, `tavg` | Weekly mean of daily max, min, and average temperature (°C) |
| `prcp_total` | Weekly total precipitation (mm) |
| `wnv_cases` | Human WNV disease cases (0 if the county-week isn't in the CDPH file) |
| `rmax`, `rmin` | Weekly mean of daily max and min relative humidity (%) |
| `sph` | Weekly mean specific humidity (kg/kg) |
| `vpd` | Weekly mean vapor pressure deficit (kPa) |
| `usdm_d0` … `usdm_d4` | Percent of county area in exactly that drought category (D0 abnormally dry to D4 exceptional) |
| `usdm_d1plus` | Percent of county area in drought (D1 or worse) |
| `usdm_dsci` | Drought Severity and Coverage Index, 0–500: the sum of percent area at D0-or-worse, D1-or-worse, … D4 |
| `population` | Census July 1 population estimate for the MMWR year |
| `pop_carried_forward` | True when the year is past the latest estimate and the latest one is reused |
| `incidence_per_100k` | `wnv_cases / population × 100,000` |
| `log_pop` | log(population), for an offset in a count model |
| `<var>_lag<k>` | Temperature, precipitation, humidity, VPD or DSCI *k* weeks earlier (k = 1, 2, 3, 4, 6, 8) |

## Data sources

| Data | Source | Coverage |
|---|---|---|
| WNV human cases | [CDPH via CHHS Open Data](https://data.chhs.ca.gov/dataset/west-nile-virus-cases-2006-present) | County of residence, week reported, 2006–present |
| Temperature and precipitation | [NOAA nClimGrid-Daily](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily) ([EpiNOAA county files](https://arc.ncics.org/nclimgrid-overview/)) | Daily county averages, 1951–present |
| Humidity and VPD | [gridMET](https://www.climatologylab.org/gridmet.html), fetched with [PyGridMET](https://docs.hyriver.io/readme/pygridmet.html) and averaged to counties using [Census county boundaries](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html) | Daily ~4 km grid, 1979–present |
| Drought | [US Drought Monitor county statistics](https://droughtmonitor.unl.edu/DmData/DataDownload.aspx) | Weekly (Tuesday maps), 2000–present |
| Population | [Census county population estimates](https://www.census.gov/data/tables/time-series/demo/popest/2020s-counties-total.html) | Annual (July 1): 2000–2009 intercensal, 2010–2019 Vintage 2020, 2020–2025 Vintage 2025 |

## Caveats

- **Week reported, not onset.** CDPH counts cases by the week they were reported, which lags
  infection by weeks. Test lagged weather rather than same-week weather only.
- **County of residence.** Cases are assigned to where the patient lives, not where they were bitten.
- **Week 52/53 spikes.** The CDPH file has week 53 rows in years with no MMWR week 53
  (e.g. 2010, 2013, 2017–2019) and large week 52 counts, which look like year-end catch-up
  reporting. Rows that don't match a real week are saved to
  `data/processed/wnv_unmatched_rows.csv` for review instead of being dropped silently.
- **Disease cases only.** Asymptomatic positive blood donors aren't included.
- **gridMET county averages are computed here.** Each ~4 km grid cell is assigned to the county
  containing its center, and cells are averaged without area weighting. That's close enough at
  this resolution, though small coastal counties rest on fewer cells.
- **Drought maps are point-in-time.** Each MMWR week gets the Drought Monitor map dated on its
  Tuesday, which reflects conditions as of that morning.
- **Population for 2010–2019** comes from the Vintage 2020 estimates rather than the 2010–2020
  intercensal series, because the intercensal county series is only published broken down by
  age, sex and race. Years after the latest estimate reuse it (`pop_carried_forward`).

## Next steps

- [x] Add county population (Census estimates) to compute incidence per 100,000
- [x] Add humidity and vapor pressure deficit from gridMET
- [x] Add weekly county drought from the US Drought Monitor
- [ ] Run the full pipeline against the real downloads and check county coverage
- [ ] Exploratory plots and a negative binomial model with a log(population) offset
