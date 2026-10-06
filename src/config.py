"""Shared paths and settings for the pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

START_YEAR = 2006  # first year of the CDPH weekly WNV series
# Weather, gridMET and drought downloads start a year earlier, so the lagged
# columns for the first weeks of START_YEAR aren't blank.
DOWNLOAD_START_YEAR = START_YEAR - 1

# California Department of Public Health, via the CHHS Open Data Portal.
# Human WNV disease cases by county of residence and week reported, 2006-present.
WNV_URL = (
    "https://data.chhs.ca.gov/dataset/3205b420-3f62-4a02-8d2e-9a9ed34c49f4/"
    "resource/6ef33c1b-9f54-49f2-a92e-51a1b78f0a06/download/wnv_human_cases.csv"
)
WNV_COLUMNS = ["Year", "Week", "County", "Reported Positive Cases"]

# NOAA nClimGrid-Daily area averages (public AWS bucket), one headerless CSV per
# variable and month: {NCLIMGRID_BASE}/YYYY/{var}-YYYYMM-cty-{scaled|prelim}.csv
# (The EpiNOAA parquet copies in the same bucket stopped updating in February 2026.)
NCLIMGRID_BASE = "https://noaa-nclimgrid-daily-pds.s3.amazonaws.com/access/averages"
NCLIMGRID_CA_CODE = "04"  # these files number states by NCEI code, not FIPS
NCLIMGRID_MISSING = -999.99
CA_FIPS = "06"
WEATHER_VARS = ["tmax", "tmin", "tavg", "prcp"]

# The 58 California counties and their FIPS codes. Every source's county names are
# checked against this list.
CA_COUNTIES = {
    "Alameda": "06001", "Alpine": "06003", "Amador": "06005", "Butte": "06007",
    "Calaveras": "06009", "Colusa": "06011", "Contra Costa": "06013", "Del Norte": "06015",
    "El Dorado": "06017", "Fresno": "06019", "Glenn": "06021", "Humboldt": "06023",
    "Imperial": "06025", "Inyo": "06027", "Kern": "06029", "Kings": "06031", "Lake": "06033",
    "Lassen": "06035", "Los Angeles": "06037", "Madera": "06039", "Marin": "06041",
    "Mariposa": "06043", "Mendocino": "06045", "Merced": "06047", "Modoc": "06049",
    "Mono": "06051", "Monterey": "06053", "Napa": "06055", "Nevada": "06057",
    "Orange": "06059", "Placer": "06061", "Plumas": "06063", "Riverside": "06065",
    "Sacramento": "06067", "San Benito": "06069", "San Bernardino": "06071",
    "San Diego": "06073", "San Francisco": "06075", "San Joaquin": "06077",
    "San Luis Obispo": "06079", "San Mateo": "06081", "Santa Barbara": "06083",
    "Santa Clara": "06085", "Santa Cruz": "06087", "Shasta": "06089", "Sierra": "06091",
    "Siskiyou": "06093", "Solano": "06095", "Sonoma": "06097", "Stanislaus": "06099",
    "Sutter": "06101", "Tehama": "06103", "Trinity": "06105", "Tulare": "06107",
    "Tuolumne": "06109", "Ventura": "06111", "Yolo": "06113", "Yuba": "06115",
}

# Every download is recorded here (UTC time, file, URL), since sources revise past data.
DOWNLOAD_LOG = RAW / "download_log.csv"

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

# gridMET (Climatology Lab, University of California Merced), from its THREDDS
# NetCDF Subset Service: {GRIDMET_NCSS}/agg_met_{var}_1979_CurrentYear_CONUS.nc
#   rmax, rmin: daily max/min relative humidity (%)
#   sph: specific humidity (kg/kg)
#   vpd: mean vapor pressure deficit (kPa)
GRIDMET_NCSS = "http://thredds.northwestknowledge.net:8080/thredds/ncss"
GRIDMET_VARS = ["rmax", "rmin", "sph", "vpd"]
GRIDMET_NAMES = {  # variable names inside the files
    "rmax": "daily_maximum_relative_humidity",
    "rmin": "daily_minimum_relative_humidity",
    "sph": "daily_mean_specific_humidity",
    "vpd": "daily_mean_vapor_pressure_deficit",
}

# US Drought Monitor county statistics: percent of county area in each category.
USDM_URL = (
    "https://usdmdataservices.unl.edu/api/CountyStatistics/"
    "GetDroughtSeverityStatisticsByAreaPercent"
)
