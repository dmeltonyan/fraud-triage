"""Build the pre-scored demo sample and load it into Supabase Postgres.

Run from the project root with:
    python -m src.export_demo            build the sample and save data/demo_sample.csv only
    python -m src.export_demo --upload   also (re)load it into Postgres using DATABASE_URL from .env

The sample comes from the test months: every transaction the cost-based policy
sends to review or block at the default budget, plus random approvals up to
`demo.max_rows` in config.yaml. Uploading replaces both demo tables, so it also
clears any reviews made in the app.
"""

import argparse

import duckdb
import pandas as pd

from src.config import database_url
from src.explain import contributions, load_model, load_test_features, top_reasons
from src.load import DATA_DIR, DB_PATH, PROJECT_ROOT
from src.policy import APPROVE, BLOCK, REVIEW, cost_based_policy
from src.train import load_config

SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
LOCAL_COPY_PATH = DATA_DIR / "demo_sample.csv"

# Exactly the columns of transactions_demo in sql/schema.sql. Nothing else leaves the machine.
DEMO_COLUMNS = [
    "transaction_id", "transaction_time", "merchant", "category", "amount", "city", "state",
    "fraud_probability", "action", "cost_approve", "cost_review", "cost_block", "loss_prevented",
    "reason_1", "reason_2", "reason_3", "is_fraud",
]


def select_demo_rows(decisions: pd.DataFrame, max_rows: int, seed: int = 0) -> pd.DataFrame:
    """Every review and block case, plus random approvals up to `max_rows` in total."""
    flagged = decisions[decisions["action"].isin([REVIEW, BLOCK])]
    approved = decisions[decisions["action"] == APPROVE]
    n_approved = max(0, min(len(approved), max_rows - len(flagged)))
    sample = pd.concat([flagged, approved.sample(n_approved, random_state=seed)])
    return sample.sort_values("trans_date_trans_time")


def to_demo_table(df: pd.DataFrame, reasons: list[list[str]]) -> pd.DataFrame:
    """Rename to the Postgres columns and keep only those."""
    out = pd.DataFrame(
        {
            "transaction_id": df["trans_num"],
            "transaction_time": df["trans_date_trans_time"],
            # Every merchant name in the simulated data starts with "fraud_", legitimate ones too.
            # Showing it in the app would look like a label, so drop it.
            "merchant": df["merchant"].str.removeprefix("fraud_"),
            "category": df["category"],
            "amount": df["amt"].round(2),
            "city": df["city"],
            "state": df["state"],
            "fraud_probability": df["p_fraud"],
            "action": df["action"],
            "cost_approve": df[APPROVE],
            "cost_review": df[REVIEW],
            "cost_block": df[BLOCK],
            "loss_prevented": df["loss_prevented"],
            "reason_1": [r[0] for r in reasons],
            "reason_2": [r[1] for r in reasons],
            "reason_3": [r[2] for r in reasons],
            "is_fraud": df["is_fraud"].astype(bool),
        }
    )
    return out[DEMO_COLUMNS].reset_index(drop=True)


def build_demo(config: dict) -> pd.DataFrame:
    df = load_test_features()
    df = df.join(cost_based_policy(df, config))
    sample = select_demo_rows(df, config["demo"]["max_rows"])

    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        places = con.sql("SELECT trans_num, merchant, city, state FROM transactions").df()
    sample = sample.merge(places, on="trans_num", how="left").set_index(sample.index)

    model = load_model()
    contrib = contributions(model, sample)
    reasons = [top_reasons(sample.loc[i], contrib.loc[i]) for i in sample.index]
    return to_demo_table(sample, reasons)


def upload(demo: pd.DataFrame) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url())
    with engine.begin() as con:  # one transaction: all or nothing
        con.exec_driver_sql(SCHEMA_PATH.read_text())
        con.execute(text("TRUNCATE reviews, transactions_demo"))
        demo.to_sql("transactions_demo", con, if_exists="append", index=False, method="multi", chunksize=1000)
        counts = con.execute(text("SELECT action, COUNT(*) FROM transactions_demo GROUP BY action ORDER BY action")).all()
    print("Rows in Supabase by action:")
    for action, n in counts:
        print(f"  {action:>8}: {n:,}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upload", action="store_true", help="load the sample into Postgres (needs DATABASE_URL)")
    args = parser.parse_args()

    demo = build_demo(load_config())
    demo.to_csv(LOCAL_COPY_PATH, index=False)
    print(f"Demo sample: {len(demo):,} rows, {int(demo['is_fraud'].sum()):,} fraud. Saved {LOCAL_COPY_PATH.relative_to(PROJECT_ROOT)}")
    print(demo["action"].value_counts().to_string())

    if args.upload:
        upload(demo)


if __name__ == "__main__":
    main()
