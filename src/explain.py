"""Plain-language reasons behind a transaction's fraud score, from SHAP values.

Run from the project root with:  python -m src.explain
(prints reasons for one approved, one reviewed and one blocked test transaction,
and saves reports/figures/shap_summary.png)

SHAP splits the model's raw score (in log-odds) into one contribution per
feature: positive pushes toward fraud, negative away from it, and the
contributions plus a base value add up exactly to the score. We get them from
LightGBM's built-in TreeSHAP (pred_contrib=True), which gives the same numbers
as the shap package's TreeExplainer, so scoring doesn't depend on shap.

Why explaining the raw model is fine although decisions use calibrated
probabilities: Platt calibration is a straight line in log-odds,
calibrated = slope x raw + intercept, with a positive slope (0.91). So each
feature's contribution to the calibrated log-odds is its raw contribution times
the same positive number. The ranking and direction of every reason is
unchanged; only the base value moves.
"""

import math

import duckdb
import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.compare import load_test_scores
from src.features import FEATURE_COLUMNS
from src.load import DB_PATH, PROJECT_ROOT
from src.policy import APPROVE, BLOCK, REVIEW, cost_based_policy
from src.train import MODELS_DIR, lightgbm_inputs, load_config

SUMMARY_PLOT_PATH = PROJECT_ROOT / "reports" / "figures" / "shap_summary.png"

CATEGORY_NAMES = {
    "entertainment": "entertainment",
    "food_dining": "food and dining",
    "gas_transport": "gas and transport",
    "grocery_net": "online grocery",
    "grocery_pos": "in-store grocery",
    "health_fitness": "health and fitness",
    "home": "home",
    "kids_pets": "kids and pets",
    "misc_net": "online miscellaneous",
    "misc_pos": "in-store miscellaneous",
    "personal_care": "personal care",
    "shopping_net": "online shopping",
    "shopping_pos": "in-store shopping",
    "travel": "travel",
}
DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]  # DuckDB: 0 = Sunday


def load_model() -> dict:
    """{"model": fitted LGBMClassifier, "categories": training category list}, saved by src.train."""
    return joblib.load(MODELS_DIR / "lightgbm.joblib")


def contributions(model: dict, df: pd.DataFrame) -> pd.DataFrame:
    """SHAP contribution of each feature to each row's raw log-odds score."""
    values = model["model"].predict(lightgbm_inputs(df, model["categories"]), pred_contrib=True)
    return pd.DataFrame(values[:, :-1], columns=FEATURE_COLUMNS, index=df.index)  # last column is the base value


def count_phrase(n: int, period: str) -> str:
    if n == 0:
        return f"no other purchases on this card in the past {period}"
    return f"{n} other purchase{'s' if n != 1 else ''} on this card in the past {period}"


def describe(feature: str, row: pd.Series) -> str:
    """One feature's value for this transaction, in words an analyst would use."""
    value = row[feature]
    if feature == "amt":
        return f"${value:,.2f} purchase"
    if feature == "amt_to_median_ratio":
        if pd.isna(value):
            return "first purchase on this card, so there is no spending history to compare with"
        typical = row["amt"] / value
        times = f"{value:.0f}" if value >= 10 else f"{value:.1f}"
        return f"${row['amt']:,.0f} is {times} times this card's typical purchase (${typical:,.0f})"
    if feature == "txn_count_1h":
        return count_phrase(int(value), "hour")
    if feature == "txn_count_24h":
        return count_phrase(int(value), "24 hours")
    if feature == "hour_of_day":
        return f"made between {int(value):02d}:00 and {int(value):02d}:59"
    if feature == "day_of_week":
        return f"made on a {DAY_NAMES[int(value)]}"
    if feature == "distance_km":
        return f"merchant is {value:,.0f} km from the cardholder's home"
    if feature == "category":
        return f"{CATEGORY_NAMES.get(value, value)} merchant"
    raise ValueError(f"No description for feature {feature!r}")


def top_reasons(row: pd.Series, contribution: pd.Series, n: int = 3) -> list[str]:
    """The `n` features that moved this score the most, either way, largest first."""
    strongest = contribution.abs().sort_values(ascending=False).index[:n]
    return [
        f"{describe(feature, row)} ({'raises' if contribution[feature] > 0 else 'lowers'} fraud risk)"
        for feature in strongest
    ]


def explain(df: pd.DataFrame, model: dict | None = None, n: int = 3) -> list[list[str]]:
    """Top reasons for every row of a features DataFrame."""
    model = model or load_model()
    contrib = contributions(model, df)
    return [top_reasons(df.loc[i], contrib.loc[i], n) for i in df.index]


def plot_summary(model: dict, df: pd.DataFrame) -> None:
    """SHAP summary (beeswarm) plot: each dot is one transaction's contribution from one feature."""
    import shap  # only needed for this plot

    X = lightgbm_inputs(df, model["categories"])
    X["category"] = X["category"].cat.codes  # the plot colours by number, so use category codes
    shap.summary_plot(contributions(model, df).to_numpy(), X, show=False)
    plt.title("What drives the fraud score (sample of test transactions)")
    SUMMARY_PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(SUMMARY_PLOT_PATH, dpi=120, bbox_inches="tight")
    plt.close("all")


def load_test_features() -> pd.DataFrame:
    """Test-month features joined with calibrated scores, in the same order as load_test_scores()."""
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        features = con.sql(
            "SELECT f.* FROM features f JOIN scores s USING (trans_num) WHERE s.set_name = 'test'"
        ).df()
    scores = load_test_scores()
    return scores.merge(features.drop(columns=["amt", "is_fraud", "trans_date_trans_time"]), on="trans_num")


def main() -> None:
    config = load_config()
    model = load_model()
    df = load_test_features()
    decisions = cost_based_policy(df, config)

    for action in [APPROVE, REVIEW, BLOCK]:
        i = decisions.index[decisions["action"] == action].to_series().sample(1, random_state=0).iloc[0]
        row, cost = df.loc[i], decisions.loc[i]
        print(f"{action.upper()}: {row['trans_num']} | {row['trans_date_trans_time']} | "
              f"${row['amt']:,.2f} | {CATEGORY_NAMES[row['category']]} | fraud probability {row['p_fraud']:.2%} | "
              f"actually {'fraud' if row['is_fraud'] else 'legitimate'}")
        print(f"  expected cost: approve ${cost[APPROVE]:,.2f}, review ${cost[REVIEW]:,.2f}, block ${cost[BLOCK]:,.2f}")
        for reason in explain(df.loc[[i]], model)[0]:
            print(f"  - {reason}")
        print()

    plot_summary(model, df.sample(5000, random_state=0))
    print(f"Saved {SUMMARY_PLOT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
