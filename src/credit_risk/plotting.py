"""Reusable plotting helpers. All figures are saved to reports/figures."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless / reproducible
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import seaborn as sns  # noqa: E402

from .config import FIGURES_DIR  # noqa: E402

sns.set_theme(style="whitegrid", context="talk")
plt.rcParams["figure.dpi"] = 110
plt.rcParams["savefig.bbox"] = "tight"


def _save(fig, name: str) -> Path:
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_roc(fpr, tpr, auc_score, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, lw=2.5, label=f"AUC = {auc_score:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(title)
    ax.legend(loc="lower right")
    return _save(fig, name)


def plot_pr(recall, precision, ap, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(recall, precision, lw=2.5, label=f"AP = {ap:.3f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(title)
    ax.legend(loc="upper right")
    return _save(fig, name)


def plot_calibration(prob_true, prob_pred, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(prob_pred, prob_true, "o-", lw=2, label="Model")
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Perfectly calibrated")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed default frequency")
    ax.set_title(title)
    ax.legend(loc="upper left")
    return _save(fig, name)


def plot_confusion(cm, name: str, title: str, labels=("No default", "Default")) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title)
    return _save(fig, name)


def plot_score_bands(band_df, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(band_df))
    ax.bar(x, band_df["actual_default_rate"], color=sns.color_palette("flare", len(band_df)))
    ax.set_xticks(x)
    ax.set_xticklabels(band_df["band"], rotation=25, ha="right")
    ax.set_ylabel("Observed default rate")
    ax.set_title(title)
    for i, v in enumerate(band_df["actual_default_rate"]):
        ax.text(i, v + 0.005, f"{v:.1%}", ha="center", fontsize=11)
    return _save(fig, name)


def plot_feature_importance(names, values, fig_name: str, title: str) -> Path:
    order = np.argsort(values)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(np.array(names)[order], np.array(values)[order],
            color=sns.color_palette("viridis", len(names)))
    ax.set_xlabel("Importance")
    ax.set_title(title)
    return _save(fig, fig_name)


def plot_regression_scatter(y_true, y_pred, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(y_true, y_pred, alpha=0.3, s=18)
    lims = [0, 1]
    ax.plot(lims, lims, "--", color="grey")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Actual LGD")
    ax.set_ylabel("Predicted LGD")
    ax.set_title(title)
    return _save(fig, name)


def plot_ecl_by_stage(stage_df, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(stage_df["stage"].astype(str), stage_df["ecl"],
           color=sns.color_palette("rocket", len(stage_df)))
    ax.set_xlabel("IFRS 9 Stage")
    ax.set_ylabel("Expected Credit Loss ($)")
    ax.set_title(title)
    for i, v in enumerate(stage_df["ecl"]):
        ax.text(i, v, f"${v/1e6:.1f}M", ha="center", va="bottom", fontsize=11)
    return _save(fig, name)


def plot_scenario_ecl(scenario_df, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = sns.color_palette("mako", len(scenario_df))
    ax.bar(scenario_df["scenario"], scenario_df["ecl"], color=colors)
    ax.set_ylabel("Portfolio ECL ($)")
    ax.set_title(title)
    for i, v in enumerate(scenario_df["ecl"]):
        ax.text(i, v, f"${v/1e6:.1f}M", ha="center", va="bottom", fontsize=11)
    return _save(fig, name)


def plot_stress_waterfall(labels, values, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#4c72b0", "#dd8452", "#c44e52"][: len(labels)]
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("Portfolio expected loss ($)")
    ax.set_title(title)
    for i, v in enumerate(values):
        ax.text(i, v, f"${v/1e6:.1f}M", ha="center", va="bottom", fontsize=11)
    return _save(fig, name)


def plot_concentration(conc_df, group_col, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 6))
    order = conc_df.sort_values("exposure", ascending=True)
    ax.barh(order[group_col], order["exposure"],
            color=sns.color_palette("crest", len(order)))
    ax.set_xlabel("Exposure at default ($)")
    ax.set_title(title)
    return _save(fig, name)


def plot_watchlist(watch_df, name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(9, 6))
    top = watch_df.head(15).iloc[::-1]
    ax.barh(top["loan_id"].astype(str), top["ews_score"],
            color=sns.color_palette("flare", len(top)))
    ax.set_xlabel("Early-warning score (P[delinquency])")
    ax.set_ylabel("Loan ID")
    ax.set_title(title)
    return _save(fig, name)
