"""Generate the analysis notebooks (.ipynb) from cell definitions.

Run once (or after changing the spec) and then execute with:
    python -m nbconvert --to notebook --execute --inplace notebooks/0*.ipynb
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

SETUP = '''\
import sys
from pathlib import Path

# Make the repo's src/ package importable when running from notebooks/.
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from src import data_loading as dl
from src.config import get_engine
from src.visualization import PALETTE, set_style

set_style()
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
engine = get_engine()
'''


def make_nb(cells, kernelspec="olist-venv"):
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "display_name": "Python (olist-venv)",
        "language": "python",
        "name": kernelspec,
    }
    nb.metadata["language_info"] = {"name": "python"}
    nb.cells = [
        nbf.v4.new_markdown_cell(src) if kind == "md"
        else nbf.v4.new_code_cell(src)
        for kind, src in cells
    ]
    return nb


NOTEBOOKS = {}

# ---------------------------------------------------------------------------
NOTEBOOKS["01_data_understanding"] = [
("md", """# 01 — Data Understanding

**Objective:** profile every Olist source table before analysis: row counts,
grain, keys, missing values, value ranges and known quality issues.

**Business context:** Olist is a Brazilian marketplace connecting small
sellers to large retailers' sites. Each table represents one part of the
order lifecycle. Understanding the grain of each table is essential —
a wrong join (e.g. order x items x payments in one flat table) silently
inflates every metric."""),
("code", SETUP),
("md", """## Row counts and grain"""),
("code", '''tables = {
    "customers":            "one row per customer_id (order-level record)",
    "orders":               "one row per order",
    "order_items":          "one row per (order_id, order_item_id)",
    "order_payments":       "one row per (order_id, payment_sequential)",
    "order_reviews":        "one row per review record (review_id NOT unique)",
    "products":             "one row per product_id",
    "sellers":              "one row per seller_id",
    "geolocation":          "one row per (zip prefix, lat, lng) point",
    "category_translation": "one row per PT category name",
}
rows = [
    {"table": t, "grain": g,
     "rows": dl.query(f"SELECT COUNT(*) n FROM raw.{t}", engine)["n"].iloc[0]}
    for t, g in tables.items()
]
pd.DataFrame(rows)'''),
("md", """## Orders table - status mix and date coverage"""),
("code", '''dl.query("""
    SELECT order_status, COUNT(*) AS orders,
           ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) AS pct
    FROM raw.orders GROUP BY order_status ORDER BY orders DESC
""", engine)'''),
("code", '''dl.query("""
    SELECT MIN(order_purchase_timestamp) AS first_purchase,
           MAX(order_purchase_timestamp) AS last_purchase,
           MIN(order_delivered_customer_date) AS first_delivery,
           MAX(order_estimated_delivery_date) AS last_estimate
    FROM raw.orders
""", engine)'''),
("md", """**Observation:** purchases span **Sep-2016 to Oct-2018**. Any recency/
retention statement must be made relative to this window — the data is
historical, so "now" is meaningless."""),
("md", """## Missing values"""),
("code", '''missing = dl.query("""
    SELECT 'orders.delivered_customer_date' AS col,
           COUNT(*) FILTER (WHERE order_delivered_customer_date IS NULL) AS nulls
    FROM raw.orders
    UNION ALL
    SELECT 'orders.delivered_carrier_date',
           COUNT(*) FILTER (WHERE order_delivered_carrier_date IS NULL)
    FROM raw.orders
    UNION ALL
    SELECT 'orders.approved_at',
           COUNT(*) FILTER (WHERE order_approved_at IS NULL) FROM raw.orders
    UNION ALL
    SELECT 'products.category_name',
           COUNT(*) FILTER (WHERE product_category_name IS NULL) FROM raw.products
    UNION ALL
    SELECT 'reviews.comment_message',
           COUNT(*) FILTER (WHERE review_comment_message IS NULL)
    FROM raw.order_reviews
    UNION ALL
    SELECT 'reviews.comment_title',
           COUNT(*) FILTER (WHERE review_comment_title IS NULL)
    FROM raw.order_reviews
""", engine)
missing'''),
("md", """Missing **delivery timestamps** are expected for non-delivered orders
(shipped/canceled/etc.) — records are excluded per-metric, not deleted.
Missing review comments are normal (most buyers leave only a score)."""),
("md", """## Customer identity - the most important modelling fact"""),
("code", '''dl.query("""
    SELECT COUNT(DISTINCT customer_id)         AS customer_ids,
           COUNT(DISTINCT customer_unique_id)  AS real_unique_customers,
           (SELECT COUNT(*) FROM (
               SELECT customer_unique_id FROM raw.customers
               GROUP BY customer_unique_id HAVING COUNT(*) > 1) r)
                                              AS customers_with_multiple_ids
    FROM raw.customers
""", engine)'''),
("md", """`customer_id` is generated **per order**; `customer_unique_id` is the
same person across orders. Every customer-level metric in this project uses
`customer_unique_id`."""),
("md", """## Known data-quality issues (from sql/01_data_quality_checks.sql)

* 789 duplicated `review_id`s and 547 orders with multiple review rows
  -> staging keeps ONE review per order (latest creation date).
* 8 delivered orders have no delivery timestamp; 6 non-delivered orders do.
* 23 orders delivered "before" carrier handover (timestamp noise).
* 9 zero-value payments; 1 order with no payment rows.
* 246 delivered orders where payment total differs from items+freight
  by >R$1 -> we therefore define revenue as items+freight, not payments.
* 610 products lack a category name; 13 categories lack English
  translation -> mapped to 'unknown'.

## Conclusion

The dataset is internally consistent (zero orphaned keys, zero invalid
scores/dates at the grain level) but has quirks that must be handled
per-metric. The staging layer in `sql/02_staging_tables.sql` encodes
all of these decisions explicitly."""),
]

