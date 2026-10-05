import pandas as pd
import pytest

from src.features import FEATURE_COLUMNS
from src.train import CATEGORICAL, LOG_NUMERIC, NUMERIC, lightgbm_inputs, recall_at_top, split_by_time


CUTOFFS = {"train_end": "2020-07-01", "tuning_end": "2020-09-01", "calibration_end": "2020-10-01"}


def make_df():
    times = [
        "2020-06-30 23:59:59",  # a: last moment of train
        "2020-07-01 00:00:00",  # b: exactly on train_end, so first moment of tuning
        "2020-08-15 12:00:00",  # c: tuning
        "2020-09-01 00:00:00",  # d: exactly on tuning_end, so first moment of calibration
        "2020-10-01 00:00:00",  # e: exactly on calibration_end, so first moment of test
        "2020-12-31 23:59:59",  # f: test
        "2019-01-01 00:00:00",  # g: train
    ]
    return pd.DataFrame({"trans_num": list("abcdefg"), "trans_date_trans_time": pd.to_datetime(times)})


def test_split_puts_every_row_in_exactly_one_set():
    df = make_df()
    parts = split_by_time(df, **CUTOFFS)
    ids = [trans_num for part in parts for trans_num in part.trans_num]
    assert sorted(ids) == sorted(df.trans_num)  # no row lost, none duplicated


def test_split_is_in_time_order():
    parts = split_by_time(make_df(), **CUTOFFS)
    for earlier, later in zip(parts, parts[1:]):
        assert earlier.trans_date_trans_time.max() < later.trans_date_trans_time.min()


def test_cutoff_moment_belongs_to_the_later_set():
    train, tuning, calibration, test = split_by_time(make_df(), **CUTOFFS)
    assert set(train.trans_num) == {"a", "g"}
    assert set(tuning.trans_num) == {"b", "c"}
    assert set(calibration.trans_num) == {"d"}
    assert set(test.trans_num) == {"e", "f"}


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


def test_lightgbm_category_codes_match_training():
    # A set that lacks some training categories must still use the training codes,
    # otherwise "grocery_pos" could mean a different code at test time.
    row = {column: 1.0 for column in FEATURE_COLUMNS}
    df = pd.DataFrame([{**row, "category": "travel"}, {**row, "category": "never_seen"}])
    X = lightgbm_inputs(df, categories=["gas_transport", "grocery_pos", "travel"])
    assert list(X.columns) == FEATURE_COLUMNS
    assert list(X["category"].cat.categories) == ["gas_transport", "grocery_pos", "travel"]
    assert X["category"].cat.codes.tolist() == [2, -1]  # unseen category becomes missing
