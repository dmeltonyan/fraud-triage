import numpy as np
import pytest

from src.calibrate import PlattCalibrator, log_odds, reliability_table


def test_log_odds():
    assert log_odds([0.5])[0] == pytest.approx(0.0)
    assert log_odds([0.9])[0] == pytest.approx(np.log(9))
    assert np.isfinite(log_odds([0.0, 1.0])).all()  # clipped, not infinite


def test_platt_undoes_a_known_overconfidence():
    # Make labels from true probabilities, then pretend a model reported every
    # probability with its odds multiplied by 13 (like scale_pos_weight = 13).
    rng = np.random.default_rng(0)
    true_p = rng.uniform(0.001, 0.2, size=200_000)
    y = rng.random(true_p.size) < true_p
    inflated = 1 / (1 + np.exp(-(log_odds(true_p) + np.log(13))))

    calibrator = PlattCalibrator().fit(inflated, y)

    assert calibrator.slope == pytest.approx(1.0, abs=0.05)
    assert calibrator.intercept == pytest.approx(-np.log(13), abs=0.1)
    assert calibrator.predict(inflated).mean() == pytest.approx(y.mean(), rel=0.02)


def test_reliability_table_counts_and_rates():
    y = [0, 0, 1, 1]
    p = [0.0005, 0.0005, 0.5, 0.5]
    table = reliability_table(y, p)
    assert table["n"].tolist() == [2, 2]
    assert table["actual"].tolist() == [0.0, 1.0]
    assert table["predicted"].tolist() == pytest.approx([0.0005, 0.5])
