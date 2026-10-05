"""The work behind the endpoints: look up transactions, score them, apply the policy, save reviews.

Scoring is by transaction ID: the card-history features were built in step 4 from
earlier transactions only, so a transaction must already be in the database.
"""

from datetime import date, datetime

import duckdb
import joblib
import pandas as pd

from src.explain import contributions, top_reasons
from src.policy import APPROVE, BLOCK, REVIEW, cost_based_policy
from src.train import MODELS_DIR, lightgbm_inputs


class NotFound(Exception):
    """Raised for an unknown transaction ID or a date with no transactions."""


# Feature columns plus the merchant name, which lives in the raw transactions table.
SELECT_TRANSACTIONS = """
    SELECT f.*, t.merchant
    FROM features f JOIN transactions t USING (trans_num)
"""


class FraudService:
    def __init__(self, db_path, config: dict, load_models: bool = True):
        self.db_path = str(db_path)
        self.config = config
        if load_models:  # once, at startup
            self.model = joblib.load(MODELS_DIR / "lightgbm.joblib")
            self.calibrator = joblib.load(MODELS_DIR / "calibrator.joblib")
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS reviews ("
                "transaction_id VARCHAR, decision VARCHAR, note VARCHAR, reviewed_at TIMESTAMP)"
            )

    def _connect(self):
        # A short-lived connection per call, so the file isn't locked between requests.
        return duckdb.connect(self.db_path)

    # Scoring. Tests replace these two with fakes so they don't need trained model files.
    def probabilities(self, df: pd.DataFrame) -> pd.Series:
        raw = self.model["model"].predict_proba(lightgbm_inputs(df, self.model["categories"]))[:, 1]
        return pd.Series(self.calibrator.predict(raw), index=df.index)

    def reasons(self, df: pd.DataFrame) -> list[list[str]]:
        contrib = contributions(self.model, df)
        return [top_reasons(df.loc[i], contrib.loc[i]) for i in df.index]

    def day_decisions(self, day: date) -> pd.DataFrame:
        """Every transaction on `day`, scored, with the policy's expected costs and action."""
        with self._connect() as con:
            df = con.execute(
                SELECT_TRANSACTIONS + " WHERE CAST(f.trans_date_trans_time AS DATE) = ?"
                " ORDER BY f.trans_date_trans_time, f.trans_num",
                [day],
            ).df()
        if df.empty:
            raise NotFound(f"No transactions on {day}. The data covers 2019-01-01 to 2020-12-31.")
        df["day"] = day
        df["p_fraud"] = self.probabilities(df)
        return df.join(cost_based_policy(df, self.config))

    def score(self, transaction_id: str) -> dict:
        with self._connect() as con:
            found = con.execute(
                "SELECT CAST(trans_date_trans_time AS DATE) FROM features WHERE trans_num = ?", [transaction_id]
            ).fetchone()
        if found is None:
            raise NotFound(f"Transaction {transaction_id} not found.")

        day = self.day_decisions(found[0])
        row = day[day["trans_num"] == transaction_id]
        r = row.iloc[0]
        return {
            "transaction_id": transaction_id,
            "timestamp": r["trans_date_trans_time"],
            "amount": r["amt"],
            "merchant": r["merchant"],
            "category": r["category"],
            "fraud_probability": r["p_fraud"],
            "action": r["action"],
            "expected_costs": {"approve": r[APPROVE], "review": r[REVIEW], "block": r[BLOCK]},
            "reasons": self.reasons(row)[0],
        }

    def queue(self, day: date) -> dict:
        df = self.day_decisions(day)
        cases = df[df["action"] == REVIEW].sort_values(APPROVE, ascending=False)
        return {
            "date": day.isoformat(),
            "review_budget": self.config["review"]["daily_review_budget"],
            "cases": [
                {
                    "transaction_id": r.trans_num,
                    "timestamp": r.trans_date_trans_time,
                    "merchant": r.merchant,
                    "category": r.category,
                    "amount": r.amt,
                    "fraud_probability": r.p_fraud,
                    "expected_loss": r.approve,
                    "loss_prevented": r.loss_prevented,
                }
                for r in cases.itertuples()
            ],
        }

    def save_review(self, transaction_id: str, decision: str, note: str | None) -> dict:
        reviewed_at = datetime.now()
        with self._connect() as con:
            if con.execute("SELECT 1 FROM transactions WHERE trans_num = ?", [transaction_id]).fetchone() is None:
                raise NotFound(f"Transaction {transaction_id} not found.")
            con.execute("INSERT INTO reviews VALUES (?, ?, ?, ?)", [transaction_id, decision, note, reviewed_at])
        return {"transaction_id": transaction_id, "decision": decision, "note": note, "reviewed_at": reviewed_at}
