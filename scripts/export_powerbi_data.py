"""Export the analytical tables that feed the Power BI report.

Two ways to get the data into Power BI (documented in powerbi/README.md):
  A. Direct PostgreSQL connection to the analytics/staging schemas.
  B. Import the CSVs produced by this script (portable - no DB needed).

Usage:  python scripts/export_powerbi_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src import data_loading as dl
from src.config import PROCESSED_DATA_DIR, get_engine

EXPORT_DIR = PROCESSED_DATA_DIR  # data/processed/


def main() -> None:
    engine = get_engine()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------- fact table ----------------------------------
    fact = dl.query(
        """
        SELECT order_id, customer_unique_id, purchase_date, purchase_month,
               order_status, is_qualifying_order,
               item_count, items_value, freight_value, order_total_value,
               payment_total, payment_types, max_installments,
               delivered_ts::date AS delivered_date,
               estimated_delivery_ts::date AS estimated_delivery_date,
               delivery_days, delivery_delay_days, is_late_delivery,
               review_score, primary_category, customer_state, customer_city
        FROM staging.orders_enriched
        """,
        engine,
    )
    fact.to_csv(EXPORT_DIR / "fact_orders.csv", index=False)

    # ----------------------- customer dimension -----------------------------
    dim_customers = dl.query(
        """
        SELECT r.customer_unique_id, r.order_count, r.first_purchase_date,
               r.last_purchase_date, c.first_purchase_month,
               r.recency_days, r.frequency, r.monetary_brl,
               r.r_score, r.f_score, r.m_score, r.rfm_score, r.rfm_segment,
               r.avg_review_score, r.late_deliveries,
               c.is_repeat_customer, c.days_to_second_order,
               c.customer_lifetime_days
        FROM analytics.rfm_customers r
        JOIN analytics.customer_metrics c
          ON c.customer_unique_id = r.customer_unique_id
        """,
        engine,
    )
    dim_customers.to_csv(EXPORT_DIR / "dim_customers.csv", index=False)

    # --------------------------- date table --------------------------------
    dates = pd.date_range("2016-09-01", "2018-10-31", freq="D")
    dim_date = pd.DataFrame({
        "date": dates,
        "year": dates.year,
        "month": dates.month,
        "month_name": dates.strftime("%B"),
        "year_month": dates.strftime("%Y-%m"),
        "quarter": dates.quarter,
        "year_quarter": dates.year.astype(str) + "-Q" + dates.quarter.astype(str),
        "day_of_week": dates.day_name(),
    })
    dim_date.to_csv(EXPORT_DIR / "dim_date.csv", index=False)

    # ---------------------- precomputed analysis tables ---------------------
    for table in [
        "analytics.cohort_retention",
        "analytics.cohort_sizes",
        "analytics.cohort_summary",
        "analytics.rfm_segments",
        "analytics.segment_opportunity",
        "analytics.segment_experience",
        "analytics.delivery_summary",
        "analytics.review_by_delivery",
        "analytics.review_distribution_by_delivery",
        "analytics.repeat_by_first_delivery",
        "analytics.late_by_category",
        "analytics.late_by_state",
        "analytics.monthly_orders",
        "analytics.monthly_revenue",
        "analytics.revenue_by_category",
        "analytics.revenue_by_state",
        "analytics.customer_purchase_frequency",
        "analytics.payment_mix",
        "analytics.kpi_overview",
        "analytics.order_value_distribution",
    ]:
        name = table.split(".")[1]
        dl.load_table(table, engine).to_csv(
            EXPORT_DIR / f"{name}.csv", index=False)

    print(f"Exported {len(list(EXPORT_DIR.glob('*.csv')))} CSVs to {EXPORT_DIR}")
    for p in sorted(EXPORT_DIR.glob("*.csv")):
        print(f"  {p.name:<45} {p.stat().st_size / 1024:>8.0f} KB")


if __name__ == "__main__":
    main()
