"""Model 4 — Credit portfolio stress testing.

Applies base / downside / severe macro scenarios to the portfolio, measures
sector and geography concentration, and reports sensitivity to unemployment,
interest-rate, and rent-shock proxies. Reuses the ECL scenario multipliers so
stress results are consistent with the ECL engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from . import plotting
from .config import SCENARIOS


def _herfindahl(exposures: np.ndarray) -> float:
    """Herfindahl-Hirschman Index of concentration (0=diffuse, 1=single-name)."""
    total = exposures.sum()
    if total <= 0:
        return 0.0
    shares = exposures / total
    return float(np.sum(shares ** 2))


@dataclass
class StressResult:
    scenario_summary: pd.DataFrame
    sector_concentration: pd.DataFrame
    region_concentration: pd.DataFrame
    sensitivity: pd.DataFrame
    concentration_metrics: dict[str, Any]
    figures: dict[str, str] = field(default_factory=dict)


def run_stress_test(
    df: pd.DataFrame,
    pd_hat: pd.DataFrame,
    lgd_hat: pd.DataFrame,
    make_figures: bool = True,
) -> StressResult:
    base = (
        df[["loan_id", "sector", "region", "ead"]]
        .merge(pd_hat, on="loan_id")
        .merge(lgd_hat, on="loan_id")
    )
    pd0 = base["pd_hat"].to_numpy()
    lgd0 = base["lgd_hat"].to_numpy()
    ead = base["ead"].to_numpy()

    # ---- Scenario expected losses --------------------------------------
    rows = []
    scenario_loss = {}
    for name, cfg in SCENARIOS.items():
        pd_s = np.clip(pd0 * cfg["pd_multiplier"], 0, 1)
        lgd_s = np.clip(lgd0 * cfg["lgd_multiplier"], 0, 1)
        el = pd_s * lgd_s * ead
        scenario_loss[name] = el
        rows.append(
            {
                "scenario": name,
                "unemployment": cfg["unemployment"],
                "rate_shock_bps": cfg["rate_shock_bps"],
                "rent_shock_pct": cfg["rent_shock_pct"],
                "expected_loss": float(el.sum()),
                "loss_rate": float(el.sum() / ead.sum()),
                "avg_stressed_pd": float(pd_s.mean()),
                "avg_stressed_lgd": float(lgd_s.mean()),
            }
        )
    scenario_summary = pd.DataFrame(rows)
    base_loss = scenario_summary.loc[
        scenario_summary["scenario"] == "base", "expected_loss"
    ].iloc[0]
    scenario_summary["loss_increase_vs_base"] = (
        scenario_summary["expected_loss"] - base_loss
    )

    # ---- Concentration analysis ----------------------------------------
    def _concentration(group_col: str, severe_loss: np.ndarray) -> pd.DataFrame:
        g = base.assign(severe_loss=severe_loss).groupby(group_col)
        out = g.agg(exposure=("ead", "sum"),
                    n_loans=("loan_id", "size"),
                    severe_loss=("severe_loss", "sum")).reset_index()
        out["exposure_share"] = out["exposure"] / out["exposure"].sum()
        out["severe_loss_rate"] = out["severe_loss"] / out["exposure"]
        return out.sort_values("exposure", ascending=False).reset_index(drop=True)

    sev = scenario_loss["severe"]
    sector_conc = _concentration("sector", sev)
    region_conc = _concentration("region", sev)

    concentration_metrics = {
        "sector_hhi": _herfindahl(sector_conc["exposure"].to_numpy()),
        "region_hhi": _herfindahl(region_conc["exposure"].to_numpy()),
        "top_sector": sector_conc.iloc[0]["sector"],
        "top_sector_share": float(sector_conc.iloc[0]["exposure_share"]),
        "top_region": region_conc.iloc[0]["region"],
        "top_region_share": float(region_conc.iloc[0]["exposure_share"]),
    }

    # ---- Single-factor sensitivity -------------------------------------
    # Perturb one risk driver at a time and measure Δ expected loss vs base.
    sens_rows = []
    base_el = (pd0 * lgd0 * ead).sum()
    sensitivities = {
        "PD +25% (unemployment proxy)": (1.25, 1.00),
        "PD +50% (unemployment proxy)": (1.50, 1.00),
        "LGD +15% (collateral/rent proxy)": (1.00, 1.15),
        "LGD +30% (collateral/rent proxy)": (1.00, 1.30),
        "PD +25% & LGD +15% (rate shock)": (1.25, 1.15),
    }
    for label, (pm, lm) in sensitivities.items():
        el = (np.clip(pd0 * pm, 0, 1) * np.clip(lgd0 * lm, 0, 1) * ead).sum()
        sens_rows.append(
            {
                "shock": label,
                "expected_loss": float(el),
                "delta_vs_base": float(el - base_el),
                "pct_change": float((el - base_el) / base_el),
            }
        )
    sensitivity = pd.DataFrame(sens_rows).sort_values("delta_vs_base", ascending=False)

    figures: dict[str, str] = {}
    if make_figures:
        figures["stress_scenarios"] = str(
            plotting.plot_stress_waterfall(
                scenario_summary["scenario"].tolist(),
                scenario_summary["expected_loss"].tolist(),
                "stress_scenarios", "Expected Loss by Stress Scenario")
        )
        figures["stress_sector_concentration"] = str(
            plotting.plot_concentration(sector_conc, "sector",
                                        "stress_sector_concentration",
                                        "Exposure Concentration by Sector")
        )
        figures["stress_region_concentration"] = str(
            plotting.plot_concentration(region_conc, "region",
                                        "stress_region_concentration",
                                        "Exposure Concentration by Region")
        )

    return StressResult(
        scenario_summary=scenario_summary,
        sector_concentration=sector_conc,
        region_concentration=region_conc,
        sensitivity=sensitivity,
        concentration_metrics=concentration_metrics,
        figures=figures,
    )
