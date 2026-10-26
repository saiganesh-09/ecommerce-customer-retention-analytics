"""Cohort retention analysis in pandas (mirrors sql/04_cohort_retention.sql).

Cohort = calendar month of a customer's first observed *qualifying*
(delivered) purchase. A customer counts as retained in month N if they
placed >=1 qualifying order in calendar month (cohort + N).
"""

from __future__ import annotations

import pandas as pd


def build_cohort_table(orders: pd.DataFrame) -> pd.DataFrame:
    """Long-format cohort retention table.

    Returns columns: cohort_month, cohort_size, months_since_first,
    active_customers, retention_pct, is_observed.
    """
    q = orders.loc[orders["is_qualifying_order"],
                   ["customer_unique_id", "purchase_month"]].copy()
    q["purchase_month"] = pd.to_datetime(q["purchase_month"])

    first = (q.groupby("customer_unique_id")["purchase_month"]
              .min().rename("cohort_month"))
    act = (q.merge(first, on="customer_unique_id")
             [["customer_unique_id", "cohort_month", "purchase_month"]]
             .drop_duplicates())
    act["months_since_first"] = (
        (act["purchase_month"].dt.year - act["cohort_month"].dt.year) * 12
        + act["purchase_month"].dt.month - act["cohort_month"].dt.month
    )

    sizes = (first.value_counts()
             .rename("cohort_size")
             .rename_axis("cohort_month")
             .reset_index())
    last_month = q["purchase_month"].max().to_period("M").to_timestamp()

    grouped = (act.groupby(["cohort_month", "months_since_first",
                            "purchase_month"])
                  .agg(active_customers=("customer_unique_id", "nunique"))
                  .reset_index()
                  .rename(columns={"purchase_month": "activity_month"}))
    grouped = grouped.merge(sizes, on="cohort_month")
    grouped["retention_pct"] = (
        grouped["active_customers"] / grouped["cohort_size"] * 100).round(2)
    grouped["is_observed"] = grouped["activity_month"] <= last_month
    return grouped.sort_values(["cohort_month", "months_since_first"])


def retention_matrix(cohort: pd.DataFrame,
                     observed_only: bool = True) -> pd.DataFrame:
    """Pivot the long table into the classic cohort x month matrix (%)."""
    df = cohort.loc[cohort["is_observed"]] if observed_only else cohort
    mat = df.pivot(index="cohort_month", columns="months_since_first",
                   values="retention_pct")
    mat.index = mat.index.strftime("%Y-%m")
    mat.columns = mat.columns.astype(int)
    return mat.sort_index(axis=1)


def cohort_summary(cohort: pd.DataFrame) -> pd.DataFrame:
    """Average retention per months_since_first over observed cohorts only."""
    obs = cohort.loc[cohort["is_observed"]]
    s = (obs.groupby("months_since_first")
            .agg(cohorts_observed=("cohort_month", "nunique"),
                 returning_customers=("active_customers", "sum"),
                 customers_in_window=("cohort_size", "sum"))
            .reset_index())
    s["avg_retention_pct"] = (
        s["returning_customers"] / s["customers_in_window"] * 100).round(2)
    return s
