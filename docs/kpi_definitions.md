# KPI Definitions

Every KPI below names its analytical population, formula and where it is
computed. The same definitions apply in SQL, Python and Power BI.

## Scope rules used throughout

| Term | Meaning |
|---|---|
| **Qualifying order** | `order_status = 'delivered'`. Used for revenue, AOV, customer metrics, cohorts, RFM. |
| **Customer** | `customer_unique_id` (the permanent person identity). `customer_id` is per-order and is never used for customer metrics. |
| **Revenue (order_total_value)** | `SUM(price) + SUM(freight_value)` per order from `order_items`. Chosen over `payment_total` because 246 delivered orders show a payment/items mismatch >R$1, and payments exclude canceled orders cleanly anyway. |
| **Late delivery** | `delivered_date > estimated_delivery_date`, computable only when both timestamps exist. |
| **Reference date (RFM)** | `max(qualifying purchase_date) + 1 = 2018-10-18`. |

## KPI catalogue

| KPI | Definition | Population | Source |
|---|---|---|---|
| Total orders | `COUNT(order_id)` | all orders | `analytics.kpi_overview` |
| Delivered orders | count where `is_qualifying_order` | delivered | `analytics.kpi_overview` |
| Unique customers | `COUNT(DISTINCT customer_unique_id)` | all orders | `analytics.kpi_overview` |
| Customers with delivered order | distinct customers having >=1 qualifying order | qualifying | `analytics.kpi_overview` |
| Total revenue | `SUM(order_total_value)` | qualifying orders | `analytics.kpi_overview` |
| Average order value (AOV) | `AVG(order_total_value)` | qualifying orders | `analytics.kpi_overview` |
| One-time customers | customers with `order_count = 1` | qualifying customers | `analytics.customer_metrics` |
| Repeat customers | customers with `order_count > 1` | qualifying customers | `analytics.customer_metrics` |
| Repeat purchase rate | `repeat_customers / customers_with_delivered_order` | qualifying customers | `analytics.customer_metrics` |
| Days to second order | `second_purchase_date - first_purchase_date` | repeat customers | `analytics.customer_metrics` |
| Cohort size | distinct customers whose first qualifying order falls in the cohort month | qualifying customers | `analytics.cohort_sizes` |
| Retention (month N) | `DISTINCT customers active in month cohort+N / cohort_size` | observed windows only | `analytics.cohort_retention` |
| Recency (R) | `reference_date - last qualifying purchase_date` (days) | qualifying customers | `analytics.rfm_customers` |
| Frequency (F) | count of qualifying orders | qualifying customers | `analytics.rfm_customers` |
| Monetary (M) | `SUM(order_total_value)` | qualifying customers | `analytics.rfm_customers` |
| Delivery days | `delivered_date - purchase_date` | delivered w/ timestamps | `staging.orders_enriched` |
| Delivery delay | `delivered_date - estimated_delivery_date` | delivered w/ timestamps | `staging.orders_enriched` |
| Late delivery % | `late orders / delivered orders with timestamps` | delivered w/ timestamps | `analytics.delivery_summary` |
| Avg review score | `AVG(review_score)` | orders with a review | `analytics.review_by_delivery` |
| Repeat rate by first delivery | customers with >1 qualifying order, grouped by first order's late flag | customers whose first order has timestamps | `analytics.repeat_by_first_delivery` |

## Deliberate exclusions

| Excluded from | Population | Why |
|---|---|---|
| All customer/revenue metrics | canceled (625) + unavailable (609) orders | no fulfilled purchase, no revenue |
| All customer/revenue metrics | created/approved/processing/invoiced/shipped (1,729) | lifecycle outcome not confirmable inside the data window |
| Delivery-duration metrics | 8 delivered orders missing `delivered_ts` | duration unknown |
| Repeat-by-delivery comparison | first orders without both delivery timestamps | experience can't be classified |
| Review metrics | orders without a review row | score unknown (not assumed neutral) |
