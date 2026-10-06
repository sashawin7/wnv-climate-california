"""Download daily gridMET humidity and VPD and average them to California counties.

gridMET is a ~4 km daily grid. For each year, this fetches the grid over California
with PyGridMET, assigns every grid cell to the county that contains its center, and
averages the cells in each county. Each year is cached in data/raw/gridmet/ as a
small CSV, so a rerun only fetches missing years (the current year is always
refetched, since it's still growing).

Variables (see config.GRIDMET_VARS): rmax, rmin (%), sph (kg/kg), vpd (kPa).
Output: data/raw/gridmet_ca_county_daily.csv with columns date, county, fips, rmax, rmin, sph, vpd.

Run from the project root:
    python -m src.download_gridmet                     # START_YEAR to this year
    python -m src.download_gridmet --start 2010 --end 2012

A year of four variables over California is a few hundred MB while it's processed.
"""

import argparse
from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd

from src.config import CA_FIPS, COUNTY_SHAPES_URL, GRIDMET_VARS, RAW, START_YEAR

CACHE = RAW / "gridmet"
SHAPES = RAW / "ca_counties.gpkg"
OUT = RAW / "gridmet_ca_county_daily.csv"


def ca_counties() -> gpd.GeoDataFrame:
    """California county polygons (EPSG:4326), cached after the first download."""
    if SHAPES.exists():
        return gpd.read_file(SHAPES)
    us = gpd.read_file(COUNTY_SHAPES_URL)
    ca = us[us["STATEFP"] == CA_FIPS].to_crs(4326)
    ca = ca.rename(columns={"NAME": "county", "GEOID": "fips"})[["county", "fips", "geometry"]]
    ca = ca.sort_values("county").reset_index(drop=True)
    SHAPES.parent.mkdir(parents=True, exist_ok=True)
    ca.to_file(SHAPES, driver="GPKG")
    return ca


def cell_county_index(lat: np.ndarray, lon: np.ndarray, counties: gpd.GeoDataFrame) -> np.ndarray:
    """For a lat x lon grid, the row number in `counties` containing each cell center, or -1.

    Returned flat, in the same order as reshaping a (lat, lon) array with .reshape(-1).
    A county with no cell center inside it gets the cell nearest its centroid.
    """
    lon2d, lat2d = np.meshgrid(lon, lat)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon2d.ravel(), lat2d.ravel()), crs=4326)
    hit = gpd.sjoin(pts, counties[["geometry"]], how="left", predicate="within")
    hit = hit[~hit.index.duplicated()]  # a point on a shared border: keep one county
    idx = hit["index_right"].fillna(-1).astype(int).to_numpy()

    for i, geom in enumerate(counties.geometry):
        if not (idx == i).any():
            c = geom.representative_point()
            nearest = np.argmin((lon2d.ravel() - c.x) ** 2 + (lat2d.ravel() - c.y) ** 2)
            idx[nearest] = i
    return idx


def county_means(ds, counties: gpd.GeoDataFrame, variables: list[str]) -> pd.DataFrame:
    """Average a (time, lat, lon) dataset over each county. Returns one row per county-day."""
    idx = cell_county_index(ds["lat"].values, ds["lon"].values, counties)
    times = pd.to_datetime(ds["time"].values).normalize()
    frames = []
    for i, row in counties.iterrows():
        cells = idx == i
        out = {"date": times, "county": row["county"], "fips": row["fips"]}
        for v in variables:
            arr = ds[v].values.reshape(len(times), -1)[:, cells]
            with np.errstate(all="ignore"):
                out[v] = np.nanmean(arr, axis=1)
        frames.append(pd.DataFrame(out))
    return pd.concat(frames, ignore_index=True)


def fetch_year(year: int, counties: gpd.GeoDataFrame) -> pd.DataFrame:
    import pygridmet  # imported here so the tests don't need it

    ca_shape = counties.union_all()
    end = min(date(year, 12, 31), date.today())
    ds = pygridmet.get_bygeom(
        ca_shape, (f"{year}-01-01", end.isoformat()), variables=GRIDMET_VARS
    )
    return county_means(ds, counties, GRIDMET_VARS)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=int, default=START_YEAR)
    p.add_argument("--end", type=int, default=date.today().year)
    args = p.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    counties = ca_counties()
    this_year = date.today().year

    for year in range(args.start, args.end + 1):
        path = CACHE / f"{year}.csv"
        if path.exists() and year < this_year:
            continue
        df = fetch_year(year, counties)
        df.to_csv(path, index=False)
        print(f"{year}: {df['date'].nunique()} days, {df['county'].nunique()} counties")

    files = sorted(f for f in CACHE.glob("*.csv") if args.start <= int(f.stem) <= args.end)
    if not files:
        raise SystemExit("No gridMET data downloaded.")
    daily = pd.concat([pd.read_csv(f, dtype={"fips": str}) for f in files], ignore_index=True)
    daily = daily.sort_values(["county", "date"])
    daily.to_csv(OUT, index=False)
    print(f"\nWrote {OUT.name}: {len(daily):,} rows, {daily['county'].nunique()} counties")


if __name__ == "__main__":
    main()
