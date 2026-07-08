-- ============================================================================
-- 08_watchlist_extraction.sql — Early-warning watchlist extraction
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "Which accounts should collections/servicing act on now, ranked by expected
--  loss at risk?" This reproduces the early-warning watchlist logic in SQL:
-- combine behavioural stress signals (delinquency, utilisation, stage) with
-- exposure to prioritise intervention before charge-off.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 8a. Latest behavioural snapshot per loan (the "current" servicing view).
-- ---------------------------------------------------------------------------
WITH latest_snapshot AS (
    SELECT DISTINCT ON (loan_id)
        loan_id, snapshot_month, dpd, dpd_bucket, utilization,
        ifrs9_stage, outstanding_balance
    FROM fact_loan_monthly
    ORDER BY loan_id, snapshot_month DESC     -- Postgres DISTINCT ON = latest row
),
-- Trailing 6-month behaviour: how many months delinquent, peak DPD, util trend.
trailing AS (
    SELECT
        loan_id,
        SUM(CASE WHEN dpd > 0 THEN 1 ELSE 0 END) AS months_delinquent_6m,
        MAX(dpd)                                 AS max_dpd_6m,
        MAX(utilization) - MIN(utilization)      AS util_range_6m
    FROM (
        SELECT loan_id, dpd, utilization,
               ROW_NUMBER() OVER (PARTITION BY loan_id
                                  ORDER BY snapshot_month DESC) AS rn
        FROM fact_loan_monthly
    ) w
    WHERE rn <= 6
    GROUP BY loan_id
)
SELECT
    ls.loan_id,
    d.sector,
    d.region,
    ls.dpd_bucket,
    ls.ifrs9_stage,
    t.months_delinquent_6m,
    t.max_dpd_6m,
    ROUND(e.pd_12m, 4)                                    AS pd_12m,
    -- Expected loss at risk = PD x LGD x current exposure (from fact_ecl).
    ROUND(e.pd_12m * e.lgd * ls.outstanding_balance, 2)  AS expected_loss_at_risk,
    -- Simple transparent watch score blending the strongest stress signals.
    ROUND(
        0.45 * e.pd_12m
      + 0.25 * LEAST(t.max_dpd_6m / 90.0, 1.0)
      + 0.20 * (ls.ifrs9_stage - 1) / 2.0
      + 0.10 * LEAST(t.months_delinquent_6m / 6.0, 1.0)
    , 4)                                                  AS watch_score
FROM latest_snapshot ls
JOIN trailing  t USING (loan_id)
JOIN dim_loan  d USING (loan_id)
JOIN fact_ecl  e USING (loan_id)
-- Watchlist entry criteria: any elevated-risk trigger.
WHERE ls.ifrs9_stage >= 2
   OR e.pd_12m >= 0.15
   OR t.max_dpd_6m >= 30
ORDER BY expected_loss_at_risk DESC
LIMIT 50;

-- ---------------------------------------------------------------------------
-- 8b. Watchlist rollup: count and exposure at risk by sector and region.
--     Gives the committee a one-glance view of where stress is concentrated.
-- ---------------------------------------------------------------------------
WITH latest_snapshot AS (
    SELECT DISTINCT ON (loan_id)
        loan_id, ifrs9_stage, dpd, outstanding_balance
    FROM fact_loan_monthly
    ORDER BY loan_id, snapshot_month DESC
),
watch AS (
    SELECT d.sector, d.region,
           e.pd_12m * e.lgd * ls.outstanding_balance AS eltr
    FROM latest_snapshot ls
    JOIN dim_loan d USING (loan_id)
    JOIN fact_ecl e USING (loan_id)
    WHERE ls.ifrs9_stage >= 2 OR e.pd_12m >= 0.15 OR ls.dpd >= 30
)
SELECT
    sector,
    region,
    COUNT(*)                       AS watchlist_accounts,
    ROUND(SUM(eltr), 2)            AS expected_loss_at_risk
FROM watch
GROUP BY ROLLUP (sector, region)   -- subtotals per sector + grand total
ORDER BY sector NULLS LAST, region NULLS LAST;
