-- =============================================================================
-- 02_staging_tables.sql
--
-- Builds cleaned, typed staging tables from raw.*.
--
-- Design decisions (documented in docs/methodology.md):
--   * customer_unique_id is the customer identity; customer_id is per-order.
--   * "Qualifying" orders for customer/revenue metrics = order_status =
--     'delivered' only. Canceled/unavailable orders generate no fulfilled
--     revenue; created/approved/processing/invoiced/shipped are lifecycle
--     states whose outcome cannot be confirmed inside the data window.
--   * Reviews: keep ONE review row per order (latest review_creation_date,
--     tie-broken by review_id) because some orders carry multiple review rows
--     and some review_ids are duplicated in the source.
--   * Order revenue is defined at the order grain BEFORE any join to items or
--     payments, so one-to-many relationships can never inflate totals.
-- =============================================================================

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- staging.orders - one row per order, enriched with the permanent customer id
-- and delivery-performance flags.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.orders CASCADE;
CREATE TABLE staging.orders AS
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_status,
    o.order_purchase_timestamp                                     AS purchase_ts,
    o.order_purchase_timestamp::date                               AS purchase_date,
    date_trunc('month', o.order_purchase_timestamp)::date          AS purchase_month,
    c.customer_city,
    c.customer_state,
    c.customer_zip_code_prefix,
    o.order_delivered_customer_date                                AS delivered_ts,
    o.order_estimated_delivery_date                                AS estimated_delivery_ts,
    -- Days from purchase to actual delivery (NULL when not delivered).
    (o.order_delivered_customer_date::date
        - o.order_purchase_timestamp::date)                        AS delivery_days,
    -- Days late relative to the promised estimate; negative = early/on time.
    (o.order_delivered_customer_date::date
        - o.order_estimated_delivery_date::date)                   AS delivery_delay_days,
    CASE
        WHEN o.order_status = 'delivered'
         AND o.order_delivered_customer_date IS NOT NULL
         AND o.order_delivered_customer_date::date
             > o.order_estimated_delivery_date::date
        THEN TRUE ELSE FALSE
    END                                                            AS is_late_delivery,
    o.order_status = 'delivered'                                   AS is_qualifying_order
FROM raw.orders o
JOIN raw.customers c ON c.customer_id = o.customer_id;

CREATE UNIQUE INDEX staging_orders_order_id_idx ON staging.orders (order_id);
CREATE INDEX staging_orders_customer_idx ON staging.orders (customer_unique_id);
CREATE INDEX staging_orders_month_idx ON staging.orders (purchase_month);

COMMENT ON TABLE staging.orders IS
  'One row per order. Customer identity = customer_unique_id. '
  'is_late_delivery only computed for delivered orders with both timestamps.';

-- ---------------------------------------------------------------------------
-- staging.order_items - order-item grain, enriched with English category.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.order_items CASCADE;
CREATE TABLE staging.order_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    COALESCE(t.product_category_name_english,
             p.product_category_name,
             'unknown')                AS product_category,
    i.price,
    i.freight_value,
    i.price + i.freight_value           AS item_total_value,
    s.seller_state
FROM raw.order_items i
LEFT JOIN raw.products p   ON p.product_id = i.product_id
LEFT JOIN raw.category_translation t
       ON t.product_category_name = p.product_category_name
LEFT JOIN raw.sellers s    ON s.seller_id = i.seller_id;

CREATE INDEX staging_order_items_order_idx ON staging.order_items (order_id);

-- ---------------------------------------------------------------------------
-- staging.order_payments - payments pre-aggregated to the ORDER grain so that
-- joining payments to orders can never multiply order rows.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.order_payments CASCADE;
CREATE TABLE staging.order_payments AS
SELECT
    order_id,
    COUNT(*)                       AS payment_rows,
    SUM(payment_value)             AS payment_total,
    MAX(payment_installments)      AS max_installments,
    string_agg(DISTINCT payment_type, '+'
               ORDER BY payment_type) AS payment_types
