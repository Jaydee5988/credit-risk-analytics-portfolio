"""Tests for the ECL formula, staging, and scenario weighting."""
import numpy as np
import pandas as pd
import pytest

from credit_risk import ecl_engine
from credit_risk.config import SCENARIOS


def test_lifetime_pd_monotonic_and_bounded():
    pd_12m = np.array([0.0, 0.05, 0.2, 0.5, 1.0])
    life = ecl_engine.lifetime_pd(pd_12m, horizon_years=5)
    assert (life >= pd_12m - 1e-9).all()          # lifetime >= 12m
    assert (life >= 0).all() and (life <= 1).all()
    assert life[0] == pytest.approx(0.0)
    assert life[-1] == pytest.approx(1.0)


def test_lifetime_pd_formula():
    # 1 - (1-0.1)^5
    assert ecl_engine.lifetime_pd(np.array([0.1]), 5)[0] == pytest.approx(1 - 0.9 ** 5)


def test_stage_assignment():
    pd_12m = np.array([0.01, 0.20, 0.01, 0.01])
    dpd = np.array([0, 0, 45, 120])
    dflt = np.array([0, 0, 0, 0])
    stages = ecl_engine.assign_stage(pd_12m, dpd, dflt)
    assert list(stages) == [1, 2, 2, 3]


def test_ecl_identity_single_loan():
    """ECL for a Stage 1 loan equals PD*LGD*EAD*discount in the base scenario."""
    df = pd.DataFrame({
        "loan_id": [1], "sector": ["Residential"], "region": ["Denver Metro"],
        "ead": [100_000.0], "current_dpd": [0], "default_flag": [0],
    })
    pd_hat = pd.DataFrame({"loan_id": [1], "pd_hat": [0.05]})
    lgd_hat = pd.DataFrame({"loan_id": [1], "lgd_hat": [0.40]})
    res = ecl_engine.compute_ecl(df, pd_hat, lgd_hat, make_figures=False)
    row = res.loan_level.iloc[0]
    assert row["stage"] == 1
    expected = 0.05 * 0.40 * 100_000.0 * row["discount_factor"]
    assert row["ecl_base"] == pytest.approx(expected)


def test_scenario_weighting_is_convex_combination():
    df = pd.DataFrame({
        "loan_id": range(50),
        "sector": ["Residential"] * 50,
        "region": ["Denver Metro"] * 50,
        "ead": [100_000.0] * 50,
        "current_dpd": [0] * 50,
        "default_flag": [0] * 50,
    })
    pd_hat = pd.DataFrame({"loan_id": range(50), "pd_hat": [0.05] * 50})
    lgd_hat = pd.DataFrame({"loan_id": range(50), "lgd_hat": [0.40] * 50})
    res = ecl_engine.compute_ecl(df, pd_hat, lgd_hat, make_figures=False)
    p = res.portfolio
    manual = (p["ecl_base"] * SCENARIOS["base"]["weight"]
              + p["ecl_downside"] * SCENARIOS["downside"]["weight"]
              + p["ecl_severe"] * SCENARIOS["severe"]["weight"])
    assert p["weighted_ecl"] == pytest.approx(manual)
    # weighted ECL must sit between base and severe totals
    assert p["ecl_base"] <= p["weighted_ecl"] <= p["ecl_severe"]


def test_scenario_weights_sum_to_one():
    assert sum(v["weight"] for v in SCENARIOS.values()) == pytest.approx(1.0)


def test_stage3_uses_full_pd():
    df = pd.DataFrame({
        "loan_id": [1], "sector": ["Office CRE"], "region": ["National"],
        "ead": [100_000.0], "current_dpd": [120], "default_flag": [1],
    })
    pd_hat = pd.DataFrame({"loan_id": [1], "pd_hat": [0.05]})
    lgd_hat = pd.DataFrame({"loan_id": [1], "lgd_hat": [0.50]})
    res = ecl_engine.compute_ecl(df, pd_hat, lgd_hat, make_figures=False)
    row = res.loan_level.iloc[0]
    assert row["stage"] == 3
    # effective PD = 1.0 => base ECL = 1.0 * LGD * EAD * discount
    expected = 1.0 * 0.50 * 100_000.0 * row["discount_factor"]
    assert row["ecl_base"] == pytest.approx(expected)
