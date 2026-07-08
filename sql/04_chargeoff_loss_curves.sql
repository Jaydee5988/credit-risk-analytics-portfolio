-- ============================================================================
-- 04_chargeoff_loss_curves.sql — Charge-off, recovery, and cumulative loss curves
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "How much are we charging off each month, what do we recover, and how does
--  cumulative net loss build up by vintage as loans season?" Loss curves are
-- the empirical backbone of lifetime-loss / CECL estimation and are compared
-- directly against modelled ECL to check the reserve is adequate.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 4a. Monthly gross charge-offs, recoveries, and annualised net charge-off rate.
--     NCO rate is the industry-standard credit-quality KPI:
--       annualised NCO% = 12 * net_charge_off / average_outstanding_balance
-- ---------------------------------------------------------------------------
SELECT
    snapshot_month,
    SUM(charge_off_amount)                                    AS gross_charge_off,
    SUM(recovery_amount)                                      AS recoveries,
    SUM(charge_off_amount - recovery_amount)                  AS net_charge_off,
    SUM(outstanding_balance)                                  AS ending_balance,
    ROUND( 12.0 * SUM(charge_off_amount - recovery_amount)
           / NULLIF(SUM(outstanding_balance), 0), 4)          AS annualised_nco_rate
FROM fact_loan_monthly
GROUP BY snapshot_month
ORDER BY snapshot_month;

-- ---------------------------------------------------------------------------
-- 4b. Cumulative net-loss curve by vintage and age (months_on_book).
--     Denominator is original balance at booking, so curves are comparable
--     across vintages of different sizes. This is the chart credit teams overlay
--     to see whether newer books are tracking above prior loss experience.
-- ---------------------------------------------------------------------------
WITH loan_vintage AS (
    SELECT loan_id,
           EXTRACT(YEAR FROM origination_date)::INT || '-Q'
               || EXTRACT(QUARTER FROM origination_date)::INT AS vintage
    FROM dim_loan
),
orig_balance AS (
    -- Balance at booking (months_on_book = 0) is the loss-curve denominator.
    SELECT v.vintage, SUM(m.outstanding_balance) AS booked_balance
    FROM fact_loan_monthly m
    JOIN loan_vintage v USING (loan_id)
    WHERE m.months_on_book = 0
    GROUP BY v.vintage
),
monthly_loss AS (
    SELECT
        v.vintage,
        m.months_on_book,
        SUM(m.charge_off_amount - m.recovery_amount) AS net_loss
    FROM fact_loan_monthly m
    JOIN loan_vintage v USING (loan_id)
    GROUP BY v.vintage, m.months_on_book
)
SELECT
    ml.vintage,
    ml.months_on_book,
    ml.net_loss,
    SUM(ml.net_loss) OVER (PARTITION BY ml.vintage
                           ORDER BY ml.months_on_book)          AS cumulative_net_loss,
    ROUND( SUM(ml.net_loss) OVER (PARTITION BY ml.vintage
                                  ORDER BY ml.months_on_book)
           / NULLIF(ob.booked_balance, 0), 4)                   AS cumulative_loss_rate
FROM monthly_loss ml
JOIN orig_balance ob USING (vintage)
ORDER BY ml.vintage, ml.months_on_book;

-- ---------------------------------------------------------------------------
-- 4c. Realised LGD from actual charge-offs vs. recoveries, by sector.
--     realised_lgd = 1 - (recoveries / charged-off exposure). Backtesting the
--     LGD model against this is covered in docs/model_validation_report.md.
-- ---------------------------------------------------------------------------
SELECT
    l.sector,
    COUNT(*)                                                   AS charge_off_events,
    SUM(m.charge_off_amount)                                   AS charged_off_exposure,
    SUM(m.recovery_amount)                                     AS recoveries,
    ROUND( 1 - SUM(m.recovery_amount)
               / NULLIF(SUM(m.charge_off_amount), 0), 4)       AS realised_lgd
FROM fact_loan_monthly m
JOIN dim_loan l USING (loan_id)
WHERE m.is_charged_off = 1
GROUP BY l.sector
ORDER BY realised_lgd DESC;
