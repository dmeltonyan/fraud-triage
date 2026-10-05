"""Split by time, train the logistic regression baseline and LightGBM, calibrate
LightGBM, report test metrics, and save calibrated scores for the decision policy.

Run from the project root with:  python -m src.train
"""

import json
import math

import duckdb
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.calibrate import PlattCalibrator, plot_reliability
from src.features import FEATURE_COLUMNS
from src.load import DB_PATH, PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "config.yaml"
METRICS_PATH = PROJECT_ROOT / "reports" / "metrics.json"
CALIBRATION_PLOT_PATH = PROJECT_ROOT / "reports" / "figures" / "calibration.png"
MODELS_DIR = PROJECT_ROOT / "models"  # gitignored: rebuilt by running this script

# How each feature is prepared for logistic regression.
LOG_NUMERIC = ["amt", "amt_to_median_ratio"]  # heavily skewed: log first, then scale
NUMERIC = ["txn_count_1h", "txn_count_24h", "distance_km"]  # scale only
CATEGORICAL = ["category", "hour_of_day", "day_of_week"]  # one column per value


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def load_features() -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.sql("SELECT * FROM features").df()


def split_by_time(df: pd.DataFrame, train_end: str, tuning_end: str, calibration_end: str):
    """Return (train, tuning, calibration, test). Each end date is the first moment NOT in that set."""
    time = df["trans_date_trans_time"]
    train_end, tuning_end, calibration_end = map(pd.Timestamp, (train_end, tuning_end, calibration_end))
    train = df[time < train_end]
    tuning = df[(time >= train_end) & (time < tuning_end)]
    calibration = df[(time >= tuning_end) & (time < calibration_end)]
    test = df[time >= calibration_end]
    return train, tuning, calibration, test


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


def train_lightgbm(train: pd.DataFrame, tuning: pd.DataFrame, settings: dict, scale_pos_weight: float):
    """Fit LightGBM on train, using the tuning months only to decide when to stop adding trees."""
    categories = sorted(train["category"].unique())
    model = lgb.LGBMClassifier(
        n_estimators=settings["max_trees"],
        learning_rate=settings["learning_rate"],
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        verbose=-1,
    )
    model.fit(
        lightgbm_inputs(train, categories),
        train["is_fraud"],
        eval_X=lightgbm_inputs(tuning, categories),
        eval_y=tuning["is_fraud"],
        eval_metric="average_precision",
        callbacks=[lgb.early_stopping(settings["early_stopping_rounds"], verbose=False)],
    )
    return model, categories


