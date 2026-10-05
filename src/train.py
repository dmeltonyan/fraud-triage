"""Split by time, train the logistic regression baseline and LightGBM, and report test metrics.

Run from the project root with:  python -m src.train
"""

import json
import math

import duckdb
import lightgbm as lgb
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


def lightgbm_inputs(df: pd.DataFrame, categories: list[str]) -> pd.DataFrame:
    """Features for LightGBM. Trees need no scaling or one-hot: `category` becomes a
    pandas categorical (with the training categories, so codes match across sets),
    and a missing ratio stays missing, which LightGBM handles on its own."""
    X = df[FEATURE_COLUMNS].copy()
    known = X["category"].where(X["category"].isin(categories))  # unseen category -> missing
    X["category"] = known.astype(pd.CategoricalDtype(categories))
    return X


def train_lightgbm(train: pd.DataFrame, validation: pd.DataFrame, settings: dict):
    """Fit LightGBM on train, using validation only to decide when to stop adding trees."""
    categories = sorted(train["category"].unique())
    model = lgb.LGBMClassifier(
        n_estimators=settings["max_trees"],
        learning_rate=settings["learning_rate"],
        scale_pos_weight=settings["scale_pos_weight"],
        random_state=42,
        verbose=-1,
    )
    model.fit(
        lightgbm_inputs(train, categories),
        train["is_fraud"],
        eval_X=lightgbm_inputs(validation, categories),
        eval_y=validation["is_fraud"],
        eval_metric="average_precision",
        callbacks=[lgb.early_stopping(settings["early_stopping_rounds"], verbose=False)],
    )
    return model, categories


def feature_importance(model: lgb.LGBMClassifier, top: int = 10) -> dict[str, float]:
    """Share of the model's total gain from splits on each feature, largest first."""
    gain = model.booster_.feature_importance(importance_type="gain")
    shares = pd.Series(gain / gain.sum(), index=model.booster_.feature_name())
    return shares.sort_values(ascending=False).head(top).round(4).to_dict()


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

    baseline = build_baseline()
    baseline.fit(train[FEATURE_COLUMNS], train["is_fraud"])
    booster, categories = train_lightgbm(train, validation, config["lightgbm"])

    # Each model's probability of fraud for a set of transactions.
    scorers = {
        "logistic_regression": lambda part: baseline.predict_proba(part[FEATURE_COLUMNS])[:, 1],
        "lightgbm": lambda part: booster.predict_proba(lightgbm_inputs(part, categories))[:, 1],
    }
    results = {
        model_name: {
            name: evaluate(part["is_fraud"], score(part), review_share)
            for name, part in [("validation", validation), ("test", test)]
        }
        for model_name, score in scorers.items()
    }

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
        "models": results,
        "lightgbm_trees": int(booster.best_iteration_),
        "lightgbm_feature_importance": feature_importance(booster),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n")

    for name, info in metrics["sets"].items():
        print(f"{name:>10}: {info['rows']:>9,} rows, {info['fraud']:>5,} fraud")
    print(f"\nAlways predicting 'not fraud' on test: {always_not_fraud_accuracy:.2%} accurate, catches 0 fraud")

    print(f"\nTest months (recall and precision when reviewing the riskiest {review_share:.0%}):")
    print(f"{'':>20} {'PR-AUC':>8} {'ROC AUC':>8} {'recall':>8} {'precision':>10}")
    for model_name, by_set in results.items():
        m = by_set["test"]
        print(
            f"{model_name:>20} {m['pr_auc']:>8.3f} {m['roc_auc']:>8.3f} "
            f"{m['recall_at_top']:>8.1%} {m['precision_at_top']:>10.1%}"
        )
    print("(validation scores are in the metrics file; LightGBM's are slightly optimistic "
          "because validation chose its number of trees)")

    print(f"\nLightGBM used {metrics['lightgbm_trees']} trees. Feature importance (share of total gain):")
    for feature, share in metrics["lightgbm_feature_importance"].items():
        print(f"{feature:>20} {share:>7.1%}")
    print(f"\nSaved {METRICS_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