# ---------------------------------------------------------------------------
NOTEBOOKS["02_exploratory_analysis"] = [
("md", """# 02 — Exploratory Analysis

**Objective:** establish the business baseline: how many orders/customers,
how much revenue, how concentrated the customer base is.

**Business questions:** What does a typical Olist order look like? How many
customers ever come back? Where does revenue come from?"""),
("code", SETUP),
("md", "## Headline KPIs (qualifying = delivered orders)"),
("code", '''kpi = dl.load_table("analytics.kpi_overview", engine)
kpi.T.rename(columns={0: "value"})'''),
("md", """**Reading the numbers:** ~96.5% of orders reach 'delivered' status.
Revenue is defined as item price + freight summed over delivered orders
(payments are kept as a separate reconciliation measure because ~250
orders show payment/item mismatches)."""),
("md", "## Monthly orders & revenue trend"),
("code", '''monthly = dl.load_table("analytics.monthly_orders", engine)
monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"])

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(monthly["purchase_month"], monthly["orders"], marker="o",
        color=PALETTE["primary"], label="Delivered orders")
ax2 = ax.twinx()
ax2.plot(monthly["purchase_month"], monthly["revenue_brl"] / 1000,
         marker="s", color=PALETTE["accent"], label="Revenue (R$ k)")
ax.set_title("Monthly delivered orders and revenue")
ax.set_ylabel("Orders"); ax2.set_ylabel("Revenue (R$ thousands)")
plt.show()'''),
("md", """Strong growth through 2017, a peak around **Nov-2017** (Black Friday),
then a high plateau through 2018. The last months are partial (data ends
mid-Oct-2018) — trend claims should exclude the boundary months."""),
("md", "## One-time vs repeat customers"),
("code", '''freq = dl.load_table("analytics.customer_purchase_frequency", engine)
freq.head(10)'''),
("code", '''fig, ax = plt.subplots(figsize=(9, 4.5))
top = freq.head(8)
ax.bar(top["order_count"].astype(str), top["customers"],
       color=PALETTE["primary"])
ax.set_yscale("log")
ax.set_title("Customers by number of delivered orders (log scale)")
ax.set_xlabel("Delivered orders per customer"); ax.set_ylabel("Customers")
plt.show()

one_time = freq.loc[freq["order_count"] == 1, "customers"].iloc[0]
total = freq["customers"].sum()
print(f"one-time customers: {one_time:,} of {total:,} "
      f"({one_time/total*100:.1f}%)")'''),
("md", """**The central fact of this dataset:** ~97% of customers order exactly
once. Olist is effectively a single-purchase marketplace — which is exactly
why retention analysis matters."""),
("md", "## How long until a second order?"),
("code", '''customers = dl.load_table("analytics.customer_metrics", engine)
d2 = customers["days_to_second_order"].dropna()
fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(d2.clip(0, 365), bins=60, color=PALETTE["primary"])
ax.set_title("Days between first and second delivered order (repeat buyers)")
ax.set_xlabel("days"); ax.set_ylabel("customers")
plt.show()
print(f"median {d2.median():.0f} days | mean {d2.mean():.1f} days")'''),
("md", "## Revenue by category & state"),
("code", '''cat = dl.load_table("analytics.revenue_by_category", engine)
fig, ax = plt.subplots(figsize=(10, 5))
top10 = cat.head(10)
ax.barh(top10["product_category"][::-1], top10["revenue_brl"][::-1]/1e6,
        color=PALETTE["primary"])
ax.set_title("Top 10 categories by revenue")
ax.set_xlabel("R$ millions")
plt.show()'''),
("code", '''st = dl.load_table("analytics.revenue_by_state", engine)
st.head(10)'''),
("md", """## Order value distribution"""),
("code", '''ovd = dl.load_table("analytics.order_value_distribution", engine)
ovd'''),
("md", """## Conclusion

* Business grew rapidly to ~R$1M+/month by late 2017, then plateaued.
* **97% of customers buy once** — repeat purchasing is rare in this
  marketplace model.
* Repeat buyers typically return within ~1 month (median 29 days) when
  they do return.
* Revenue is spread across categories; SP state alone is ~37%.
* Median order ~R$105 — meaningful but not huge basket sizes."""),
]

