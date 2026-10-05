"""Hand-checkable examples, all with review = $5 and false decline = $10."""

import numpy as np
import pytest

from src.costs import approve_cost, block_cost, review_cost

COSTS = {"review_cost_usd": 5.0, "false_decline_cost_usd": 10.0}


def test_approve_cost():
    # 2% chance of fraud on $300: 0.02 x 300 = $6
    assert approve_cost(0.02, 300) == pytest.approx(6.0)


def test_review_cost_is_flat():
    # Always $5, however likely fraud is
    assert review_cost(0.02, COSTS) == pytest.approx(5.0)
    assert review_cost(0.9, COSTS) == pytest.approx(5.0)


def test_block_cost():
    # 2% fraud means 98% legitimate: 0.98 x 10 = $9.80
    assert block_cost(0.02, COSTS) == pytest.approx(9.8)
    # 90% fraud: 0.10 x 10 = $1
    assert block_cost(0.9, COSTS) == pytest.approx(1.0)


def test_worked_example_cheapest_action():
    # p = 0.02, $300: approve $6.00, review $5.00, block $9.80 -> review is cheapest
    costs = [approve_cost(0.02, 300), review_cost(0.02, COSTS), block_cost(0.02, COSTS)]
    assert np.argmin(costs) == 1


def test_functions_work_on_whole_columns():
    p = np.array([0.0, 0.5, 1.0])
    amount = np.array([100.0, 100.0, 100.0])
    assert approve_cost(p, amount).tolist() == [0.0, 50.0, 100.0]
    assert review_cost(p, COSTS).tolist() == [5.0, 5.0, 5.0]
    assert block_cost(p, COSTS).tolist() == [10.0, 5.0, 0.0]
