"""Download daily county-level weather for California from NOAA nClimGrid-Daily.

Variables: tmax, tmin, tavg (deg C) and prcp (mm), averaged over each county.

Each month is filtered to California and cached in data/raw/nclimgrid/, so a rerun
only fetches months it doesn't have yet. Final ("scaled") months are kept;
preliminary ("prelim") recent months are refetched until NOAA finalizes them.
All cached months are then combined into data/raw/nclimgrid_ca_county_daily.csv.

Run from the project root:
    python -m src.download_weather                     # START_YEAR to this year
    python -m src.download_weather --start 1990 --end 2025
"""

import argparse
import io
from datetime import date

import pandas as pd
import requests

from src.config import CA_FIPS, NCLIMGRID_BASE, RAW, START_YEAR, WEATHER_VARS

CACHE = RAW / "nclimgrid"
OUT = RAW / "nclimgrid_ca_county_daily.csv"


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    return next((lower[c] for c in candidates if c in lower), None)


def keep_california(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to California without assuming exact column names."""
    state_col = find_col(df, ["state", "state_name", "st", "state_abbr", "state_code"])
    if state_col is not None:
        s = df[state_col].astype(str).str.strip().str.upper()
        mask = s.isin(["CA", "CALIFORNIA", "06", "6"])
        if mask.any():
            return df[mask]
    code_col = find_col(df, ["fips", "region_code", "county_fips", "geoid", "code"])
    if code_col is not None:
        codes = df[code_col].astype(str).str.strip().str.zfill(5)
        return df[codes.str.startswith(CA_FIPS)]
    raise SystemExit(f"No state or FIPS column found. Columns are: {list(df.columns)}")


def fetch_month(year: int, month: int) -> tuple[pd.DataFrame, str] | None:
    for status in ("scaled", "prelim"):
        url = f"{NCLIMGRID_BASE}/YEAR={year}/STATUS={status}/{year}{month:02d}.parquet"
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            return pd.read_parquet(io.BytesIO(r.content)), status
    return None


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    elif {"year", "month", "day"} <= set(df.columns):
        df["date"] = pd.to_datetime(df[["year", "month", "day"]])
    for v in WEATHER_VARS:
        if v in df.columns:
            df[v] = pd.to_numeric(df[v], errors="coerce")
    county_col = find_col(df, ["county", "county_name", "region_name", "name"])
    if county_col and county_col != "county":
        df = df.rename(columns={county_col: "county"})
    df["county"] = (
        df["county"].astype(str).str.replace(r"\s+County$", "", regex=True).str.strip()
    )
    return df


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=START_YEAR)
    p.add_argument("--end", type=int, default=date.today().year)
    args = p.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    today = date.today()
    months = [
        (y, m)
        for y in range(args.start, args.end + 1)
        for m in range(1, 13)
        if (y, m) <= (today.year, today.month)
    ]

    for y, m in months:
        ym = f"{y}{m:02d}"
        if (CACHE / f"{ym}_scaled.parquet").exists():
            continue
        result = fetch_month(y, m)
        if result is None:
            print(f"{ym}: not available yet, skipping")
            continue
        df, status = result
        ca = keep_california(df)
        for old in CACHE.glob(f"{ym}_*.parquet"):
            old.unlink()
        ca.to_parquet(CACHE / f"{ym}_{status}.parquet", index=False)
        print(f"{ym}: {len(ca):,} rows ({status})")

    files = sorted(
        f for f in CACHE.glob("*.parquet")
        if args.start <= int(f.name[:4]) <= args.end
    )
    if not files:
        raise SystemExit("No weather data downloaded.")
    daily = standardize(pd.concat([pd.read_parquet(f) for f in files], ignore_index=True))
    daily = daily.sort_values(["county", "date"])
    daily.to_csv(OUT, index=False)

    n_cty = daily["county"].nunique()
    print(f"\nWrote {OUT.name}: {len(daily):,} rows, {n_cty} counties")
    print(f"Columns: {list(daily.columns)}")
    if n_cty != 58:
        print("Warning: expected 58 California counties. Check the county column above.")


if __name__ == "__main__":
    main()
