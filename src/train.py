"""Split by time, train the logistic regression baseline, and report test metrics.

Run from the project root with:  python -m src.train
"""

import json
import math

import duckdb
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.features import FEATURE_COLUMNS
from src.load import DB_PATH, PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "config.yaml"
METRICS_PATH = PROJECT_ROOT / "reports" / "metrics.json"

# How each feature is prepared for logistic regression.
LOG_NUMERIC = ["amt", "amt_to_median_ratio"]  # heavily skewed: log first, then scale
NUMERIC = ["txn_count_1h", "txn_count_24h", "distance_km"]  # scale only
CATEGORICAL = ["category", "hour_of_day", "day_of_week"]  # one column per value


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def load_features() -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.sql("SELECT * FROM features").df()


def split_by_time(df: pd.DataFrame, train_end: str, validation_end: str):
    """Return (train, validation, test). Each end date is the first moment NOT in that set."""
    time = df["trans_date_trans_time"]
    train_end, validation_end = pd.Timestamp(train_end), pd.Timestamp(validation_end)
    train = df[time < train_end]
    validation = df[(time >= train_end) & (time < validation_end)]
    test = df[time >= validation_end]
    return train, validation, test


def build_baseline() -> Pipeline:
    """Preprocessing plus logistic regression, as one object fitted on training data only."""
    log_numeric = Pipeline([
        ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
        # A card's first transaction has no ratio: fill it with the training median
        # and add a 0/1 column saying it was missing.
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])
    preprocess = ColumnTransformer([
        ("log_numeric", log_numeric, LOG_NUMERIC),
        ("numeric", StandardScaler(), NUMERIC),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])
    return Pipeline([("preprocess", preprocess), ("model", LogisticRegression(max_iter=1000))])


def recall_at_top(y_true, scores, share: float) -> tuple[float, float]:
    """Review the riskiest `share` of transactions: return (recall, precision) of that group."""
    y_true = np.asarray(y_true)
    n_reviewed = math.ceil(share * len(y_true))
    reviewed = np.argsort(-np.asarray(scores), kind="stable")[:n_reviewed]
    caught = y_true[reviewed].sum()
    return caught / y_true.sum(), caught / n_reviewed


def evaluate(y_true, scores, review_share: float) -> dict:
    recall, precision = recall_at_top(y_true, scores, review_share)
    return {
        "pr_auc": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "recall_at_top": float(recall),
        "precision_at_top": float(precision),
    }


def main() -> None:
    config = load_config()
    review_share = config["evaluation"]["review_share"]
    train, validation, test = split_by_time(load_features(), **config["split"])

    model = build_baseline()
    model.fit(train[FEATURE_COLUMNS], train["is_fraud"])

    results = {}
    for name, part in [("validation", validation), ("test", test)]:
        scores = model.predict_proba(part[FEATURE_COLUMNS])[:, 1]  # probability of fraud
        results[name] = evaluate(part["is_fraud"], scores, review_share)

    # The trap: predicting "not fraud" every time is right whenever a transaction is legitimate.
    always_not_fraud_accuracy = 1 - test["is_fraud"].mean()

    metrics = {
        "split": config["split"],
        "review_share": review_share,
        "sets": {
            name: {"rows": len(part), "fraud": int(part["is_fraud"].sum())}
            for name, part in [("train", train), ("validation", validation), ("test", test)]
        },
        "always_not_fraud_accuracy_test": float(always_not_fraud_accuracy),
        "models": {"logistic_regression": results},
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n")

    for name, info in metrics["sets"].items():
        print(f"{name:>10}: {info['rows']:>9,} rows, {info['fraud']:>5,} fraud")
    print(f"\nAlways predicting 'not fraud' on test: {always_not_fraud_accuracy:.2%} accurate, catches 0 fraud")
    print(f"\nLogistic regression (reviewing the riskiest {review_share:.0%}):")
    for name, m in results.items():
        print(
            f"{name:>10}: PR-AUC {m['pr_auc']:.3f} | ROC AUC {m['roc_auc']:.3f} | "
            f"recall {m['recall_at_top']:.1%} | precision {m['precision_at_top']:.1%}"
        )
    print(f"\nSaved {METRICS_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
