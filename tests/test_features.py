import duckdb
import pandas as pd
import pytest

from src.features import FEATURE_COLUMNS, build_features

# Six hand-made transactions on two cards. Every card lives at (40.0, -75.0);
# merchants are at the same spot unless a test says otherwise.
#   num  card  time                 amount
TRANSACTIONS = [
    ("t1", 1, "2020-01-01 10:00:00", 10.0),
    ("t2", 1, "2020-01-01 10:30:00", 20.0),
    ("t3", 1, "2020-01-01 11:15:00", 30.0),
    ("t4", 2, "2020-01-01 10:20:00", 50.0),
    ("t5", 1, "2020-01-02 10:45:00", 100.0),
    ("t6", 2, "2020-01-01 10:20:00", 70.0),  # same card and same second as t4
]
LATER_TRANSACTION = ("t7", 1, "2020-01-03 09:00:00", 500.0)


def make_db(rows):
    """An in-memory DuckDB with a `transactions` table holding `rows`."""
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE transactions (trans_num VARCHAR, cc_num BIGINT, "
        "trans_date_trans_time TIMESTAMP, amt DOUBLE, category VARCHAR, "
        'lat DOUBLE, "long" DOUBLE, merch_lat DOUBLE, merch_long DOUBLE, is_fraud INTEGER)'
    )
    con.executemany(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, 'misc_net', 40.0, -75.0, 40.0, -75.0, 0)",
        rows,
    )
    return con


def features_by_id(con):
    """Build features and return {trans_num: {column: value}}."""
    build_features(con)
    df = con.sql("SELECT * FROM features").df()
    return df.set_index("trans_num").to_dict(orient="index")


@pytest.fixture
def features():
    return features_by_id(make_db(TRANSACTIONS))


def test_counts_are_correct(features):
    # t2: t1 was 30 minutes earlier
    assert features["t2"]["txn_count_1h"] == 1
    # t3: t2 is 45 minutes earlier, t1 is 75 minutes earlier (outside the hour)
    assert features["t3"]["txn_count_1h"] == 1
    assert features["t3"]["txn_count_24h"] == 2
    # t5: 23.5 hours after t3, 24.25 after t2, 24.75 after t1
    assert features["t5"]["txn_count_1h"] == 0
    assert features["t5"]["txn_count_24h"] == 1


def test_first_transaction_has_no_history(features):
    assert features["t1"]["txn_count_1h"] == 0
    assert features["t1"]["txn_count_24h"] == 0
    assert pd.isna(features["t1"]["amt_to_median_ratio"])  # no earlier amounts to compare with


def test_amount_ratio_uses_median_of_earlier_amounts(features):
    assert features["t2"]["amt_to_median_ratio"] == pytest.approx(20 / 10)
    assert features["t3"]["amt_to_median_ratio"] == pytest.approx(30 / 15)  # median(10, 20)
    assert features["t5"]["amt_to_median_ratio"] == pytest.approx(100 / 20)  # median(10, 20, 30)


def test_same_second_transactions_do_not_see_each_other(features):
    for trans_num in ["t4", "t6"]:
        assert features[trans_num]["txn_count_1h"] == 0
        assert features[trans_num]["txn_count_24h"] == 0


def test_adding_a_later_transaction_changes_no_earlier_features():
    # The leak test: if any feature looked at the future, adding t7 would
    # change some earlier transaction's values.
    before = features_by_id(make_db(TRANSACTIONS))
    after = features_by_id(make_db(TRANSACTIONS + [LATER_TRANSACTION]))

    for trans_num, row in before.items():
        for column in FEATURE_COLUMNS:
            old, new = row[column], after[trans_num][column]
            assert old == new or (pd.isna(old) and pd.isna(new)), f"{trans_num}.{column} changed from {old} to {new}"


def test_time_features():
    con = make_db([("t1", 1, "2020-01-01 23:30:00", 10.0)])  # 2020-01-01 was a Wednesday
    row = features_by_id(con)["t1"]
    assert row["hour_of_day"] == 23
    assert row["day_of_week"] == 3  # 0 = Sunday


def test_distance_is_one_degree_of_latitude():
    con = make_db([("t1", 1, "2020-01-01 10:00:00", 10.0)])
    con.execute("UPDATE transactions SET merch_lat = 41.0")  # 1 degree north of home
    assert features_by_id(con)["t1"]["distance_km"] == pytest.approx(111.19, abs=0.01)


def test_no_forbidden_columns_are_features():
    forbidden = {"gender", "dob", "age", "first", "last", "street", "city", "state", "zip", "job", "lat", "long", "city_pop"}
    assert forbidden.isdisjoint(FEATURE_COLUMNS)
