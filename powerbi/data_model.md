# Power BI Data Model

Star schema for the Olist retention report. Two fact-style tables at
different grains plus supporting dimension and precomputed analysis tables.

## Diagram

```
                    dim_date
                   (date PK)
                        |
                        | 1:*  (single direction: dim_date -> fact_orders)
                        |
dim_customers -----> fact_orders
(customer_unique_id     (order_id PK)
 PK) 1:*
```

Supporting tables (disconnected, used by dedicated pages):

* `cohort_retention` — long-format retention matrix (cohort_month x months_since_first)
* `cohort_sizes` — customers acquired per cohort month
* `rfm_segments` — segment rollup for the RFM page
* `segment_opportunity` — prioritisation metrics per segment
* `delivery_summary`, `review_by_delivery`, `repeat_by_first_delivery`,
  `review_distribution_by_delivery`, `late_by_category`, `late_by_state` —
  delivery page tables
* `monthly_orders` / `monthly_revenue` — trend tables (or compute from fact)
* `revenue_by_category`, `revenue_by_state`, `customer_purchase_frequency`,
  `payment_mix`, `kpi_overview`, `order_value_distribution` — supporting tables

## Table grains and keys

| Table | Grain | Key | Relationship |
|---|---|---|---|
| fact_orders | one row per **order_id** (99,441) | order_id | dim_customers 1:* on customer_unique_id; dim_date 1:* on purchase_date |
| dim_customers | one row per **customer_unique_id** (93,358) | customer_unique_id | 1:* to fact_orders |
| dim_date | one row per calendar day | date | 1:* to fact_orders[purchase_date] |
| cohort_retention | cohort_month x months_since_first | composite | none (page-level table) |
| rfm_segments | one row per segment | rfm_segment | none |
| delivery/analysis tables | varies | varies | none |

## Important modelling decisions

1. **Order grain is preserved.** `fact_orders` never joins items and
   payments simultaneously at row level — both were pre-aggregated to the
   order grain in SQL, so totals cannot double-count.
2. **Revenue measure = `order_total_value`** (item price + freight) and is
   only meaningful for `is_qualifying_order = TRUE`. `payment_total` is a
   separate reconciliation column — do NOT sum it as revenue.
3. **Customer identity = `customer_unique_id`** everywhere.
   `dim_customers` contains only the 93,358 customers with >=1 delivered
   order; the ~2,700 customers seen only on non-delivered orders exist in
   `fact_orders` but not in `dim_customers` (blank segment is expected).
4. **Single-direction filters.** Keep dim -> fact direction one-way.
5. `dim_date` spans 2016-09-01..2018-10-31 and is marked as a Date table.
6. The cohort table is **precomputed** (long format) — Power BI is the
   visualisation layer, not the calculation layer, for retention. The
   `is_observed` flag must be respected to avoid reading incomplete
   windows as zero retention.
