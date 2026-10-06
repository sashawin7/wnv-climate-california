"""Combine weekly WNV cases, weather, humidity, drought and population into one dataset.

Steps
1. Group daily county weather (NOAA nClimGrid) into MMWR weeks (Sunday-Saturday):
   mean temperatures, summed precipitation, and the number of days observed.
2. Lay out one row per county per MMWR week, from the first weather week to the end
   of the analysis period, so a week missing from a source shows up as blanks
   instead of a missing row.
3. Load the CDPH WNV file. It lists only county-weeks with at least one case, and
   has a few duplicate rows, which are summed. Any county-week missing from it
   gets 0 cases.
4. If downloaded, add:
   - gridMET humidity and VPD, averaged over each MMWR week
   - US Drought Monitor percentages from the map dated inside each MMWR week
     (maps come out on Tuesdays, and every MMWR week has exactly one Tuesday)
5. Add lagged columns, since cases are counted by week *reported*, which comes weeks
   after infection. Lags are matched by date (week_start minus 7*k days), so a
   missing week gives a missing lag rather than shifting everything after it.
   Lags are computed before the output is cut to the analysis period, so weather
   downloaded before START_YEAR fills the lags of its first weeks.
6. Keep only the analysis period: START_YEAR week 1 through the latest week in the
   CDPH file. Weeks after CDPH's latest report aren't known to have zero cases.
7. If downloaded, add Census population for the MMWR year, plus incidence per
   100,000 and log(population) for use as a model offset.

WNV rows that don't match a county-week (e.g. week 53 in a year without an MMWR
week 53, or a county name that isn't one of the 58) are written to
data/processed/wnv_unmatched_rows.csv rather than dropped silently.

Run from the project root:  python -m src.build_dataset
"""

import warnings

import numpy as np
import pandas as pd
from epiweeks import Week, Year

from src.config import CA_COUNTIES, PROCESSED, RAW, START_YEAR

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
    """'CA: Kern County', 'Kern County' and 'kern' all become 'Kern'."""
    return (
        s.astype(str)
        .str.replace(r"^[A-Za-z]{2}:\s*", "", regex=True)
        .str.replace(r"\s+County$", "", regex=True)
        .str.strip()
        .str.title()
    )


def unknown_counties(counties: pd.Series) -> list[str]:
    """Names that aren't one of the 58 California counties."""
    return sorted(set(counties.dropna()) - set(CA_COUNTIES))


