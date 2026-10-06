"""Combine weekly WNV cases, weather, humidity, drought and population into one dataset.

Steps
1. Group daily county weather (NOAA nClimGrid) into MMWR weeks (Sunday-Saturday):
   mean temperatures, summed precipitation, and the number of days observed.
   This sets the county-weeks in the output.
2. Load the CDPH WNV file. It lists only county-weeks with at least one case, and
   has a few duplicate rows, which are summed. Any county-week missing from it
   gets 0 cases.
3. If downloaded, add:
   - gridMET humidity and VPD, averaged over each MMWR week
   - US Drought Monitor percentages from the map dated inside each MMWR week
     (maps come out on Tuesdays, and every MMWR week has exactly one Tuesday)
   - Census population for the MMWR year, plus incidence per 100,000 and
     log(population) for use as a model offset
4. Add lagged columns, since cases are counted by week *reported*, which comes weeks
   after infection. Lags are matched by date (week_start minus 7*k days), so a
   missing week gives a missing lag rather than shifting everything after it.

WNV rows that don't match a weather week (e.g. week 53 in a year without an MMWR
week 53) are written to data/processed/wnv_unmatched_rows.csv rather than dropped
silently.

Run from the project root:  python -m src.build_dataset
"""

import numpy as np
import pandas as pd
from epiweeks import Week

from src.config import PROCESSED, RAW

WEATHER_IN = RAW / "nclimgrid_ca_county_daily.csv"
WNV_IN = RAW / "wnv_human_cases.csv"
GRIDMET_IN = RAW / "gridmet_ca_county_daily.csv"
DROUGHT_IN = RAW / "usdm_ca_county_weekly.csv"
POP_IN = RAW / "ca_county_population.csv"
OUT = PROCESSED / "ca_wnv_weather_weekly.csv"
UNMATCHED_OUT = PROCESSED / "wnv_unmatched_rows.csv"

KEYS = ["county", "mmwr_year", "mmwr_week"]
GRIDMET_VARS = ["rmax", "rmin", "sph", "vpd"]
USDM_CATS = ["d0", "d1", "d2", "d3", "d4"]
LAG_VARS = ["tavg", "tmax", "tmin", "prcp_total", "rmax", "rmin", "sph", "vpd", "usdm_dsci"]
LAGS = [1, 2, 3, 4, 6, 8]


def county_key(s: pd.Series) -> pd.Series:
    return s.astype(str).str.replace(r"\s+County$", "", regex=True).str.strip().str.title()


