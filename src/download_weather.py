"""Download daily county-level weather for California from NOAA nClimGrid-Daily.

Variables: tmax, tmin, tavg (deg C) and prcp (mm), averaged over each county.

NOAA publishes one CSV per variable and month for every US county, with no header:
region type, region code, region name, year, month, element, then one column per day
(31 columns, -999.99 for days that don't exist or aren't processed yet). Region codes
use NCEI state numbers (California is 04, not FIPS 06).

Each month is filtered to California and cached in data/raw/nclimgrid/, so a rerun
only fetches months it doesn't have yet. Final ("scaled") months are kept;
preliminary ("prelim") recent months are refetched until NOAA finalizes them.
All cached months are then combined into data/raw/nclimgrid_ca_county_daily.csv
with columns date, county, fips, tmax, tmin, tavg, prcp.

Run from the project root:
    python -m src.download_weather                     # DOWNLOAD_START_YEAR to this year
    python -m src.download_weather --start 1990 --end 2025
"""

import argparse
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from src.config import (
    CA_COUNTIES, CA_FIPS, DOWNLOAD_START_YEAR, NCLIMGRID_BASE, NCLIMGRID_CA_CODE,
    NCLIMGRID_MISSING, RAW, WEATHER_VARS,
)
from src.fetch import get, log_download

CACHE = RAW / "nclimgrid"
OUT = RAW / "nclimgrid_ca_county_daily.csv"
ID_COLS = ["region_type", "code", "name", "year", "month", "element"]


def month_url(var: str, year: int, month: int, status: str) -> str:
    return f"{NCLIMGRID_BASE}/{year}/{var}-{year}{month:02d}-cty-{status}.csv"


def parse_month(text: str, var: str) -> pd.DataFrame:
    """One NOAA county file -> long California rows: date, county, fips, <var>."""
    names = ID_COLS + [str(d) for d in range(1, 32)]
    df = pd.read_csv(io.StringIO(text), header=None, names=names, dtype={"code": str})
    df["code"] = df["code"].str.strip().str.zfill(5)
    df = df[df["code"].str.startswith(NCLIMGRID_CA_CODE)]
    long = df.melt(id_vars=ID_COLS, var_name="day", value_name=var)
    long["date"] = pd.to_datetime(
        dict(year=long["year"], month=long["month"], day=long["day"].astype(int)),
        errors="coerce",  # Feb 30 and the like
    )
    long = long.dropna(subset=["date"])
    long[var] = pd.to_numeric(long[var], errors="coerce").mask(
        lambda s: s.round(2) == NCLIMGRID_MISSING
    )
    long["fips"] = CA_FIPS + long["code"].str[-3:]
    long["county"] = (
        long["name"].str.replace(r"^[A-Z]{2}:\s*", "", regex=True)
        .str.replace(r"\s+County$", "", regex=True).str.strip()
    )
    return long[["date", "county", "fips", var]]


def fetch_month(year: int, month: int) -> tuple[pd.DataFrame, str] | None:
    """All four variables for one month, preferring final data. None if not published."""
    for status in ("scaled", "prelim"):
        frames = []
        for var in WEATHER_VARS:
            r = get(month_url(var, year, month, status), ok_missing=True)
            if r is None:
                break
            frames.append(parse_month(r.text, var).set_index(["date", "county", "fips"]))
        else:
            return pd.concat(frames, axis=1).reset_index(), status
    return None


def download_month(ym: tuple[int, int]) -> tuple[str, str | None]:
    """Fetch and cache one month. Returns a message and the URL pattern fetched."""
    y, m = ym
    tag = f"{y}{m:02d}"
    result = fetch_month(y, m)
    if result is None:
        return f"{tag}: not published yet, skipping", None
    df, status = result
    for old in CACHE.glob(f"{tag}_*.csv"):
        old.unlink()
    df.to_csv(CACHE / f"{tag}_{status}.csv", index=False)
    return f"{tag}: {len(df):,} rows ({status})", month_url("{var}", y, m, status)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=DOWNLOAD_START_YEAR)
    p.add_argument("--end", type=int, default=date.today().year)
    args = p.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    today = date.today()
    todo = [
        (y, m)
        for y in range(args.start, args.end + 1)
        for m in range(1, 13)
        if (y, m) <= (today.year, today.month)
        and not (CACHE / f"{y}{m:02d}_scaled.csv").exists()
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for msg, url in pool.map(download_month, todo):
            print(msg)
            if url:
                log_download("nclimgrid", url)

    files = sorted(
        f for f in CACHE.glob("*.csv") if args.start <= int(f.name[:4]) <= args.end
    )
    if not files:
        raise SystemExit("No weather data downloaded.")
    daily = pd.concat(
        [pd.read_csv(f, dtype={"fips": str}, parse_dates=["date"]) for f in files],
        ignore_index=True,
    )
    daily = daily.dropna(subset=WEATHER_VARS, how="all")  # days NOAA hasn't processed yet
    daily = daily.sort_values(["county", "date"])
    daily.to_csv(OUT, index=False)

    print(f"\nWrote {OUT.name}: {len(daily):,} rows, {daily['county'].nunique()} counties, "
          f"{daily['date'].min():%Y-%m-%d} to {daily['date'].max():%Y-%m-%d}")
    unknown = set(daily["county"]) - set(CA_COUNTIES)
    missing = set(CA_COUNTIES) - set(daily["county"])
    if unknown or missing:
        print(f"Warning: county names don't match the 58 counties. "
              f"Unknown: {sorted(unknown)}; missing: {sorted(missing)}")
    blanks = daily[WEATHER_VARS].isna().sum()
    if blanks.any():
        print(f"Note: blank daily values: {blanks[blanks > 0].to_dict()}")


if __name__ == "__main__":
    main()
