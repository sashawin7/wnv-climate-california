"""Shared paths and settings for the pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

START_YEAR = 2006  # first year of the CDPH weekly WNV series

# California Department of Public Health, via the CHHS Open Data Portal.
# Human WNV disease cases by county of residence and week reported, 2006-present.
WNV_URL = (
    "https://data.chhs.ca.gov/dataset/3205b420-3f62-4a02-8d2e-9a9ed34c49f4/"
    "resource/6ef33c1b-9f54-49f2-a92e-51a1b78f0a06/download/wnv_human_cases.csv"
)

# NOAA nClimGrid-Daily, EpiNOAA analysis-ready county averages (public AWS bucket).
# Files: {NCLIMGRID_BASE}/YEAR=YYYY/STATUS={scaled|prelim}/YYYYMM.parquet
NCLIMGRID_BASE = (
    "https://noaa-nclimgrid-daily-pds.s3.amazonaws.com/EpiNOAA/v1-0-0/parquet/cty"
)
CA_FIPS = "06"
WEATHER_VARS = ["tmax", "tmin", "tavg", "prcp"]

# US Census Bureau county population estimates (July 1 of each year), one file per
# decade. Where files overlap, the newer vintage wins.
#   2000-2010: intercensal estimates
#   2010-2019: Vintage 2020 postcensal estimates (the 2010-2020 intercensal series is
#              only published broken down by age/sex/race, not as county totals)
#   2020-2025: Vintage 2025 postcensal estimates
CENSUS_POP_URLS = [
    "https://www2.census.gov/programs-surveys/popest/datasets/2000-2010/intercensal/county/co-est00int-tot.csv",
    "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/counties/totals/co-est2020-alldata.csv",
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv",
]

# Census cartographic boundary file, used to average gridMET grid cells to counties.
COUNTY_SHAPES_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"

# gridMET (Climatology Lab, University of California Merced), fetched with PyGridMET.
#   rmax, rmin: daily max/min relative humidity (%)
#   sph: specific humidity (kg/kg)
#   vpd: mean vapor pressure deficit (kPa)
GRIDMET_VARS = ["rmax", "rmin", "sph", "vpd"]

# US Drought Monitor county statistics: percent of county area in each category.
USDM_URL = (
    "https://usdmdataservices.unl.edu/api/CountyStatistics/"
    "GetDroughtSeverityStatisticsByAreaPercent"
)
