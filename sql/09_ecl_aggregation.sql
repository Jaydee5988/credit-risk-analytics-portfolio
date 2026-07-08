-- ============================================================================
-- 09_ecl_aggregation.sql — ECL aggregation & allowance reconciliation
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "What is the total IFRS 9 allowance, how does it split by stage/sector, and
--  how does the probability-weighted number compare to each macro scenario?"
-- These are the aggregations that feed the financial statements and the risk
-- committee memo (reports/risk_committee_memo.md).
--
-- Identity: ecl_weighted = 0.50*ecl_base + 0.35*ecl_downside + 0.15*ecl_severe
-- (scenario weights live in dim_scenario).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 9a. Headline portfolio allowance and coverage ratio.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                          AS loans,
    SUM(ead)                                          AS total_ead,
    SUM(ecl_weighted)                                 AS weighted_ecl,
    ROUND(SUM(ecl_weighted) / NULLIF(SUM(ead), 0), 4) AS coverage_ratio,
    SUM(ecl_base)                                     AS ecl_base,
    SUM(ecl_downside)                                 AS ecl_downside,
    SUM(ecl_severe)                                   AS ecl_severe
FROM fact_ecl;

-- ---------------------------------------------------------------------------
-- 9b. ECL by stage and sector with coverage ratios (allowance breakdown).
--     GROUPING SETS gives stage x sector detail plus per-stage subtotals in one
--     pass — the layout used for the allowance note.
-- ---------------------------------------------------------------------------
SELECT
    ifrs9_stage,
    COALESCE(sector, 'ALL SECTORS')                   AS sector,
    COUNT(*)                                          AS loans,
    SUM(ead)                                          AS total_ead,
    SUM(ecl_weighted)                                 AS total_ecl,
    ROUND(SUM(ecl_weighted) / NULLIF(SUM(ead), 0), 4) AS coverage_ratio
FROM fact_ecl
GROUP BY GROUPING SETS ((ifrs9_stage, sector), (ifrs9_stage))
ORDER BY ifrs9_stage, sector NULLS FIRST;

-- ---------------------------------------------------------------------------
-- 9c. Scenario reconciliation: rebuild the weighted ECL from dim_scenario
--     weights and confirm it matches the stored ecl_weighted column.
--     A non-zero reconciliation_diff would flag a data/logic break.
-- ---------------------------------------------------------------------------
WITH totals AS (
    SELECT
        SUM(ecl_base)     AS base,
        SUM(ecl_downside) AS downside,
        SUM(ecl_severe)   AS severe,
        SUM(ecl_weighted) AS stored_weighted
    FROM fact_ecl
),
weights AS (
    SELECT
        MAX(CASE WHEN scenario = 'base'     THEN weight END) AS w_base,
        MAX(CASE WHEN scenario = 'downside' THEN weight END) AS w_downside,
        MAX(CASE WHEN scenario = 'severe'   THEN weight END) AS w_severe
    FROM dim_scenario
)
SELECT
    ROUND(t.base, 2)                                          AS ecl_base,
    ROUND(t.downside, 2)                                      AS ecl_downside,
    ROUND(t.severe, 2)                                        AS ecl_severe,
    ROUND(w.w_base*t.base + w.w_downside*t.downside
          + w.w_severe*t.severe, 2)                           AS recomputed_weighted,
    ROUND(t.stored_weighted, 2)                               AS stored_weighted,
    ROUND(ABS(w.w_base*t.base + w.w_downside*t.downside
          + w.w_severe*t.severe - t.stored_weighted), 2)      AS reconciliation_diff
FROM totals t CROSS JOIN weights w;

-- ---------------------------------------------------------------------------
-- 9d. Top ECL contributors: which loans drive most of the allowance?
--     Cumulative share shows how concentrated the reserve is in a few names.
-- ---------------------------------------------------------------------------
WITH ranked AS (
    SELECT loan_id, sector, region, ifrs9_stage, ead, ecl_weighted,
           ecl_weighted / SUM(ecl_weighted) OVER () AS ecl_share,
           ROW_NUMBER() OVER (ORDER BY ecl_weighted DESC) AS rn
    FROM fact_ecl
)
SELECT
    rn AS rank, loan_id, sector, region, ifrs9_stage,
    ead,
    ROUND(ecl_weighted, 2)                            AS ecl_weighted,
    ROUND(ecl_share, 4)                               AS ecl_share,
    ROUND(SUM(ecl_share) OVER (ORDER BY rn), 4)       AS cumulative_ecl_share
FROM ranked
WHERE rn <= 20
ORDER BY rn;
