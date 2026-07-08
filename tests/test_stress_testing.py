"""Tests for stress scenario ordering and concentration metrics."""
import numpy as np

from credit_risk import lgd_model, pd_model, stress_testing


def test_severe_loss_exceeds_base(small_portfolio):
    pd_res = pd_model.train_pd_model(small_portfolio, make_figures=False)
    lgd_res = lgd_model.train_lgd_model(small_portfolio, make_figures=False)
    stress = stress_testing.run_stress_test(
        small_portfolio, pd_res.scored, lgd_res.predicted, make_figures=False
    )
    s = stress.scenario_summary.set_index("scenario")["expected_loss"]
    assert s["base"] < s["downside"] < s["severe"]


def test_concentration_hhi_bounds():
    exposures = np.array([25.0, 25.0, 25.0, 25.0])
    assert stress_testing._herfindahl(exposures) == 0.25   # 4 equal buckets
    assert stress_testing._herfindahl(np.array([100.0])) == 1.0
    assert stress_testing._herfindahl(np.array([0.0, 0.0])) == 0.0


def test_sensitivity_positive(small_portfolio):
    pd_res = pd_model.train_pd_model(small_portfolio, make_figures=False)
    lgd_res = lgd_model.train_lgd_model(small_portfolio, make_figures=False)
    stress = stress_testing.run_stress_test(
        small_portfolio, pd_res.scored, lgd_res.predicted, make_figures=False
    )
    # Every upward shock should increase expected loss vs base.
    assert (stress.sensitivity["delta_vs_base"] > 0).all()
