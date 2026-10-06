"""Checks for the population, drought and gridMET steps on small made-up data,
shaped like the real files. Run with:  pytest"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import box

from src.build_dataset import build, weekly_drought
from src.download_gridmet import county_means
from src.download_population import combine, tidy_census
from tests.test_build_dataset import make_daily, make_wnv


# Population -----------------------------------------------------------------

def census_table(years: list[int], kern: list[int]) -> pd.DataFrame:
    """A wide table like co-est20XX-alldata.csv (read with dtype=str)."""
    rows = [
        # state row, a California county, and a county in another state
        {"SUMLEV": "040", "STATE": "06", "COUNTY": "000", "CTYNAME": "California"},
        {"SUMLEV": "050", "STATE": "06", "COUNTY": "029", "CTYNAME": "Kern County"},
        {"SUMLEV": "050", "STATE": "32", "COUNTY": "003", "CTYNAME": "Clark County"},
    ]
    df = pd.DataFrame(rows)
    df["ESTIMATESBASE2000"] = "1"
    for y, k in zip(years, kern):
        df[f"POPESTIMATE{y}"] = ["99999999", str(k), "1"]
    return df


def test_population():
    old = tidy_census(census_table([2019, 2020], [900_000, 905_000]), "co-est2020-alldata")
    new = tidy_census(census_table([2020, 2021], [910_000, 915_000]), "co-est2025-alldata")
    pop = combine([old, new])

    assert set(pop["county"]) == {"Kern"}  # state row and other states dropped
    assert pop["fips"].iloc[0] == "06029"
    by_year = pop.set_index("year")
    assert by_year.loc[2020, "population"] == 910_000  # newer vintage wins
    assert by_year.loc[2020, "vintage"] == "co-est2025-alldata"
    assert list(pop["year"]) == [2019, 2020, 2021]


# Drought --------------------------------------------------------------------

def usdm_rows(d: list[float], none: float) -> pd.DataFrame:
    """One Drought Monitor row for Kern, dated Tuesday 2020-07-21 (MMWR 2020 week 30)."""
    return pd.DataFrame([{
        "MapDate": "20200721", "FIPS": "06029", "County": "Kern County", "State": "CA",
        "None": none, "D0": d[0], "D1": d[1], "D2": d[2], "D3": d[3], "D4": d[4],
        "ValidStart": "2020-07-21", "ValidEnd": "2020-07-27", "StatisticFormatID": 1,
    }])


@pytest.mark.parametrize("form", ["categorical", "cumulative"])
def test_drought_either_form(form):
    # Same map both ways: 10% none, 20% D0 only, 30% D1, 25% D2, 15% D3, 0% D4
    if form == "categorical":
        rows = usdm_rows([20, 30, 25, 15, 0], none=10)
    else:
        rows = usdm_rows([90, 70, 40, 15, 0], none=10)
    w = weekly_drought(rows).iloc[0]

    assert (w["county"], w["mmwr_year"], w["mmwr_week"]) == ("Kern", 2020, 30)
    assert [w[f"usdm_d{i}"] for i in range(5)] == [20, 30, 25, 15, 0]
    assert w["usdm_d1plus"] == 70
    assert w["usdm_dsci"] == 90 + 70 + 40 + 15 + 0


# gridMET --------------------------------------------------------------------

def test_county_means():
    # 4 x 4 grid of cell centers at 0.5, 1.5, 2.5, 3.5. "West" covers x < 2, "East" x >= 2.
    lat = np.array([3.5, 2.5, 1.5, 0.5])  # gridMET latitudes run north to south
    lon = np.array([0.5, 1.5, 2.5, 3.5])
    vpd = np.zeros((2, 4, 4))
    vpd[:, :, :2] = 1.0
    vpd[:, :, 2:] = 3.0
    vpd[1, 0, 3] = np.nan  # a missing cell is skipped, not averaged as 0
    ds = xr.Dataset(
        {"vpd": (("time", "lat", "lon"), vpd)},
        coords={"time": pd.date_range("2020-07-01", periods=2), "lat": lat, "lon": lon},
    )
    counties = gpd.GeoDataFrame(
        {"county": ["East", "West"], "fips": ["06001", "06003"]},
        geometry=[box(2, 0, 4, 4), box(0, 0, 2, 4)],
        crs=4326,
    )
    out = county_means(ds, counties, ["vpd"]).set_index(["county", "date"])["vpd"]
    assert out[("West", pd.Timestamp("2020-07-01"))] == 1.0
    assert out[("East", pd.Timestamp("2020-07-02"))] == 3.0


# Full build -----------------------------------------------------------------

def test_build_with_all_sources():
    daily = make_daily()
    gridmet = daily[["date", "county"]].assign(rmax=80.0, rmin=20.0, sph=0.008, vpd=1.5)
    drought = pd.concat([usdm_rows([20, 30, 25, 15, 0], none=10)], ignore_index=True)
    pop = pd.DataFrame({
        "county": ["Kern", "Fresno"], "fips": ["06029", "06019"],
        "year": [2019, 2019], "population": [900_000, 1_000_000],
        "vintage": ["co-est2020-alldata"] * 2,
    })
    dataset, _ = build(daily, make_wnv(), gridmet, drought, pop)
    by_key = dataset.set_index(["county", "mmwr_year", "mmwr_week"])

    kern30 = by_key.loc[("Kern", 2020, 30)]
    assert kern30["population"] == 900_000
    assert bool(kern30["pop_carried_forward"])  # 2020 reuses the 2019 estimate
    assert kern30["incidence_per_100k"] == pytest.approx(9 / 900_000 * 1e5)
    assert kern30["log_pop"] == pytest.approx(np.log(900_000))
    assert kern30["vpd"] == 1.5 and kern30["vpd_lag1"] == 1.5

    assert by_key.loc[("Kern", 2020, 30), "usdm_dsci"] == 215
    assert by_key.loc[("Kern", 2020, 31), "usdm_dsci_lag1"] == 215
    assert pd.isna(by_key.loc[("Fresno", 2020, 30), "usdm_dsci"])  # no map for Fresno


def test_lags_match_by_date():
    # Drop one week of weather. The lag pointing at it should be missing, and the
    # week after should still lag correctly (a row-based shift would get this wrong).
    daily = make_daily()
    daily = daily[~daily["date"].between("2020-07-19", "2020-07-25")]  # MMWR 2020 week 30
    daily.loc[daily["date"].between("2020-07-12", "2020-07-18"), "tavg"] = 25.0  # week 29
    dataset, _ = build(daily, make_wnv())
    by_key = dataset.set_index(["county", "mmwr_year", "mmwr_week"])

    assert ("Kern", 2020, 30) not in by_key.index
    assert pd.isna(by_key.loc[("Kern", 2020, 31), "tavg_lag1"])
    assert by_key.loc[("Kern", 2020, 31), "tavg_lag2"] == 25.0
