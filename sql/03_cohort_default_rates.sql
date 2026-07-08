-- ============================================================================
-- 03_cohort_default_rates.sql — Cohort default rates by segment
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "What is the realised default rate by origination cohort, and how does it
--  break down by credit-score band and sector?" Cohort default rates validate
-- that risk-based pricing/underwriting is working: worse score bands and
-- riskier sectors should show materially higher default rates.
--
-- Default definition: a loan is "defaulted" if it ever reaches 90+ DPD or is
-- charged off within the observation window (a standard 90-DPD default flag).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 3a. Default rate by origination quarter x credit-score band.
-- ---------------------------------------------------------------------------
WITH loan_default AS (
    SELECT
        l.loan_id,
        l.origination_date,
        l.sector,
        l.credit_score,
        MAX(CASE WHEN m.dpd >= 90 OR m.dpd_bucket IN ('90+', 'ChargedOff')
                 THEN 1 ELSE 0 END) AS defaulted
    FROM dim_loan l
    JOIN fact_loan_monthly m USING (loan_id)
    GROUP BY l.loan_id, l.origination_date, l.sector, l.credit_score
),
banded AS (
    SELECT *,
        EXTRACT(YEAR FROM origination_date)::INT || '-Q'
            || EXTRACT(QUARTER FROM origination_date)::INT AS vintage,
        CASE
            WHEN credit_score >= 740 THEN '1. 740+ (Prime)'
            WHEN credit_score >= 680 THEN '2. 680-739 (Near-prime)'
            WHEN credit_score >= 620 THEN '3. 620-679 (Subprime)'
            ELSE                          '4. <620 (Deep subprime)'
        END AS score_band
    FROM loan_default
)
SELECT
    vintage,
    score_band,
    COUNT(*)                                 AS loans,
    SUM(defaulted)                           AS defaults,
    ROUND(AVG(defaulted)::NUMERIC, 4)        AS default_rate
FROM banded
GROUP BY vintage, score_band
ORDER BY vintage, score_band;

-- ---------------------------------------------------------------------------
-- 3b. Default rate by sector with a portfolio-wide comparison and index.
--     default_rate_index > 1.0 flags sectors riskier than the book average —
--     a quick concentration-of-risk read for the credit committee.
-- ---------------------------------------------------------------------------
WITH loan_default AS (
    SELECT
        l.loan_id,
        l.sector,
        MAX(CASE WHEN m.dpd >= 90 OR m.dpd_bucket IN ('90+', 'ChargedOff')
                 THEN 1 ELSE 0 END) AS defaulted
    FROM dim_loan l
    JOIN fact_loan_monthly m USING (loan_id)
    GROUP BY l.loan_id, l.sector
)
SELECT
    sector,
    COUNT(*)                                                    AS loans,
    SUM(defaulted)                                              AS defaults,
    ROUND(AVG(defaulted)::NUMERIC, 4)                           AS default_rate,
    ROUND(AVG(AVG(defaulted)) OVER ()::NUMERIC, 4)              AS portfolio_default_rate,
    ROUND( (AVG(defaulted) / NULLIF(AVG(AVG(defaulted)) OVER (), 0))::NUMERIC, 2)
                                                                AS default_rate_index
FROM loan_default
GROUP BY sector
ORDER BY default_rate DESC;
