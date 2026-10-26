# Methodology

How the analysis is built, and why each decision was made.

## Architecture

```
raw.*            -- CSVs loaded verbatim (TEXT-correct types, no transforms)
staging.*        -- cleaned, typed, single-grain tables
analytics.*      -- business tables: KPIs, customer metrics, cohorts,
                    RFM, delivery, segment opportunity
Python (src/)    -- independent re-implementation used for reconciliation
Notebooks        -- narrative layer over the same tables
Power BI         -- consumes analytics.* / exported CSVs
```

Two implementations (SQL and pandas) compute the same numbers;
`scripts/run_analysis.py` asserts they agree (see
`outputs/reports/reconciliation.md` — currently 9/9 checks PASS,
including 100% row-level segment agreement).

## Core decisions

### 1. Customer identity = `customer_unique_id`

`customer_id` is generated per order (each order gets a new customers row).
`customer_unique_id` is the stable person identity. Using `customer_id`
for retention would report a 0% repeat rate — a classic trap in this
dataset.

### 2. "Qualifying" = delivered orders

For any metric involving money or customer value we use only
`order_status = 'delivered'`:

* canceled (625) and unavailable (609) orders are not fulfilled purchases;
* created / approved / processing / invoiced / shipped (1,729, ~1.7%)
  cannot be confirmed as completed inside the data window.

Order-level KPIs (status mix) still count all orders — the exclusion is
documented per metric rather than silently deleting rows.

### 3. Revenue = items + freight, not payments

`order_total_value = SUM(price) + SUM(freight_value)` per order.

Why not `payment_total`? 246 delivered orders show a payment/items
mismatch >R$1 (vouchers, partial refunds, data quirks), 9 payment rows
are R$0 and 1 order has no payment rows at all. Item values are complete
for every order and are the cleaner revenue proxy. `payment_total` is
kept in the fact table for reconciliation only.

### 4. Grain discipline

Joins happen only between tables pre-aggregated to the same grain:

* `orders_enriched` (order grain) is built from `staging.orders` +
  items-aggregated-to-order + payments-aggregated-to-order + one-review-
  per-order. One-to-many joins can therefore never inflate totals —
  verified by test `order_total = items + freight` on all 99,441 rows.
* `customer_metrics` (customer grain) aggregates `orders_enriched`.
* `cohort_retention` is computed from distinct (customer, month) pairs.

### 5. Reviews: one row per order

The source has 789 duplicated `review_id`s and 547 orders with multiple
review rows. Staging keeps the row with the latest
`review_creation_date` (tie-break `review_id`). This is a documented
simplification — alternative choices (e.g. averaging scores) move the
numbers by <0.01 given only ~0.5% of orders are affected.

### 6. Cohort analysis

* Cohort = month of first **observed** qualifying purchase. We explicitly
  do **not** claim it is the customer's first-ever purchase.
* Month 0 = acquisition month (100% by construction, shown for
  completeness).
* Months beyond the observed data window are flagged `is_observed=FALSE`
  and excluded from headline claims — never zero-filled. A cohort with
  no activity in a month it *could* have shown activity in still produces
  a row with the true (possibly 0) value; a cohort whose window is
  truncated produces no claim at all.

### 7. RFM scoring

* **Reference date** = `2018-10-18` (day after the last qualifying
  purchase). Measuring recency against "today" would make every customer
  look ~7+ years inactive.
* **R and M**: quintiles via `NTILE(5)` with a deterministic tie-break on
  `customer_unique_id` (larger buckets first — replicated exactly in
  pandas; verified to 100% agreement).
* **F**: fixed bins 1,2,3,4,5+ — with ~97% of customers at frequency 1, a
  quintile on frequency is meaningless.
* Segments are assigned by an **ordered rule list** (first match wins):

| Order | Rule | Segment |
|---|---|---|
| 1 | R>=4, F>=3, M>=4 | Champions |
| 2 | F>=3, R>=3 | Loyal Customers |
| 3 | F>=2, R<=2 | At Risk |
| 4 | F=2, R>=4 | Potential Loyalists |
| 5 | F>=2, R=3 | Needs Attention |
| 6 | F=1, M>=4, R<=2 | High-Value Inactive |
| 7 | F=1, R>=4 | Recent One-Time Buyers |
| 8 | F=1, R=3 | Other One-Time Buyers |
| 9 | F=1, R<=2 | Inactive One-Time Buyers |

Every eligible customer lands in exactly one segment (validated).

### 8. Delivery vs repeat-purchase comparison

Customers are grouped by the delivery experience of their **first**
qualifying order. Grouping by *any* order would let later orders contaminate
the exposure (a customer could have an on-time first order and a late third).
We report two cuts:

* all classifiable first orders;
* a **windowed** cut requiring the first order >=180 days before the data
  end, so every customer had comparable time to return.

Even so this is an **association**, not causation — confounders (category,
distance, season, seller) are discussed in `docs/limitations.md`.

## Reproducibility

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
docker run -d --name olist-postgres -p 5434:5432 -v olist_pgdata:/var/lib/postgresql/data \
  -e POSTGRES_USER=olist -e POSTGRES_PASSWORD=<pw> -e POSTGRES_DB=olist_analytics \
  postgres:16-alpine
python scripts/setup_database.py --scripts sql/02_staging_tables.sql
# run sql/03..09 in order (psql or any client)
python scripts/run_analysis.py          # DQ report, reconciliation, tables, figures
python scripts/export_powerbi_data.py   # Power BI CSV exports
pytest                                  # 55 tests
```