def add_mmwr(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    weeks = df[date_col].dt.date.map(Week.fromdate)
    df["mmwr_year"] = weeks.map(lambda w: w.year)
    df["mmwr_week"] = weeks.map(lambda w: w.week)
    return df


def weekly_weather(daily: pd.DataFrame) -> pd.DataFrame:
    daily = add_mmwr(daily.assign(county=county_key(daily["county"])))
    agg = {
        "week_start": ("date", "min"),
        "n_days": ("date", "count"),
        "tmax": ("tmax", "mean"),
        "tmin": ("tmin", "mean"),
        "tavg": ("tavg", "mean"),
        "prcp_total": ("prcp", "sum"),
    }
    group_keys = KEYS + (["fips"] if "fips" in daily.columns else [])
    weekly = daily.groupby(group_keys, as_index=False).agg(**agg)
    # Label each week by its Sunday, even when the data starts midweek.
    weekly["week_start"] = weekly.apply(
        lambda r: pd.Timestamp(Week(r["mmwr_year"], r["mmwr_week"]).startdate()), axis=1
    )
    return weekly


def weekly_gridmet(daily: pd.DataFrame) -> pd.DataFrame:
    daily = add_mmwr(daily.assign(county=county_key(daily["county"])))
    return daily.groupby(KEYS, as_index=False)[GRIDMET_VARS].mean()


def weekly_drought(usdm: pd.DataFrame) -> pd.DataFrame:
    """Drought Monitor rows -> one row per county-week.

    The API's "traditional" statistics may be cumulative (D1 = percent in D1 or worse)
    or categorical (D1 = percent in D1 only). Categorical rows add up to 100 across
    None and D0-D4; this checks which form arrived and converts so the output has both:
      usdm_d0 ... usdm_d4   percent of area in exactly that category
      usdm_d1plus           percent of area in drought (D1 or worse)
      usdm_dsci             Drought Severity and Coverage Index, 0-500
                            (sum of cumulative D0-D4 percents)
    """
    df = usdm.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    cats = df[USDM_CATS].astype(float)
    row_total = df["none"].astype(float) + cats.sum(axis=1)
    categorical = np.allclose(row_total, 100, atol=0.5)

    if categorical:
        exact = cats
        cumulative = cats.iloc[:, ::-1].cumsum(axis=1).iloc[:, ::-1]
    else:
        cumulative = cats
        exact = cats - cats.shift(-1, axis=1).fillna(0)

    out = pd.DataFrame({
        "county": county_key(df["county"]),
        "date": pd.to_datetime(df["mapdate"].astype(str), format="%Y%m%d"),
    })
    for c in USDM_CATS:
        out[f"usdm_{c}"] = exact[c].round(2).values
    out["usdm_d1plus"] = cumulative["d1"].round(2).values
    out["usdm_dsci"] = cumulative.sum(axis=1).round(2).values
    out = add_mmwr(out)
    out = out.drop(columns="date").drop_duplicates(KEYS, keep="last")
    return out


def population_by_year(pop: pd.DataFrame, years: pd.Series) -> pd.DataFrame:
    """County population for each MMWR year. Years after the latest estimate reuse it."""
    pop = pop.assign(county=county_key(pop["county"]))[["county", "year", "population"]]
    last = pop["year"].max()
    grid = pd.MultiIndex.from_product(
        [pop["county"].unique(), sorted(years.unique())], names=["county", "mmwr_year"]
    ).to_frame(index=False)
    grid["year"] = grid["mmwr_year"].clip(upper=last)
    out = grid.merge(pop, on=["county", "year"], how="left")
    out["pop_carried_forward"] = out["mmwr_year"] > last
    return out.drop(columns="year")


def load_wnv(path) -> pd.DataFrame:
    wnv = pd.read_csv(path)
    wnv.columns = [c.strip().lower() for c in wnv.columns]
    case_col = next(c for c in wnv.columns if "case" in c)
    wnv = wnv.rename(columns={"year": "mmwr_year", "week": "mmwr_week", case_col: "wnv_cases"})
    return wnv[KEYS + ["wnv_cases"]]


def add_lags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(KEYS).reset_index(drop=True)
    vars_present = [v for v in LAG_VARS if v in df.columns]
    base = df[["county", "week_start"] + vars_present]
    for k in LAGS:
        shifted = base.assign(week_start=base["week_start"] + pd.Timedelta(weeks=k))
        shifted = shifted.rename(columns={v: f"{v}_lag{k}" for v in vars_present})
        df = df.merge(shifted, on=["county", "week_start"], how="left")
    order = [c for c in df.columns if "_lag" not in c]
    order += [f"{v}_lag{k}" for v in vars_present for k in LAGS]
    return df[order]


def build(
    daily: pd.DataFrame,
    wnv: pd.DataFrame,
    gridmet: pd.DataFrame | None = None,
    drought: pd.DataFrame | None = None,
    pop: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekly = weekly_weather(daily)

    wnv = wnv.assign(county=county_key(wnv["county"]))
    wnv = wnv.groupby(KEYS, as_index=False)["wnv_cases"].sum()  # merge duplicate rows
    merged = weekly.merge(wnv, on=KEYS, how="left")
    merged["wnv_cases"] = merged["wnv_cases"].fillna(0).astype(int)

    if gridmet is not None:
        merged = merged.merge(weekly_gridmet(gridmet), on=KEYS, how="left")
    if drought is not None:
        merged = merged.merge(weekly_drought(drought), on=KEYS, how="left")
    if pop is not None:
        p = population_by_year(pop, merged["mmwr_year"])
        merged = merged.merge(p, on=["county", "mmwr_year"], how="left")
        merged["incidence_per_100k"] = merged["wnv_cases"] / merged["population"] * 1e5
        merged["log_pop"] = np.log(merged["population"])

    matched = wnv.merge(weekly[KEYS], on=KEYS, how="left", indicator=True)
    unmatched = matched.loc[matched["_merge"] == "left_only", KEYS + ["wnv_cases"]]
    return add_lags(merged), unmatched


def read_optional(path, **kwargs) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_csv(path, **kwargs)
    print(f"Skipping {path.name}: not downloaded yet")
    return None


def main() -> None:
    daily = pd.read_csv(WEATHER_IN)
    wnv = load_wnv(WNV_IN)
    gridmet = read_optional(GRIDMET_IN)
    drought = read_optional(DROUGHT_IN, dtype={"FIPS": str, "MapDate": str})
    pop = read_optional(POP_IN)
    dataset, unmatched = build(daily, wnv, gridmet, drought, pop)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(dataset):,} county-weeks, "
          f"{dataset['county'].nunique()} counties, "
          f"{dataset['wnv_cases'].sum():,} cases")

    for col, label in [("rmax", "gridMET"), ("usdm_dsci", "drought"), ("population", "population")]:
        if col in dataset.columns:
            missing = dataset[col].isna().mean()
            if missing > 0.01:
                print(f"Note: {missing:.1%} of county-weeks have no {label} data. "
                      f"Check that county names match and the years overlap.")
    if "pop_carried_forward" in dataset.columns and dataset["pop_carried_forward"].any():
        years = sorted(int(y) for y in dataset.loc[dataset["pop_carried_forward"], "mmwr_year"].unique())
        print(f"Note: population for {years} reuses the latest Census estimate.")

    if len(unmatched):
        unmatched.to_csv(UNMATCHED_OUT, index=False)
        print(f"Warning: {unmatched['wnv_cases'].sum():,} cases in {len(unmatched)} WNV rows "
              f"had no matching weather week. See {UNMATCHED_OUT.name}.")


if __name__ == "__main__":
    main()
