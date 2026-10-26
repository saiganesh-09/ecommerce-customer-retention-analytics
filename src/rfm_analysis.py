"""RFM segmentation in pandas (mirrors sql/05_rfm_segmentation.sql).

Scoring rules (documented in the SQL script and docs/methodology.md):
  * reference date = day after the last observed qualifying purchase
  * R/M scored into quintiles; F uses fixed bins (1,2,3,4,5+)
  * segments assigned by an ordered rule list - first match wins
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEGMENT_ORDER = [
    "Champions", "Loyal Customers", "Potential Loyalists", "Needs Attention",
    "At Risk", "High-Value Inactive", "Recent One-Time Buyers",
    "Other One-Time Buyers", "Inactive One-Time Buyers",
]


def reference_date(orders: pd.DataFrame) -> pd.Timestamp:
    """Day after the latest qualifying purchase."""
    return orders.loc[orders["is_qualifying_order"],
                      "purchase_date"].max() + pd.Timedelta(days=1)


def assign_segment(r: int, f: int, m: int) -> str:
    """Ordered segment rules - first match wins. Mirrors the SQL CASE."""
    if r >= 4 and f >= 3 and m >= 4:
        return "Champions"
    if f >= 3 and r >= 3:
        return "Loyal Customers"
    if f >= 2 and r <= 2:
        return "At Risk"
    if f == 2 and r >= 4:
        return "Potential Loyalists"
    if f >= 2 and r == 3:
        return "Needs Attention"
    if f == 1 and m >= 4 and r <= 2:
        return "High-Value Inactive"
    if f == 1 and r >= 4:
        return "Recent One-Time Buyers"
    if f == 1 and r == 3:
        return "Other One-Time Buyers"
    return "Inactive One-Time Buyers"


def compute_rfm(customers: pd.DataFrame, ref_date: pd.Timestamp) -> pd.DataFrame:
    """Compute R/F/M, scores and segment for each customer.

    Parameters
    ----------
    customers : frame with customer_unique_id, order_count,
        last_purchase_date, total_spend_brl (from build_customer_metrics).
    """
    df = customers.copy()
    df["recency_days"] = (ref_date - df["last_purchase_date"]).dt.days
    df["frequency"] = df["order_count"]
    df["monetary_brl"] = df["total_spend_brl"]

    # Quintile scores implemented as NTILE-equivalent position ranks with a
    # deterministic tiebreak (customer_unique_id) - identical to the SQL.
    def _ntile(col: str, ascending: bool) -> pd.Series:
        # Exact NTILE(n) semantics: bucket sizes differ by <=1 and the
        # remainder rows go to the FIRST buckets (PostgreSQL behaviour).
        srt = df.sort_values(
            [col, "customer_unique_id"], ascending=[ascending, True])
        pos = np.arange(1, len(df) + 1)
        base, rem = divmod(len(df), 5)
        bounds = np.cumsum(
            [base + 1 if i < rem else base for i in range(5)])
        buckets = np.searchsorted(bounds, pos, side="left") + 1
        return pd.Series(buckets, index=srt.index)

    df["r_score"] = _ntile("recency_days", ascending=False)  # 5 = most recent
    df["m_score"] = _ntile("monetary_brl", ascending=True)   # 5 = highest
    df["f_score"] = df["frequency"].clip(upper=5).astype(int)

    df["rfm_score"] = df["r_score"] * 100 + df["f_score"] * 10 + df["m_score"]
    df["rfm_segment"] = [
        assign_segment(r, f, m)
        for r, f, m in zip(df["r_score"], df["f_score"], df["m_score"])
    ]
    return df


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    """Segment-level rollup matching analytics.rfm_segments."""
    g = rfm.groupby("rfm_segment")
    s = pd.DataFrame({
        "customers": g.size(),
        "total_revenue_brl": g["monetary_brl"].sum().round(2),
        "avg_spend_brl": g["monetary_brl"].mean().round(2),
        "avg_recency_days": g["recency_days"].mean().round(0),
        "avg_frequency": g["frequency"].mean().round(2),
        "avg_review_score": g["avg_review_score"].mean().round(2),
        "late_delivery_pct": (
            g["late_deliveries"].sum() / g["frequency"].sum() * 100).round(1),
    }).reset_index()
    s["pct_customers"] = (s["customers"] / s["customers"].sum() * 100).round(2)
    s["pct_revenue"] = (s["total_revenue_brl"]
                        / s["total_revenue_brl"].sum() * 100).round(2)
    s["rfm_segment"] = pd.Categorical(s["rfm_segment"],
                                      categories=SEGMENT_ORDER, ordered=True)
    return s.sort_values("total_revenue_brl", ascending=False)
