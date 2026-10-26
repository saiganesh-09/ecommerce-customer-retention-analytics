-- =============================================================================
-- 03_customer_metrics.sql
--
-- A. Overall business performance   -> analytics.kpi_overview,
--                                      analytics.monthly_orders
-- B. Customer purchasing behaviour  -> analytics.customer_metrics
--
-- Population: all orders are counted in the KPI overview; customer-level
-- metrics (orders per customer, repeat rate, spend) use QUALIFYING orders
-- (status = 'delivered') so that revenue and repeat behaviour are measured on
-- fulfilled purchases only.
-- =============================================================================

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- A1. Headline KPIs (order status mix uses ALL orders; spend uses qualifying)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.kpi_overview;
CREATE TABLE analytics.kpi_overview AS
SELECT
    COUNT(*)                                                   AS total_orders,
    COUNT(*) FILTER (WHERE is_qualifying_order)                AS delivered_orders,
    COUNT(*) FILTER (WHERE order_status = 'canceled')          AS canceled_orders,
    COUNT(*) FILTER (WHERE order_status = 'unavailable')       AS unavailable_orders,
    COUNT(*) FILTER (WHERE order_status NOT IN
        ('delivered', 'canceled', 'unavailable'))              AS in_progress_orders,
    COUNT(DISTINCT customer_unique_id)                         AS total_customers,
    COUNT(DISTINCT customer_unique_id)
        FILTER (WHERE is_qualifying_order)                     AS customers_with_delivered_order,
    ROUND(SUM(order_total_value)
          FILTER (WHERE is_qualifying_order), 2)               AS total_revenue_brl,
    ROUND(AVG(order_total_value)
          FILTER (WHERE is_qualifying_order), 2)               AS avg_order_value_brl,
    MIN(purchase_date)                                         AS first_order_date,
    MAX(purchase_date)                                         AS last_order_date
FROM staging.orders_enriched;

-- ---------------------------------------------------------------------------
-- A2. Monthly order / revenue trend (qualifying orders)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.monthly_orders;
CREATE TABLE analytics.monthly_orders AS
SELECT
    purchase_month,
    COUNT(*)                                AS orders,
    COUNT(DISTINCT customer_unique_id)      AS active_customers,
    ROUND(SUM(order_total_value), 2)        AS revenue_brl,
    ROUND(AVG(order_total_value), 2)        AS avg_order_value_brl,
    ROUND(AVG(delivery_days), 1)            AS avg_delivery_days
FROM staging.orders_enriched
WHERE is_qualifying_order
GROUP BY purchase_month
ORDER BY purchase_month;

-- ---------------------------------------------------------------------------
-- B. Customer-level metrics - one row per customer_unique_id.
--    Restricted to customers with >=1 qualifying (delivered) order.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.customer_metrics;
CREATE TABLE analytics.customer_metrics AS
WITH qualifying_orders AS (
    SELECT order_id, customer_unique_id, purchase_ts, purchase_date,
           order_total_value, review_score, is_late_delivery
    FROM staging.orders_enriched
    WHERE is_qualifying_order
),
ordered AS (
    SELECT q.*,
           ROW_NUMBER() OVER (PARTITION BY customer_unique_id
                              ORDER BY purchase_ts, order_id) AS order_seq
    FROM qualifying_orders q
),
agg AS (
    SELECT
        customer_unique_id,
        COUNT(*)                              AS order_count,
        MIN(purchase_ts)                      AS first_purchase_ts,
        MIN(purchase_date)                    AS first_purchase_date,
        MAX(purchase_ts)                      AS last_purchase_ts,
        MAX(purchase_date)                    AS last_purchase_date,
        ROUND(SUM(order_total_value), 2)      AS total_spend_brl,
        ROUND(AVG(order_total_value), 2)      AS avg_order_value_brl,
        AVG(review_score)                     AS avg_review_score,
        SUM(is_late_delivery::int)            AS late_deliveries
    FROM ordered
    GROUP BY customer_unique_id
),
second_order AS (
    SELECT customer_unique_id,
           MIN(purchase_date) FILTER (WHERE order_seq = 2) AS second_purchase_date
    FROM ordered
    GROUP BY customer_unique_id
)
SELECT
    a.customer_unique_id,
    a.order_count,
    a.first_purchase_ts,
    a.first_purchase_date,
    date_trunc('month', a.first_purchase_ts)::date AS first_purchase_month,
    a.last_purchase_ts,
    a.last_purchase_date,
    (a.last_purchase_date - a.first_purchase_date) AS customer_lifetime_days,
    s.second_purchase_date,
    (s.second_purchase_date - a.first_purchase_date) AS days_to_second_order,
    a.total_spend_brl,
    a.avg_order_value_brl,
    a.avg_review_score,
    a.late_deliveries,
    a.order_count > 1                              AS is_repeat_customer
FROM agg a
LEFT JOIN second_order s USING (customer_unique_id);

CREATE UNIQUE INDEX customer_metrics_idx ON analytics.customer_metrics (customer_unique_id);

COMMENT ON TABLE analytics.customer_metrics IS
  'One row per customer_unique_id with >=1 delivered order. Revenue = item '
  'price + freight summed over that customer''s delivered orders.';

-- ---------------------------------------------------------------------------
-- Summary: one-time vs repeat customers + order-count distribution
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.customer_purchase_frequency;
CREATE TABLE analytics.customer_purchase_frequency AS
SELECT
    order_count,
    COUNT(*)                                                AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)      AS pct_of_customers,
    ROUND(SUM(total_spend_brl), 2)                          AS revenue_brl,
    ROUND(100.0 * SUM(total_spend_brl)
                / SUM(SUM(total_spend_brl)) OVER (), 2)     AS pct_of_revenue
FROM analytics.customer_metrics
GROUP BY order_count
ORDER BY order_count;

SELECT * FROM analytics.kpi_overview;

SELECT
    COUNT(*)                                             AS customers_with_orders,
    COUNT(*) FILTER (WHERE order_count = 1)              AS one_time_customers,
    COUNT(*) FILTER (WHERE order_count > 1)              AS repeat_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE order_count > 1) / COUNT(*), 2)
                                                         AS repeat_purchase_rate_pct,
    ROUND(AVG(days_to_second_order), 1)                  AS avg_days_to_2nd_order,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY days_to_second_order)
                                                         AS median_days_to_2nd_order
FROM analytics.customer_metrics;