FROM raw.order_payments
GROUP BY order_id;

CREATE UNIQUE INDEX staging_order_payments_order_idx
    ON staging.order_payments (order_id);

-- ---------------------------------------------------------------------------
-- staging.order_reviews - exactly ONE review per order (latest creation date).
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.order_reviews CASCADE;
CREATE TABLE staging.order_reviews AS
SELECT order_id, review_id, review_score, review_creation_date,
       review_answer_timestamp
FROM (
    SELECT r.*,
           ROW_NUMBER() OVER (
               PARTITION BY r.order_id
               ORDER BY r.review_creation_date DESC NULLS LAST,
                        r.review_id
           ) AS rn
    FROM raw.order_reviews r
) ranked
WHERE rn = 1;

CREATE UNIQUE INDEX staging_order_reviews_order_idx
    ON staging.order_reviews (order_id);

-- ---------------------------------------------------------------------------
-- staging.orders_enriched - the analysis-ready ORDER-GRAIN fact table.
-- Every measure is pre-aggregated to one row per order, then joined, so the
-- totals below are protected against one-to-many duplication.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.orders_enriched CASCADE;
CREATE TABLE staging.orders_enriched AS
SELECT
    o.order_id,
    o.customer_unique_id,
    o.order_status,
    o.purchase_ts,
    o.purchase_date,
    o.purchase_month,
    o.customer_city,
    o.customer_state,
    o.delivered_ts,
    o.estimated_delivery_ts,
    o.delivery_days,
    o.delivery_delay_days,
    o.is_late_delivery,
    o.is_qualifying_order,
    COALESCE(i.item_count, 0)      AS item_count,
    COALESCE(i.items_value, 0)     AS items_value,
    COALESCE(i.freight_value, 0)   AS freight_value,
    COALESCE(i.items_value, 0)
        + COALESCE(i.freight_value, 0) AS order_total_value,  -- revenue measure
    p.payment_total,
    p.payment_types,
    p.max_installments,
    r.review_score,
    pc.primary_category            -- category of the highest-value item
FROM staging.orders o
LEFT JOIN (
    SELECT order_id,
           COUNT(*)              AS item_count,
           SUM(price)            AS items_value,
           SUM(freight_value)    AS freight_value
    FROM staging.order_items
    GROUP BY order_id
) i ON i.order_id = o.order_id
LEFT JOIN staging.order_payments p ON p.order_id = o.order_id
LEFT JOIN staging.order_reviews  r ON r.order_id = o.order_id
LEFT JOIN (
    SELECT DISTINCT ON (order_id) order_id, product_category AS primary_category
    FROM (
        SELECT order_id, product_category,
               SUM(price + freight_value) AS cat_value
        FROM staging.order_items
        GROUP BY order_id, product_category
    ) v
    ORDER BY order_id, cat_value DESC
) pc ON pc.order_id = o.order_id;

CREATE UNIQUE INDEX staging_orders_enriched_idx
    ON staging.orders_enriched (order_id);
CREATE INDEX staging_orders_enriched_cust_idx
    ON staging.orders_enriched (customer_unique_id);

COMMENT ON COLUMN staging.orders_enriched.order_total_value IS
  'Revenue measure used throughout: item prices + freight, from order_items. '
  'payment_total is stored separately and NOT used as revenue (see docs).';

-- Quick sanity output --------------------------------------------------------
SELECT
    COUNT(*)                                            AS orders,
    COUNT(*) FILTER (WHERE is_qualifying_order)         AS qualifying_delivered,
    COUNT(*) FILTER (WHERE is_late_delivery)            AS late_deliveries,
    COUNT(DISTINCT customer_unique_id)                  AS unique_customers,
    ROUND(SUM(order_total_value) FILTER (WHERE is_qualifying_order), 2)
                                                        AS qualifying_revenue_brl
FROM staging.orders_enriched;
