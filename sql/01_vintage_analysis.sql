-- ============================================================================
-- 01_vintage_analysis.sql — Vintage (cohort-by-age) delinquency curves
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "Are loans we originated recently going bad faster than older vintages?"
-- Vintage analysis groups loans by origination cohort (here: quarter) and
-- tracks a performance metric by months_on_book. Comparing the same age across
-- vintages isolates underwriting quality from portfolio seasoning — the core
-- diagnostic for spotting deteriorating origination standards early.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1a. 90+ DPD rate by origination vintage and age (the classic vintage curve).
--     Read across a row to see how a cohort ages; read down a column to compare
--     cohorts at the same age.
-- ---------------------------------------------------------------------------
WITH loan_vintage AS (
    SELECT
        loan_id,
        -- Bucket origination into a YYYY-Qn cohort label.
        EXTRACT(YEAR FROM origination_date)::INT                       AS vintage_year,
        EXTRACT(QUARTER FROM origination_date)::INT                    AS vintage_quarter,
        EXTRACT(YEAR FROM origination_date)::INT || '-Q'
            || EXTRACT(QUARTER FROM origination_date)::INT             AS vintage
    FROM dim_loan
),
monthly AS (
    SELECT
        v.vintage,
        m.months_on_book,
        m.loan_id,
        CASE WHEN m.dpd >= 90 OR m.dpd_bucket IN ('90+', 'ChargedOff')
             THEN 1 ELSE 0 END                                         AS is_90plus
    FROM fact_loan_monthly m
    JOIN loan_vintage v USING (loan_id)
)
SELECT
    vintage,
    months_on_book,
    COUNT(*)                                   AS loans_observed,
    SUM(is_90plus)                             AS loans_90plus,
    ROUND(AVG(is_90plus)::NUMERIC, 4)          AS rate_90plus
FROM monthly
GROUP BY vintage, months_on_book
ORDER BY vintage, months_on_book;

-- ---------------------------------------------------------------------------
-- 1b. Cumulative bad rate by age — once a loan hits 90+ it stays "ever bad".
--     Cumulative curves are what credit teams chart to compare vintages on a
--     single monotonic line. Uses a window MAX to make the flag "sticky".
-- ---------------------------------------------------------------------------
WITH loan_vintage AS (
    SELECT loan_id,
           EXTRACT(YEAR FROM origination_date)::INT || '-Q'
               || EXTRACT(QUARTER FROM origination_date)::INT AS vintage
    FROM dim_loan
),
flagged AS (
    SELECT
        v.vintage,
        m.loan_id,
        m.months_on_book,
        -- Sticky "ever 90+ up to this age" flag per loan.
        MAX(CASE WHEN m.dpd >= 90 OR m.dpd_bucket IN ('90+', 'ChargedOff')
                 THEN 1 ELSE 0 END)
            OVER (PARTITION BY m.loan_id ORDER BY m.months_on_book) AS ever_90plus
    FROM fact_loan_monthly m
    JOIN loan_vintage v USING (loan_id)
)
SELECT
    vintage,
    months_on_book,
    COUNT(DISTINCT loan_id)                     AS cohort_size,
    ROUND(AVG(ever_90plus)::NUMERIC, 4)         AS cumulative_bad_rate
FROM flagged
GROUP BY vintage, months_on_book
ORDER BY vintage, months_on_book;
