-- ============================================================================
-- 06_exposure_concentration.sql — Exposure concentration (HHI) & single-name risk
-- ============================================================================
-- Dialect: PostgreSQL. Depends on: schema.sql.
--
-- Business question
-- -----------------
-- "Where is the book over-concentrated?" Concentration risk (by sector, region,
--  or single borrower) is a top credit-committee concern: a shock to one
-- segment can drive outsized losses. The Herfindahl-Hirschman Index (HHI) is
-- the standard single-number measure — mirrors src/credit_risk/stress_testing.py.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 6a. Exposure and share by sector, with rank. Share = EAD / total EAD.
-- ---------------------------------------------------------------------------
SELECT
    sector,
    COUNT(*)                                              AS loans,
    SUM(ead)                                              AS total_ead,
    ROUND(SUM(ead) / SUM(SUM(ead)) OVER (), 4)           AS exposure_share,
    ROUND(SUM(ecl_weighted), 2)                          AS total_ecl,
    RANK() OVER (ORDER BY SUM(ead) DESC)                 AS exposure_rank
FROM fact_ecl
GROUP BY sector
ORDER BY total_ead DESC;

-- ---------------------------------------------------------------------------
-- 6b. HHI by dimension. HHI = sum of squared percentage shares (0-1 scale).
--     Rule of thumb: > 0.25 highly concentrated, 0.15-0.25 moderate, < 0.15
--     diversified. Computed here for both sector and region in one result set.
-- ---------------------------------------------------------------------------
WITH sector_tot AS (        -- exposure per sector
    SELECT sector AS grp, SUM(ead) AS grp_ead FROM fact_ecl GROUP BY sector
),
region_tot AS (             -- exposure per region
    SELECT region AS grp, SUM(ead) AS grp_ead FROM fact_ecl GROUP BY region
),
sector_hhi AS (
    SELECT 'sector' AS dimension,
           SUM( POWER(grp_ead / SUM(grp_ead) OVER (), 2) ) AS hhi
    FROM sector_tot
),
region_hhi AS (
    SELECT 'region' AS dimension,
           SUM( POWER(grp_ead / SUM(grp_ead) OVER (), 2) ) AS hhi
    FROM region_tot
)
SELECT dimension, ROUND(hhi, 4) AS hhi,
       CASE WHEN hhi > 0.25 THEN 'Highly concentrated'
            WHEN hhi > 0.15 THEN 'Moderately concentrated'
            ELSE 'Diversified' END AS concentration_flag
FROM (
    SELECT * FROM sector_hhi
    UNION ALL
    SELECT * FROM region_hhi
) x
ORDER BY dimension;

-- ---------------------------------------------------------------------------
-- 6c. Single-name concentration: top 10 exposures and their cumulative share.
--     Large-exposure monitoring is a standard credit-limit control.
-- ---------------------------------------------------------------------------
WITH ranked AS (
    SELECT
        loan_id, sector, region, ead, ecl_weighted, ifrs9_stage,
        ead / SUM(ead) OVER () AS exposure_share,
        ROW_NUMBER() OVER (ORDER BY ead DESC) AS rn
    FROM fact_ecl
)
SELECT
    rn AS rank,
    loan_id, sector, region, ifrs9_stage,
    ead,
    ROUND(exposure_share, 4)                                   AS exposure_share,
    ROUND(SUM(exposure_share) OVER (ORDER BY rn), 4)           AS cumulative_share,
    ROUND(ecl_weighted, 2)                                     AS ecl_weighted
FROM ranked
WHERE rn <= 10
ORDER BY rn;
