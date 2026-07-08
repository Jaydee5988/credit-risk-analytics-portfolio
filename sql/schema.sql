-- ============================================================================
-- schema.sql — Analytical data model for the credit-risk data mart
-- ============================================================================
-- Dialect: ANSI SQL / PostgreSQL. Runs on Postgres 12+ without extensions.
--
-- Purpose
-- -------
-- This is the reporting/analytics layer a credit-risk team would query on top
-- of a loan servicing system. It is intentionally simple (star-ish schema):
--
--   dim_loan            one row per loan  (origination attributes)
--   fact_loan_monthly   one row per loan per month  (performance snapshots)
--   fact_ecl            one row per loan  (latest PD/LGD/EAD/ECL output)
--   dim_scenario        macro scenario weights & multipliers
--
-- Column names mirror the Python portfolio in src/credit_risk/ so the same
-- concepts (dpd, ltv, dscr, ead, ifrs9_stage, ecl_weighted) appear end to end.
--
-- NOTE: These are DDL definitions plus a tiny illustrative seed so every query
-- in this folder parses and runs against an empty-or-seeded database. The
-- numbers are synthetic and for demonstration only — not real lending data.
-- The Python pipeline writes the equivalent tables to data/processed/*.csv;
-- loading those CSVs into these tables (COPY ... FROM) reproduces full results.
-- ============================================================================

DROP TABLE IF EXISTS fact_loan_monthly;
DROP TABLE IF EXISTS fact_ecl;
DROP TABLE IF EXISTS dim_loan;
DROP TABLE IF EXISTS dim_scenario;

-- ----------------------------------------------------------------------------
-- dim_loan — static / origination attributes, one row per loan.
-- ----------------------------------------------------------------------------
CREATE TABLE dim_loan (
    loan_id           INTEGER      PRIMARY KEY,
    origination_date  DATE         NOT NULL,
    sector            VARCHAR(32)  NOT NULL,   -- Residential, Office CRE, ...
    region            VARCHAR(32)  NOT NULL,
    credit_score      INTEGER      NOT NULL,   -- FICO-style, 520-820
    dti               NUMERIC(6,2) NOT NULL,   -- debt-to-income, %
    ltv_orig          NUMERIC(6,2) NOT NULL,   -- loan-to-value at origination, %
    dscr              NUMERIC(6,3) NOT NULL,   -- debt service coverage ratio
    loan_amount       NUMERIC(14,2) NOT NULL,  -- original exposure
    interest_rate     NUMERIC(6,3) NOT NULL,
    term_months       INTEGER      NOT NULL
);

-- ----------------------------------------------------------------------------
-- fact_loan_monthly — monthly performance snapshot, one row per loan-month.
-- This is the grain that powers vintage, roll-rate, loss-curve and migration
-- analysis. dpd_bucket is the standard delinquency bucketing used by servicers.
-- ----------------------------------------------------------------------------
CREATE TABLE fact_loan_monthly (
    loan_id             INTEGER     NOT NULL REFERENCES dim_loan(loan_id),
    snapshot_month      DATE        NOT NULL,      -- first day of the month
    months_on_book      INTEGER     NOT NULL,      -- age since origination
    outstanding_balance NUMERIC(14,2) NOT NULL,
    scheduled_payment   NUMERIC(14,2) NOT NULL,
    dpd                 INTEGER     NOT NULL,       -- days past due
    dpd_bucket          VARCHAR(16) NOT NULL,       -- Current,1-29,30-59,60-89,90+,ChargedOff
    utilization         NUMERIC(6,2),               -- revolving utilisation, %
    ifrs9_stage         SMALLINT    NOT NULL,       -- 1 / 2 / 3
    is_charged_off      SMALLINT    NOT NULL DEFAULT 0,
    charge_off_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
    recovery_amount     NUMERIC(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (loan_id, snapshot_month)
);

CREATE INDEX ix_flm_month  ON fact_loan_monthly (snapshot_month);
CREATE INDEX ix_flm_bucket ON fact_loan_monthly (dpd_bucket);

-- ----------------------------------------------------------------------------
-- fact_ecl — one row per loan: latest model output (mirrors ecl_loan_level).
-- ----------------------------------------------------------------------------
CREATE TABLE fact_ecl (
    loan_id         INTEGER      PRIMARY KEY REFERENCES dim_loan(loan_id),
    as_of_date      DATE         NOT NULL,
    sector          VARCHAR(32)  NOT NULL,
    region          VARCHAR(32)  NOT NULL,
    ead             NUMERIC(14,2) NOT NULL,   -- exposure at default
    pd_12m          NUMERIC(9,6) NOT NULL,    -- 12-month PD (calibrated)
    pd_lifetime     NUMERIC(9,6) NOT NULL,
    lgd             NUMERIC(9,6) NOT NULL,
    current_dpd     INTEGER      NOT NULL,
    ifrs9_stage     SMALLINT     NOT NULL,
    ecl_base        NUMERIC(14,2) NOT NULL,
    ecl_downside    NUMERIC(14,2) NOT NULL,
    ecl_severe      NUMERIC(14,2) NOT NULL,
    ecl_weighted    NUMERIC(14,2) NOT NULL,   -- reported IFRS 9 allowance
    coverage_ratio  NUMERIC(9,6) NOT NULL     -- ecl_weighted / ead
);

-- ----------------------------------------------------------------------------
-- dim_scenario — macro scenario definitions (matches config.SCENARIOS).
-- ----------------------------------------------------------------------------
CREATE TABLE dim_scenario (
    scenario        VARCHAR(16) PRIMARY KEY,
    weight          NUMERIC(4,2) NOT NULL,
    pd_multiplier   NUMERIC(4,2) NOT NULL,
    lgd_multiplier  NUMERIC(4,2) NOT NULL,
    unemployment    NUMERIC(4,1) NOT NULL,
    rate_shock_bps  INTEGER      NOT NULL,
    rent_shock_pct  NUMERIC(4,2) NOT NULL
);

INSERT INTO dim_scenario VALUES
    ('base',     0.50, 1.00, 1.00,  4.0,   0,  0.00),
    ('downside', 0.35, 1.75, 1.20,  7.0, 150, -0.10),
    ('severe',   0.15, 3.00, 1.45, 10.0, 300, -0.25);

-- ----------------------------------------------------------------------------
-- Minimal illustrative seed so the query files run standalone.
-- (Two loans, a few monthly snapshots each. Replace with COPY from
--  data/processed/ for the full 12,000-loan portfolio.)
-- ----------------------------------------------------------------------------
INSERT INTO dim_loan
    (loan_id, origination_date, sector, region, credit_score, dti, ltv_orig,
     dscr, loan_amount, interest_rate, term_months)
VALUES
    (1, DATE '2023-01-01', 'Residential', 'Denver Metro', 705, 32.0, 68.0,
     1.42, 320000.00, 6.50, 360),
    (2, DATE '2023-04-01', 'Office CRE',  'Mountain West', 640, 44.0, 82.0,
     1.05, 1800000.00, 7.20, 240);

INSERT INTO fact_loan_monthly
    (loan_id, snapshot_month, months_on_book, outstanding_balance,
     scheduled_payment, dpd, dpd_bucket, utilization, ifrs9_stage,
     is_charged_off, charge_off_amount, recovery_amount)
VALUES
    (1, DATE '2023-01-01', 0, 320000, 2000,  0, 'Current', 20, 1, 0, 0, 0),
    (1, DATE '2023-02-01', 1, 319000, 2000,  0, 'Current', 22, 1, 0, 0, 0),
    (1, DATE '2023-03-01', 2, 318000, 2000, 15, '1-29',    25, 1, 0, 0, 0),
    (2, DATE '2023-04-01', 0, 1800000, 14000,  0, 'Current', 55, 1, 0, 0, 0),
    (2, DATE '2023-05-01', 1, 1795000, 14000, 35, '30-59',   60, 2, 0, 0, 0),
    (2, DATE '2023-06-01', 2, 1790000, 14000, 95, '90+',     70, 3, 0, 0, 0),
    (2, DATE '2023-07-01', 3, 0,       14000, 999, 'ChargedOff', 70, 3, 1,
     1200000, 250000);

INSERT INTO fact_ecl
    (loan_id, as_of_date, sector, region, ead, pd_12m, pd_lifetime, lgd,
     current_dpd, ifrs9_stage, ecl_base, ecl_downside, ecl_severe,
     ecl_weighted, coverage_ratio)
VALUES
    (1, DATE '2023-03-01', 'Residential', 'Denver Metro', 315000, 0.021000,
     0.100600, 0.230000, 15, 1521.45, 3193.05, 6626.30, 2830.66, 0.008986),
    (2, DATE '2023-07-01', 'Office CRE', 'Mountain West', 1200000, 1.000000,
     1.000000, 0.520000, 999, 624000.00, 748800.00, 904800.00, 702000.00,
     0.585000);
