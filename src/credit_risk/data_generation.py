"""Synthetic credit portfolio generation.

We generate a loan-level dataset whose default behaviour is driven by a
transparent, economically sensible latent model. This lets every downstream
model (PD/LGD/ECL/stress/EWS) learn a real signal while keeping the data
fully synthetic, reproducible, and free of any external dependency.

CAVEAT: This data is synthetic and for demonstration only. It is not real
lending data and must not be used for production underwriting decisions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import N_LOANS, RANDOM_SEED, REGIONS, SECTORS
from .utils import set_seed


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_portfolio(n: int = N_LOANS, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate a loan-level synthetic credit portfolio.

    Returns one row per loan with borrower attributes, exposure, a realised
    default flag (default within 12m), realised LGD for defaulted loans, and
    12 months of behavioural history summarised into features.
    """
    set_seed(seed)
    rng = np.random.default_rng(seed)

    # --- Borrower / loan attributes -------------------------------------
    loan_id = np.arange(1, n + 1)
    sector = rng.choice(SECTORS, size=n, p=[0.40, 0.20, 0.15, 0.15, 0.10])
    region = rng.choice(REGIONS, size=n, p=[0.30, 0.25, 0.20, 0.15, 0.10])

    # FICO-style credit score, bounded 520-820
    credit_score = np.clip(rng.normal(700, 55, n), 520, 820)

    # Debt-to-income ratio (%)
    dti = np.clip(rng.normal(36, 10, n), 5, 75)

    # Loan-to-value ratio (%) — key CRE / real estate driver
    ltv = np.clip(rng.normal(72, 12, n), 30, 110)

    # Loan amount (exposure at origination), lognormal by sector scale
    sector_scale = pd.Series(
        {"Residential": 0.35, "Multifamily": 1.2, "Retail CRE": 0.9,
         "Office CRE": 1.1, "Industrial": 0.8}
    )
    base_amt = rng.lognormal(mean=12.3, sigma=0.6, size=n)
    loan_amount = np.round(base_amt * sector_scale.reindex(sector).to_numpy(), -2)
    loan_amount = np.clip(loan_amount, 25_000, 8_000_000)

    interest_rate = np.clip(rng.normal(6.8, 1.4, n), 3.0, 14.0)
    term_months = rng.choice([60, 120, 180, 240, 360], size=n)
    loan_age_months = rng.integers(1, 60, size=n)

    # Debt service coverage ratio (income / debt service) — CRE health metric
    dscr = np.clip(rng.normal(1.35, 0.35, n), 0.4, 3.5)

    # Utilization on any associated revolving line (%)
    utilization = np.clip(rng.beta(2, 3, n) * 100, 0, 100)

    # --- Behavioural history (12 monthly snapshots) ---------------------
    # We simulate a per-borrower "stress" propensity, then draw monthly
    # delinquency / utilisation paths. Summaries feed the early-warning model.
    stress = _sigmoid(
        0.9 * ((680 - credit_score) / 50)
        + 0.5 * ((dti - 36) / 10)
        + 0.4 * ((ltv - 72) / 12)
        + 0.4 * ((1.35 - dscr) / 0.35)
    )
    months = 12
    # monthly DPD draws increase with stress
    dpd_path = rng.poisson(lam=(stress[:, None] * 18), size=(n, months))
    util_path = np.clip(
        utilization[:, None] / 100
        + rng.normal(0, 0.05, (n, months))
        + stress[:, None] * np.linspace(0, 0.15, months)[None, :],
        0, 1,
    )
    # missed payments: a month counts as missed if DPD in that month > 5
    missed_payment_path = (dpd_path > 5).astype(int)

    max_dpd_12m = dpd_path.max(axis=1)
    avg_dpd_12m = dpd_path.mean(axis=1)
    missed_payments_12m = missed_payment_path.sum(axis=1)
    util_trend = util_path[:, -3:].mean(axis=1) - util_path[:, :3].mean(axis=1)
    avg_utilization_12m = util_path.mean(axis=1) * 100
    max_utilization_12m = util_path.max(axis=1) * 100
    # current days past due (last month)
    current_dpd = dpd_path[:, -1]

    # --- Latent default model -------------------------------------------
    # Log-odds of default within 12 months.
    logit_pd = (
        -3.2
        + 2.4 * ((680 - credit_score) / 50)
        + 0.9 * ((dti - 36) / 10)
        + 1.1 * ((ltv - 72) / 12)
        + 0.8 * ((1.35 - dscr) / 0.35)
        + 0.5 * (utilization / 100)
        + 0.04 * missed_payments_12m
        + 0.015 * max_dpd_12m
    )
    # sector risk add-on
    sector_risk = pd.Series(
        {"Residential": -0.15, "Multifamily": -0.05, "Retail CRE": 0.25,
         "Office CRE": 0.45, "Industrial": 0.05}
    )
    logit_pd = logit_pd + sector_risk.reindex(sector).to_numpy()
    true_pd = _sigmoid(logit_pd)
    default_flag = rng.binomial(1, true_pd)

    # --- Loss Given Default ---------------------------------------------
    # LGD driven mainly by LTV (collateral coverage) and sector liquidity.
    sector_lgd_base = pd.Series(
        {"Residential": 0.20, "Multifamily": 0.28, "Retail CRE": 0.42,
         "Office CRE": 0.50, "Industrial": 0.35}
    )
    lgd_mean = np.clip(
        sector_lgd_base.reindex(sector).to_numpy()
        + 0.35 * ((ltv - 72) / 100)
        - 0.10 * ((dscr - 1.35))
        + rng.normal(0, 0.05, n),
        0.02, 0.95,
    )
    # Only defaulted loans have a realised LGD; others NaN.
    realised_lgd = np.where(default_flag == 1,
                            np.clip(lgd_mean + rng.normal(0, 0.08, n), 0.01, 0.99),
                            np.nan)

    # Exposure at default: outstanding balance ~ amortised, plus draw for
    # revolving exposure driven by utilisation.
    amort_factor = np.clip(1 - loan_age_months / (term_months + 1e-9), 0.15, 1.0)
    ead = loan_amount * amort_factor * (0.85 + 0.15 * (utilization / 100))
    ead = np.round(ead, 2)

    df = pd.DataFrame(
        {
            "loan_id": loan_id,
            "sector": sector,
            "region": region,
            "credit_score": np.round(credit_score, 0).astype(int),
            "dti": np.round(dti, 2),
            "ltv": np.round(ltv, 2),
            "dscr": np.round(dscr, 3),
            "loan_amount": loan_amount,
            "interest_rate": np.round(interest_rate, 3),
            "term_months": term_months,
            "loan_age_months": loan_age_months,
            "utilization": np.round(utilization, 2),
            # behavioural summaries
            "avg_utilization_12m": np.round(avg_utilization_12m, 2),
            "max_utilization_12m": np.round(max_utilization_12m, 2),
            "utilization_trend": np.round(util_trend, 4),
            "missed_payments_12m": missed_payments_12m,
            "max_dpd_12m": max_dpd_12m,
            "avg_dpd_12m": np.round(avg_dpd_12m, 3),
            "current_dpd": current_dpd,
            # exposure & outcomes
            "ead": ead,
            "true_pd": np.round(true_pd, 6),
            "default_flag": default_flag.astype(int),
            "lgd": np.round(realised_lgd, 6),
        }
    )
    return df


# Feature groups used across models -----------------------------------------
PD_FEATURES = [
    "credit_score", "dti", "ltv", "dscr", "loan_amount", "interest_rate",
    "term_months", "loan_age_months", "utilization", "missed_payments_12m",
    "max_dpd_12m",
]
PD_CATEGORICAL = ["sector", "region"]

LGD_FEATURES = [
    "ltv", "dscr", "credit_score", "loan_amount", "interest_rate",
    "utilization",
]
LGD_CATEGORICAL = ["sector", "region"]

EWS_FEATURES = [
    "avg_utilization_12m", "max_utilization_12m", "utilization_trend",
    "missed_payments_12m", "max_dpd_12m", "avg_dpd_12m", "current_dpd",
    "dti", "dscr", "credit_score",
]
