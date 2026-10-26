-- =============================================================================
-- 01_data_quality_checks.sql
--
-- Runs a battery of data-quality checks against the raw.* tables and writes
-- one row per check into a temporary results table, then prints the report.
--
-- Severity levels:
--   INFO    - observed fact / distribution, no action needed
--   WARN    - known data quirk that specific analyses must handle
--   FAIL    - violates a hard assumption (should be 0)
-- =============================================================================

\set ON_ERROR_STOP on

CREATE TEMP TABLE dq_results (
    check_order SERIAL,
    check_area  TEXT,
    check_name  TEXT,
    severity    TEXT,
    detail      TEXT
);

-- ---------------------------------------------------------------------------
-- A. Row counts
-- ---------------------------------------------------------------------------
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'row_counts', 'raw.' || t.table_name, 'INFO', t.row_count::text || ' rows'
FROM (
    SELECT 'customers'           AS table_name, COUNT(*) AS row_count FROM raw.customers
    UNION ALL SELECT 'orders',            COUNT(*) FROM raw.orders
    UNION ALL SELECT 'order_items',       COUNT(*) FROM raw.order_items
    UNION ALL SELECT 'order_payments',    COUNT(*) FROM raw.order_payments
    UNION ALL SELECT 'order_reviews',     COUNT(*) FROM raw.order_reviews
    UNION ALL SELECT 'products',          COUNT(*) FROM raw.products
    UNION ALL SELECT 'sellers',           COUNT(*) FROM raw.sellers
    UNION ALL SELECT 'geolocation',       COUNT(*) FROM raw.geolocation
    UNION ALL SELECT 'category_translation', COUNT(*) FROM raw.category_translation
) t;

-- ---------------------------------------------------------------------------
-- B. Key integrity
-- ---------------------------------------------------------------------------
-- customer_id missing or duplicated in customers
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'keys', 'customers.customer_id nulls',
       CASE WHEN COUNT(*) FILTER (WHERE customer_id IS NULL) = 0 THEN 'FAIL(0)' ELSE 'FAIL' END,
       COUNT(*) FILTER (WHERE customer_id IS NULL)::text
FROM raw.customers;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'keys', 'customers.customer_id duplicates', 'INFO',
       COUNT(*)::text || ' customer_ids on >1 row (expected: customer_id is per-order)'
FROM (
    SELECT customer_id FROM raw.customers
    GROUP BY customer_id HAVING COUNT(*) > 1
) d;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'keys', 'customer_unique_id reuse', 'INFO',
       COUNT(*)::text || ' unique customers have >1 customer_id (= repeat buyers)'
FROM (
    SELECT customer_unique_id FROM raw.customers
    GROUP BY customer_unique_id HAVING COUNT(*) > 1
) d;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'keys', 'orders.order_id nulls', 'FAIL(0)',
       COUNT(*) FILTER (WHERE order_id IS NULL)::text
FROM raw.orders;

-- duplicate review_ids (a known quirk of this dataset)
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'keys', 'order_reviews duplicate review_ids', 'WARN',
       COUNT(*)::text || ' review_ids appear on >1 row'
FROM (
    SELECT review_id FROM raw.order_reviews
    GROUP BY review_id HAVING COUNT(*) > 1
) d;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'keys', 'orders with >1 review row', 'WARN',
       COUNT(*)::text || ' orders have multiple review rows'
FROM (
    SELECT order_id FROM raw.order_reviews
    GROUP BY order_id HAVING COUNT(*) > 1
) d;

-- ---------------------------------------------------------------------------
-- C. Referential integrity (orphaned foreign keys)
-- ---------------------------------------------------------------------------
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'referential', 'orders -> customers orphans', 'FAIL(0)', COUNT(*)::text
FROM raw.orders o
LEFT JOIN raw.customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'referential', 'order_items -> orders orphans', 'FAIL(0)', COUNT(*)::text
FROM raw.order_items i
LEFT JOIN raw.orders o ON o.order_id = i.order_id
WHERE o.order_id IS NULL;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'referential', 'order_payments -> orders orphans', 'FAIL(0)', COUNT(*)::text
FROM raw.order_payments p
LEFT JOIN raw.orders o ON o.order_id = p.order_id
WHERE o.order_id IS NULL;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'referential', 'order_reviews -> orders orphans', 'FAIL(0)', COUNT(*)::text
FROM raw.order_reviews r
LEFT JOIN raw.orders o ON o.order_id = r.order_id
WHERE o.order_id IS NULL;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'referential', 'order_items -> products orphans', 'WARN', COUNT(*)::text
FROM raw.order_items i
LEFT JOIN raw.products p ON p.product_id = i.product_id
WHERE i.product_id IS NOT NULL AND p.product_id IS NULL;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'referential', 'order_items -> sellers orphans', 'FAIL(0)', COUNT(*)::text
FROM raw.order_items i
LEFT JOIN raw.sellers s ON s.seller_id = i.seller_id
WHERE s.seller_id IS NULL;

