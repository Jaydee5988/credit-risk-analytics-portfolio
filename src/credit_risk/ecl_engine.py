"""Model 3 — Expected Credit Loss (ECL) engine.

Combines PD, LGD, and EAD into loan-level and portfolio-level ECL using
IFRS 9 / CECL-style staging and probability-weighted macro scenarios.

Core identity (per stage/scenario):

    ECL = PD  x  LGD  x  EAD  x  discount_factor

Stage 1 uses a 12-month PD; Stages 2 and 3 use a lifetime PD (12m PD scaled to
the lifetime horizon via a survival transform). Stage 3 (already defaulted /
90+ DPD) is treated as PD = 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from . import plotting
from .config import (
    DISCOUNT_RATE,
    LIFETIME_HORIZON_YEARS,
    SCENARIOS,
    STAGE2_DPD_THRESHOLD,
    STAGE2_PD_THRESHOLD,
    STAGE3_DPD_THRESHOLD,
)


def lifetime_pd(pd_12m: np.ndarray, horizon_years: int = LIFETIME_HORIZON_YEARS) -> np.ndarray:
    """Convert a 12-month PD to a cumulative lifetime PD.

    Assuming a constant marginal hazard, survival to the horizon is
    (1 - PD_12m) ** horizon, so lifetime PD = 1 - that. Bounded to [0, 1].
    """
    pd_12m = np.clip(pd_12m, 0.0, 1.0)
    return 1.0 - np.power(1.0 - pd_12m, horizon_years)


def assign_stage(pd_12m: np.ndarray, current_dpd: np.ndarray,
                 default_flag: np.ndarray) -> np.ndarray:
    """Assign IFRS 9 stages 1/2/3 from PD, delinquency, and default status."""
    stage = np.ones_like(pd_12m, dtype=int)
    # Stage 2: significant increase in credit risk
    sicr = (pd_12m >= STAGE2_PD_THRESHOLD) | (current_dpd >= STAGE2_DPD_THRESHOLD)
    stage[sicr] = 2
    # Stage 3: credit-impaired / defaulted
    impaired = (current_dpd >= STAGE3_DPD_THRESHOLD) | (default_flag == 1)
    stage[impaired] = 3
    return stage


def _effective_pd(stage: np.ndarray, pd_12m: np.ndarray, pd_lifetime: np.ndarray) -> np.ndarray:
    """PD applied per stage: 12m for Stage 1, lifetime for Stage 2, 1.0 for Stage 3."""
    eff = np.where(stage == 1, pd_12m, pd_lifetime)
    eff = np.where(stage == 3, 1.0, eff)
    return eff


@dataclass
class ECLResult:
    loan_level: pd.DataFrame
    portfolio: dict[str, Any]
    by_stage: pd.DataFrame
    by_scenario: pd.DataFrame
    figures: dict[str, str] = field(default_factory=dict)


def compute_ecl(
    df: pd.DataFrame,
    pd_hat: pd.DataFrame,
    lgd_hat: pd.DataFrame,
    make_figures: bool = True,
) -> ECLResult:
    """Compute scenario-weighted ECL at loan and portfolio level.

    Parameters
    ----------
    df       : portfolio with ead, current_dpd, default_flag, loan_id
    pd_hat   : loan_id + pd_hat (12-month PD from the PD model)
    lgd_hat  : loan_id + lgd_hat (from the LGD model)
    """
    base = (
        df[["loan_id", "sector", "region", "ead", "current_dpd", "default_flag"]]
        .merge(pd_hat, on="loan_id")
        .merge(lgd_hat, on="loan_id")
    )

    pd_12m = base["pd_hat"].to_numpy()
    pd_life = lifetime_pd(pd_12m)
    stage = assign_stage(pd_12m, base["current_dpd"].to_numpy(),
                         base["default_flag"].to_numpy())
    base["stage"] = stage

    # discount factor: Stage 1 ~1 year, lifetime stages over the horizon midpoint.
    horizon = np.where(stage == 1, 1.0, LIFETIME_HORIZON_YEARS / 2.0)
    discount = 1.0 / np.power(1.0 + DISCOUNT_RATE, horizon)
    base["discount_factor"] = discount

    ead = base["ead"].to_numpy()
    lgd = base["lgd_hat"].to_numpy()

    scenario_ecls = {}
    for name, cfg in SCENARIOS.items():
        pd_scn = np.clip(pd_12m * cfg["pd_multiplier"], 0, 1)
        pd_life_scn = lifetime_pd(pd_scn)
        eff_pd = _effective_pd(stage, pd_scn, pd_life_scn)
        lgd_scn = np.clip(lgd * cfg["lgd_multiplier"], 0, 1)
        ecl = eff_pd * lgd_scn * ead * discount
        base[f"ecl_{name}"] = ecl
        scenario_ecls[name] = ecl

    # Probability-weighted ECL (the reported IFRS 9 number).
    weights = {k: v["weight"] for k, v in SCENARIOS.items()}
    weighted = sum(scenario_ecls[k] * w for k, w in weights.items())
    base["ecl_weighted"] = weighted

    # effective (base-scenario) PD/LGD for reporting
    base["effective_pd_base"] = _effective_pd(stage, pd_12m, pd_life)
    base["coverage_ratio"] = base["ecl_weighted"] / base["ead"].replace(0, np.nan)

    # ---- Aggregations --------------------------------------------------
    by_stage = (
        base.groupby("stage")
        .agg(n_loans=("loan_id", "size"),
             ead=("ead", "sum"),
             ecl=("ecl_weighted", "sum"),
             avg_pd=("effective_pd_base", "mean"),
             avg_lgd=("lgd_hat", "mean"))
        .reset_index()
    )
    by_stage["coverage_ratio"] = by_stage["ecl"] / by_stage["ead"]

    by_scenario = pd.DataFrame(
        {
            "scenario": list(SCENARIOS.keys()),
            "weight": [SCENARIOS[k]["weight"] for k in SCENARIOS],
            "ecl": [float(scenario_ecls[k].sum()) for k in SCENARIOS],
        }
    )

    total_ead = float(ead.sum())
    total_ecl = float(weighted.sum())
    portfolio = {
        "total_ead": total_ead,
        "weighted_ecl": total_ecl,
        "coverage_ratio": total_ecl / total_ead if total_ead else 0.0,
        "ecl_base": float(scenario_ecls["base"].sum()),
        "ecl_downside": float(scenario_ecls["downside"].sum()),
        "ecl_severe": float(scenario_ecls["severe"].sum()),
        "n_stage1": int((stage == 1).sum()),
        "n_stage2": int((stage == 2).sum()),
        "n_stage3": int((stage == 3).sum()),
    }

    figures: dict[str, str] = {}
    if make_figures:
        figures["ecl_by_stage"] = str(
            plotting.plot_ecl_by_stage(by_stage, "ecl_by_stage",
                                       "ECL by IFRS 9 Stage")
        )
        figures["ecl_by_scenario"] = str(
            plotting.plot_scenario_ecl(by_scenario, "ecl_by_scenario",
                                       "Portfolio ECL by Macro Scenario")
        )

    return ECLResult(
        loan_level=base,
        portfolio=portfolio,
        by_stage=by_stage,
        by_scenario=by_scenario,
        figures=figures,
    )
