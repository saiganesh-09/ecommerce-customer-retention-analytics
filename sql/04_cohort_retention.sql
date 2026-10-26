-- =============================================================================
-- 04_cohort_retention.sql
--
-- Monthly acquisition-cohort retention analysis.
--
-- Methodology:
--   * Cohort = month of the customer's FIRST observed qualifying (delivered)
--     purchase. This is the first purchase *in the data window*, which is not
--     necessarily the customer's first purchase ever.
--   * A customer is "active" in cohort month M+n if they placed >=1 qualifying
--     order in calendar month (cohort_month + n).
--   * Month 0 is the acquisition month itself -> retention is 100% by
--     construction and is included for completeness.
--   * months_since_first values that extend beyond the observed data window
--     are flagged is_observed = FALSE (incomplete window), NOT filled with 0.
--
-- Outputs:
--   analytics.cohort_sizes      - customers acquired per cohort month
--   analytics.cohort_retention  - long-format retention matrix
-- =============================================================================

\set ON_ERROR_STOP on

WITH first_orders AS (
    -- The customer's first observed QUALIFYING purchase defines the cohort.
    SELECT customer_unique_id,
           MIN(purchase_month) AS cohort_month
    FROM staging.orders_enriched
    WHERE is_qualifying_order
    GROUP BY customer_unique_id
),
activity AS (
    -- One row per (customer, activity month) - distinct months only.
    SELECT DISTINCT o.customer_unique_id,
           f.cohort_month,
           o.purchase_month AS activity_month
    FROM staging.orders_enriched o
    JOIN first_orders f USING (customer_unique_id)
    WHERE o.is_qualifying_order
),
activity_numbered AS (
    SELECT *,
           (EXTRACT(YEAR FROM activity_month)
            - EXTRACT(YEAR FROM cohort_month)) * 12
         + (EXTRACT(MONTH FROM activity_month)
            - EXTRACT(MONTH FROM cohort_month)) AS months_since_first
    FROM activity
),
data_bounds AS (
    -- Last fully observed calendar month in the dataset.
    SELECT date_trunc('month', MAX(purchase_ts))::date AS last_data_month
    FROM staging.orders_enriched
    WHERE is_qualifying_order
)
SELECT
    a.cohort_month,
    cs.cohort_size,
    a.months_since_first::int,
    a.activity_month,
    COUNT(DISTINCT a.customer_unique_id)         AS active_customers,
    ROUND(100.0 * COUNT(DISTINCT a.customer_unique_id)
                / cs.cohort_size, 2)             AS retention_pct,
    (a.activity_month <= b.last_data_month)      AS is_observed
INTO TEMP cohort_calc
FROM activity_numbered a
JOIN (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM first_orders GROUP BY cohort_month
) cs ON cs.cohort_month = a.cohort_month
CROSS JOIN data_bounds b
GROUP BY a.cohort_month, cs.cohort_size, a.months_since_first,
         a.activity_month, b.last_data_month;

DROP TABLE IF EXISTS analytics.cohort_retention;
CREATE TABLE analytics.cohort_retention AS
SELECT * FROM cohort_calc ORDER BY cohort_month, months_since_first;

DROP TABLE IF EXISTS analytics.cohort_sizes;
CREATE TABLE analytics.cohort_sizes AS
SELECT cohort_month, cohort_size,
       ROUND(SUM(cohort_size) OVER (ORDER BY cohort_month), 0) AS cumulative_customers
FROM (SELECT DISTINCT cohort_month, cohort_size FROM cohort_calc) s
ORDER BY cohort_month;

-- ---------------------------------------------------------------------------
-- Retention summary (headline metrics used in docs and the dashboard)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.cohort_summary;
CREATE TABLE analytics.cohort_summary AS
SELECT
    months_since_first,
    COUNT(DISTINCT cohort_month)                                 AS cohorts_observed,
    SUM(active_customers)                                        AS returning_customers,
    SUM(cohort_size)                                             AS customers_in_window,
    ROUND(100.0 * SUM(active_customers) / SUM(cohort_size), 2)   AS avg_retention_pct
FROM analytics.cohort_retention
WHERE is_observed
GROUP BY months_since_first
ORDER BY months_since_first;

-- Preview: cohort sizes + month-1/3/6/12 retention per cohort
SELECT cs.cohort_month, cs.cohort_size,
       MAX(cr.retention_pct) FILTER (WHERE cr.months_since_first = 1)  AS m1,
       MAX(cr.retention_pct) FILTER (WHERE cr.months_since_first = 3)  AS m3,
       MAX(cr.retention_pct) FILTER (WHERE cr.months_since_first = 6)  AS m6,
       MAX(cr.retention_pct) FILTER (WHERE cr.months_since_first = 12) AS m12
FROM analytics.cohort_sizes cs
LEFT JOIN analytics.cohort_retention cr
       ON cr.cohort_month = cs.cohort_month AND cr.is_observed
GROUP BY cs.cohort_month, cs.cohort_size
ORDER BY cs.cohort_month;
