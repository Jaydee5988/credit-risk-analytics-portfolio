-- ============================================================================
-- 07_stage_migration.sql — IFRS 9 stage migration matrix
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "How are loans migrating between IFRS 9 stages, and how much exposure/ECL is
--  moving into Stage 2 (SICR) and Stage 3 (impaired)?" Stage migration drives
-- the allowance: a Stage 1 -> Stage 2 move flips a loan from 12-month to
-- lifetime ECL, materially increasing the reserve. Regulators expect explicit
-- migration monitoring under IFRS 9 / CECL.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 7a. Stage transition matrix (prior month -> current month), by loan count
--     and by exposure. Diagonal = stable; above diagonal = deterioration.
-- ---------------------------------------------------------------------------
WITH staged AS (
    SELECT
        loan_id,
        snapshot_month,
        ifrs9_stage,
        outstanding_balance,
        LAG(ifrs9_stage) OVER (PARTITION BY loan_id
                               ORDER BY snapshot_month) AS prev_stage
    FROM fact_loan_monthly
)
SELECT
    prev_stage                                              AS from_stage,
    ifrs9_stage                                             AS to_stage,
    COUNT(*)                                                AS n_loans,
    ROUND( COUNT(*)::NUMERIC
           / SUM(COUNT(*)) OVER (PARTITION BY prev_stage), 4) AS transition_rate,
    SUM(outstanding_balance)                               AS exposure_moved
FROM staged
WHERE prev_stage IS NOT NULL
GROUP BY prev_stage, ifrs9_stage
ORDER BY from_stage, to_stage;

-- ---------------------------------------------------------------------------
-- 7b. Net stage drift this period: inflows vs. outflows per stage.
--     Positive net_flow = the stage is growing (book deteriorating into it).
-- ---------------------------------------------------------------------------
WITH staged AS (
    SELECT loan_id, snapshot_month, ifrs9_stage,
           LAG(ifrs9_stage) OVER (PARTITION BY loan_id
                                  ORDER BY snapshot_month) AS prev_stage
    FROM fact_loan_monthly
),
moves AS (
    SELECT prev_stage, ifrs9_stage
    FROM staged
    WHERE prev_stage IS NOT NULL AND prev_stage <> ifrs9_stage
)
SELECT
    s.stage,
    COALESCE(inflow.n, 0)                                   AS moved_in,
    COALESCE(outflow.n, 0)                                  AS moved_out,
    COALESCE(inflow.n, 0) - COALESCE(outflow.n, 0)          AS net_flow
FROM (SELECT 1 AS stage UNION SELECT 2 UNION SELECT 3) s
LEFT JOIN (SELECT ifrs9_stage AS stage, COUNT(*) n FROM moves GROUP BY ifrs9_stage) inflow
       ON inflow.stage = s.stage
LEFT JOIN (SELECT prev_stage  AS stage, COUNT(*) n FROM moves GROUP BY prev_stage)  outflow
       ON outflow.stage = s.stage
ORDER BY s.stage;

-- ---------------------------------------------------------------------------
-- 7c. Current stage distribution with ECL coverage (from fact_ecl).
--     Coverage should rise sharply Stage 1 -> 2 -> 3, exactly as IFRS 9 intends.
-- ---------------------------------------------------------------------------
SELECT
    ifrs9_stage,
    COUNT(*)                                       AS loans,
    SUM(ead)                                       AS total_ead,
    SUM(ecl_weighted)                              AS total_ecl,
    ROUND(SUM(ecl_weighted) / NULLIF(SUM(ead), 0), 4) AS coverage_ratio,
    ROUND(AVG(pd_12m), 4)                          AS avg_pd_12m
FROM fact_ecl
GROUP BY ifrs9_stage
ORDER BY ifrs9_stage;
