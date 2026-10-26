"""Run the full Python analysis pipeline.

Prerequisites: the database has been built with
    python scripts/setup_database.py --scripts sql/02_staging_tables.sql
and every sql/03..08 script has been executed (see README).

Outputs:
  * outputs/reports/data_quality_report.md
  * outputs/reports/reconciliation.md        (SQL vs Python agreement)
  * outputs/summary_tables/*.csv             (headline tables)
  * outputs/figures/*.png                    (charts)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd

from src import cohort_analysis as ca
from src import customer_metrics as cm
from src import data_loading as dl
from src import data_validation as dv
from src import delivery_analysis as da
from src import rfm_analysis as ra
from src import visualization as viz
from src.config import (OUTPUTS_DIR, SUMMARY_TABLES_DIR, get_engine)

REPORTS_DIR = OUTPUTS_DIR / "reports"


def export(df: pd.DataFrame, name: str,
           directory: Path = SUMMARY_TABLES_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def run() -> None:
    viz.set_style()
    engine = get_engine()

    # ------------------------------------------------------------------
    # 1. Data-quality report
    # ------------------------------------------------------------------
    print("1/6  data-quality checks")
    dq = dv.run_all_checks(engine)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "data_quality_report.md").write_text(
        dv.render_report(dq), encoding="utf-8")

    # ------------------------------------------------------------------
    # 2. Load + recompute in pandas
    # ------------------------------------------------------------------
    print("2/6  loading staging data and recomputing metrics")
    orders = dl.load_orders_enriched(engine)
    customers_py = cm.build_customer_metrics(orders)
    cohort_py = ca.build_cohort_table(orders)
    ref_date = ra.reference_date(orders)
    rfm_py = ra.compute_rfm(customers_py, ref_date)
    seg_py = ra.segment_summary(rfm_py)
    deliv = da.delivery_summary(orders)
    rev_del = da.review_by_delivery(orders)
    rep_del = da.repeat_by_first_delivery(orders, min_window_days=180)

    # ------------------------------------------------------------------
    # 3. Reconcile SQL vs Python
    # ------------------------------------------------------------------
    print("3/6  reconciling SQL vs Python results")
    customers_sql = dl.load_table("analytics.customer_metrics", engine)
    cohort_sql = dl.load_table("analytics.cohort_retention", engine)
    rfm_sql = dl.load_table("analytics.rfm_customers", engine)
    seg_sql = dl.load_table("analytics.rfm_segments", engine)
    deliv_sql = dl.load_table("analytics.delivery_summary", engine)

    checks = []

    def chk(name: str, sql_val, py_val, tol: float = 0.01):
        ok = abs(float(sql_val) - float(py_val)) <= tol
        checks.append({"check": name, "sql": sql_val, "python": py_val,
                       "status": "PASS" if ok else "FAIL"})

    chk("qualifying customers", len(customers_sql), len(customers_py), 0)
    chk("total revenue BRL", customers_sql["total_spend_brl"].sum(),
        customers_py["total_spend_brl"].sum(), 1.0)
    chk("repeat customers",
        int((customers_sql["order_count"] > 1).sum()),
        int((customers_py["order_count"] > 1).sum()), 0)
    chk("cohort rows", len(cohort_sql), len(cohort_py), 0)
    chk("cohort sizes total", cohort_sql.drop_duplicates(
        "cohort_month")["cohort_size"].sum(),
        cohort_py.drop_duplicates("cohort_month")["cohort_size"].sum(), 0)
    chk("rfm customers", len(rfm_sql), len(rfm_py), 0)
    seg_match = (
        rfm_sql.set_index("customer_unique_id")["rfm_segment"].sort_index()
        .eq(rfm_py.set_index("customer_unique_id")["rfm_segment"]
            .sort_index())
    )
    chk("rfm segment agreement", 100.0,
        float(seg_match.mean() * 100), 0.0)
    chk("late orders", int(deliv_sql["late_orders"].iloc[0]),
        deliv["late_orders"], 0)
    chk("late pct", float(deliv_sql["late_delivery_pct"].iloc[0]),
        deliv["late_delivery_pct"], 0.01)

    recon = pd.DataFrame(checks)
    md_rows = ["| check | sql | python | status |", "|---|---|---|---|"]
    md_rows += [
        f"| {r.check} | {r.sql} | {r.python} | {r.status} |"
        for r in recon.itertuples()
    ]
    (REPORTS_DIR / "reconciliation.md").write_text(
        "# SQL vs Python reconciliation\n\n" + "\n".join(md_rows) + "\n",
        encoding="utf-8")
    print(recon.to_string(index=False))

    # ------------------------------------------------------------------
    # 4. Export summary tables
    # ------------------------------------------------------------------
    print("4/6  exporting summary tables")
    export(customers_py, "customer_metrics")
    export(cm.order_count_distribution(customers_py),
           "customer_purchase_frequency")
    export(cohort_py, "cohort_retention")
    export(ca.retention_matrix(cohort_py).reset_index()
           .rename(columns={"cohort_month": "cohort"}),
           "cohort_retention_matrix")
    export(ca.cohort_summary(cohort_py), "cohort_summary")
    export(rfm_py, "rfm_customers")
    export(seg_py, "rfm_segments")
    export(pd.DataFrame([deliv]), "delivery_summary")
    export(rev_del, "review_by_delivery")
    export(rep_del, "repeat_by_first_delivery")
    export(da.late_rate_by(orders, "primary_category"), "late_by_category")
    export(da.late_rate_by(orders, "customer_state", min_orders=100),
           "late_by_state")

    # ------------------------------------------------------------------
    # 5. Figures
    # ------------------------------------------------------------------
    print("5/6  generating figures")

    fig = viz.cohort_heatmap(ca.retention_matrix(cohort_py))
    viz.save_fig(fig, "cohort_retention_heatmap")

    # segment customers + revenue
    s = seg_py.sort_values("customers", ascending=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    colors = [viz.SEGMENT_COLORS.get(x, "#8a8d91") for x in s["rfm_segment"]]
    axes[0].barh(s["rfm_segment"], s["customers"], color=colors)
    axes[0].set_title("Customers per RFM segment")
    axes[0].set_xlabel("Customers")
    axes[1].barh(s["rfm_segment"], s["total_revenue_brl"] / 1e6, color=colors)
    axes[1].set_title("Historical revenue per RFM segment")
    axes[1].set_xlabel("Revenue (R$ millions)")
    fig.tight_layout()
    viz.save_fig(fig, "rfm_segments")

    # delivery: review scores late vs on-time
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(rev_del["delivery_outcome"], rev_del["avg_review_score"],
                  color=[viz.PALETTE["bad"], viz.PALETTE["good"]])
    ax.bar_label(bars, fmt="%.2f")
    ax.set_ylim(0, 5)
    ax.set_title("Average review score: late vs on-time deliveries")
    ax.set_ylabel("Avg review score")
    viz.save_fig(fig, "review_score_by_delivery")

    # repeat rate by first-order delivery experience
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = rep_del["cohort_label"]
    bars = ax.bar(x, rep_del["repeat_rate_pct_windowed"],
                  color=[viz.PALETTE["bad"], viz.PALETTE["primary"]])
    ax.bar_label(bars, fmt="%.2f%%")
    ax.set_title("Repeat-purchase rate by first-order delivery "
                 "(customers with >=180-day window)")
    ax.set_ylabel("% placing another order")
    viz.save_fig(fig, "repeat_rate_by_first_delivery")

    # monthly orders + revenue trend
    monthly = dl.load_table("analytics.monthly_orders", engine)
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"])
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(monthly["purchase_month"], monthly["orders"],
            marker="o", color=viz.PALETTE["primary"], label="Orders")
    ax2 = ax.twinx()
    ax2.plot(monthly["purchase_month"], monthly["revenue_brl"] / 1000,
             marker="s", color=viz.PALETTE["accent"], label="Revenue (R$ k)")
    ax.set_title("Monthly delivered orders and revenue")
    ax.set_ylabel("Orders"); ax2.set_ylabel("Revenue (R$ thousands)")
    fig.tight_layout()
    viz.save_fig(fig, "monthly_orders_revenue")

    # top categories by revenue
    cat = dl.load_table("analytics.revenue_by_category", engine).head(10)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(cat["product_category"][::-1],
            cat["revenue_brl"][::-1] / 1e6,
            color=viz.PALETTE["primary"])
    ax.set_title("Top 10 categories by revenue")
    ax.set_xlabel("Revenue (R$ millions)")
    fig.tight_layout()
    viz.save_fig(fig, "revenue_by_category")

    # ------------------------------------------------------------------
    # 6. Done -> headline numbers for docs
    # ------------------------------------------------------------------
    print("6/6  done. Headline numbers:")
    n = len(customers_py)
    rep = (customers_py["order_count"] > 1).sum()
    print(f"  qualifying customers : {n:,}")
    print(f"  repeat customers     : {rep:,} ({rep / n * 100:.2f}%)")
    print(f"  total revenue        : R$ {customers_py['total_spend_brl'].sum():,.2f}")
    print(f"  late deliveries      : {deliv['late_orders']:,} "
          f"({deliv['late_delivery_pct']}% of delivered)")
    print(f"  reports  -> {REPORTS_DIR}")
    print(f"  figures  -> {viz.FIGURES_DIR}")


if __name__ == "__main__":
    run()
