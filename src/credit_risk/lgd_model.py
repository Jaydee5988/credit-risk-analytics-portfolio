"""Model 2 — Loss Given Default (LGD) regression.

Predicts loss severity (0-1) on the defaulted-loan subpopulation. Reports
MAE/RMSE, segment-level error analysis, and permutation feature importance
(SHAP-style interpretability without the heavy dependency).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import plotting
from .config import RANDOM_SEED
from .data_generation import LGD_CATEGORICAL, LGD_FEATURES


@dataclass
class LGDResult:
    metrics: dict[str, Any]
    segment_errors: pd.DataFrame
    importance: pd.DataFrame
    predicted: pd.DataFrame              # loan_id + lgd_hat for full book
    figures: dict[str, str] = field(default_factory=dict)
    model: Any = None


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), LGD_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), LGD_CATEGORICAL),
        ]
    )


def train_lgd_model(df: pd.DataFrame, make_figures: bool = True) -> LGDResult:
    defaulted = df[df["default_flag"] == 1].copy()
    X = defaulted[LGD_FEATURES + LGD_CATEGORICAL]
    y = defaulted["lgd"].to_numpy()

    X_train, X_test, y_train, y_test, seg_train, seg_test = train_test_split(
        X, y, defaulted["sector"], test_size=0.30, random_state=RANDOM_SEED
    )

    model = Pipeline(
        [("prep", _preprocessor()),
         ("reg", GradientBoostingRegressor(random_state=RANDOM_SEED))]
    )
    model.fit(X_train, y_train)
    pred = np.clip(model.predict(X_test), 0, 1)

    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    metrics = {
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": rmse,
        "r2": float(r2_score(y_test, pred)),
        "mean_actual_lgd": float(y_test.mean()),
        "mean_predicted_lgd": float(pred.mean()),
        "n_defaulted": int(len(defaulted)),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }

    # Segment-level error analysis (by sector).
    seg_df = pd.DataFrame({"sector": seg_test.to_numpy(),
                           "actual": y_test, "pred": pred})
    segment_errors = (
        seg_df.assign(abs_err=lambda d: (d["actual"] - d["pred"]).abs())
        .groupby("sector")
        .agg(n=("actual", "size"),
             mean_actual_lgd=("actual", "mean"),
             mean_pred_lgd=("pred", "mean"),
             mae=("abs_err", "mean"))
        .reset_index()
        .sort_values("mae", ascending=False)
    )

    # Permutation importance for interpretability.
    perm = permutation_importance(
        model, X_test, y_test, n_repeats=10,
        random_state=RANDOM_SEED, scoring="neg_mean_absolute_error"
    )
    feat_names = LGD_FEATURES + LGD_CATEGORICAL
    importance = (
        pd.DataFrame({"feature": feat_names,
                      "importance": perm.importances_mean})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    # Predict LGD across the whole book (used by ECL for non-defaulted too).
    lgd_hat_full = np.clip(model.predict(df[LGD_FEATURES + LGD_CATEGORICAL]), 0, 1)
    predicted = pd.DataFrame({"loan_id": df["loan_id"].to_numpy(),
                              "lgd_hat": lgd_hat_full})

    figures: dict[str, str] = {}
    if make_figures:
        figures["lgd_scatter"] = str(
            plotting.plot_regression_scatter(y_test, pred, "lgd_scatter",
                                             "LGD: Predicted vs Actual")
        )
        figures["lgd_importance"] = str(
            plotting.plot_feature_importance(
                importance["feature"].tolist(),
                importance["importance"].to_numpy(),
                "lgd_importance", "LGD Permutation Importance (Δ MAE)")
        )

    return LGDResult(
        metrics=metrics,
        segment_errors=segment_errors,
        importance=importance,
        predicted=predicted,
        figures=figures,
        model=model,
    )
