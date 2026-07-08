"""Central configuration: paths, constants, and shared assumptions.

Keeping tunable assumptions in one place makes the portfolio auditable — a
reviewer can see every macro/scenario assumption without reading model code.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data" / "processed"
REPORTS_DIR = ROOT_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

for _d in (DATA_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Synthetic portfolio assumptions
# ---------------------------------------------------------------------------
N_LOANS = 12_000
SECTORS = ["Residential", "Multifamily", "Retail CRE", "Office CRE", "Industrial"]
REGIONS = ["Colorado Springs", "Denver Metro", "Front Range", "Mountain West", "National"]

# ---------------------------------------------------------------------------
# ECL / IFRS 9 - CECL style staging assumptions
# ---------------------------------------------------------------------------
# Stage 1: 12-month ECL. Stage 2 / 3: lifetime ECL.
LIFETIME_HORIZON_YEARS = 5
STAGE2_PD_THRESHOLD = 0.15        # 12m PD above this => significant increase in credit risk
STAGE2_DPD_THRESHOLD = 30         # 30+ days past due => Stage 2
STAGE3_DPD_THRESHOLD = 90         # 90+ days past due / default => Stage 3
DISCOUNT_RATE = 0.08              # effective interest rate used to discount ECL

# ---------------------------------------------------------------------------
# Macro-economic scenarios for ECL weighting and stress testing.
# Weights sum to 1.0. Multipliers scale baseline PD/LGD.
# These are illustrative planning assumptions, not forecasts.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "base": {
        "weight": 0.50,
        "pd_multiplier": 1.00,
        "lgd_multiplier": 1.00,
        "unemployment": 4.0,
        "rate_shock_bps": 0,
        "rent_shock_pct": 0.0,
    },
    "downside": {
        "weight": 0.35,
        "pd_multiplier": 1.75,
        "lgd_multiplier": 1.20,
        "unemployment": 7.0,
        "rate_shock_bps": 150,
        "rent_shock_pct": -0.10,
    },
    "severe": {
        "weight": 0.15,
        "pd_multiplier": 3.00,
        "lgd_multiplier": 1.45,
        "unemployment": 10.0,
        "rate_shock_bps": 300,
        "rent_shock_pct": -0.25,
    },
}

# Score band cutoffs for PD (probability of default), low->high risk.
SCORE_BANDS = [
    ("A (Prime)", 0.00, 0.03),
    ("B (Near-prime)", 0.03, 0.08),
    ("C (Acceptable)", 0.08, 0.15),
    ("D (Watch)", 0.15, 0.30),
    ("E (Substandard)", 0.30, 1.01),
]
