-- =============================================================================
-- 05_rfm_segmentation.sql
--
-- RFM (Recency, Frequency, Monetary) customer segmentation.
--
-- Definitions:
--   * Reference date = day after the last observed qualifying purchase in the
--     dataset (2018-10-18). Using "now" would be wrong: the data ends in
--     Oct-2018, so recency must be measured against the data window, not the
--     wall clock.
--   * R = days between reference date and last qualifying purchase.
--   * F = number of distinct qualifying (delivered) orders.
--   * M = total spend (item price + freight) on qualifying orders.
--
-- Scoring (documented rules, not pure quintiles):
--   * R and M are scored into quintiles (NTILE(5)) over the customer base.
--   * F uses FIXED bins because ~97% of customers have exactly 1 order - a
--     quintile split on frequency is meaningless for this dataset:
--       F=1 -> 1, F=2 -> 2, F=3 -> 3, F=4 -> 4, F>=5 -> 5
--
-- Segments are assigned by the ordered CASE below (first match wins). Every
-- eligible customer receives exactly one segment.
-- =============================================================================

\set ON_ERROR_STOP on

DROP TABLE IF EXISTS analytics.rfm_customers;
CREATE TABLE analytics.rfm_customers AS
WITH params AS (
    SELECT MAX(purchase_date) + 1 AS reference_date
    FROM staging.orders_enriched
    WHERE is_qualifying_order
),
rfm_base AS (
    SELECT
        m.customer_unique_id,
        m.order_count,
        m.first_purchase_date,
        m.last_purchase_date,
        ((SELECT reference_date FROM params) - m.last_purchase_date) AS recency_days,
        m.order_count                                              AS frequency,
        m.total_spend_brl                                          AS monetary_brl,
        m.avg_review_score,
        m.late_deliveries
    FROM analytics.customer_metrics m
),
scored AS (
    SELECT *,
        -- Deterministic quintiles: customer_unique_id breaks ties so the
        -- SQL and pandas implementations agree row-for-row.
        NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id)
                                                          AS r_score,  -- 5 = most recent
        CASE
            WHEN frequency >= 5 THEN 5
            WHEN frequency = 4  THEN 4
            WHEN frequency = 3  THEN 3
            WHEN frequency = 2  THEN 2
            ELSE 1
        END                                               AS f_score,
        NTILE(5) OVER (ORDER BY monetary_brl, customer_unique_id)
                                                          AS m_score   -- 5 = highest
    FROM rfm_base
)
SELECT
    customer_unique_id,
    order_count,
    first_purchase_date,
    last_purchase_date,
    recency_days,
    frequency,
    monetary_brl,
    r_score,
    f_score,
    m_score,
    (r_score * 100 + f_score * 10 + m_score)  AS rfm_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 3 AND m_score >= 4 THEN 'Champions'
        WHEN f_score >= 3 AND r_score >= 3                  THEN 'Loyal Customers'
        WHEN f_score >= 2 AND r_score <= 2                  THEN 'At Risk'
        WHEN f_score = 2  AND r_score >= 4                  THEN 'Potential Loyalists'
        WHEN f_score >= 2 AND r_score = 3                   THEN 'Needs Attention'
        WHEN f_score = 1  AND m_score >= 4 AND r_score <= 2 THEN 'High-Value Inactive'
        WHEN f_score = 1  AND r_score >= 4                  THEN 'Recent One-Time Buyers'
        WHEN f_score = 1  AND r_score = 3                   THEN 'Other One-Time Buyers'
        ELSE 'Inactive One-Time Buyers'
    END AS rfm_segment,
    avg_review_score,
    late_deliveries,
    (SELECT reference_date FROM params) AS reference_date
FROM scored;

CREATE UNIQUE INDEX rfm_customers_idx ON analytics.rfm_customers (customer_unique_id);
CREATE INDEX rfm_segment_idx ON analytics.rfm_customers (rfm_segment);

COMMENT ON TABLE analytics.rfm_customers IS
  'RFM per customer_unique_id (delivered orders only). Reference date = '
  'max(purchase_date)+1 = 2018-10-18. Segments assigned by ordered CASE.';

-- ---------------------------------------------------------------------------
-- Segment-level summary
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS analytics.rfm_segments;
CREATE TABLE analytics.rfm_segments AS
SELECT
    rfm_segment,
    COUNT(*)                                AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)
                                            AS pct_customers,
    ROUND(SUM(monetary_brl), 2)             AS total_revenue_brl,
    ROUND(100.0 * SUM(monetary_brl)
                / SUM(SUM(monetary_brl)) OVER (), 2)
                                            AS pct_revenue,
    ROUND(AVG(monetary_brl), 2)             AS avg_spend_brl,
    ROUND(AVG(recency_days), 0)             AS avg_recency_days,
    ROUND(AVG(frequency), 2)                AS avg_frequency,
    ROUND(AVG(avg_review_score), 2)         AS avg_review_score,
    ROUND(100.0 * SUM(late_deliveries)
                / NULLIF(SUM(frequency), 0), 1) AS late_delivery_pct
FROM analytics.rfm_customers
GROUP BY rfm_segment
ORDER BY total_revenue_brl DESC;

SELECT * FROM analytics.rfm_segments;
