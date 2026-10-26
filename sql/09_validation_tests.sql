-- =============================================================================
-- 09_validation_tests.sql
--
-- Reconciliation and validation checks on the analytical tables. Every check
-- prints PASS or FAIL with a detail value; FAIL means a hard invariant was
-- violated and downstream numbers should not be trusted.
-- =============================================================================

\set ON_ERROR_STOP on

CREATE TEMP TABLE validation_results (
    check_order SERIAL,
    check_name  TEXT,
    status      TEXT,
    detail      TEXT
);

-- 1. orders_enriched is exactly one row per order -----------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'orders_enriched unique order_id',
       CASE WHEN COUNT(*) = COUNT(DISTINCT order_id) THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' rows / ' || COUNT(DISTINCT order_id)::text || ' distinct'
FROM staging.orders_enriched;

-- 2. Every order_id in enriched exists in raw.orders ---------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'enriched covers all raw orders',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' missing'
FROM raw.orders o
LEFT JOIN staging.orders_enriched e USING (order_id)
WHERE e.order_id IS NULL;

-- 3. Customer metrics row count == distinct qualifying customers --------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'customer_metrics covers all qualifying customers',
       CASE WHEN a.n = b.n THEN 'PASS' ELSE 'FAIL' END,
       a.n::text || ' rows vs ' || b.n::text || ' distinct customers'
FROM (SELECT COUNT(*) n FROM analytics.customer_metrics) a,
     (SELECT COUNT(DISTINCT customer_unique_id) n
        FROM staging.orders_enriched WHERE is_qualifying_order) b;

-- 4. Revenue reconciliation: sum(customer total_spend) == sum(order totals) ---
INSERT INTO validation_results (check_name, status, detail)
SELECT 'revenue: customers reconcile to orders',
       CASE WHEN ABS(a.s - b.s) < 0.01 THEN 'PASS' ELSE 'FAIL' END,
       'customers ' || a.s::text || ' vs orders ' || b.s::text
FROM (SELECT SUM(total_spend_brl) s FROM analytics.customer_metrics) a,
     (SELECT SUM(order_total_value) s
        FROM staging.orders_enriched WHERE is_qualifying_order) b;

-- 5. Repeat-purchase rate computed two independent ways ------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'repeat rate consistency (metrics vs raw)',
       CASE WHEN ABS(a.r - b.r) < 0.01 THEN 'PASS' ELSE 'FAIL' END,
       'metrics ' || ROUND(a.r, 4)::text || ' vs raw ' || ROUND(b.r, 4)::text
FROM (
    SELECT 100.0 * COUNT(*) FILTER (WHERE order_count > 1) / COUNT(*) r
    FROM analytics.customer_metrics
) a,
(
    SELECT 100.0 * COUNT(*) FILTER (WHERE n > 1) / COUNT(*) r
    FROM (
        SELECT customer_unique_id, COUNT(*) n
        FROM staging.orders_enriched
        WHERE is_qualifying_order
        GROUP BY customer_unique_id
    ) c
) b;

-- 6. Cohort month-0 retention is 100% for every observed cohort ---------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'cohort month-0 retention = 100%',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' violations'
FROM analytics.cohort_retention
WHERE months_since_first = 0 AND ABS(retention_pct - 100) > 0.01;

-- 7. Cohort retention bounds ---------------------------------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'cohort retention within [0,100]',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' out of range'
FROM analytics.cohort_retention
WHERE retention_pct < 0 OR retention_pct > 100;

-- 8. A customer is counted at most once per (cohort, month) --------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'cohort active_customers <= cohort_size',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' violations'
FROM analytics.cohort_retention
WHERE active_customers > cohort_size;

-- 9. Cohort sizes sum to the qualifying-customer population --------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'cohort sizes sum to customer count',
       CASE WHEN a.s = b.n THEN 'PASS' ELSE 'FAIL' END,
       a.s::text || ' vs ' || b.n::text
FROM (SELECT SUM(cohort_size) s FROM analytics.cohort_sizes) a,
     (SELECT COUNT(*) n FROM analytics.customer_metrics) b;

-- 10. Every eligible customer has exactly one RFM segment ----------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'rfm customers == customer_metrics customers',
       CASE WHEN a.n = b.n THEN 'PASS' ELSE 'FAIL' END,
       a.n::text || ' vs ' || b.n::text
FROM (SELECT COUNT(*) n FROM analytics.rfm_customers) a,
     (SELECT COUNT(*) n FROM analytics.customer_metrics) b;

INSERT INTO validation_results (check_name, status, detail)
SELECT 'rfm segment is never null',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' null segments'
FROM analytics.rfm_customers WHERE rfm_segment IS NULL;

INSERT INTO validation_results (check_name, status, detail)
SELECT 'rfm segment counts reconcile',
       CASE WHEN a.n = b.n THEN 'PASS' ELSE 'FAIL' END,
       'sum of segments ' || a.n::text || ' vs customers ' || b.n::text
FROM (SELECT SUM(customers) n FROM analytics.rfm_segments) a,
     (SELECT COUNT(*) n FROM analytics.rfm_customers) b;

-- 11. RFM scores in range -------------------------------------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'rfm scores within 1..5',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' out of range'
FROM analytics.rfm_customers
WHERE r_score NOT BETWEEN 1 AND 5
   OR f_score NOT BETWEEN 1 AND 5
   OR m_score NOT BETWEEN 1 AND 5;

-- 12. Review dedup: no order has >1 staged review -------------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'staging reviews: one per order',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' orders with >1 review'
FROM (SELECT order_id FROM staging.order_reviews
      GROUP BY order_id HAVING COUNT(*) > 1) d;

-- 13. Order-total never negative -------------------------------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'order_total_value >= 0',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' negative'
FROM staging.orders_enriched WHERE order_total_value < 0;

-- 14. Late deliveries only flagged when timestamps exist -------------------------
INSERT INTO validation_results (check_name, status, detail)
SELECT 'late flag requires both timestamps',
       CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END,
       COUNT(*)::text || ' violations'
FROM staging.orders_enriched
WHERE is_late_delivery AND (delivered_ts IS NULL OR estimated_delivery_ts IS NULL);

SELECT * FROM validation_results ORDER BY check_order;
