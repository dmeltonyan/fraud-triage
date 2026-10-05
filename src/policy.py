"""Turn fraud probabilities into actions: approve, review, or block.

The functions take a DataFrame with one row per transaction and these columns:
    day       calendar day (the review budget resets each day)
    p_fraud   calibrated fraud probability
    amt       amount in dollars

The review budget is applied with the whole day's transactions in view, as if
analysts worked through the day's queue at the end of it. A live system would
have to decide as transactions arrive (see DECISIONS.md).
"""

import pandas as pd

from src.costs import approve_cost, block_cost, review_cost

APPROVE, REVIEW, BLOCK = "approve", "review", "block"


def expected_costs(df: pd.DataFrame, costs: dict) -> pd.DataFrame:
    """Expected dollar cost of each action for every transaction."""
    return pd.DataFrame(
        {
            APPROVE: approve_cost(df["p_fraud"], df["amt"]),
            REVIEW: review_cost(df["p_fraud"], costs),
            BLOCK: block_cost(df["p_fraud"], costs),
        },
        index=df.index,
    )


def within_daily_budget(day: pd.Series, priority: pd.Series, eligible: pd.Series, budget: int) -> pd.Series:
    """True for the `budget` eligible rows with the highest priority on each day."""
    rank = priority.where(eligible).groupby(day).rank(method="first", ascending=False)
    return eligible & (rank <= budget)


def cost_based_policy(df: pd.DataFrame, config: dict, budget: int | None = None, allow_block: bool = True) -> pd.DataFrame:
    """Choose the cheapest action for each transaction, within the daily review budget.

    1. Work out the expected cost of approve, review, and block.
    2. Expected loss prevented by a review = (cheapest of approve and block) - review cost.
       It is positive exactly when review is the cheapest action.
    3. Each day, the `budget` cases with the largest loss prevented get reviewed.
    4. Any other case gets the cheaper of approve and block.

    With allow_block=False the only choices are approve and review, so the policy
    differs from the threshold policy only in how it ranks cases for review.

    Returns the expected costs, the loss prevented, and the chosen `action`.
    """
    budget = config["review"]["daily_review_budget"] if budget is None else budget
    result = expected_costs(df, config["costs"])
    options = [APPROVE, BLOCK] if allow_block else [APPROVE]

    result["loss_prevented"] = result[options].min(axis=1) - result[REVIEW]
    reviewed = within_daily_budget(df["day"], result["loss_prevented"], result["loss_prevented"] > 0, budget)
    result["action"] = result[options].idxmin(axis=1).where(~reviewed, REVIEW)
    return result


def threshold_policy(df: pd.DataFrame, budget: int) -> pd.Series:
    """Review the `budget` highest-probability transactions each day; approve the rest."""
    reviewed = within_daily_budget(df["day"], df["p_fraud"], pd.Series(True, index=df.index), budget)
    return pd.Series(APPROVE, index=df.index).where(~reviewed, REVIEW)


def approve_all(df: pd.DataFrame) -> pd.Series:
    return pd.Series(APPROVE, index=df.index)


def outcomes(df: pd.DataFrame, actions: pd.Series, costs: dict) -> dict:
    """What actually happened under `actions`, using the true is_fraud labels."""
    fraud = df["is_fraud"] == 1
    caught = fraud & actions.isin([REVIEW, BLOCK])
    missed = fraud & (actions == APPROVE)
    declined = ~fraud & (actions == BLOCK)

    fraud_lost = float(df.loc[missed, "amt"].sum())
    reviews = int((actions == REVIEW).sum())
    return {
        "fraud_dollars_lost": fraud_lost,
        "fraud_dollars_caught": float(df.loc[caught, "amt"].sum()),
        "frauds_caught": int(caught.sum()),
        "frauds_missed": int(missed.sum()),
        "reviews": reviews,
        "blocks": int((actions == BLOCK).sum()),
        "legit_declined": int(declined.sum()),
        "total_cost": fraud_lost
        + reviews * costs["review_cost_usd"]
        + int(declined.sum()) * costs["false_decline_cost_usd"],
    }
