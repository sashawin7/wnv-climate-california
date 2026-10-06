"""Download weekly US Drought Monitor statistics for every California county.

The Drought Monitor publishes a map every Tuesday. For each county it reports the
percent of land area in each category: None, D0 (abnormally dry), D1 (moderate),
D2 (severe), D3 (extreme), D4 (exceptional). Weekly maps start in January 2000.

Each year is cached in data/raw/usdm/, so a rerun only fetches missing years (the
current year is always refetched). Output: data/raw/usdm_ca_county_weekly.csv
with the API's columns: MapDate, FIPS, County, State, None, D0-D4, ValidStart, ValidEnd.

Run from the project root:
    python -m src.download_drought                     # DOWNLOAD_START_YEAR to this year
    python -m src.download_drought --start 2010 --end 2012
"""

import argparse
import io
from datetime import date

import pandas as pd

from src.config import DOWNLOAD_START_YEAR, RAW, USDM_URL
from src.fetch import get, log_download

CACHE = RAW / "usdm"
OUT = RAW / "usdm_ca_county_weekly.csv"
EXPECTED = ["MapDate", "FIPS", "County", "None", "D0", "D1", "D2", "D3", "D4"]


def fetch_year(year: int) -> pd.DataFrame | None:
    """One year of weekly maps for every California county, or None if there are none yet."""
    params = {
        "aoi": "CA",  # a state abbreviation returns every county in the state
        "startdate": f"1/1/{year}",
        "enddate": f"12/31/{year}",
        "statisticsType": 1,  # "traditional": cumulative percents (D1 = D1 or worse)
    }
    r = get(USDM_URL, params=params, headers={"Accept": "text/csv"})
    log_download("usdm", r.url)
    if not r.text.strip():  # the API answers an empty 200 when no maps match
        return None
    df = pd.read_csv(io.StringIO(r.text), dtype={"FIPS": str, "MapDate": str})
    if missing := [c for c in EXPECTED if c not in df.columns]:
        raise SystemExit(f"Drought Monitor response for {year} lacks {missing}: {r.text[:200]!r}")
    return df


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=DOWNLOAD_START_YEAR)
    p.add_argument("--end", type=int, default=date.today().year)
    args = p.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    this_year = date.today().year
    for year in range(args.start, args.end + 1):
        path = CACHE / f"{year}.csv"
        if path.exists() and year < this_year:
            continue
        df = fetch_year(year)
        if df is None:
            print(f"{year}: no maps yet, skipping")
            continue
        df.to_csv(path, index=False)
        print(f"{year}: {df['MapDate'].nunique()} weekly maps, {df['FIPS'].nunique()} counties")

    files = sorted(f for f in CACHE.glob("*.csv") if args.start <= int(f.stem) <= args.end)
    if not files:
        raise SystemExit("No drought data downloaded.")
    usdm = pd.concat(
        [pd.read_csv(f, dtype={"FIPS": str, "MapDate": str}) for f in files], ignore_index=True
    )
    usdm = usdm.drop_duplicates(["FIPS", "MapDate"]).sort_values(["FIPS", "MapDate"])
    usdm.to_csv(OUT, index=False)
    print(f"\nWrote {OUT.name}: {len(usdm):,} rows, {usdm['FIPS'].nunique()} counties")


if __name__ == "__main__":
    main()
