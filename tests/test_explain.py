import math

import pandas as pd

from src.explain import describe, top_reasons

ROW = pd.Series(
    {
        "amt": 1240.0,
        "amt_to_median_ratio": 9.0,
        "txn_count_1h": 0,
        "txn_count_24h": 1,
        "hour_of_day": 23,
        "day_of_week": 0,
        "distance_km": 84.6,
        "category": "shopping_net",
    }
)


def test_describe_each_feature():
    assert describe("amt", ROW) == "$1,240.00 purchase"
    assert describe("amt_to_median_ratio", ROW) == "$1,240 is 9.0 times this card's typical purchase ($138)"
    assert describe("txn_count_1h", ROW) == "no other purchases on this card in the past hour"
    assert describe("txn_count_24h", ROW) == "1 other purchase on this card in the past 24 hours"
    assert describe("hour_of_day", ROW) == "made between 23:00 and 23:59"
    assert describe("day_of_week", ROW) == "made on a Sunday"
    assert describe("distance_km", ROW) == "merchant is 85 km from the cardholder's home"
    assert describe("category", ROW) == "online shopping merchant"


def test_first_purchase_has_no_ratio():
    row = ROW.copy()
    row["amt_to_median_ratio"] = math.nan
    assert "first purchase on this card" in describe("amt_to_median_ratio", row)


def test_top_reasons_are_largest_by_size_with_direction():
    contribution = pd.Series(
        {"amt": 2.5, "amt_to_median_ratio": 0.4, "txn_count_1h": 0.0, "txn_count_24h": -0.1,
         "hour_of_day": 1.2, "day_of_week": 0.05, "distance_km": 0.01, "category": -0.8}
    )
    assert top_reasons(ROW, contribution) == [
        "$1,240.00 purchase (raises fraud risk)",
        "made between 23:00 and 23:59 (raises fraud risk)",
        "online shopping merchant (lowers fraud risk)",
    ]
