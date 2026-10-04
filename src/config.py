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
