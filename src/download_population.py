"""Download annual county population estimates for California from the Census Bureau.

Reads the wide POPESTIMATE<year> columns from each county totals file in
config.CENSUS_POP_URLS, keeps California counties, and writes a long file:
data/raw/ca_county_population.csv with columns county, fips, year, population, vintage.

Run from the project root:  python -m src.download_population
"""

import io
import re

import pandas as pd
import requests

from src.config import CA_FIPS, CENSUS_POP_URLS, RAW

OUT = RAW / "ca_county_population.csv"
POP_COL = re.compile(r"^POPESTIMATE(\d{4})$")


def tidy_census(raw: pd.DataFrame, vintage: str) -> pd.DataFrame:
    """Turn one wide Census county totals table into long California rows."""
    df = raw.copy()
    df.columns = [c.strip().upper() for c in df.columns]
    df = df[(df["SUMLEV"].astype(int) == 50) & (df["STATE"].astype(int) == int(CA_FIPS))]
    year_cols = {c: int(m.group(1)) for c in df.columns if (m := POP_COL.match(c))}
    if not year_cols:
        raise SystemExit(f"No POPESTIMATE<year> columns in {vintage}. Columns: {list(df.columns)}")

    long = df.melt(
        id_vars=["STATE", "COUNTY", "CTYNAME"],
        value_vars=list(year_cols),
        var_name="col",
        value_name="population",
    )
    long["year"] = long["col"].map(year_cols)
    long["population"] = pd.to_numeric(long["population"]).astype(int)
    long["fips"] = (
        long["STATE"].astype(int).astype(str).str.zfill(2)
        + long["COUNTY"].astype(int).astype(str).str.zfill(3)
    )
    long["county"] = long["CTYNAME"].str.replace(r"\s+County$", "", regex=True).str.strip()
    long["vintage"] = vintage
    return long[["county", "fips", "year", "population", "vintage"]]


def combine(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Stack the decade files. For years in more than one file, keep the newest vintage."""
    df = pd.concat(tables, ignore_index=True)  # tables are given oldest vintage first
    df["order"] = df.groupby(["fips", "year"]).cumcount()
    df = df.sort_values("order").drop_duplicates(["fips", "year"], keep="last")
    return df.drop(columns="order").sort_values(["county", "year"]).reset_index(drop=True)


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    tables = []
    for url in CENSUS_POP_URLS:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        vintage = url.rsplit("/", 1)[-1].removesuffix(".csv")
        raw = pd.read_csv(io.BytesIO(r.content), encoding="latin-1", dtype=str)
        tables.append(tidy_census(raw, vintage))
        print(f"{vintage}: {tables[-1]['year'].min()}-{tables[-1]['year'].max()}")

    pop = combine(tables)
    pop.to_csv(OUT, index=False)
    print(f"\nWrote {OUT.name}: {pop['county'].nunique()} counties, "
          f"{pop['year'].min()}-{pop['year'].max()}")


if __name__ == "__main__":
    main()
