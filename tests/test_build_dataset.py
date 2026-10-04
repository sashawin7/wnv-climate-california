"""Checks the join logic on small made-up data. Run with:  pytest"""

import pandas as pd

from src.build_dataset import build


def make_daily() -> pd.DataFrame:
    dates = pd.date_range("2020-01-05", "2020-12-26")  # MMWR 2020 weeks 2-52
    rows = [
        {"date": d, "county": c, "tmax": 30.0, "tmin": 10.0, "tavg": 20.0, "prcp": 1.0}
        for c in ["Kern County", "Fresno"]
        for d in dates
    ]
    return pd.DataFrame(rows)


def make_wnv() -> pd.DataFrame:
    return pd.DataFrame({
        "county": ["Kern", "Kern", "Fresno", "Kern"],
        "mmwr_year": [2020, 2020, 2020, 2019],
        "mmwr_week": [30, 30, 31, 53],  # duplicate row; 2019 has no MMWR week 53
        "wnv_cases": [8, 1, 2, 5],
    })


def test_build():
    dataset, unmatched = build(make_daily(), make_wnv())
    by_key = dataset.set_index(["county", "mmwr_year", "mmwr_week"])

    assert dataset["county"].nunique() == 2  # "Kern County" and "Kern" are matched
    assert len(dataset) == 2 * 51
    assert by_key.loc[("Kern", 2020, 30), "wnv_cases"] == 9  # duplicates summed
    assert by_key.loc[("Fresno", 2020, 31), "wnv_cases"] == 2
    assert dataset["wnv_cases"].sum() == 11  # every other week filled with 0

    week = by_key.loc[("Kern", 2020, 30)]
    assert week["n_days"] == 7
    assert week["prcp_total"] == 7.0
    assert week["tavg"] == 20.0
    assert week["tavg_lag1"] == 20.0
    assert pd.isna(by_key.loc[("Kern", 2020, 2), "tavg_lag1"])  # no earlier week

    assert unmatched["wnv_cases"].sum() == 5  # reported, not silently dropped
