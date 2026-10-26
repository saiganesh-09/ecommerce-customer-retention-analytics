"""Data-quality and reconciliation tests (require the live database)."""

from __future__ import annotations

import pytest

from src import data_loading as dl

from conftest import requires_db as needs_db


@needs_db
class TestRawIntegrity:
    def test_expected_row_counts(self, engine):
        expected = {
            "customers": 99441, "orders": 99441, "order_items": 112650,
            "order_payments": 103886, "order_reviews": 99224,
            "products": 32951, "sellers": 3095, "geolocation": 1000163,
            "category_translation": 71,
        }
        for table, n in expected.items():
            got = dl.query(f"SELECT COUNT(*) n FROM raw.{table}",
                           engine)["n"].iloc[0]
            assert got == n, f"{table}: {got} != {n}"

    def test_no_orphaned_order_items(self, engine):
        n = dl.query(
            """SELECT COUNT(*) n FROM raw.order_items i
               LEFT JOIN raw.orders o ON o.order_id = i.order_id
               WHERE o.order_id IS NULL""", engine)["n"].iloc[0]
        assert n == 0

    def test_no_null_customer_keys(self, engine):
        n = dl.query(
            """SELECT COUNT(*) n FROM raw.orders o
               JOIN raw.customers c ON c.customer_id = o.customer_id
               WHERE c.customer_unique_id IS NULL""",
            engine)["n"].iloc[0]
        assert n == 0


@needs_db
class TestStagingIntegrity:
    def test_one_row_per_order(self, engine):
        df = dl.query(
            "SELECT COUNT(*) n, COUNT(DISTINCT order_id) d "
            "FROM staging.orders_enriched", engine)
        assert df["n"].iloc[0] == df["d"].iloc[0] == 99441

    def test_one_review_per_order(self, engine):
        n = dl.query(
            "SELECT COUNT(*) n FROM (SELECT order_id FROM "
            "staging.order_reviews GROUP BY order_id "
            "HAVING COUNT(*) > 1) d", engine)["n"].iloc[0]
        assert n == 0

    def test_late_flag_needs_timestamps(self, engine):
        n = dl.query(
            "SELECT COUNT(*) n FROM staging.orders_enriched "
            "WHERE is_late_delivery AND (delivered_ts IS NULL OR "
            "estimated_delivery_ts IS NULL)", engine)["n"].iloc[0]
        assert n == 0


@needs_db
class TestAnalyticsIntegrity:
    def test_cohort_month0_is_100(self, engine):
        n = dl.query(
            "SELECT COUNT(*) n FROM analytics.cohort_retention "
            "WHERE months_since_first = 0 "
            "AND ABS(retention_pct - 100) > 0.01", engine)["n"].iloc[0]
        assert n == 0

    def test_cohort_sizes_sum(self, engine):
        a = dl.query("SELECT SUM(cohort_size) s FROM "
                     "analytics.cohort_sizes", engine)["s"].iloc[0]
        b = dl.query("SELECT COUNT(*) n FROM analytics.customer_metrics",
                     engine)["n"].iloc[0]
        assert a == b

    def test_rfm_no_null_segments(self, engine):
        n = dl.query("SELECT COUNT(*) n FROM analytics.rfm_customers "
                     "WHERE rfm_segment IS NULL", engine)["n"].iloc[0]
        assert n == 0

    def test_revenue_reconciles(self, engine):
        a = dl.query("SELECT SUM(total_spend_brl) s FROM "
                     "analytics.customer_metrics", engine)["s"].iloc[0]
        b = dl.query("SELECT SUM(order_total_value) s FROM "
                     "staging.orders_enriched WHERE is_qualifying_order",
                     engine)["s"].iloc[0]
        assert abs(float(a) - float(b)) < 0.01
