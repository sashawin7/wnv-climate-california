"""Combine weekly WNV cases and weekly weather into one county-week dataset.

Steps
1. Group daily county weather into MMWR weeks (Sunday-Saturday): mean temperatures,
   summed precipitation, and the number of days observed.
2. Load the CDPH WNV file. It lists only county-weeks with at least one case, and
   has a few duplicate rows, which are summed.
3. Left-join cases onto every county-week of weather, so any county-week missing
   from the WNV file gets 0 cases.
4. Add lagged weather columns, since cases are counted by week *reported*, which
   comes weeks after infection.

WNV rows that don't match a weather week (e.g. week 53 in a year without an MMWR
week 53) are written to data/processed/wnv_unmatched_rows.csv rather than dropped
silently.

Run from the project root:  python -m src.build_dataset
"""

import pandas as pd
from epiweeks import Week

from src.config import PROCESSED, RAW

WEATHER_IN = RAW / "nclimgrid_ca_county_daily.csv"
WNV_IN = RAW / "wnv_human_cases.csv"
OUT = PROCESSED / "ca_wnv_weather_weekly.csv"
UNMATCHED_OUT = PROCESSED / "wnv_unmatched_rows.csv"

KEYS = ["county", "mmwr_year", "mmwr_week"]
LAG_VARS = ["tavg", "tmax", "tmin", "prcp_total"]
LAGS = [1, 2, 3, 4, 6, 8]


def county_key(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\s+County$", "", regex=True).str.strip().str.title()


def weekly_weather(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily["county"] = county_key(daily["county"])
    weeks = daily["date"].dt.date.map(Week.fromdate)
    daily["mmwr_year"] = weeks.map(lambda w: w.year)
    daily["mmwr_week"] = weeks.map(lambda w: w.week)

    agg = {
        "week_start": ("date", "min"),
        "n_days": ("date", "count"),
        "tmax": ("tmax", "mean"),
        "tmin": ("tmin", "mean"),
        "tavg": ("tavg", "mean"),
        "prcp_total": ("prcp", "sum"),
    }
    group_keys = KEYS + (["fips"] if "fips" in daily.columns else [])
    return daily.groupby(group_keys, as_index=False).agg(**agg)


def load_wnv(path) -> pd.DataFrame:
    wnv = pd.read_csv(path)
    wnv.columns = [c.strip().lower() for c in wnv.columns]
    case_col = next(c for c in wnv.columns if "case" in c)
    wnv = wnv.rename(columns={"year": "mmwr_year", "week": "mmwr_week", case_col: "wnv_cases"})
    return wnv[KEYS + ["wnv_cases"]]


def add_lags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(KEYS).copy()
    by_county = df.groupby("county")
    for var in LAG_VARS:
        for k in LAGS:
            df[f"{var}_lag{k}"] = by_county[var].shift(k)
    return df


def build(daily: pd.DataFrame, wnv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekly = weekly_weather(daily)
    wnv = wnv.assign(county=county_key(wnv["county"]))
    wnv = wnv.groupby(KEYS, as_index=False)["wnv_cases"].sum()  # merge duplicate rows
    merged = weekly.merge(wnv, on=KEYS, how="left")
    merged["wnv_cases"] = merged["wnv_cases"].fillna(0).astype(int)

    matched = wnv.merge(weekly[KEYS], on=KEYS, how="left", indicator=True)
    unmatched = matched.loc[matched["_merge"] == "left_only", KEYS + ["wnv_cases"]]
    return add_lags(merged), unmatched


def main() -> None:
    daily = pd.read_csv(WEATHER_IN)
    wnv = load_wnv(WNV_IN)
    dataset, unmatched = build(daily, wnv)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(dataset):,} county-weeks, "
          f"{dataset['county'].nunique()} counties, "
          f"{dataset['wnv_cases'].sum():,} cases")

    if len(unmatched):
        unmatched.to_csv(UNMATCHED_OUT, index=False)
        print(f"Warning: {unmatched['wnv_cases'].sum():,} cases in {len(unmatched)} WNV rows "
              f"had no matching weather week. See {UNMATCHED_OUT.name}.")


if __name__ == "__main__":
    main()
