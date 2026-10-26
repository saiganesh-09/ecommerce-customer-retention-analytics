"""Unit tests for src/customer_metrics.py on synthetic fixtures."""

from __future__ import annotations

from src.customer_metrics import (build_customer_metrics,
                                  order_count_distribution, repeat_rate)


class TestBuildCustomerMetrics:
    def test_only_qualifying_orders_count(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders)
        # c5 has only a canceled order -> excluded entirely
        assert set(m["customer_unique_id"]) == {"c1", "c2", "c3", "c4"}

    def test_order_counts(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders).set_index(
            "customer_unique_id")
        assert m.loc["c1", "order_count"] == 2
        assert m.loc["c2", "order_count"] == 2
        assert m.loc["c3", "order_count"] == 1
        assert m.loc["c4", "order_count"] == 1

    def test_total_spend(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders).set_index(
            "customer_unique_id")
        assert m.loc["c1", "total_spend_brl"] == 150.0
        assert m.loc["c2", "total_spend_brl"] == 240.0

    def test_first_and_second_purchase(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders).set_index(
            "customer_unique_id")
        assert str(m.loc["c1", "first_purchase_date"].date()) == "2018-01-01"
        assert str(m.loc["c1", "second_purchase_date"].date()) == "2018-02-01"
        assert m.loc["c1", "days_to_second_order"] == 31
        # one-time buyers have no second-purchase fields
        assert m.loc["c3", "days_to_second_order"] != m.loc[
            "c3", "days_to_second_order"]  # NaN check

    def test_repeat_flag(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders).set_index(
            "customer_unique_id")
        assert bool(m.loc["c1", "is_repeat_customer"]) is True
        assert bool(m.loc["c3", "is_repeat_customer"]) is False


class TestRepeatRate:
    def test_value(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders)
        assert repeat_rate(m) == 50.0  # 2 of 4 customers repeat


class TestOrderCountDistribution:
    def test_reconciles_to_population(self, synthetic_orders):
        m = build_customer_metrics(synthetic_orders)
        d = order_count_distribution(m)
        assert d["customers"].sum() == len(m)
        assert abs(d["revenue_brl"].sum()
                   - m["total_spend_brl"].sum()) < 0.01
        assert abs(d["pct_of_customers"].sum() - 100) < 0.05