def add_mmwr(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    weeks = df[date_col].dt.date.map(Week.fromdate)
    df["mmwr_year"] = weeks.map(lambda w: w.year)
    df["mmwr_week"] = weeks.map(lambda w: w.week)
    return df


def week_start(year: int, week: int) -> pd.Timestamp:
    return pd.Timestamp(Week(year, week).startdate())


def weekly_weather(daily: pd.DataFrame) -> pd.DataFrame:
    daily = add_mmwr(daily.assign(county=county_key(daily["county"])))
    weekly = daily.groupby(KEYS, as_index=False).agg(
        n_days=("date", "count"),
        tmax=("tmax", "mean"),
        tmin=("tmin", "mean"),
        tavg=("tavg", "mean"),
        prcp_total=("prcp", "sum"),
        n_prcp_days=("prcp", "count"),
    )
    # A week with no precipitation values is unknown, not 0 mm.
    weekly.loc[weekly["n_prcp_days"] == 0, "prcp_total"] = np.nan
    return weekly.drop(columns="n_prcp_days")


def week_grid(counties, first: pd.Timestamp, last: pd.Timestamp) -> pd.DataFrame:
    """One row per county per MMWR week whose Sunday falls between first and last."""
    weeks = add_mmwr(pd.DataFrame({"week_start": pd.date_range(first, last, freq="7D")}),
                     "week_start")
    grid = pd.DataFrame({"county": sorted(counties)}).merge(weeks, how="cross")
    return grid[["county", "mmwr_year", "mmwr_week", "week_start"]]


def weekly_gridmet(daily: pd.DataFrame) -> pd.DataFrame:
    daily = add_mmwr(daily.assign(county=county_key(daily["county"])))
    return daily.groupby(KEYS, as_index=False)[GRIDMET_VARS].mean()


def weekly_drought(usdm: pd.DataFrame) -> pd.DataFrame:
    """Drought Monitor rows -> one row per county-week.

    The API's "traditional" statistics come cumulative (D1 = percent in D1 or worse),
    but categorical rows (D1 = percent in D1 only) are handled too, row by row.
    A categorical row adds up to 100 across None and D0-D4; a cumulative row adds
    up to 100 plus D1-D4, so it only adds up to 100 when D1-D4 are 0, and then
    both readings agree. The output has both forms:
      usdm_d0 ... usdm_d4   percent of area in exactly that category
      usdm_d1plus           percent of area in drought (D1 or worse)
      usdm_dsci             Drought Severity and Coverage Index, 0-500
                            (sum of cumulative D0-D4 percents)
    """
    df = usdm.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    cats = df[USDM_CATS].astype(float)
    row_total = df["none"].astype(float) + cats.sum(axis=1)
    categorical = (row_total - 100).abs() <= 0.05  # values have two decimals

    non_increasing = (cats.diff(axis=1).iloc[:, 1:] <= 0.005).all(axis=1)
    if bad := int((~categorical & ~non_increasing).sum()):
        warnings.warn(f"{bad} Drought Monitor rows are neither categorical nor cumulative")

    exact = cats.where(categorical, cats - cats.shift(-1, axis=1).fillna(0), axis=0)
    cumulative = cats.where(~categorical, cats.iloc[:, ::-1].cumsum(axis=1).iloc[:, ::-1],
                            axis=0)

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
    case_cols = [c for c in wnv.columns if "case" in c]
    if len(case_cols) != 1:
        raise ValueError(f"Expected one case-count column in {path}, found {case_cols}")
    wnv = wnv.rename(columns={
        "year": "mmwr_year", "week": "mmwr_week", "week reported": "mmwr_week",
        case_cols[0]: "wnv_cases",
    })
    return wnv[KEYS + ["wnv_cases"]]


def latest_wnv_week(wnv: pd.DataFrame) -> Week:
    """The latest real MMWR week in the WNV file (ignoring e.g. week 53 of a 52-week year)."""
    pairs = sorted(set(zip(wnv["mmwr_year"], wnv["mmwr_week"])), reverse=True)
    return next(Week(int(y), int(w)) for y, w in pairs if w <= Year(int(y)).totalweeks())


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
    period: tuple[Week, Week] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join everything into one row per county-week.

    period: first and last MMWR week to keep. Without it, the output spans the
    weather data. Rows run from the first weather week regardless, so lags can
    reach back before the period's start.
    """
    weekly = weekly_weather(daily)
    weeks = weekly[["mmwr_year", "mmwr_week"]].drop_duplicates()
    sundays = [week_start(y, w) for y, w in zip(weeks["mmwr_year"], weeks["mmwr_week"])]
    start, end = min(sundays), max(sundays)
    if period is not None:
        start = min(start, pd.Timestamp(period[0].startdate()))
        end = pd.Timestamp(period[1].startdate())

    merged = week_grid(weekly["county"].unique(), start, end)
    merged.insert(1, "fips", merged["county"].map(CA_COUNTIES))
    merged = merged.merge(weekly, on=KEYS, how="left")
    merged["n_days"] = merged["n_days"].fillna(0).astype(int)

    wnv = wnv.assign(county=county_key(wnv["county"]))
    wnv = wnv.groupby(KEYS, as_index=False)["wnv_cases"].sum()  # merge duplicate rows
    merged = merged.merge(wnv, on=KEYS, how="left")
    merged["wnv_cases"] = merged["wnv_cases"].fillna(0).astype(int)

    if gridmet is not None:
        merged = merged.merge(weekly_gridmet(gridmet), on=KEYS, how="left")
    if drought is not None:
        merged = merged.merge(weekly_drought(drought), on=KEYS, how="left")
    if merged.duplicated(KEYS).any():
        raise ValueError("Some county-weeks appear more than once after joining the sources")

    matched = wnv.merge(merged[KEYS], on=KEYS, how="left", indicator=True)
    unmatched = matched.loc[matched["_merge"] == "left_only", KEYS + ["wnv_cases"]]

    merged = add_lags(merged)
    if period is not None:
        merged = merged[merged["week_start"] >= pd.Timestamp(period[0].startdate())]
        merged = merged.reset_index(drop=True)

    if pop is not None:
        p = population_by_year(pop, merged["mmwr_year"])
        merged = merged.merge(p, on=["county", "mmwr_year"], how="left")
        merged["incidence_per_100k"] = merged["wnv_cases"] / merged["population"] * 1e5
        merged["log_pop"] = np.log(merged["population"])
        merged = merged[[c for c in merged.columns if "_lag" not in c]
                        + [c for c in merged.columns if "_lag" in c]]
    return merged, unmatched


def read_optional(path, **kwargs) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_csv(path, **kwargs)
    print(f"Skipping {path.name}: not downloaded yet")
    return None


def report_coverage(dataset: pd.DataFrame) -> None:
    """Say which counties lack each source entirely, and how many county-weeks are blank."""
    for col, label in [("tavg", "weather"), ("rmax", "gridMET"), ("usdm_dsci", "drought"),
                       ("population", "population")]:
        if col not in dataset.columns:
            continue
        blank = dataset[col].isna()
        none = sorted(set(dataset["county"]) - set(dataset.loc[~blank, "county"]))
        if blank.any():
            print(f"Note: {blank.mean():.1%} of county-weeks have no {label} data"
                  + (f"; none at all for {none}" if none else ""))
    if missing := sorted(set(CA_COUNTIES) - set(dataset["county"])):
        print(f"Warning: counties missing from the output: {missing}")


def main() -> None:
    daily = pd.read_csv(WEATHER_IN, dtype={"fips": str})
    wnv = load_wnv(WNV_IN)
    gridmet = read_optional(GRIDMET_IN, dtype={"fips": str})
    drought = read_optional(DROUGHT_IN, dtype={"FIPS": str, "MapDate": str})
    pop = read_optional(POP_IN, dtype={"fips": str})

    for label, df, col in [("weather", daily, "county"), ("WNV", wnv, "county"),
                           ("gridMET", gridmet, "county"), ("drought", drought, "County"),
                           ("population", pop, "county")]:
        if df is not None and (bad := unknown_counties(county_key(df[col]))):
            print(f"Warning: {label} has county names that aren't California counties: {bad}")

    period = (Week(START_YEAR, 1), latest_wnv_week(wnv))
    dataset, unmatched = build(daily, wnv, gridmet, drought, pop, period)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(dataset):,} county-weeks, "
          f"{dataset['county'].nunique()} counties, {dataset['wnv_cases'].sum():,} cases, "
          f"MMWR {period[0]} to {period[1]}")

    report_coverage(dataset)
    if "pop_carried_forward" in dataset.columns and dataset["pop_carried_forward"].any():
        years = sorted(int(y) for y in dataset.loc[dataset["pop_carried_forward"], "mmwr_year"].unique())
        print(f"Note: population for {years} reuses the latest Census estimate.")

    if len(unmatched):
        unmatched.to_csv(UNMATCHED_OUT, index=False)
        print(f"Warning: {unmatched['wnv_cases'].sum():,} cases in {len(unmatched)} WNV rows "
              f"had no matching county-week. See {UNMATCHED_OUT.name}.")


if __name__ == "__main__":
    main()