# ---------------------------------------------------------------------------
NOTEBOOKS["03_cohort_retention"] = [
("md", """# 03 — Cohort Retention Analysis

**Objective:** measure how customer purchasing activity evolves after the
first observed purchase.

**Definitions used here:**
* **Cohort** = calendar month of a customer's first *qualifying* (delivered)
  order. First *observed* purchase — customers may have bought on Olist
  before the dataset starts.
* **Month 0** = the acquisition month (retention = 100% by construction).
* **Retained in month N** = placed >=1 delivered order that month.
* Cohort-months extending past the data window are flagged `is_observed`
  and excluded from headline claims — they are NOT zero-filled."""),
("code", SETUP),
("code", '''from src import cohort_analysis as ca

orders = dl.load_orders_enriched(engine)
cohort = ca.build_cohort_table(orders)
sizes = cohort.drop_duplicates("cohort_month")[["cohort_month", "cohort_size"]]
sizes'''),
("md", "Small early cohorts (2016) reflect Olist's ramp-up; cohorts from 2017-01 onward are large enough to compare."),
("md", "## Retention matrix (observed months only)"),
("code", '''matrix = ca.retention_matrix(cohort)
matrix.round(2)'''),
("code", '''from src.visualization import cohort_heatmap
fig = cohort_heatmap(matrix)
plt.show()'''),
("md", """## Average retention per month-since-first"""),
("code", '''summary = ca.cohort_summary(cohort)
fig, ax = plt.subplots(figsize=(10, 4.5))
ax.bar(summary["months_since_first"], summary["avg_retention_pct"],
       color=PALETTE["primary"])
ax.set_title("Average share of a cohort ordering in month N")
ax.set_xlabel("months since first purchase")
ax.set_ylabel("% of cohort")
plt.show()
summary.head(13)'''),
("md", """## Conclusion

* Month-1 retention is **well under 1%** in every cohort, and it stays
  near zero — there is no meaningful 'return curve' to bend in the
  observed window.
* Longer-horizon numbers (m6, m12) hover at ~0.1-0.5%: repeat behaviour
  exists but is rare and does not strengthen over time.
* **Interpretation:** unlike subscription businesses, Olist shows no
  cohort that 'warms up'. Retention strategy here is not about keeping
  a subscription alive — it is about prompting the second purchase.
* Caveat: 'active in month N' counts a repeat order in *any* later
  month only once per month, so a customer buying in month 3 appears
  at month 3 but not month 2 — the matrix is not cumulative."""),
]

