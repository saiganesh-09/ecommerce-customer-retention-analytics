# Verified Findings

Every number below was produced by the executed pipeline (PostgreSQL 16 +
pandas), not estimated. SQL and Python implementations agree on all
reconciliation checks (`outputs/reports/reconciliation.md`, 9/9 PASS).
Population = 99,441 orders / 96,478 delivered / 93,358 customers with a
delivered order, Sep-2016 to Oct-2018, unless stated otherwise.

## F1 — ~97% of customers buy exactly once

* **Question:** what share of customers place only one order?
* **Result:** 90,557 of 93,358 qualifying customers are one-time buyers;
  repeat purchase rate = **3.00%** (2,801 customers).
* **Artefacts:** `analytics.customer_metrics`,
  `analytics.customer_purchase_frequency`, `sql/03_customer_metrics.sql`
* **Meaning:** Olist behaves like a single-purchase marketplace. The
  retention problem is not "stopping churn" — it is converting the first
  order into a second.
* **Limitation:** first purchase is only the first *observed* one; a
  customer's true order history before Sep-2016 is unknown.

## F2 — Revenue baseline

* **Result:** R$15,419,773.75 total qualifying revenue; AOV R$159.83;
  median order R$105.28 (p90 R$305.92). Median customer lifetime spend
  R$107.78.
* **Artefacts:** `analytics.kpi_overview`,
  `analytics.order_value_distribution`
* Revenue = item price + freight (see methodology — not `payment_total`).

## F3 — Growth pattern

* **Result:** strong growth through 2017, peak around Nov-2017
  (~R$1.1M/month, Black Friday), then a plateau at ~R$1M/month through
  2018; final months truncated by the data window.
* **Artefacts:** `analytics.monthly_orders`, figure
  `monthly_orders_revenue.png`

## F4 — Cohort retention is flat near zero

* **Question:** how does retention change across monthly cohorts?
* **Result:** month-1 retention averages **0.48%** across the 20 observed
  cohorts; month-2 0.34%; month-6 0.23%. No cohort shows a strengthening
  return curve.
* **Artefacts:** `analytics.cohort_retention`,
  `analytics.cohort_summary`, `cohort_retention_heatmap.png`
* **Meaning:** customers do not "warm up" over time — whoever comes back
  does so early and rarely.

## F5 — When customers do return, they return fast

* **Question:** how long to a second order?
* **Result:** median **29 days**, mean 81.2 days (right-skewed) between
  first and second delivered order among repeat customers.
* **Meaning:** the post-purchase window (~first 1-3 months) is the
  highest-leverage time for a second-purchase prompt.

## F6 — Late delivery strongly coincides with bad reviews

* **Question:** are late deliveries associated with lower scores?
* **Result:** 6.77% of delivered orders arrive late (avg 10.6 days late
  when late; typical promise ~24 days vs ~12.5 actual). Late orders
  average **2.27** review score and 62.4% score <=2; on-time orders
  average **4.29** with 9.3% <=2.
* **Artefacts:** `analytics.delivery_summary`,
  `analytics.review_by_delivery`, `review_score_by_delivery.png`
* **Caveat:** association, not causation (confounders in
  `docs/limitations.md`).

## F7 — Late first delivery is associated with lower repeat purchasing

* **Question:** do customers with a late first order return less?
* **Result:** repeat rate **2.73%** after a late first order vs **3.30%**
  after on-time (relative gap ~17%). On the fair-window cut (first order
  >=180 days before data end): **3.09% vs 4.07%** (~24% relative gap).
  Direction is consistent in both cuts.
* **Artefacts:** `analytics.repeat_by_first_delivery`,
  `repeat_rate_by_first_delivery.png`
* **Caveat:** observational; late-exposed customers may differ
  systematically.

## F8 — Value concentrates in a few segments

* **Result:** "Recent One-Time Buyers" = 36,141 customers (38.7%),
  R$5.94M historical revenue (38.5%), avg recency 91 days. "High-Value
  Inactive" = 13,782 customers, R$4.24M (27.5%), avg spend R$307.86,
  avg recency 395 days. All proven repeat segments (Champions, Loyal,
  Potential Loyalists, Needs Attention, At Risk) total only 2,801
  customers (3.0%).
* **Artefacts:** `analytics.rfm_segments`, `rfm_segments.png`

## F9 — Lateness is geographically concentrated

* **Result:** highest late-delivery rates in North/North-East states —
  AL 21.4%, MA 17.4%, SE 15.2%, PI 13.9%, CE 13.8% — vs a national 6.8%.
  Highest-late categories: audio 11.9%, home comfort 9.9%, baby 8.2%.
* **Artefacts:** `analytics.late_by_state`, `analytics.late_by_category`
* **Meaning:** late delivery is partly a logistics-network problem
  (long distances from SP-based sellers), which matters for interpreting
  F7 — region confounds experience.

## F10 — Revenue mix

* **Result:** SP state = 37.4% of revenue (RJ 13.3%, MG 11.8%). Top
  categories: health_beauty R$1.41M, watches_gifts R$1.26M,
  bed_bath_table R$1.23M. Credit card = 74.8% of orders, boleto 19.9%.
* **Artefacts:** `analytics.revenue_by_state`,
  `analytics.revenue_by_category`, `analytics.payment_mix`

## What the data cannot answer

* Whether retention interventions *cause* returns (needs an experiment).
* True customer lifetime value (no post-2018 data, no cost data).
* Why customers don't return (no qualitative data).
* Campaign profitability (no margin or marketing-cost data — see
  `docs/business_recommendations.md` for what would be needed).
