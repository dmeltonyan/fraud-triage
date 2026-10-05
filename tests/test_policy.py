import copy

import numpy as np
import pandas as pd
import pytest

from src.policy import APPROVE, BLOCK, REVIEW, cost_based_policy, outcomes, threshold_policy
from src.train import load_config

CONFIG = {
    "costs": {"review_cost_usd": 5.0, "false_decline_cost_usd": 10.0},
    "review": {"daily_review_budget": 2},
}


def make_df(rows):
    """rows: (day, p_fraud, amt, is_fraud)"""
    return pd.DataFrame(rows, columns=["day", "p_fraud", "amt", "is_fraud"])


def test_three_transaction_example():
    # A: p=0.001, $20   -> approve $0.02, review $5, block $9.99   -> approve
    # B: p=0.05,  $400  -> approve $20,   review $5, block $9.50   -> review (prevents $4.50)
    # C: p=0.95,  $900  -> approve $855,  review $5, block $0.50   -> block
    df = make_df([("d1", 0.001, 20, 0), ("d1", 0.05, 400, 0), ("d1", 0.95, 900, 1)])
    result = cost_based_policy(df, CONFIG)
    assert result["action"].tolist() == [APPROVE, REVIEW, BLOCK]
    assert result.loc[1, "loss_prevented"] == pytest.approx(4.5)


def test_daily_budget_is_never_exceeded():
    rng = np.random.default_rng(0)
    n = 3000
    df = make_df(zip(rng.choice(["d1", "d2", "d3"], n), rng.uniform(0.01, 0.3, n), rng.uniform(50, 1000, n), [0] * n))
    for budget in [0, 1, 2, 10]:
        result = cost_based_policy(df, CONFIG, budget=budget)
        per_day = result["action"].eq(REVIEW).groupby(df["day"]).sum()
        assert (per_day <= budget).all()
        assert per_day.max() == budget  # plenty of candidates, so every slot is used


def test_budget_goes_to_largest_loss_prevented_and_overflow_falls_back():
    # p = 0.02 everywhere, so block costs $9.80 and approve (p x amount) is the alternative:
    #   $300: approve $6 -> review prevents $1     (smallest: falls back to approve)
    #   $450: approve $9 -> review prevents $4
    #   $400: approve $8 -> review prevents $3
    df = make_df([("d1", 0.02, 300, 0), ("d1", 0.02, 450, 0), ("d1", 0.02, 400, 0)])
    result = cost_based_policy(df, CONFIG)
    assert result["loss_prevented"].tolist() == pytest.approx([1.0, 4.0, 3.0])
    assert result["action"].tolist() == [APPROVE, REVIEW, REVIEW]

    # When block is cheaper than approve, the overflow case is blocked instead.
    # p = 0.05: block $9.50 beats approve ($20+), so every case prevents $4.50; ties go by row order.
    df = make_df([("d1", 0.05, 400, 0), ("d1", 0.05, 1000, 0), ("d1", 0.05, 700, 0)])
    assert cost_based_policy(df, CONFIG)["action"].tolist() == [REVIEW, REVIEW, BLOCK]


def test_large_high_probability_transaction_is_never_approved():
    # Even when the day's review budget is used up, a $2,000 case at p=0.9 must not be approved.
    df = make_df([("d1", 0.9, 2000, 1)] * 5)
    for budget in [0, 2, 10]:
        assert APPROVE not in cost_based_policy(df, CONFIG, budget=budget)["action"].tolist()


def test_small_low_probability_transaction_is_approved():
    df = make_df([("d1", 0.002, 15, 0)])
    assert cost_based_policy(df, CONFIG)["action"].tolist() == [APPROVE]


def test_changing_config_changes_decisions_without_code_changes():
    # Uses the real config.yaml. p=0.04 on $300: approve $12, review $5, block $9.60 -> review.
    config = load_config()
    df = make_df([("d1", 0.04, 300, 0)])
    assert cost_based_policy(df, config)["action"].tolist() == [REVIEW]

    expensive_reviews = copy.deepcopy(config)
    expensive_reviews["costs"]["review_cost_usd"] = 15.0  # now review $15 > block $9.60
    assert cost_based_policy(df, expensive_reviews)["action"].tolist() == [BLOCK]


def test_threshold_policy_reviews_top_probabilities_each_day():
    df = make_df([("d1", 0.9, 10, 1), ("d1", 0.1, 999, 0), ("d1", 0.5, 50, 0), ("d2", 0.01, 5, 0)])
    assert threshold_policy(df, budget=2).tolist() == [REVIEW, APPROVE, REVIEW, REVIEW]


def test_outcomes_accounting():
    df = make_df([("d1", 0, 100, 1), ("d1", 0, 200, 1), ("d1", 0, 50, 0), ("d1", 0, 70, 0)])
    actions = pd.Series([APPROVE, REVIEW, BLOCK, REVIEW])
    result = outcomes(df, actions, CONFIG["costs"])
    assert result["fraud_dollars_lost"] == 100  # approved fraud
    assert result["fraud_dollars_caught"] == 200  # reviewed fraud
    assert result["reviews"] == 2
    assert result["legit_declined"] == 1  # blocked a legitimate $50
    assert result["total_cost"] == 100 + 2 * 5 + 1 * 10
