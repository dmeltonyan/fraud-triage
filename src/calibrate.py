"""Turn LightGBM's scores into honest probabilities and draw a reliability curve.

LightGBM was trained with fraud rows counted 13 times (scale_pos_weight), so its
raw scores are roughly twice too high. Platt scaling fits a small logistic
regression on the calibration month that maps each raw score to a probability
that matches how often fraud actually happened.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

# Probability bins for the reliability curve. Fraud is rare, so most scores are
# tiny: bins get narrower near zero instead of being 0-0.1, 0.1-0.2, ...
BIN_EDGES = [0, 0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 0.6, 1.0]


def log_odds(p) -> np.ndarray:
    """log(p / (1 - p)), clipped so 0 and 1 don't become infinite."""
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


class PlattCalibrator:
    """calibrated = sigmoid(slope * log_odds(raw) + intercept), fitted on one held-out set.

    Training with a fraud weight of w adds about log(w) to every log-odds, so the
    fitted intercept should come out near -log(13) = -2.6.
    """

    def fit(self, raw_scores, y_true) -> "PlattCalibrator":
        # C is huge so there is effectively no regularization: just the best-fitting line.
        self.model = LogisticRegression(C=1e6)
        self.model.fit(log_odds(raw_scores).reshape(-1, 1), np.asarray(y_true))
        return self

    def predict(self, raw_scores) -> np.ndarray:
        return self.model.predict_proba(log_odds(raw_scores).reshape(-1, 1))[:, 1]

    @property
    def slope(self) -> float:
        return float(self.model.coef_[0, 0])

    @property
    def intercept(self) -> float:
        return float(self.model.intercept_[0])


def reliability_table(y_true, probabilities) -> pd.DataFrame:
    """Per probability bin: how many transactions, average predicted probability, actual fraud rate."""
    df = pd.DataFrame({"y": np.asarray(y_true), "p": np.asarray(probabilities)})
    df["bin"] = pd.cut(df["p"], BIN_EDGES, include_lowest=True)
    table = df.groupby("bin", observed=True).agg(n=("y", "size"), predicted=("p", "mean"), actual=("y", "mean"))
    return table.reset_index()


def plot_reliability(y_true, raw, calibrated, path: Path, title: str) -> None:
    """Predicted probability vs actual fraud rate, before and after calibration."""
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([1e-4, 1], [1e-4, 1], color="grey", linestyle="--", label="perfect calibration")
    for label, p in [("raw LightGBM", raw), ("calibrated", calibrated)]:
        table = reliability_table(y_true, p)
        table = table[table["actual"] > 0]  # log scale can't show a 0% bin
        ax.plot(table["predicted"], table["actual"], marker="o", label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("predicted fraud probability")
    ax.set_ylabel("actual fraud rate")
    ax.set_title(title)
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
