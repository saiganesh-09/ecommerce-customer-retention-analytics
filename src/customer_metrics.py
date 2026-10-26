"""Customer-level metrics computed in pandas.

These functions independently recompute the same numbers produced by
sql/03_customer_metrics.sql so the SQL and Python pipelines can be
reconciled against each other.
"""

from __future__ import annotations

import pandas as pd


def build_customer_metrics(orders: pd.DataFrame) -> pd.DataFrame:
    """One row per customer_unique_id over qualifying orders.

    Parameters
    ----------
    orders : staging.orders_enriched frame (all statuses); qualifying
        rows are selected internally via is_qualifying_order.
    """
    q = orders.loc[orders["is_qualifying_order"]].sort_values(
        ["customer_unique_id", "purchase_ts", "order_id"])

    g = q.groupby("customer_unique_id")
    out = pd.DataFrame({
        "order_count": g.size(),
        "first_purchase_ts": g["purchase_ts"].min(),
        "last_purchase_ts": g["purchase_ts"].max(),
        "total_spend_brl": g["order_total_value"].sum().round(2),
        "avg_order_value_brl": g["order_total_value"].mean().round(2),
        "avg_review_score": g["review_score"].mean(),
        "late_deliveries": g["is_late_delivery"].sum(),
    })
    out["first_purchase_date"] = out["first_purchase_ts"].dt.normalize()
    out["last_purchase_date"] = out["last_purchase_ts"].dt.normalize()
    out["first_purchase_month"] = out["first_purchase_ts"].dt.to_period("M")
    out["customer_lifetime_days"] = (
        out["last_purchase_date"] - out["first_purchase_date"]).dt.days

    seq = q.groupby("customer_unique_id").cumcount() + 1
    second = (
        q.loc[seq == 2]
         .set_index("customer_unique_id")["purchase_ts"]
         .dt.normalize()
         .rename("second_purchase_date")
    )
    out = out.join(second)
    out["days_to_second_order"] = (
        out["second_purchase_date"] - out["first_purchase_date"]).dt.days
    out["is_repeat_customer"] = out["order_count"] > 1
    return out.reset_index()


def repeat_rate(customers: pd.DataFrame) -> float:
    """Share of qualifying customers who placed more than one order."""
    return float((customers["order_count"] > 1).mean() * 100)


def order_count_distribution(customers: pd.DataFrame) -> pd.DataFrame:
    """customers / revenue per order-count bucket."""
    dist = (customers.groupby("order_count")
                     .agg(customers=("customer_unique_id", "size"),
                          revenue_brl=("total_spend_brl", "sum"))
                     .reset_index())
    dist["pct_of_customers"] = (dist["customers"]
                                / dist["customers"].sum() * 100).round(2)
    dist["pct_of_revenue"] = (dist["revenue_brl"]
                              / dist["revenue_brl"].sum() * 100).round(2)
    dist["revenue_brl"] = dist["revenue_brl"].round(2)
    return dist
