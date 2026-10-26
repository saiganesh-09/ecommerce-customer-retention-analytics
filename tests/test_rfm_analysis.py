"""Unit tests for src/rfm_analysis.py including NTILE edge cases."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.rfm_analysis import (assign_segment, compute_rfm, reference_date,
                              segment_summary)


def _customers(n, monetary=None, last=None, orders=None):
    return pd.DataFrame({
        "customer_unique_id": [f"c{i:03d}" for i in range(n)],
        "order_count": orders or [1] * n,
        "last_purchase_date": pd.to_datetime(
            last or ["2018-10-01"] * n),
        "total_spend_brl": monetary or [100.0] * n,
        "avg_review_score": [4.0] * n,
        "late_deliveries": [0] * n,
    })


class TestNtileSemantics:
    """The Python _ntile must match PostgreSQL NTILE: larger buckets first."""

    def test_remainder_goes_to_first_buckets(self):
        # N=7, 5 buckets -> sizes [2,2,1,1,1]
        df = _customers(7, monetary=[10, 20, 30, 40, 50, 60, 70])
        ref = pd.Timestamp("2018-10-18")
        out = compute_rfm(df, ref)
        # monetary ascending: c000 lowest -> m_score 1; c005,c006 top -> 5
        m = out.set_index("customer_unique_id")["m_score"]
        assert m.loc["c000"] == 1
        assert m.loc["c001"] == 1
        assert m.loc["c002"] == 2
        assert m.loc["c003"] == 2
        assert m.loc["c004"] == 3
        assert m.loc["c005"] == 4
        assert m.loc["c006"] == 5

    def test_recency_direction(self):
        df = _customers(5, last=["2018-10-17"] * 4 + ["2018-01-01"],
                        monetary=[10, 20, 30, 40, 50])
        out = compute_rfm(df, pd.Timestamp("2018-10-18"))
        m = out.set_index("customer_unique_id")
        # c004 bought longest ago -> lowest r_score
        assert m.loc["c004", "r_score"] == 1


class TestSegmentRules:
    @pytest.mark.parametrize("r,f,m,expected", [
        (5, 3, 5, "Champions"),
        (4, 4, 4, "Champions"),
        (3, 3, 3, "Loyal Customers"),
        (4, 3, 2, "Loyal Customers"),        # f>=3 & r>=3 wins over m
        (1, 2, 5, "At Risk"),                 # repeat buyer gone quiet
        (2, 5, 1, "At Risk"),
        (4, 2, 2, "Potential Loyalists"),
        (5, 2, 1, "Potential Loyalists"),
        (3, 2, 4, "Needs Attention"),
        (1, 1, 4, "High-Value Inactive"),
        (2, 1, 5, "High-Value Inactive"),
        (4, 1, 2, "Recent One-Time Buyers"),
        (5, 1, 1, "Recent One-Time Buyers"),
        (3, 1, 3, "Other One-Time Buyers"),
        (3, 1, 4, "Other One-Time Buyers"),   # m>=4 but r=3 -> not HVI
        (1, 1, 3, "Inactive One-Time Buyers"),
        (2, 1, 2, "Inactive One-Time Buyers"),
    ])
    def test_rule(self, r, f, m, expected):
        assert assign_segment(r, f, m) == expected

    def test_every_customer_gets_a_segment(self):
        df = _customers(50, monetary=list(np.linspace(10, 500, 50)),
                        last=pd.date_range("2018-06-01", periods=50)
                            .strftime("%Y-%m-%d").tolist())
        out = compute_rfm(df, pd.Timestamp("2018-10-18"))
        assert out["rfm_segment"].notna().all()


class TestSegmentSummary:
    def test_reconciles(self, synthetic_orders):
        from src.customer_metrics import build_customer_metrics
        cm = build_customer_metrics(synthetic_orders)
        rfm = compute_rfm(cm, pd.Timestamp("2018-04-15"))
        s = segment_summary(rfm)
        assert s["customers"].sum() == len(cm)
        assert abs(s["total_revenue_brl"].sum()
                   - cm["total_spend_brl"].sum()) < 0.01
        assert abs(s["pct_customers"].sum() - 100) < 0.05


class TestReferenceDate:
    def test_day_after_last_qualifying(self, synthetic_orders):
        # last qualifying purchase in the fixture is 2018-04-02
        assert reference_date(synthetic_orders) == pd.Timestamp("2018-04-03")
