import pandas as pd
import pytest

from src.features import FEATURE_COLUMNS
from src.train import CATEGORICAL, LOG_NUMERIC, NUMERIC, recall_at_top, split_by_time


def make_df():
    times = [
        "2020-06-30 23:59:59",  # last moment of train
        "2020-07-01 00:00:00",  # exactly on train_end: first moment of validation
        "2020-09-15 12:00:00",
        "2020-10-01 00:00:00",  # exactly on validation_end: first moment of test
        "2020-12-31 23:59:59",
        "2019-01-01 00:00:00",
    ]
    return pd.DataFrame({"trans_num": list("abcdef"), "trans_date_trans_time": pd.to_datetime(times)})


def test_split_puts_every_row_in_exactly_one_set():
    df = make_df()
    train, validation, test = split_by_time(df, "2020-07-01", "2020-10-01")
    ids = list(train.trans_num) + list(validation.trans_num) + list(test.trans_num)
    assert sorted(ids) == sorted(df.trans_num)  # no row lost, none duplicated


def test_split_is_in_time_order():
    train, validation, test = split_by_time(make_df(), "2020-07-01", "2020-10-01")
    assert train.trans_date_trans_time.max() < validation.trans_date_trans_time.min()
    assert validation.trans_date_trans_time.max() < test.trans_date_trans_time.min()


def test_cutoff_moment_belongs_to_the_later_set():
    train, validation, test = split_by_time(make_df(), "2020-07-01", "2020-10-01")
    assert set(train.trans_num) == {"a", "f"}
    assert set(validation.trans_num) == {"b", "c"}
    assert set(test.trans_num) == {"d", "e"}


def test_recall_at_top():
    # 10 transactions, 2 fraud. Reviewing the top 20% means the 2 highest scores.
    y_true = [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
    scores = [0.9, 0.1, 0.2, 0.8, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1]
    recall, precision = recall_at_top(y_true, scores, 0.2)
    assert recall == pytest.approx(0.5)  # caught 1 of 2 frauds
    assert precision == pytest.approx(0.5)  # 1 of the 2 reviewed was fraud


def test_every_feature_is_prepared_exactly_once():
    prepared = LOG_NUMERIC + NUMERIC + CATEGORICAL
    assert sorted(prepared) == sorted(FEATURE_COLUMNS)
