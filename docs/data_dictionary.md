# Data Dictionary

## Source: Olist Brazilian E-Commerce Public Dataset

* Source: [Kaggle — Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
* License: CC BY-NC-SA 4.0 (attribution, non-commercial, share-alike) —
  fine for a portfolio project; raw CSVs are **not** committed to git.
* Coverage: ~100k orders, Sep-2016 to Oct-2018, real anonymised data.

## raw.* — source tables (loaded verbatim)

### raw.customers (99,441 rows)
One row per `customer_id`. **`customer_id` is per-order** — a person who
orders twice gets two different `customer_id`s.

| Column | Type | Notes |
|---|---|---|
| customer_id | text PK | order-level customer record id |
| customer_unique_id | text | **the real customer identity** |
| customer_zip_code_prefix | text | 5-digit zip prefix |
| customer_city / customer_state | text | location |

### raw.orders (99,441 rows)
One row per `order_id`.

| Column | Type | Notes |
|---|---|---|
| order_id | text PK | |
| customer_id | text | -> raw.customers |
| order_status | text | delivered 96,478 / shipped 1,107 / canceled 625 / unavailable 609 / invoiced 314 / processing 301 / created 5 / approved 2 |
| order_purchase_timestamp | ts | 2016-09-04 .. 2018-10-17 |
| order_approved_at | ts | payment approval |
| order_delivered_carrier_date | ts | handover to carrier |
| order_delivered_customer_date | ts | NULL for non-delivered (and 8 delivered) |
| order_estimated_delivery_date | ts | promised date shown at purchase |

### raw.order_items (112,650 rows)
Grain `(order_id, order_item_id)` — one order can hold up to 21 items
(avg 1.14).

| Column | Type | Notes |
|---|---|---|
| order_id, order_item_id | composite PK | item sequence inside the order |
| product_id | text | -> raw.products |
| seller_id | text | -> raw.sellers |
| shipping_limit_date | ts | seller's deadline to ship |
| price | numeric | item price (BRL) |
| freight_value | numeric | shipping charged for the item |

### raw.order_payments (103,886 rows)
Grain `(order_id, payment_sequential)` — up to 29 payment rows per order
(installments/split tender).

| Column | Type | Notes |
|---|---|---|
| payment_sequential | int | sequence of payment attempts/methods |
| payment_type | text | credit_card, boleto, voucher, debit_card |
| payment_installments | int | |
| payment_value | numeric | 9 rows are R$0 |

### raw.order_reviews (99,224 rows)
One row per review record. **review_id is not unique** (789 duplicated
ids; 547 orders have >1 row).

| Column | Type | Notes |
|---|---|---|
| review_id | text | NOT unique in source |
| order_id | text | -> raw.orders |
| review_score | int | 1..5 — dist: 1=11,424, 2=3,151, 3=8,179, 4=19,142, 5=57,328 |
| review_comment_title/message | text | mostly NULL (optional text) |
| review_creation_date, review_answer_timestamp | ts | |

### raw.products (32,951 rows)
| Column | Notes |
|---|---|
| product_id PK | |
| product_category_name | NULL for 610 products; PT names — join translation for English |
| product_name_lenght, product_description_lenght, product_photos_qty | source spellings kept verbatim |
| product_weight_g, product_length_cm, product_height_cm, product_width_cm | |

### raw.sellers (3,095 rows) — seller_id PK + location.
### raw.geolocation (1,000,163 rows) — zip prefix -> lat/lng samples; a zip maps to many points (not used in this analysis).
### raw.category_translation (71 rows) — PT -> EN category names; 13 categories in products lack a translation.

## staging.* — cleaned single-grain tables

| Table | Grain | Built from | Key columns added |
|---|---|---|---|
| staging.orders | order_id | orders+customers | `customer_unique_id`, `purchase_month`, `delivery_days`, `delivery_delay_days`, `is_late_delivery`, `is_qualifying_order` |
| staging.order_items | (order_id, order_item_id) | items+products+translation+sellers | `product_category` (EN, 'unknown' fallback), `item_total_value`, `seller_state` |
| staging.order_payments | order_id | payments aggregated | `payment_total`, `payment_types`, `max_installments` |
| staging.order_reviews | order_id | reviews deduped (latest creation) | `review_score` |
| staging.orders_enriched | order_id | all of the above | `item_count`, `items_value`, `freight_value`, `order_total_value`, `primary_category` |

## analytics.* — business tables

| Table | Grain | Content |
|---|---|---|
| kpi_overview | 1 row | headline business numbers |
| monthly_orders / monthly_revenue | month | orders, customers, revenue, AOV, delivery time |
| customer_metrics | customer_unique_id | order_count, first/last purchase, spend, review avg, late count, `is_repeat_customer`, `days_to_second_order` |
| customer_purchase_frequency | order_count | customers & revenue per order-count |
| cohort_sizes / cohort_retention / cohort_summary | cohort_month [x months_since_first] | acquisition cohorts and retention matrix |
| rfm_customers | customer_unique_id | R/F/M, scores, `rfm_segment` |
| rfm_segments / segment_opportunity / segment_experience | rfm_segment | segment rollups used for prioritisation |
| delivery_summary | 1 row | delivery KPIs |
| review_by_delivery / review_distribution_by_delivery | outcome [x score] | satisfaction vs lateness |
| repeat_by_first_delivery | first-order outcome | repeat rates incl. 180-day-window cut |
| late_by_category / late_by_state | category / state | lateness concentration |
| revenue_by_category / revenue_by_state | category / state | revenue mix |
| order_value_distribution / payment_mix | 1 row / payment_types | AOV percentiles, tender mix |
