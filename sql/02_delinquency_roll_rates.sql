-- ============================================================================
-- 02_delinquency_roll_rates.sql — Month-over-month delinquency roll rates
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "Of the loans that were 30-59 days past due last month, what share rolled
--  forward to 60-89 this month, cured back to current, or stayed put?"
-- Roll rates (a.k.a. transition/migration rates) are the backbone of
-- delinquency forecasting and loss-rate estimation. Forward-roll rates feed
-- flow-based ECL/allowance models; cure rates feed collections strategy.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 2a. Full roll-rate matrix: from-bucket (prior month) -> to-bucket (this month).
--     Each cell is the probability of moving between buckets over one month.
-- ---------------------------------------------------------------------------
WITH transitions AS (
    SELECT
        m.snapshot_month,
        m.loan_id,
        LAG(m.dpd_bucket) OVER (PARTITION BY m.loan_id
                                ORDER BY m.snapshot_month) AS from_bucket,
        m.dpd_bucket                                       AS to_bucket
    FROM fact_loan_monthly m
)
SELECT
    from_bucket,
    to_bucket,
    COUNT(*)                                                        AS n_loans,
    ROUND( COUNT(*)::NUMERIC
           / SUM(COUNT(*)) OVER (PARTITION BY from_bucket), 4)      AS roll_rate
FROM transitions
WHERE from_bucket IS NOT NULL          -- drop each loan's first observation
GROUP BY from_bucket, to_bucket
ORDER BY
    -- Order buckets by severity for a readable matrix.
    CASE from_bucket WHEN 'Current' THEN 0 WHEN '1-29' THEN 1
         WHEN '30-59' THEN 2 WHEN '60-89' THEN 3 WHEN '90+' THEN 4
         ELSE 5 END,
    CASE to_bucket   WHEN 'Current' THEN 0 WHEN '1-29' THEN 1
         WHEN '30-59' THEN 2 WHEN '60-89' THEN 3 WHEN '90+' THEN 4
         ELSE 5 END;

-- ---------------------------------------------------------------------------
-- 2b. Forward-roll and cure rates over time — the two headline collections KPIs.
--     forward_roll_rate: share of each month's delinquent book that worsened.
--     cure_rate:         share that improved (moved to a less severe bucket).
-- ---------------------------------------------------------------------------
WITH sev AS (
    SELECT loan_id, snapshot_month, dpd_bucket,
           CASE dpd_bucket WHEN 'Current' THEN 0 WHEN '1-29' THEN 1
                WHEN '30-59' THEN 2 WHEN '60-89' THEN 3 WHEN '90+' THEN 4
                ELSE 5 END AS severity
    FROM fact_loan_monthly
),
transitions AS (
    SELECT
        snapshot_month,
        LAG(severity)   OVER (PARTITION BY loan_id ORDER BY snapshot_month) AS from_sev,
        severity                                                            AS to_sev
    FROM sev
)
SELECT
    snapshot_month,
    COUNT(*)                                                          AS delinquent_loans,
    ROUND(AVG(CASE WHEN to_sev > from_sev THEN 1 ELSE 0 END)::NUMERIC, 4) AS forward_roll_rate,
    ROUND(AVG(CASE WHEN to_sev < from_sev THEN 1 ELSE 0 END)::NUMERIC, 4) AS cure_rate
FROM transitions
WHERE from_sev IS NOT NULL
  AND from_sev BETWEEN 1 AND 4        -- only accounts already delinquent last month
GROUP BY snapshot_month
ORDER BY snapshot_month;
