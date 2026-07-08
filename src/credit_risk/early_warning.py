"""Model 5 — Early-warning / delinquency risk.

Uses time-window behavioural features (rolling utilisation, payment misses,
delinquency trend) to predict near-term delinquency, then ranks the book to
produce a monitoring watchlist of the highest-risk accounts.

Target: near-term delinquency = current_dpd >= 30 OR eventual default. This
is deliberately behavioural (not just originations), mimicking a servicing
monitoring model rather than an underwriting scorecard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from . import plotting
from .config import RANDOM_SEED
from .data_generation import EWS_FEATURES


@dataclass
class EWSResult:
    metrics: dict[str, Any]
    watchlist: pd.DataFrame
    scored: pd.DataFrame
    figures: dict[str, str] = field(default_factory=dict)
    model: Any = None


def _build_target(df: pd.DataFrame) -> np.ndarray:
    return (((df["current_dpd"] >= 30) | (df["default_flag"] == 1)).astype(int)).to_numpy()


def train_ews_model(df: pd.DataFrame, make_figures: bool = True) -> EWSResult:
    X = df[EWS_FEATURES]
    y = _build_target(df)

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index, test_size=0.30, random_state=RANDOM_SEED, stratify=y
    )

    model = GradientBoostingClassifier(random_state=RANDOM_SEED)
    model.fit(X_train, y_train)
    p_test = model.predict_proba(X_test)[:, 1]

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, p_test)),
        "pr_auc": float(average_precision_score(y_test, p_test)),
        "event_rate": float(y.mean()),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }

    # top-decile capture: share of true events in the top 10% by score
    order = np.argsort(-p_test)
    top_n = max(1, int(0.10 * len(p_test)))
    top_idx = order[:top_n]
    metrics["top_decile_capture_rate"] = float(y_test[top_idx].sum() / max(1, y_test.sum()))

    # Score whole book and build watchlist.
    ews_score = model.predict_proba(X)[:, 1]
    scored = df[["loan_id", "sector", "region", "ead", "current_dpd",
                 "missed_payments_12m", "utilization_trend", "credit_score"]].copy()
    scored["ews_score"] = ews_score
    scored["expected_loss_at_risk"] = scored["ews_score"] * scored["ead"]

    watchlist = (
        scored.sort_values("ews_score", ascending=False)
        .head(25)
        .reset_index(drop=True)
    )

    figures: dict[str, str] = {}
    if make_figures:
        figures["ews_watchlist"] = str(
            plotting.plot_watchlist(watchlist, "ews_watchlist",
                                    "Top Watchlist Accounts by Early-Warning Score")
        )

    return EWSResult(
        metrics=metrics,
        watchlist=watchlist,
        scored=scored[["loan_id", "ews_score", "expected_loss_at_risk"]],
        figures=figures,
        model=model,
    )
