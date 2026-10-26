"""Delivery performance analysis in pandas (mirrors sql/06_delivery_analysis.sql)."""

from __future__ import annotations

import pandas as pd


def _timed(orders: pd.DataFrame) -> pd.DataFrame:
    """Delivered orders that have both delivery timestamps."""
    mask = (orders["order_status"].eq("delivered")
            & orders["delivered_ts"].notna()
            & orders["estimated_delivery_ts"].notna())
    return orders.loc[mask]


def delivery_summary(orders: pd.DataFrame) -> dict:
    """Headline delivery metrics."""
    d = _timed(orders)
    promised = (d["estimated_delivery_ts"].dt.normalize()
                - d["purchase_date"]).dt.days
    return {
        "delivered_with_timestamps": int(len(d)),
        "avg_delivery_days": round(float(d["delivery_days"].mean()), 1),
        "median_delivery_days": float(d["delivery_days"].median()),
        "p90_delivery_days": float(d["delivery_days"].quantile(0.9)),
        "avg_promised_days": round(float(promised.mean()), 1),
        "late_orders": int(d["is_late_delivery"].sum()),
        "late_delivery_pct": round(float(d["is_late_delivery"].mean() * 100), 2),
        "avg_days_late_when_late": round(
            float(d.loc[d["is_late_delivery"], "delivery_delay_days"].mean()), 1),
        "avg_delay_days_all": round(float(d["delivery_delay_days"].mean()), 1),
    }


def review_by_delivery(orders: pd.DataFrame) -> pd.DataFrame:
    """Review score stats split by on-time vs late delivery."""
    d = _timed(orders).dropna(subset=["review_score"]).copy()
    d["delivery_outcome"] = d["is_late_delivery"].map(
        {True: "late", False: "on_time"})
    g = d.groupby("delivery_outcome")
    return pd.DataFrame({
        "orders_with_review": g.size(),
        "avg_review_score": g["review_score"].mean().round(2),
        "pct_score_1_2": g["review_score"].apply(
            lambda s: (s <= 2).mean() * 100).round(2),
        "pct_score_5": g["review_score"].apply(
            lambda s: (s == 5).mean() * 100).round(2),
        "avg_delivery_days": g["delivery_days"].mean().round(1),
        "avg_delay_days": g["delivery_delay_days"].mean().round(1),
    }).reset_index()


def repeat_by_first_delivery(orders: pd.DataFrame,
                             min_window_days: int = 180,
                             data_end: pd.Timestamp | None = None
                             ) -> pd.DataFrame:
    """Repeat rate grouped by the delivery experience of the FIRST order.

    Also reports a windowed variant restricting to customers whose first
    order is at least `min_window_days` before the dataset end, so each
    customer had a fair follow-up period.
    """
    q = orders.loc[orders["is_qualifying_order"]]
    data_end = data_end or q["purchase_ts"].max()
    cutoff = data_end - pd.Timedelta(days=min_window_days)

    first_ts = q.groupby("customer_unique_id")["purchase_ts"].min()
    first_orders = q.merge(first_ts.rename("first_ts"),
                           on="customer_unique_id")
    first_orders = first_orders[
        first_orders["purchase_ts"] == first_orders["first_ts"]]
    first_orders = first_orders.dropna(
        subset=["delivered_ts", "estimated_delivery_ts"])
    first_orders = first_orders.drop_duplicates("customer_unique_id")

    order_counts = q.groupby("customer_unique_id").size()
    res = first_orders[["customer_unique_id", "is_late_delivery",
                        "first_ts"]].copy()
    res["later_orders"] = (res["customer_unique_id"].map(order_counts) - 1)
    res["has_window"] = res["first_ts"] <= cutoff
    res["group"] = res["is_late_delivery"].map(
        {True: "first_order_late", False: "first_order_on_time"})

    def _rate(df: pd.DataFrame) -> float:
        return round(float((df["later_orders"] > 0).mean() * 100), 2)

    out = []
    for name, grp in res.groupby("group"):
        w = grp.loc[grp["has_window"]]
        out.append({
            "cohort_label": name,
            "customers": len(grp),
            "repeat_customers": int((grp["later_orders"] > 0).sum()),
            "repeat_rate_pct": _rate(grp),
            "customers_windowed": len(w),
            "repeat_rate_pct_windowed": _rate(w),
        })
    return pd.DataFrame(out)


def late_rate_by(orders: pd.DataFrame, dim: str,
                 min_orders: int = 300) -> pd.DataFrame:
    """Late-delivery rate per dimension (e.g. primary_category, state)."""
    d = _timed(orders)
    g = d.groupby(dim)
    out = pd.DataFrame({
        "delivered_orders": g.size(),
        "avg_delivery_days": g["delivery_days"].mean().round(1),
        "late_pct": g["is_late_delivery"].mean().mul(100).round(1),
        "avg_review_score": g["review_score"].mean().round(2),
    }).reset_index()
    return out.loc[out["delivered_orders"] >= min_orders].sort_values(
        "late_pct", ascending=False)