# ---------------------------------------------------------------------------
NOTEBOOKS["04_rfm_segmentation"] = [
("md", """# 04 — RFM Customer Segmentation

**Objective:** segment all qualifying customers by Recency, Frequency and
Monetary value to identify where retention effort could pay off.

**Method:**
* Reference date = day after last observed purchase (**2018-10-18**), not
  today's date — the data ends Oct-2018.
* R and M scored into quintiles; F uses fixed bins (1,2,3,4,5+) because
  ~97% of customers have frequency 1 (a quintile on F is meaningless).
* Segments assigned by ordered rules — see docs/methodology.md."""),
("code", SETUP),
("code", '''rfm = dl.load_table("analytics.rfm_customers", engine)
rfm[["recency_days","frequency","monetary_brl",
     "r_score","f_score","m_score","rfm_segment"]].describe(include="all")'''),
("md", "## R, F, M distributions"),
("code", '''fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].hist(rfm["recency_days"], bins=50, color=PALETTE["primary"])
axes[0].set_title("Recency (days since last order)")
axes[1].hist(rfm["frequency"].clip(0, 10), bins=10, color=PALETTE["accent"])
axes[1].set_title("Frequency (orders)")
axes[2].hist(rfm["monetary_brl"].clip(0, 2000), bins=50,
             color=PALETTE["good"])
axes[2].set_title("Monetary (R$, clipped at 2000)")
fig.tight_layout(); plt.show()'''),
("md", "## Segment summary"),
("code", '''seg = dl.load_table("analytics.rfm_segments", engine)
seg'''),
("code", '''from src.visualization import SEGMENT_COLORS
s = seg.sort_values("customers", ascending=True)
colors = [SEGMENT_COLORS.get(x, "#8a8d91") for x in s["rfm_segment"]]
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].barh(s["rfm_segment"], s["customers"], color=colors)
axes[0].set_title("Customers per segment")
axes[1].barh(s["rfm_segment"], s["total_revenue_brl"]/1e6, color=colors)
axes[1].set_title("Historical revenue per segment (R$ M)")
fig.tight_layout(); plt.show()'''),
("md", """**Reading:** the four one-time-buyer segments hold ~97% of customers.
'High-Value Inactive' is notable — 13.8k customers who each spent ~R$308
on average (about twice the overall AOV) but haven't returned in ~13
months. 'At Risk' and 'Needs Attention' are the small pools of proven
repeat buyers who have gone quiet."""),
("md", "## Recency vs monetary scatter (sample)"),
("code", '''sample = rfm.sample(8000, random_state=42)
fig, ax = plt.subplots(figsize=(9, 5))
for name, grp in sample.groupby("rfm_segment"):
    ax.scatter(grp["recency_days"], grp["monetary_brl"].clip(0, 2000),
               s=6, alpha=0.5, label=name,
               color=SEGMENT_COLORS.get(name))
ax.set_title("Recency vs monetary value by segment")
ax.set_xlabel("recency (days)"); ax.set_ylabel("total spend (R$, clipped)")
ax.legend(markerscale=3, fontsize=8)
plt.show()'''),
("md", """## Conclusion

* Segmentation is heavily skewed to one-time buyers — consistent with the
  3% repeat rate.
* **High-Value Inactive** = biggest historical revenue pool after Recent
  One-Time Buyers (R$4.2M, 27% of revenue) with proven willingness to
  spend — the most defensible re-engagement target.
* Repeat-capable segments (Champions, Loyal, Potential Loyalists,
  Needs Attention, At Risk) are tiny (~3,800 customers combined) but
  already show multi-order behaviour.
* Every segment assignment is validated in sql/09_validation_tests.sql
  (counts reconcile to the customer population, no null segments)."""),
]

