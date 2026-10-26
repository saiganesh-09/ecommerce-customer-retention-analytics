-- =============================================================================
-- 08_business_recommendations.sql
--
-- Builds the segment-prioritisation table used to answer:
--   "Which customer segment should the business try to retain first?"
--
-- The table combines size, historical value, engagement and experience
-- metrics per RFM segment. Ranking is done in docs/business_recommendations.md
-- (a documented judgement call), NOT by an opaque formula.
-- =============================================================================

\set ON_ERROR_STOP on

DROP TABLE IF EXISTS analytics.segment_opportunity;
CREATE TABLE analytics.segment_opportunity AS
SELECT
    s.rfm_segment,
    s.customers,
    s.pct_customers,
    s.total_revenue_brl,
    s.pct_revenue,
    s.avg_spend_brl,
    s.avg_recency_days,
    s.avg_frequency,
    s.avg_review_score,
    s.late_delivery_pct,
    -- "Value per customer if they never return" vs upside framing:
    -- for repeat-capable segments, avg spend per ORDER is the per-return value.
    ROUND(s.avg_spend_brl / s.avg_frequency, 2) AS avg_value_per_order_brl,
    -- proxy reach: how many customers could a campaign touch
    s.customers * ROUND(s.avg_spend_brl / s.avg_frequency, 2)
                                               AS indicative_order_value_pool
FROM analytics.rfm_segments s;

SELECT * FROM analytics.segment_opportunity ORDER BY total_revenue_brl DESC;

-- Segment x delivery-experience detail for the prioritisation narrative -------
DROP TABLE IF EXISTS analytics.segment_experience;
CREATE TABLE analytics.segment_experience AS
SELECT
    rfm_segment,
    COUNT(*) FILTER (WHERE avg_review_score <= 2) AS unhappy_customers,
    COUNT(*) FILTER (WHERE late_deliveries > 0)   AS customers_hit_by_late_delivery,
    ROUND(100.0 * COUNT(*) FILTER (WHERE late_deliveries > 0)
          / COUNT(*), 1)                          AS pct_experienced_late
FROM analytics.rfm_customers
GROUP BY rfm_segment;

SELECT * FROM analytics.segment_experience;
