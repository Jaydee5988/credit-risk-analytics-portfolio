# Model Cards

Concise governance-style documentation for each model: purpose, inputs, method,
outputs, and limitations. All models are trained on **synthetic** data and are
for demonstration only — not production underwriting.

Global assumptions live in `src/credit_risk/config.py` (random seed, portfolio
size, macro scenarios, IFRS 9 staging thresholds, discount rate, score bands).

---

## 0. Synthetic data generator

- **Purpose:** produce a reproducible, dependency-free loan book with a genuine
  latent default signal so every model learns something real.
- **Method:** borrower attributes (credit score, DTI, LTV, DSCR, utilisation,
  sector, region) drive a logistic latent PD; defaults are drawn from it. LGD is
  driven by LTV, DSCR, and sector liquidity. Twelve monthly behavioural snapshots
  (DPD, utilisation, missed payments) are simulated and summarised.
- **Outputs:** one row per loan with attributes, EAD, `default_flag`, realised
  `lgd` (defaults only), and behavioural summaries.
- **Limitation:** signal is designed, not observed; correlations are cleaner than
  reality. Default rate ≈ 18% is intentionally elevated for a risk demonstration.

---

## 1. Probability of Default (PD)

- **Purpose:** estimate 12-month probability of default per loan.
- **Inputs:** credit score, DTI, LTV, DSCR, loan amount, rate, term, age,
  utilisation, missed payments, max DPD, sector, region.
- **Method:** `StandardScaler` + one-hot in a pipeline; **logistic regression**
  (class-balanced, isotonically calibrated) compared against
  **gradient boosting**. Best model chosen by ROC-AUC.
- **Outputs:** calibrated PD per loan, ROC/PR curves, calibration curve,
  confusion matrix at a 0.15 policy threshold, and five risk score bands.
- **Metrics:** ROC-AUC, PR-AUC, Brier score.
- **Limitation:** point-in-time 12-month PD only; no through-the-cycle
  adjustment or PD term structure.

## 2. Loss Given Default (LGD)

- **Purpose:** predict loss severity (0–1) on defaulted loans.
- **Inputs:** LTV, DSCR, credit score, loan amount, rate, utilisation, sector,
  region — trained on the defaulted subpopulation only.
- **Method:** gradient-boosted regression; predictions clipped to [0, 1].
- **Outputs:** LGD per loan, predicted-vs-actual scatter, sector-level error
  table, permutation-importance ranking of drivers.
- **Metrics:** MAE, RMSE, R².
- **Limitation:** no explicit recovery-timing/discounting of workout cash flows;
  LGD modelled as a single severity fraction.

## 3. Expected Credit Loss (ECL) engine

- **Purpose:** convert PD, LGD, and EAD into booked expected loss under IFRS 9 /
  CECL logic.
- **Method:** `ECL = PD × LGD × EAD × discount_factor` per loan.
  - **Staging:** Stage 1 (12-month PD); Stage 2 if 12m PD ≥ 0.15 or 30+ DPD
    (lifetime PD); Stage 3 if 90+ DPD or defaulted (PD = 1).
  - **Lifetime PD:** constant-hazard transform `1 − (1 − PD₁₂)^H`, H = 5y.
  - **Scenario weighting:** probability-weighted across base/downside/severe.
- **Outputs:** loan-level ECL (per scenario + weighted), ECL by stage, ECL by
  scenario, portfolio coverage ratio.
- **Limitation:** simplified discounting (single effective rate, horizon
  midpoint) and constant-hazard lifetime PD rather than a full curve.

## 4. Stress testing

- **Purpose:** quantify portfolio loss under macro stress and locate
  concentration risk.
- **Method:** apply scenario PD/LGD multipliers (tied to unemployment, rate, and
  rent-shock proxies) to compute scenario expected loss; single-factor
  sensitivity shocks; Herfindahl-Hirschman Index by sector and region.
- **Outputs:** scenario loss summary, sensitivity table, sector/region
  concentration tables and charts.
- **Limitation:** multipliers are illustrative planning assumptions, not outputs
  of a calibrated macro-econometric model.

## 5. Early-warning / delinquency

- **Purpose:** rank the live book by near-term delinquency risk for monitoring.
- **Inputs:** behavioural features — rolling/avg/max utilisation, utilisation
  trend, missed payments, avg/max/current DPD, plus DTI, DSCR, credit score.
- **Target:** near-term delinquency (`current_dpd ≥ 30` or eventual default).
- **Method:** gradient-boosted classifier; whole book scored and ranked.
- **Outputs:** delinquency probability per loan, top-25 watchlist with
  exposure-at-risk, watchlist chart.
- **Metrics:** ROC-AUC, PR-AUC, top-decile capture rate.
- **Limitation:** behavioural history is simulated as summary features rather
  than a true panel/sequence model; no survival/time-to-event treatment.
