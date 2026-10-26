-- =============================================================================
-- 06_delivery_analysis.sql
--
-- Delivery performance vs customer satisfaction and repeat purchasing.
--
-- Populations per metric (important - they differ):
--   * Delivery duration / lateness: DELIVERED orders with BOTH a delivery
--     timestamp and an estimated delivery date.
--   * Review scores: orders that have a review row (any status, though ~all
--     reviewed orders are delivered).
--   * Repeat-purchase association: customers are grouped by the delivery
--     experience of their FIRST qualifying order, then we ask whether they
--     ever placed another qualifying order. A sensitivity cut restricts to
--     customers whose first order is >= 180 days before the data end, so
--     every compared customer had a fair follow-up window.
--
-- Results are ASSOCIATIONS, not causal effects (see docs/limitations.md).
-- =============================================================================

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- 1. Delivery performance summary (order grain)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.delivery_summary;
CREATE TABLE analytics.delivery_summary AS
SELECT
    COUNT(*)                                                       AS delivered_with_ts,
    ROUND(AVG(delivery_days), 1)                                   AS avg_delivery_days,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY delivery_days)     AS median_delivery_days,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY delivery_days)     AS p90_delivery_days,
    ROUND(AVG((estimated_delivery_ts::date - purchase_date)), 1)   AS avg_promised_days,
    COUNT(*) FILTER (WHERE is_late_delivery)                       AS late_orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_late_delivery)
          / COUNT(*), 2)                                           AS late_delivery_pct,
    ROUND(AVG(delivery_delay_days)
          FILTER (WHERE is_late_delivery), 1)                      AS avg_days_late_when_late,
    ROUND(AVG(delivery_delay_days), 1)                             AS avg_delay_days_all
FROM staging.orders_enriched
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND estimated_delivery_ts IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Review score vs delivery outcome (order grain)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.review_by_delivery;
CREATE TABLE analytics.review_by_delivery AS
SELECT
    CASE WHEN is_late_delivery THEN 'late' ELSE 'on_time' END AS delivery_outcome,
    COUNT(*)                                                  AS orders_with_review,
    ROUND(AVG(review_score), 2)                               AS avg_review_score,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_score <= 2)
          / COUNT(*), 2)                                      AS pct_score_1_2,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_score = 5)
          / COUNT(*), 2)                                      AS pct_score_5,
    ROUND(AVG(delivery_days), 1)                              AS avg_delivery_days,
    ROUND(AVG(delivery_delay_days), 1)                        AS avg_delay_days
FROM staging.orders_enriched
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND estimated_delivery_ts IS NOT NULL
  AND review_score IS NOT NULL
GROUP BY 1;

-- full review-score distribution by outcome (for charting)
DROP TABLE IF EXISTS analytics.review_distribution_by_delivery;
CREATE TABLE analytics.review_distribution_by_delivery AS
SELECT
    delivery_outcome,
    review_score,
    orders,
    ROUND(100.0 * orders
          / SUM(orders) OVER (PARTITION BY delivery_outcome), 2) AS pct
FROM (
    SELECT
        CASE WHEN is_late_delivery THEN 'late' ELSE 'on_time' END AS delivery_outcome,
        review_score,
        COUNT(*) AS orders
    FROM staging.orders_enriched
    WHERE order_status = 'delivered'
      AND delivered_ts IS NOT NULL
      AND estimated_delivery_ts IS NOT NULL
      AND review_score IS NOT NULL
    GROUP BY 1, 2
) d
ORDER BY 1, 2;

-- ---------------------------------------------------------------------------
-- 3. Repeat purchasing vs FIRST-order delivery experience (customer grain)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.repeat_by_first_delivery;
CREATE TABLE analytics.repeat_by_first_delivery AS
WITH first_orders AS (
    SELECT customer_unique_id,
           MIN(purchase_ts) AS first_purchase_ts
    FROM staging.orders_enriched
    WHERE is_qualifying_order
    GROUP BY customer_unique_id
),
first_delivery AS (
    -- Delivery experience attached to the customer's first qualifying order.
    SELECT f.customer_unique_id,
           f.first_purchase_ts,
           e.is_late_delivery AS first_order_late
    FROM first_orders f
    JOIN staging.orders_enriched e
      ON e.customer_unique_id = f.customer_unique_id
     AND e.purchase_ts = f.first_purchase_ts
     AND e.is_qualifying_order
     AND e.delivered_ts IS NOT NULL
     AND e.estimated_delivery_ts IS NOT NULL
),
customer_level AS (
    SELECT d.customer_unique_id,
           d.first_order_late,
           (SELECT COUNT(*) - 1
              FROM staging.orders_enriched e2
             WHERE e2.customer_unique_id = d.customer_unique_id
               AND e2.is_qualifying_order) AS later_qualifying_orders,
           (d.first_purchase_ts::date <= DATE '2018-04-20') AS has_180d_window
    FROM first_delivery d
)
SELECT
    CASE WHEN first_order_late THEN 'first_order_late'
         ELSE 'first_order_on_time' END            AS cohort_label,
    COUNT(*)                                      AS customers,
    COUNT(*) FILTER (WHERE later_qualifying_orders > 0)
                                                  AS repeat_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE later_qualifying_orders > 0)
          / COUNT(*), 2)                          AS repeat_rate_pct,
    COUNT(*) FILTER (WHERE has_180d_window)       AS customers_180d_window,
    ROUND(100.0 * COUNT(*) FILTER (WHERE later_qualifying_orders > 0
                                    AND has_180d_window)
          / COUNT(*) FILTER (WHERE has_180d_window), 2)
                                                  AS repeat_rate_pct_180d
FROM customer_level
GROUP BY 1;

-- ---------------------------------------------------------------------------
-- 4. Lateness by product category and by customer state
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.late_by_category;
CREATE TABLE analytics.late_by_category AS
SELECT
    primary_category,
    COUNT(*)                                          AS delivered_orders,
    ROUND(AVG(delivery_days), 1)                      AS avg_delivery_days,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_late_delivery)
          / COUNT(*), 1)                              AS late_pct,
    ROUND(AVG(review_score), 2)                       AS avg_review_score
FROM staging.orders_enriched
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND estimated_delivery_ts IS NOT NULL
GROUP BY primary_category
HAVING COUNT(*) >= 300            -- keep categories with enough volume
ORDER BY late_pct DESC;

DROP TABLE IF EXISTS analytics.late_by_state;
CREATE TABLE analytics.late_by_state AS
SELECT
    customer_state,
    COUNT(*)                                          AS delivered_orders,
    ROUND(AVG(delivery_days), 1)                      AS avg_delivery_days,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_late_delivery)
          / COUNT(*), 1)                              AS late_pct,
    ROUND(AVG(review_score), 2)                       AS avg_review_score
FROM staging.orders_enriched
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND estimated_delivery_ts IS NOT NULL
GROUP BY customer_state
HAVING COUNT(*) >= 100
ORDER BY late_pct DESC;

SELECT * FROM analytics.delivery_summary;
SELECT * FROM analytics.review_by_delivery;
SELECT * FROM analytics.repeat_by_first_delivery;