def tune_lightgbm(train: pd.DataFrame, tuning: pd.DataFrame, settings: dict):
    """Train one model per scale_pos_weight candidate and keep the best on tuning PR-AUC.

    Returns (best model, its categories, {candidate weight: tuning PR-AUC}).
    """
    tried, best = {}, None
    for weight in settings["scale_pos_weight_candidates"]:
        model, categories = train_lightgbm(train, tuning, settings, weight)
        scores = model.predict_proba(lightgbm_inputs(tuning, categories))[:, 1]
        tried[weight] = float(average_precision_score(tuning["is_fraud"], scores))
        if best is None or tried[weight] > tried[best[2]]:
            best = (model, categories, weight)
    return best[0], best[1], tried


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
    train, tuning, calibration, test = split_by_time(load_features(), **config["split"])
    sets = {"train": train, "tuning": tuning, "calibration": calibration, "test": test}

    baseline = build_baseline()
    baseline.fit(train[FEATURE_COLUMNS], train["is_fraud"])
    booster, categories, weights_tried = tune_lightgbm(train, tuning, config["lightgbm"])

    # Each model's probability of fraud for a set of transactions.
    scorers = {
        "logistic_regression": lambda part: baseline.predict_proba(part[FEATURE_COLUMNS])[:, 1],
        "lightgbm": lambda part: booster.predict_proba(lightgbm_inputs(part, categories))[:, 1],
    }
    results = {
        model_name: {
            name: evaluate(part["is_fraud"], score(part), review_share)
            for name, part in [("tuning", tuning), ("calibration", calibration), ("test", test)]
        }
        for model_name, score in scorers.items()
    }

    # Calibrate LightGBM on the calibration month only, then check it on every later set.
    raw = {name: scorers["lightgbm"](part) for name, part in sets.items() if name != "train"}
    calibrator = PlattCalibrator().fit(raw["calibration"], calibration["is_fraud"])
    calibrated = {name: calibrator.predict(scores) for name, scores in raw.items()}
    calibration_report = {
        "method": "platt",
        "fitted_on": "calibration",
        "slope": calibrator.slope,
        "intercept": calibrator.intercept,
        "sets": {
            name: {
                "actual_fraud_rate": float(sets[name]["is_fraud"].mean()),
                "mean_raw": float(raw[name].mean()),
                "mean_calibrated": float(calibrated[name].mean()),
                "brier_raw": float(brier_score_loss(sets[name]["is_fraud"], raw[name])),
                "brier_calibrated": float(brier_score_loss(sets[name]["is_fraud"], calibrated[name])),
            }
            for name in raw
        },
    }
    plot_reliability(
        test["is_fraud"], raw["test"], calibrated["test"], CALIBRATION_PLOT_PATH,
        "Reliability on test months (Oct-Dec 2020)",
    )
    save_scores(sets, raw, calibrated)
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": booster, "categories": categories}, MODELS_DIR / "lightgbm.joblib")
    joblib.dump(calibrator, MODELS_DIR / "calibrator.joblib")

    # The trap: predicting "not fraud" every time is right whenever a transaction is legitimate.
    always_not_fraud_accuracy = 1 - test["is_fraud"].mean()

    # Keep the previous run's test results so we can see what this run changed.
    previous = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else None

    metrics = {
        "split": config["split"],
        "review_share": review_share,
        "sets": {name: {"rows": len(part), "fraud": int(part["is_fraud"].sum())} for name, part in sets.items()},
        "always_not_fraud_accuracy_test": float(always_not_fraud_accuracy),
        "models": results,
        "lightgbm_scale_pos_weight_tried": {str(w): pr_auc for w, pr_auc in weights_tried.items()},
        "lightgbm_scale_pos_weight": booster.get_params()["scale_pos_weight"],
        "lightgbm_trees": int(booster.best_iteration_),
        "lightgbm_feature_importance": feature_importance(booster),
        "calibration": calibration_report,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n")

    for name, info in metrics["sets"].items():
        print(f"{name:>11}: {info['rows']:>9,} rows, {info['fraud']:>5,} fraud")
    print(f"\nAlways predicting 'not fraud' on test: {always_not_fraud_accuracy:.2%} accurate, catches 0 fraud")

    print("\nLightGBM scale_pos_weight, PR-AUC on tuning months:")
    for weight, pr_auc in weights_tried.items():
        chosen = "  <- chosen" if weight == metrics["lightgbm_scale_pos_weight"] else ""
        print(f"{weight:>6}: {pr_auc:.3f}{chosen}")

    print(f"\nRecall and precision when reviewing the riskiest {review_share:.0%}:")
    print(f"{'':>20} {'set':>12} {'PR-AUC':>8} {'ROC AUC':>8} {'recall':>8} {'precision':>10}")
    for model_name, by_set in results.items():
        for set_name, m in by_set.items():
            print(
                f"{model_name:>20} {set_name:>12} {m['pr_auc']:>8.3f} {m['roc_auc']:>8.3f} "
                f"{m['recall_at_top']:>8.1%} {m['precision_at_top']:>10.1%}"
            )
    print("(LightGBM's tuning scores are optimistic: the tuning months chose its settings)")

    if previous:
        print("\nTest results compared with the previous run:")
        for model_name in results:
            old, new = previous["models"][model_name]["test"], results[model_name]["test"]
            print(
                f"{model_name:>20}: PR-AUC {old['pr_auc']:.3f} -> {new['pr_auc']:.3f} | "
                f"recall at top {old['recall_at_top']:.1%} -> {new['recall_at_top']:.1%}"
            )

    print(f"\nLightGBM used {metrics['lightgbm_trees']} trees. Feature importance (share of total gain):")
    for feature, share in metrics["lightgbm_feature_importance"].items():
        print(f"{feature:>20} {share:>7.1%}")

    print(
        f"\nPlatt calibration (fitted on calibration month): "
        f"slope {calibrator.slope:.3f}, intercept {calibrator.intercept:.3f}"
    )
    print(f"{'set':>12} {'actual':>8} {'mean raw':>9} {'mean cal':>9} {'Brier raw':>10} {'Brier cal':>10}")
    for name, c in calibration_report["sets"].items():
        print(
            f"{name:>12} {c['actual_fraud_rate']:>8.3%} {c['mean_raw']:>9.3%} {c['mean_calibrated']:>9.3%} "
            f"{c['brier_raw']:>10.5f} {c['brier_calibrated']:>10.5f}"
        )

    print(f"\nSaved {METRICS_PATH.relative_to(PROJECT_ROOT)}, {CALIBRATION_PLOT_PATH.relative_to(PROJECT_ROOT)}, "
          f"models/, and the `scores` table in {DB_PATH.name}")


def save_scores(sets: dict, raw: dict, calibrated: dict) -> None:
    """Write each scored transaction to a `scores` table for the decision policy."""
    frames = [
        sets[name][["trans_num", "trans_date_trans_time", "amt", "is_fraud"]].assign(
            set_name=name, p_raw=raw[name], p_fraud=calibrated[name]
        )
        for name in raw
    ]
    scores = pd.concat(frames, ignore_index=True)
    with duckdb.connect(str(DB_PATH)) as con:
        con.register("scores_df", scores)
        con.execute("CREATE OR REPLACE TABLE scores AS SELECT * FROM scores_df ORDER BY trans_date_trans_time, trans_num")


if __name__ == "__main__":
    main()
