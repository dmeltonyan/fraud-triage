"""Compare decision policies on the test months (Oct-Dec 2020).

Run from the project root with:  python -m src.compare
(needs the `scores` table, built by python -m src.train)

Policies:
  approve_all        approve everything
  threshold          each day, review the highest-probability cases up to the budget; approve the rest
  cost_based         the full policy: cheapest expected action, review budget by loss prevented,
                     overflow to the cheaper of approve or block
  cost_review_only   cost-based ranking but no blocking, so it differs from `threshold`
                     only in ranking by expected dollars instead of probability
"""

import copy
import json

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.load import DB_PATH, PROJECT_ROOT
from src.policy import approve_all, cost_based_policy, outcomes, threshold_policy
from src.train import load_config

RESULTS_PATH = PROJECT_ROOT / "reports" / "policy_results.json"
BUDGET_CURVE_PATH = PROJECT_ROOT / "reports" / "figures" / "budget_curve.png"

POLICY_LABELS = {
    "approve_all": "Approve everything",
    "threshold": "Threshold (top probabilities)",
    "cost_based": "Cost-based (approve / review / block)",
    "cost_review_only": "Cost-based ranking, no blocking",
}


def load_test_scores() -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        df = con.sql(
            "SELECT trans_num, trans_date_trans_time, amt, is_fraud, p_fraud "
            "FROM scores WHERE set_name = 'test' ORDER BY trans_date_trans_time, trans_num"
        ).df()
    df["day"] = df["trans_date_trans_time"].dt.date
    df["month"] = df["trans_date_trans_time"].dt.strftime("%Y-%m")
    return df


def all_actions(df: pd.DataFrame, config: dict, budget: int) -> dict[str, pd.Series]:
    """Each policy's action for every transaction at one daily budget."""
    return {
        "approve_all": approve_all(df),
        "threshold": threshold_policy(df, budget),
        "cost_based": cost_based_policy(df, config, budget)["action"],
        "cost_review_only": cost_based_policy(df, config, budget, allow_block=False)["action"],
    }


def summarize(df: pd.DataFrame, config: dict, budget: int) -> dict:
    return {name: outcomes(df, actions, config["costs"]) for name, actions in all_actions(df, config, budget).items()}


def by_month(df: pd.DataFrame, config: dict, budget: int) -> dict:
    actions = all_actions(df, config, budget)
    result = {}
    for month, rows in df.groupby("month"):
        days = rows["day"].nunique()
        result[month] = {
            "transactions_per_day": len(rows) / days,
            "frauds_per_day": rows["is_fraud"].sum() / days,
            "fraud_dollars": float(rows.loc[rows["is_fraud"] == 1, "amt"].sum()),
            "policies": {name: outcomes(rows, a.loc[rows.index], config["costs"]) for name, a in actions.items()},
        }
    return result


def plot_budget_curve(curve: dict, approve_all_lost: float, default_budget: int) -> None:
    budgets = sorted(curve)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(approve_all_lost / 1000, color="grey", linestyle=":", label=POLICY_LABELS["approve_all"])
    for name, style in [("threshold", "o-"), ("cost_review_only", "s--"), ("cost_based", "^-")]:
        lost = [curve[b][name]["fraud_dollars_lost"] / 1000 for b in budgets]
        ax.plot(budgets, lost, style, label=POLICY_LABELS[name])
    ax.axvline(default_budget, color="lightgrey", zorder=0)
    ax.set_xlabel("daily review budget (cases per day)")
    ax.set_ylabel("fraud dollars lost, Oct-Dec 2020 ($ thousands)")
    ax.set_title("Fraud lost vs review budget (test months)")
    ax.set_ylim(bottom=0)
    ax.legend()
    BUDGET_CURVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(BUDGET_CURVE_PATH, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    config = load_config()
    evaluation = config["evaluation"]
    default_budget = config["review"]["daily_review_budget"]
    df = load_test_scores()

    curve = {budget: summarize(df, config, budget) for budget in evaluation["budget_curve"]}
    default = summarize(df, config, default_budget)
    months = by_month(df, config, default_budget)

    sensitivity = {}
    for multiplier in evaluation["review_cost_multipliers"]:
        changed = copy.deepcopy(config)
        changed["costs"]["review_cost_usd"] *= multiplier
        sensitivity[f"review_cost_x{multiplier}"] = {
            "review_cost_usd": changed["costs"]["review_cost_usd"],
            "policies": summarize(df, changed, default_budget),
        }

    plot_budget_curve(curve, default["approve_all"]["fraud_dollars_lost"], default_budget)

    results = {
        "test_months": sorted(df["month"].unique().tolist()),
        "transactions": len(df),
        "frauds": int(df["is_fraud"].sum()),
        "fraud_dollars": float(df.loc[df["is_fraud"] == 1, "amt"].sum()),
        "costs": config["costs"],
        "default_budget": default_budget,
        "default": default,
        "budget_curve": {str(b): r for b, r in curve.items()},
        "by_month": months,
        "review_cost_sensitivity": sensitivity,
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")

    print(f"Test months: {len(df):,} transactions, {results['frauds']:,} frauds, "
          f"${results['fraud_dollars']:,.0f} of fraud\n")

    def table(policies: dict, title: str) -> None:
        print(title)
        print(f"{'':>18} {'fraud lost':>11} {'caught':>11} {'reviews':>8} {'blocks':>7} {'legit declined':>15} {'total cost':>11}")
        for name, o in policies.items():
            print(f"{name:>18} {o['fraud_dollars_lost']:>11,.0f} {o['fraud_dollars_caught']:>11,.0f} {o['reviews']:>8,} "
                  f"{o['blocks']:>7,} {o['legit_declined']:>15,} {o['total_cost']:>11,.0f}")
        print()

    table(default, f"Default budget ({default_budget}/day):")

    print("Budget curve, fraud dollars lost:")
    print(f"{'budget':>7} " + " ".join(f"{n:>18}" for n in ["threshold", "cost_review_only", "cost_based"]))
    for budget, r in curve.items():
        print(f"{budget:>7} " + " ".join(f"{r[n]['fraud_dollars_lost']:>18,.0f}" for n in ["threshold", "cost_review_only", "cost_based"]))
    print()

    print(f"By month at {default_budget}/day (fraud lost / total cost):")
    for month, m in months.items():
        cells = " | ".join(
            f"{n} {m['policies'][n]['fraud_dollars_lost']:,.0f} / {m['policies'][n]['total_cost']:,.0f}"
            for n in ["threshold", "cost_review_only", "cost_based"]
        )
        print(f"{month}: {m['transactions_per_day']:,.0f} txns/day, {m['frauds_per_day']:.1f} frauds/day | {cells}")
    print()

    for label, s in sensitivity.items():
        table(s["policies"], f"Review cost ${s['review_cost_usd']:.2f} ({label}):")

    print(f"Saved {RESULTS_PATH.relative_to(PROJECT_ROOT)} and {BUDGET_CURVE_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
