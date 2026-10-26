"""Revenue and delivery-metric tests (synthetic + live DB)."""

from __future__ import annotations

import pandas as pd
import pytest

from src import delivery_analysis as da
from conftest import requires_db as needs_db


class TestDeliveryMetrics:
    def test_late_count(self, synthetic_orders):
        s = da.delivery_summary(synthetic_orders)
        # o3 (25th vs 20th) and o7 (5th vs 3rd) are late; o5 lacks a ts
        assert s["late_orders"] == 2
        assert s["delivered_with_timestamps"] == 5
        assert s["late_delivery_pct"] == 40.0

    def test_orders_without_timestamps_excluded(self, synthetic_orders):
        s = da.delivery_summary(synthetic_orders)
        # o5 is delivered but has no delivered_ts -> excluded from the
        # delivery metrics entirely (not counted as on-time)
        assert s["delivered_with_timestamps"] == 5

    def test_review_by_delivery(self, synthetic_orders):
        r = da.review_by_delivery(synthetic_orders).set_index(
            "delivery_outcome")
        assert r.loc["late", "orders_with_review"] == 2
        assert r.loc["late", "avg_review_score"] == 1.5
        assert r.loc["on_time", "avg_review_score"] == pytest.approx(
            (5 + 4 + 4) / 3, abs=0.01)  # o1, o2, o4

    def test_repeat_by_first_delivery(self, synthetic_orders):
        r = da.repeat_by_first_delivery(
            synthetic_orders, min_window_days=0).set_index("cohort_label")
        # first orders: c1 Jan (on time), c2 Jan (late), c3 Feb, c4 Mar(ts-na
        # -> excluded); c5 canceled -> no qualifying first order
        assert r.loc["first_order_late", "customers"] == 1       # c2
        assert r.loc["first_order_late", "repeat_rate_pct"] == 100.0
        assert r.loc["first_order_on_time", "customers"] == 2    # c1, c3
        assert r.loc["first_order_on_time", "repeat_rate_pct"] == 50.0


class TestOrderTotals:
    def test_no_negative_values(self, synthetic_orders):
        assert (synthetic_orders["order_total_value"] >= 0).all()

    def test_qualifying_filter_keeps_delivered_only(self, synthetic_orders):
        q = synthetic_orders[synthetic_orders["is_qualifying_order"]]
        assert (q["order_status"] == "delivered").all()
        assert len(q) == 6  # o6 canceled excluded


@needs_db
class TestLiveRevenue:
    def test_total_revenue_matches_pipeline(self, engine):
        from src import data_loading as dl
        kpi = dl.load_table("analytics.kpi_overview", engine)
        assert float(kpi["total_revenue_brl"].iloc[0]) == pytest.approx(
            15419773.75, abs=0.01)

    def test_item_plus_freight_equals_order_total(self, engine):
        from src import data_loading as dl
        n = dl.query(
            "SELECT COUNT(*) n FROM staging.orders_enriched "
            "WHERE ABS(order_total_value - items_value - freight_value)"
            " > 0.001", engine)["n"].iloc[0]
        assert n == 0