# ---------------------------------------------------------------------------
NOTEBOOKS["05_delivery_experience"] = [
("md", """# 05 — Delivery Experience & Satisfaction

**Objective:** test whether late delivery is associated with worse reviews
and lower repeat purchasing.

**Method notes:**
* 'Late' = delivered after `order_estimated_delivery_date`.
* Repeat analysis groups customers by their **first** order's delivery
  experience — otherwise we'd mix cause and effect across orders.
* A windowed variant requires the first order >=180 days before the data
  end, giving every customer comparable follow-up time.
* Results are **associations** — not causal claims."""),
("code", SETUP),
("code", '''from src import delivery_analysis as da
orders = dl.load_orders_enriched(engine)
pd.Series(da.delivery_summary(orders))'''),
("md", """**Baseline:** Olist usually beats its own estimates — average promise
~24 days vs ~12.5 actual. Only ~6.8% of orders arrive late — but when they
do, they're ~10.6 days late on average."""),
("md", "## Review score: late vs on-time"),
("code", '''rev = da.review_by_delivery(orders)
rev'''),
("code", '''dist = dl.load_table("analytics.review_distribution_by_delivery", engine)
fig, ax = plt.subplots(figsize=(9, 4.5))
for outcome, grp in dist.groupby("delivery_outcome"):
    ax.bar(grp["review_score"] + (-0.2 if outcome == "late" else 0.2),
           grp["pct"], width=0.38, label=outcome,
           color=PALETTE["bad"] if outcome == "late" else PALETTE["good"])
ax.set_title("Review-score distribution: late vs on-time delivery")
ax.set_xlabel("review score"); ax.set_ylabel("% of reviewed orders")
ax.legend(); plt.show()'''),
("md", """Striking gap: **62% of late orders score 1-2** (avg 2.27) vs ~9% of
on-time orders (avg 4.29). Delivery experience and satisfaction are
strongly associated in the observational data."""),
("md", "## Repeat purchasing by first-order delivery experience"),
("code", '''rep = da.repeat_by_first_delivery(orders, min_window_days=180)
rep'''),
("md", """Customers whose first order arrived late repeat at ~2.7% (or ~3.1%
with the 180-day window) vs ~3.3% (~4.1% windowed) for on-time first
orders — a consistent direction in both cuts, roughly a **17-24% lower**
relative repeat rate after a bad first delivery."""),
("md", "## Where lateness concentrates"),
("code", '''cat_late = da.late_rate_by(orders, "primary_category", min_orders=500)
cat_late.head(12)'''),
("code", '''state_late = da.late_rate_by(orders, "customer_state", min_orders=100)
state_late.head(12)'''),
("md", """## Conclusion

* Late deliveries are ~7% of orders but punch far above their weight in
  dissatisfaction: avg review 2.27 vs 4.29.
* First-order lateness is associated with a meaningfully lower repeat
  rate in both windowed and unwindowed cuts.
* **Cannot claim causation:** late orders may differ in category mix,
  distance, season (e.g. Black Friday congestion) or seller quality —
  all potential confounders. A fair causal claim needs an experiment or
  matched comparison, documented in docs/limitations.md."""),
]

for name, cells in NOTEBOOKS.items():
    path = NB / f"{name}.ipynb"
    nbf.write(make_nb(cells), path)
    print(f"wrote {path.name}")
