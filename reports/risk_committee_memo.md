# Credit Risk Committee — Quarterly Portfolio Risk Memo

**To:** Credit Risk Committee
**From:** Credit Risk Analytics
**Date:** 2026-07-08
**Re:** Portfolio credit quality, ECL allowance, stress results & watchlist
**Classification:** Internal — Demonstration

> **Note.** Figures are from a **synthetic, reproducible** portfolio (seed 42,
> n = 12,000) produced by `run_pipeline.py`. This memo is a **work sample** in
> real risk-committee format; it is not based on real lending data.

---

## 1. Executive summary

- The book totals **$1.70bn EAD** across 12,000 loans. Credit quality is
  **barbell-shaped**: 48% of loans are prime (Band A), but a heavy 23% tail sits
  in the substandard band (Band E).
- The IFRS 9 **probability-weighted ECL allowance is $211.2m (12.45% coverage)**.
  85% of the allowance sits in Stage 2/3, consistent with the standard.
- Under the **severe** macro scenario, portfolio loss rises to an **18.3% loss
  rate ($310m)** — roughly **2.6× the base case** ($121m / 7.2%).
- Concentration is **moderate**: sector HHI 0.222, region HHI 0.225. Largest
  exposures are **Multifamily (31%)** and **Colorado Springs (30%)**.
- The early-warning system flags a watchlist capturing **45% of near-term
  delinquencies in the top decile**. **Recommended actions in §7.**

---

## 2. Portfolio overview

| Metric | Value |
|--------|------:|
| Loans | 12,000 |
| Total EAD | $1,696.4m |
| Realised default rate (synthetic) | 18.5% |
| Weighted ECL allowance | $211.2m |
| Coverage ratio | 12.45% |
| Sector HHI / Region HHI | 0.222 / 0.225 |

**Distribution by PD risk band:**

| Band | % of book | Observed default rate |
|------|----------:|----------------------:|
| A (Prime) | 47.6% | 0.6% |
| B (Near-prime) | 12.1% | 2.8% |
| C (Acceptable) | 7.5% | 12.2% |
| D (Watch) | 10.1% | 22.3% |
| E (Substandard) | 22.6% | 64.9% |

---

## 3. Key model outputs

| Model | Headline | Read-across |
|-------|----------|-------------|
| **PD** | ROC-AUC 0.94; bands monotonic & calibrated | Rank-ordering reliable for pricing/staging |
| **LGD** | Mean severity 34.8%; Office CRE highest (~52%) | Collateral-driven; CRE the loss-severe segment |
| **ECL** | $211.2m weighted; coverage 1.4%→31%→36% by stage | Allowance concentrated where risk is, as intended |
| **EWS** | ROC-AUC 0.93; 45% top-decile capture | Efficient targeting for collections |

**ECL by IFRS 9 stage:**

| Stage | Loans | EAD | ECL | Coverage |
|------:|------:|----:|----:|---------:|
| 1 | 7,983 | $1,119.5m | $16.2m | 1.4% |
| 2 | 1,798 | $258.4m | $80.2m | 31.0% |
| 3 | 2,219 | $318.5m | $114.8m | 36.0% |

---

## 4. Scenario / stress results

| Scenario (weight) | Unemployment | Expected loss | Loss rate | vs base |
|-------------------|-------------:|--------------:|----------:|--------:|
| Base (50%) | 4.0% | $121.4m | 7.2% | — |
| Downside (35%) | 7.0% | $203.7m | 12.0% | +$82.3m |
| Severe (15%) | 10.0% | $310.4m | 18.3% | +$189.1m |

**Sensitivity (single-factor):** a combined **PD +25% / LGD +15%** rate-shock
proxy raises expected loss **+36%**. Loss is roughly twice as sensitive to PD as
to LGD shocks of equal size — unemployment/PD deterioration is the dominant risk.

---

## 5. Watchlist

Top exposures by expected-loss-at-risk from the early-warning model (full list:
`model_summary.md`, extraction logic: `sql/08_watchlist_extraction.sql`):

| Loan | Sector | Region | EWS score | Exp. loss at risk | Current DPD |
|-----:|--------|--------|----------:|------------------:|------------:|
| 7244 | Office CRE | Mountain West | 0.99 | $273k | 19 |
| 2979 | Retail CRE | Mountain West | 1.00 | $254k | 4 |
| 5380 | Office CRE | Denver Metro | 0.99 | $132k | 22 |
| 1423 | Multifamily | National | 0.99 | $122k | 21 |
| 801 | Retail CRE | National | 0.99 | $122k | 21 |

Watchlist stress is concentrated in **CRE (Office/Retail) and Mountain West** —
consistent with the sector-level LGD and default-rate signals.

---

## 6. Top risks

1. **Substandard tail (Band E, 23% of book, 65% default rate)** — the dominant
   driver of both ECL and stress-case loss.
2. **CRE loss severity** — Office CRE LGD ~52%; a rent/valuation shock hits both
   PD and LGD simultaneously (the +36% combined-shock sensitivity).
3. **Concentration** — Multifamily (31%) and Colorado Springs (30%) are single
   points of failure under a regional/sector downturn.
4. **Downturn convexity** — severe-scenario loss is 2.6× base; the allowance is
   adequate at base but coverage thins fast if PD multipliers realise.
5. **Model risk** — PD shows mild mid-band miscalibration and lacks an
   out-of-time backtest (see `docs/model_validation_report.md`, findings F1/F3).

---

## 7. Recommended actions

| # | Action | Owner | Priority |
|---|--------|-------|:--------:|
| 1 | Tighten origination criteria for Band D/E CRE; add pricing floors | Credit Policy | **High** |
| 2 | Proactive outreach on top-50 watchlist accounts before charge-off | Servicing/Collections | **High** |
| 3 | Set/confirm concentration limits for Multifamily & Colorado Springs | Portfolio Mgmt | Medium |
| 4 | Hold allowance at severe-weighted level pending macro clarity | Finance/CRO | Medium |
| 5 | Recalibrate PD mid-bands; add PD term structure & OOT backtest | Modelling/MRM | Medium |

---

## 8. Limitations

Synthetic data with a *designed* signal — real portfolios will show lower model
performance and messier calibration. Macro multipliers are illustrative planning
assumptions, not econometric forecasts. Lifetime PD uses a simplified
constant-hazard transform. Full model caveats: `docs/model_cards.md` and
`docs/model_validation_report.md`.

---

*Prepared by Credit Risk Analytics. Reproducible via `python run_pipeline.py`.
Supporting detail: `reports/model_summary.md`, `docs/`, and `sql/`.*
