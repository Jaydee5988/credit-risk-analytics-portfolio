"""Tests for synthetic data shape, schema, and plausibility."""
import numpy as np

from credit_risk import data_generation


EXPECTED_COLUMNS = {
    "loan_id", "sector", "region", "credit_score", "dti", "ltv", "dscr",
    "loan_amount", "interest_rate", "term_months", "loan_age_months",
    "utilization", "avg_utilization_12m", "max_utilization_12m",
    "utilization_trend", "missed_payments_12m", "max_dpd_12m", "avg_dpd_12m",
    "current_dpd", "ead", "true_pd", "default_flag", "lgd",
}


def test_shape_and_schema(small_portfolio):
    df = small_portfolio
    assert len(df) == 1500
    assert set(df.columns) == EXPECTED_COLUMNS
    assert df["loan_id"].is_unique


def test_reproducible():
    a = data_generation.generate_portfolio(n=500, seed=123)
    b = data_generation.generate_portfolio(n=500, seed=123)
    assert a.equals(b)


def test_value_ranges(small_portfolio):
    df = small_portfolio
    assert df["default_flag"].isin([0, 1]).all()
    assert df["credit_score"].between(520, 820).all()
    assert df["ltv"].between(30, 110).all()
    assert (df["ead"] > 0).all()
    # LGD only present for defaults, and bounded to (0, 1)
    defaulted = df[df["default_flag"] == 1]
    assert defaulted["lgd"].between(0, 1).all()
    assert df.loc[df["default_flag"] == 0, "lgd"].isna().all()


def test_default_rate_plausible(small_portfolio):
    rate = small_portfolio["default_flag"].mean()
    assert 0.02 < rate < 0.40, f"implausible default rate {rate}"


def test_signal_present(small_portfolio):
    """Defaulters should have meaningfully lower credit scores than non-defaulters."""
    df = small_portfolio
    dflt = df.loc[df["default_flag"] == 1, "credit_score"].mean()
    good = df.loc[df["default_flag"] == 0, "credit_score"].mean()
    assert dflt < good
