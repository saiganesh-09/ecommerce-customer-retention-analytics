# Power BI Report — Build Guide

> **Status:** Power BI Desktop is **not installed** on the machine used to
> build this project, so no `.pbix` file is shipped. Everything needed to
> build the report in ~30-45 minutes is provided here: exported model
> tables, Power Query scripts, the data-model spec, DAX measures, page
> layouts, and validation values. Building it yourself is also excellent
> interview practice.

## What you need

1. Power BI Desktop (free, Microsoft Store or download).
2. The exported CSVs — run `python scripts/export_powerbi_data.py`
   (they land in `data/processed/`).

## Step 1 — Load the data

**Option A (recommended):** File > Get Data > Text/CSV, load each file in
`data/processed/`. Or use the prepared Power Query scripts:

1. Home > Transform data > Power Query Editor.
2. New Parameter `DataFolder` (text) = full path to `data\processed`.
3. For each file in `powerbi/power_query/`: New Source > Blank Query >
   Advanced Editor > paste the script > rename the query.
4. Repeat for the remaining CSVs with plain Get Data > Text/CSV (they are
   flat tables — default settings work; set obvious types).

**Option B:** Get Data > PostgreSQL database > `localhost:5434`,
database `olist_analytics`, and pick the `staging`/`analytics` tables.
(Docker container `olist-postgres` must be running.)

## Step 2 — Model

Follow `powerbi/data_model.md`:

* `fact_orders[customer_unique_id]` *:1 `dim_customers[customer_unique_id]`
* `fact_orders[purchase_date]` *:1 `dim_date[date]`
* Mark `dim_date` as a date table (column `date`).
* All other tables stay **disconnected** supporting tables.
* Create the measures in `powerbi/dax_measures.md` in a `_Measures` table.

## Step 3 — Validate before building visuals

Drop these into a scratch page as cards and compare with the pipeline
output (`outputs/reports/reconciliation.md`):

| Measure | Expected |
|---|---|
| Qualifying Orders | 96,478 |
| Unique Customers | 93,358 |
| Total Revenue (BRL) | 15,419,773.75 |
| Repeat Purchase Rate % | ~3.00 |
| Late Delivery % | ~6.77 |

If these match, the model is correct. If `Total Orders` is much larger
than 99,441, a relationship duplicated rows — fix before continuing.

## Step 4 — Build the four pages

Consistent style: Segoe UI, dark navy `#1F4E79` accents, one accent color
`#E07B39`, white background, 12-16pt titles, numbers formatted with
thousands separators.

### Page 1 — Executive Overview
* **KPI cards (top row):** Unique Customers, Qualifying Orders,
  Repeat Purchase Rate %, Avg Order Value (BRL), Total Revenue (BRL).
* **Line chart:** `dim_date[year_month]` vs Total Revenue + Qualifying
  Orders (dual axis or two charts).
* **Donut or 100% stacked bar:** one-time vs repeat customers
  (from `customer_purchase_frequency` or `dim_customers[is_repeat_customer]`).
* **Bar:** top 10 `revenue_by_category`.
* **Text box:** executive summary — e.g. *"97% of customers order once;
  repeat rate 3.0%; revenue concentrated in SP and recent cohorts."*

### Page 2 — Customer Retention
* **Matrix visual:** rows `cohort_retention[cohort_month]`, columns
  `months_since_first`, values `retention_pct` — conditional-format as a
  color scale (white -> navy). Filter `is_observed = TRUE`.
* **Column chart:** `cohort_sizes[cohort_month]` vs cohort_size.
* **Line chart:** `cohort_summary` avg retention vs months_since_first.
* **Card:** overall repeat rate.
* Slicer: cohort year.

### Page 3 — RFM Segmentation
* **Clustered bar:** customers per `rfm_segment` (`rfm_segments` table).
* **Bar:** `total_revenue_brl` per segment — sorted descending.
* **Scatter or bubble:** `dim_customers` recency vs monetary, legend =
  `rfm_segment` (sample if slow).
* **Table:** `segment_opportunity` — size, avg spend, recency, frequency.
* Slicers: `rfm_segment`, `is_repeat_customer`.

### Page 4 — Delivery & Experience
* **KPI cards:** Late Delivery %, Avg Delivery Days, Avg Review Score.
* **Clustered column:** `review_distribution_by_delivery` — score vs %,
  legend delivery_outcome.
* **Bar:** `review_by_delivery` avg score (late vs on_time).
* **Column:** `repeat_by_first_delivery` repeat rates (both windowed
  columns).
* **Bar / map:** `late_by_state` or `late_by_category` late_pct.
* Slicers: `primary_category`, `customer_state`.

## Screenshots

After building, export page screenshots into `powerbi/screenshots/` and
reference them in the main README (replace the preview PNGs in
`outputs/figures/`). Only claim screenshots that actually exist — the
figures in `outputs/figures/` are the Python equivalents.

## Why not a flat single table?

The order grain (fact_orders) plus a customer dimension keeps every join
1:* and prevents the classic beginner error of joining items + payments +
reviews into one wide table where totals silently double. This design
mirrors what a BI engineer would ship.
