#!/usr/bin/env python3
"""End-to-end pipeline: generate data, train all 5 models, write reports.

Usage:
    python run_pipeline.py               # full run (default portfolio size)
    python run_pipeline.py --n 3000      # smaller/faster run
    python run_pipeline.py --no-figures  # skip PNG generation

All artefacts land in data/processed/ (tables + metrics) and reports/
(figures + model_summary.md).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from credit_risk import (  # noqa: E402
    data_generation,
    ecl_engine,
    early_warning,
    lgd_model,
    pd_model,
    report,
    stress_testing,
)
from credit_risk.config import N_LOANS  # noqa: E402
from credit_risk.utils import save_metrics, save_table  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Credit risk analytics pipeline")
    parser.add_argument("--n", type=int, default=N_LOANS, help="number of loans")
    parser.add_argument("--no-figures", action="store_true", help="skip figures")
    args = parser.parse_args()
    make_figures = not args.no_figures

    t0 = time.time()
    print(f"[1/7] Generating synthetic portfolio (n={args.n:,}) ...")
    df = data_generation.generate_portfolio(n=args.n)
    save_table(df, "portfolio")
    print(f"      default rate = {df['default_flag'].mean():.2%}, "
          f"defaulted loans = {int(df['default_flag'].sum()):,}")

    print("[2/7] Training PD model (logistic vs gradient boosting) ...")
    pd_res = pd_model.train_pd_model(df, make_figures=make_figures)
    save_metrics(pd_res.metrics, "pd_metrics")
    save_table(pd_res.score_bands, "pd_score_bands")
    save_table(pd_res.scored, "pd_scored")
    print(f"      best={pd_res.best_model_name} "
          f"ROC-AUC={pd_res.metrics[pd_res.best_model_name]['roc_auc']:.3f}")

    print("[3/7] Training LGD model ...")
    lgd_res = lgd_model.train_lgd_model(df, make_figures=make_figures)
    save_metrics(lgd_res.metrics, "lgd_metrics")
    save_table(lgd_res.segment_errors, "lgd_segment_errors")
    save_table(lgd_res.predicted, "lgd_scored")
    print(f"      MAE={lgd_res.metrics['mae']:.4f} RMSE={lgd_res.metrics['rmse']:.4f}")

    print("[4/7] Computing ECL (PD x LGD x EAD, scenario-weighted) ...")
    ecl_res = ecl_engine.compute_ecl(df, pd_res.scored, lgd_res.predicted,
                                     make_figures=make_figures)
    save_metrics(ecl_res.portfolio, "ecl_portfolio")
    save_table(ecl_res.by_stage, "ecl_by_stage")
    save_table(ecl_res.by_scenario, "ecl_by_scenario")
    save_table(ecl_res.loan_level, "ecl_loan_level")
    print(f"      weighted ECL={ecl_res.portfolio['weighted_ecl']:,.0f} "
          f"coverage={ecl_res.portfolio['coverage_ratio']:.2%}")

    print("[5/7] Running stress tests ...")
    stress_res = stress_testing.run_stress_test(df, pd_res.scored, lgd_res.predicted,
                                                make_figures=make_figures)
    save_metrics(stress_res.concentration_metrics, "stress_concentration")
    save_table(stress_res.scenario_summary, "stress_scenarios")
    save_table(stress_res.sensitivity, "stress_sensitivity")
    print(f"      severe-scenario loss rate="
          f"{stress_res.scenario_summary.query('scenario==\"severe\"')['loss_rate'].iloc[0]:.2%}")

    print("[6/7] Training early-warning model ...")
    ews_res = early_warning.train_ews_model(df, make_figures=make_figures)
    save_metrics(ews_res.metrics, "ews_metrics")
    save_table(ews_res.watchlist, "ews_watchlist")
    print(f"      ROC-AUC={ews_res.metrics['roc_auc']:.3f} "
          f"top-decile capture={ews_res.metrics['top_decile_capture_rate']:.2%}")

    print("[7/7] Writing model summary report ...")
    results = {"pd": pd_res, "lgd": lgd_res, "ecl": ecl_res,
               "stress": stress_res, "ews": ews_res}
    out = report.build_summary(results)
    print(f"      wrote {out}")

    print(f"\nDone in {time.time() - t0:.1f}s. "
          "See reports/model_summary.md and reports/figures/.")


if __name__ == "__main__":
    main()
