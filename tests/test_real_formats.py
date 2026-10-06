"""Checks against the formats of the real files, as seen in October 2026. Run with:  pytest"""

import io

import pandas as pd
import pytest
from epiweeks import Week

import src.download_drought as download_drought
from src.build_dataset import build, county_key, latest_wnv_week, load_wnv, weekly_drought
from src.download_weather import parse_month
from tests.test_build_dataset import make_daily, make_wnv
from tests.test_new_sources import usdm_rows

# Two lines of a NOAA nClimGrid-Daily county file (no header, 31 day columns,
# -999.99 for days past the end of the month). California's NCEI state code is 04.
FEB_2026 = "\n".join([
    "cty,01001,AL: Autauga,2026,02,TMAX," + ",".join(["  10.00"] * 28 + ["-999.99"] * 3),
    "cty,04029,CA: Kern County,2026,02,TMAX,"
    + ",".join([f"{20 + d / 100:9.2f}" for d in range(1, 29)] + ["  -999.99"] * 3),
])


def test_county_key_matches_every_source():
    names = pd.Series(["CA: Kern County", "Kern County", "Kern", "KERN", " Kern "])
    assert set(county_key(names)) == {"Kern"}
    assert county_key(pd.Series(["CA: San Luis Obispo County"]))[0] == "San Luis Obispo"


def test_parse_noaa_month():
    out = parse_month(FEB_2026, "tmax")
    assert set(out["county"]) == {"Kern"}  # Alabama dropped, prefix and suffix removed
    assert set(out["fips"]) == {"06029"}  # NCEI 04 becomes FIPS 06
    assert len(out) == 28  # Feb 29-31 dropped
    assert out["tmax"].notna().all()
    assert out.loc[out["date"] == "2026-02-03", "tmax"].item() == pytest.approx(20.03)


def test_parse_noaa_month_unprocessed_days():
    # A preliminary month: days NOAA hasn't processed yet are -999.99 and become blank.
    line = "cty,04029,CA: Kern County,2026,09,PRCP," + ",".join(["0.00"] * 29 + ["-999.99"] * 2)
    out = parse_month(line, "prcp")
    assert len(out) == 30  # September has 30 days
    assert out["prcp"].isna().sum() == 1  # Sep 30


def test_cdph_header():
    raw = "Year,Week,County,Reported Positive Cases\n2026,39,Kern,2\n2026,39,Kern,1\n"
    wnv = load_wnv(io.StringIO(raw))
    assert list(wnv.columns) == ["county", "mmwr_year", "mmwr_week", "wnv_cases"]


def test_latest_wnv_week_skips_impossible_weeks():
    wnv = pd.DataFrame({"county": ["Kern"] * 3, "mmwr_year": [2019, 2019, 2018],
                        "mmwr_week": [53, 40, 30], "wnv_cases": [1, 1, 1]})
    assert latest_wnv_week(wnv) == Week(2019, 40)  # 2019 has no week 53


def test_drought_api_cumulative_rows():
    # As the API returned Kern for 2021-07-27: cumulative, 89.41% in D4.
    w = weekly_drought(usdm_rows([100, 100, 100, 100, 89.41], none=0)).iloc[0]
    assert [w[f"usdm_d{i}"] for i in range(5)] == [0, 0, 0, pytest.approx(10.59), 89.41]
    assert w["usdm_dsci"] == pytest.approx(489.41)


def test_drought_forms_detected_row_by_row():
    # One categorical row among cumulative ones is still read correctly.
    rows = pd.concat([
        usdm_rows([90, 70, 40, 15, 0], none=10),  # cumulative
        usdm_rows([20, 30, 25, 15, 0], none=10).assign(FIPS="06019", County="Fresno County"),
    ], ignore_index=True)
    w = weekly_drought(rows).set_index("county")
    for county in ["Kern", "Fresno"]:
        assert [w.loc[county, f"usdm_d{i}"] for i in range(5)] == [20, 30, 25, 15, 0]
        assert w.loc[county, "usdm_dsci"] == 215


def test_drought_empty_response(monkeypatch):
    class Empty:
        text = ""
        url = "https://example.test"
    monkeypatch.setattr(download_drought, "get", lambda *a, **k: Empty())
    monkeypatch.setattr(download_drought, "log_download", lambda *a, **k: None)
    assert download_drought.fetch_year(2030) is None


def test_period_trims_and_keeps_early_lags():
    # Weather covers 2020 weeks 2-52. Keep weeks 5-31: the last WNV week is 31.
    dataset, _ = build(make_daily(), make_wnv(), period=(Week(2020, 5), Week(2020, 31)))
    assert dataset["mmwr_week"].min() == 5 and dataset["mmwr_week"].max() == 31
    assert len(dataset) == 2 * 27
    first = dataset.set_index(["county", "mmwr_year", "mmwr_week"]).loc[("Kern", 2020, 5)]
    assert first["tavg_lag3"] == 20.0  # reaches week 2, before the period
    assert pd.isna(first["tavg_lag4"])  # week 1 has no weather
    assert dataset["fips"].notna().all()


def test_period_past_weather_has_blank_weather():
    # Cases reported after the weather data ends keep their rows, with blank weather.
    daily = make_daily()
    daily = daily[daily["date"] < "2020-07-26"]  # weather ends after week 30
    dataset, unmatched = build(daily, make_wnv(), period=(Week(2020, 2), Week(2020, 31)))
    by_key = dataset.set_index(["county", "mmwr_year", "mmwr_week"])
    fresno31 = by_key.loc[("Fresno", 2020, 31)]
    assert fresno31["wnv_cases"] == 2 and pd.isna(fresno31["tavg"])
    assert fresno31["tavg_lag1"] == 20.0
    assert unmatched["wnv_cases"].sum() == 5  # only the impossible 2019 week 53


def test_week_without_precipitation_is_blank():
    daily = make_daily()
    daily.loc[daily["date"].between("2020-07-19", "2020-07-25"), "prcp"] = float("nan")
    dataset, _ = build(daily, make_wnv())
    by_key = dataset.set_index(["county", "mmwr_year", "mmwr_week"])
    assert pd.isna(by_key.loc[("Kern", 2020, 30), "prcp_total"])
    assert by_key.loc[("Kern", 2020, 31), "prcp_total"] == 7.0