-- ---------------------------------------------------------------------------
-- D. Order lifecycle / status / dates
-- ---------------------------------------------------------------------------
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'orders', 'order_status distribution', 'INFO',
       string_agg(order_status || '=' || n::text, ', ' ORDER BY n DESC)
FROM (SELECT order_status, COUNT(*) n FROM raw.orders GROUP BY 1) s;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'orders', 'purchase timestamp range', 'INFO',
       MIN(order_purchase_timestamp)::text || ' .. ' || MAX(order_purchase_timestamp)::text
FROM raw.orders;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'orders', 'purchase timestamp nulls', 'FAIL(0)',
       COUNT(*) FILTER (WHERE order_purchase_timestamp IS NULL)::text
FROM raw.orders;

-- physically impossible date orderings
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'dates', 'approved before purchase', 'WARN', COUNT(*)::text
FROM raw.orders
WHERE order_approved_at < order_purchase_timestamp;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'dates', 'delivered before purchase', 'WARN', COUNT(*)::text
FROM raw.orders
WHERE order_delivered_customer_date < order_purchase_timestamp;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'dates', 'delivered before carrier handover', 'WARN', COUNT(*)::text
FROM raw.orders
WHERE order_delivered_customer_date < order_delivered_carrier_date;

-- delivered orders that still lack a delivery timestamp
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'dates', 'status=delivered but no delivery timestamp', 'WARN', COUNT(*)::text
FROM raw.orders
WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL;

-- non-delivered statuses that nevertheless carry a delivery timestamp
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'dates', 'non-delivered status with delivery timestamp', 'WARN', COUNT(*)::text
FROM raw.orders
WHERE order_status NOT IN ('delivered') AND order_delivered_customer_date IS NOT NULL;

-- ---------------------------------------------------------------------------
-- E. Monetary values
-- ---------------------------------------------------------------------------
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'money', 'order_items price <= 0', 'WARN', COUNT(*)::text
FROM raw.order_items WHERE price IS NULL OR price <= 0;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'money', 'order_items freight < 0', 'FAIL(0)', COUNT(*)::text
FROM raw.order_items WHERE freight_value < 0;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'money', 'order_payments value < 0', 'FAIL(0)', COUNT(*)::text
FROM raw.order_payments WHERE payment_value < 0;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'money', 'order_payments value = 0', 'WARN', COUNT(*)::text
FROM raw.order_payments WHERE payment_value = 0;

-- orders with no payment rows at all
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'money', 'orders without payment rows', 'WARN', COUNT(*)::text
FROM raw.orders o
WHERE NOT EXISTS (SELECT 1 FROM raw.order_payments p WHERE p.order_id = o.order_id);

-- reconciliation: payment total vs item+freight total (delivered orders only)
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'money', 'delivered orders where payments != items+freight (>R$1)', 'WARN',
       COUNT(*)::text
FROM (
    SELECT o.order_id
    FROM raw.orders o
    JOIN (
        SELECT order_id, SUM(price + freight_value) AS item_total
        FROM raw.order_items GROUP BY order_id
    ) i ON i.order_id = o.order_id
    JOIN (
        SELECT order_id, SUM(payment_value) AS pay_total
        FROM raw.order_payments GROUP BY order_id
    ) p ON p.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND ABS(i.item_total - p.pay_total) > 1.00
) diff;

-- ---------------------------------------------------------------------------
-- F. Reviews / categories
-- ---------------------------------------------------------------------------
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'reviews', 'review_score outside 1..5', 'FAIL(0)', COUNT(*)::text
FROM raw.order_reviews
WHERE review_score IS NULL OR review_score NOT BETWEEN 1 AND 5;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'reviews', 'review_score distribution', 'INFO',
       string_agg(review_score::text || '=' || n::text, ', ' ORDER BY review_score)
FROM (SELECT review_score, COUNT(*) n FROM raw.order_reviews GROUP BY 1) s;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'products', 'products without a category name', 'WARN', COUNT(*)::text
FROM raw.products WHERE product_category_name IS NULL;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'products', 'categories without an English translation', 'WARN', COUNT(*)::text
FROM raw.products p
LEFT JOIN raw.category_translation t
       ON t.product_category_name = p.product_category_name
WHERE p.product_category_name IS NOT NULL
  AND t.product_category_name IS NULL;

-- ---------------------------------------------------------------------------
-- G. Fan-out / join multiplication sanity
-- ---------------------------------------------------------------------------
INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'grain', 'max items on a single order', 'INFO',
       MAX(n)::text || ' items (avg ' || ROUND(AVG(n), 2)::text || ')'
FROM (SELECT order_id, COUNT(*) n FROM raw.order_items GROUP BY order_id) i;

INSERT INTO dq_results (check_area, check_name, severity, detail)
SELECT 'grain', 'max payment rows on a single order', 'INFO',
       MAX(n)::text || ' payment rows'
FROM (SELECT order_id, COUNT(*) n FROM raw.order_payments GROUP BY order_id) p;

-- ---------------------------------------------------------------------------
-- Report
-- ---------------------------------------------------------------------------
SELECT check_area, check_name, severity, detail
FROM dq_results
ORDER BY check_order;
