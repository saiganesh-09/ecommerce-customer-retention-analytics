-- =============================================================================
-- 07_revenue_analysis.sql
--
-- Revenue structure: trends, categories, geography, order value distribution.
-- Population: qualifying (delivered) orders. Revenue = item price + freight.
-- =============================================================================

\set ON_ERROR_STOP on

-- Revenue by product category (order-grain, primary category = highest-value
-- item's category; category-level revenue uses ITEM values instead) -----------
DROP TABLE IF EXISTS analytics.revenue_by_category;
CREATE TABLE analytics.revenue_by_category AS
SELECT
    i.product_category,
    COUNT(DISTINCT i.order_id)                        AS orders,
    COUNT(*)                                          AS items,
    ROUND(SUM(i.item_total_value), 2)                 AS revenue_brl,
    ROUND(100.0 * SUM(i.item_total_value)
          / SUM(SUM(i.item_total_value)) OVER (), 2)  AS pct_revenue,
    ROUND(AVG(i.item_total_value), 2)                 AS avg_item_value_brl
FROM staging.order_items i
JOIN staging.orders o ON o.order_id = i.order_id
WHERE o.is_qualifying_order
GROUP BY i.product_category
ORDER BY revenue_brl DESC;

-- Revenue by customer state ---------------------------------------------------
DROP TABLE IF EXISTS analytics.revenue_by_state;
CREATE TABLE analytics.revenue_by_state AS
SELECT
    customer_state,
    COUNT(DISTINCT customer_unique_id)               AS customers,
    COUNT(*)                                         AS orders,
    ROUND(SUM(order_total_value), 2)                 AS revenue_brl,
    ROUND(100.0 * SUM(order_total_value)
          / SUM(SUM(order_total_value)) OVER (), 2)  AS pct_revenue,
    ROUND(AVG(order_total_value), 2)                 AS avg_order_value_brl
FROM staging.orders_enriched
WHERE is_qualifying_order
GROUP BY customer_state
ORDER BY revenue_brl DESC;

-- Order value distribution ----------------------------------------------------
DROP TABLE IF EXISTS analytics.order_value_distribution;
CREATE TABLE analytics.order_value_distribution AS
SELECT
    percentile_cont(0.25) WITHIN GROUP (ORDER BY order_total_value) AS p25,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY order_total_value) AS p50,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY order_total_value) AS p75,
    percentile_cont(0.90) WITHIN GROUP (ORDER BY order_total_value) AS p90,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY order_total_value) AS p99,
    ROUND(AVG(order_total_value), 2)                                AS mean,
    ROUND(MAX(order_total_value), 2)                                AS max_value
FROM staging.orders_enriched
WHERE is_qualifying_order;

-- Monthly revenue with running total (for the exec dashboard trend) -----------
DROP TABLE IF EXISTS analytics.monthly_revenue;
CREATE TABLE analytics.monthly_revenue AS
SELECT
    purchase_month,
    revenue_brl,
    avg_order_value_brl,
    orders,
    active_customers,
    ROUND(SUM(revenue_brl) OVER (ORDER BY purchase_month), 2) AS cumulative_revenue_brl
FROM analytics.monthly_orders
ORDER BY purchase_month;

-- Payment method mix (qualifying orders) --------------------------------------
DROP TABLE IF EXISTS analytics.payment_mix;
CREATE TABLE analytics.payment_mix AS
SELECT
    payment_types,
    COUNT(*)                                        AS orders,
    ROUND(SUM(order_total_value), 2)                AS revenue_brl,
    ROUND(AVG(order_total_value), 2)                AS avg_order_value_brl
FROM staging.orders_enriched
WHERE is_qualifying_order AND payment_types IS NOT NULL
GROUP BY payment_types
ORDER BY revenue_brl DESC;

SELECT * FROM analytics.order_value_distribution;
SELECT * FROM analytics.revenue_by_category LIMIT 10;
SELECT * FROM analytics.revenue_by_state LIMIT 10;
