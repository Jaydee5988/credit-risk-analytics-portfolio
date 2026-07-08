-- ============================================================================
-- 05_utilization_trends.sql — Revolving utilisation trends & early-warning flags
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "Is utilisation creeping up across the book, and which accounts show a sharp
--  recent increase?" Rising utilisation is a leading indicator of stress —
-- borrowers draw down available credit before they miss payments. This feeds
-- the early-warning model (src/credit_risk/early_warning.py).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 5a. Portfolio utilisation trend by month, with 3-month moving average.
-- ---------------------------------------------------------------------------
WITH monthly AS (
    SELECT
        snapshot_month,
        AVG(utilization)                                 AS avg_utilization,
        AVG(CASE WHEN utilization >= 80 THEN 1.0 ELSE 0 END) AS pct_high_util
    FROM fact_loan_monthly
    WHERE utilization IS NOT NULL
    GROUP BY snapshot_month
)
SELECT
    snapshot_month,
    ROUND(avg_utilization, 2)                            AS avg_utilization,
    ROUND(pct_high_util, 4)                              AS pct_util_over_80,
    ROUND(AVG(avg_utilization) OVER (ORDER BY snapshot_month
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS util_3m_moving_avg
FROM monthly
ORDER BY snapshot_month;

-- ---------------------------------------------------------------------------
-- 5b. Per-loan utilisation trend: latest vs. 3 months prior. Flag accounts
--     with a large recent jump — the exact signal the EWS watchlist keys on.
-- ---------------------------------------------------------------------------
WITH ranked AS (
    SELECT
        loan_id,
        snapshot_month,
        utilization,
        ROW_NUMBER() OVER (PARTITION BY loan_id
                           ORDER BY snapshot_month DESC) AS rn_desc
    FROM fact_loan_monthly
    WHERE utilization IS NOT NULL
),
latest AS (
    SELECT loan_id, utilization AS util_now      FROM ranked WHERE rn_desc = 1
),
prior AS (
    SELECT loan_id, utilization AS util_3m_ago   FROM ranked WHERE rn_desc = 4
)
SELECT
    l.loan_id,
    d.sector,
    d.region,
    ROUND(p.util_3m_ago, 2)                       AS util_3m_ago,
    ROUND(l.util_now, 2)                          AS util_now,
    ROUND(l.util_now - p.util_3m_ago, 2)          AS util_delta_3m,
    CASE
        WHEN l.util_now - p.util_3m_ago >= 20 THEN 'RISING_FAST'
        WHEN l.util_now - p.util_3m_ago >= 10 THEN 'RISING'
        ELSE 'STABLE'
    END                                           AS util_trend_flag
FROM latest l
JOIN prior  p USING (loan_id)
JOIN dim_loan d ON d.loan_id = l.loan_id
WHERE l.util_now - p.util_3m_ago >= 10            -- only surface rising accounts
ORDER BY util_delta_3m DESC;
