"""Model 1 — Probability of Default (PD) classification.

Compares a calibrated logistic regression (the industry-standard, transparent
scorecard workhorse) against gradient boosting. Reports ROC-AUC, PR-AUC, a
calibration curve, confusion matrix, and risk score bands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import plotting
from .config import RANDOM_SEED, SCORE_BANDS
from .data_generation import PD_CATEGORICAL, PD_FEATURES


@dataclass
class PDResult:
    metrics: dict[str, Any]
    score_bands: pd.DataFrame
    scored: pd.DataFrame                 # loan_id + pd_hat (chosen model)
    figures: dict[str, str] = field(default_factory=dict)
    best_model_name: str = ""
    model: Any = None


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), PD_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), PD_CATEGORICAL),
        ]
    )


def _build_score_bands(y_true: np.ndarray, pd_hat: np.ndarray) -> pd.DataFrame:
    rows = []
    for label, lo, hi in SCORE_BANDS:
        mask = (pd_hat >= lo) & (pd_hat < hi)
        n = int(mask.sum())
        rows.append(
            {
                "band": label,
                "pd_low": lo,
                "pd_high": min(hi, 1.0),
                "n_loans": n,
                "pct_of_book": n / len(pd_hat) if len(pd_hat) else 0.0,
                "avg_predicted_pd": float(pd_hat[mask].mean()) if n else 0.0,
                "actual_default_rate": float(y_true[mask].mean()) if n else 0.0,
            }
        )
    return pd.DataFrame(rows)


def train_pd_model(df: pd.DataFrame, make_figures: bool = True) -> PDResult:
    X = df[PD_FEATURES + PD_CATEGORICAL]
    y = df["default_flag"].to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.30, random_state=RANDOM_SEED, stratify=y
    )

    # Logistic regression, isotonically calibrated for reliable PDs.
    logit = Pipeline(
        [("prep", _preprocessor()),
         ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))]
    )
    logit_cal = CalibratedClassifierCV(logit, method="isotonic", cv=3)
    logit_cal.fit(X_train, y_train)

    # Gradient boosting.
    gb = Pipeline(
        [("prep", _preprocessor()),
         ("clf", GradientBoostingClassifier(random_state=RANDOM_SEED))]
    )
    gb.fit(X_train, y_train)

    models = {"logistic_regression": logit_cal, "gradient_boosting": gb}
    metrics: dict[str, Any] = {}
    for name, model in models.items():
        p = model.predict_proba(X_test)[:, 1]
        metrics[name] = {
            "roc_auc": float(roc_auc_score(y_test, p)),
            "pr_auc": float(average_precision_score(y_test, p)),
            "brier": float(brier_score_loss(y_test, p)),
        }

    # Pick best by ROC-AUC.
    best_name = max(metrics, key=lambda k: metrics[k]["roc_auc"])
    best_model = models[best_name]
    p_best = best_model.predict_proba(X_test)[:, 1]

    # Confusion matrix at a policy threshold (approve if PD < 0.15).
    threshold = 0.15
    y_pred = (p_best >= threshold).astype(int)
    cm = confusion_matrix(y_test, y_pred)
    metrics["decision_threshold"] = threshold
    metrics["best_model"] = best_name
    metrics["confusion_matrix"] = cm.tolist()
    metrics["test_default_rate"] = float(y_test.mean())
    metrics["n_train"] = int(len(y_train))
    metrics["n_test"] = int(len(y_test))

    score_bands = _build_score_bands(y_test, p_best)

    # Score the full book with the chosen model for downstream ECL/EWS.
    pd_hat_full = best_model.predict_proba(X)[:, 1]
    scored = pd.DataFrame({"loan_id": df["loan_id"].to_numpy(), "pd_hat": pd_hat_full})

    figures: dict[str, str] = {}
    if make_figures:
        fpr, tpr, _ = roc_curve(y_test, p_best)
        figures["pd_roc"] = str(
            plotting.plot_roc(fpr, tpr, metrics[best_name]["roc_auc"],
                              "pd_roc", f"PD ROC — {best_name}")
        )
        prec, rec, _ = precision_recall_curve(y_test, p_best)
        figures["pd_pr"] = str(
            plotting.plot_pr(rec, prec, metrics[best_name]["pr_auc"],
                             "pd_pr", f"PD Precision-Recall — {best_name}")
        )
        prob_true, prob_pred = calibration_curve(y_test, p_best, n_bins=10, strategy="quantile")
        figures["pd_calibration"] = str(
            plotting.plot_calibration(prob_true, prob_pred,
                                      "pd_calibration", f"PD Calibration — {best_name}")
        )
        figures["pd_confusion"] = str(
            plotting.plot_confusion(cm, "pd_confusion",
                                    f"PD Confusion Matrix (PD≥{threshold})")
        )
        figures["pd_score_bands"] = str(
            plotting.plot_score_bands(score_bands, "pd_score_bands",
                                      "Observed Default Rate by Risk Band")
        )

    return PDResult(
        metrics=metrics,
        score_bands=score_bands,
        scored=scored,
        figures=figures,
        best_model_name=best_name,
        model=best_model,
    )
