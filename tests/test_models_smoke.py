"""Smoke tests: every model trains and produces sane metrics on small data."""
from credit_risk import early_warning, lgd_model, pd_model


def test_pd_model_trains_and_discriminates(small_portfolio):
    res = pd_model.train_pd_model(small_portfolio, make_figures=False)
    for name in ("logistic_regression", "gradient_boosting"):
        assert 0.5 < res.metrics[name]["roc_auc"] <= 1.0
        assert 0.0 <= res.metrics[name]["brier"] <= 1.0
    assert len(res.scored) == len(small_portfolio)
    assert res.scored["pd_hat"].between(0, 1).all()
    # score bands should be present and cover the book
    assert res.score_bands["n_loans"].sum() == res.metrics["n_test"]


def test_lgd_model_trains(small_portfolio):
    res = lgd_model.train_lgd_model(small_portfolio, make_figures=False)
    assert res.metrics["mae"] >= 0
    assert res.metrics["rmse"] >= res.metrics["mae"]
    assert len(res.predicted) == len(small_portfolio)
    assert res.predicted["lgd_hat"].between(0, 1).all()
    assert not res.importance.empty


def test_ews_model_trains_and_ranks(small_portfolio):
    res = early_warning.train_ews_model(small_portfolio, make_figures=False)
    assert 0.5 < res.metrics["roc_auc"] <= 1.0
    assert 0 < res.metrics["top_decile_capture_rate"] <= 1.0
    assert len(res.watchlist) <= 25
    # watchlist should be sorted by score descending
    scores = res.watchlist["ews_score"].to_numpy()
    assert (scores[:-1] >= scores[1:]).all()
