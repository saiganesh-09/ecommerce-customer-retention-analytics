# DAX Measures

Create these as **measures** (suggested table: `_Measures`). Every measure
names its source columns exactly as exported by
`scripts/export_powerbi_data.py`.

## Base measures (fact_orders)

```dax
Total Orders = COUNTROWS(fact_orders)

Qualifying Orders =
CALCULATE([Total Orders], fact_orders[is_qualifying_order] = TRUE())

Unique Customers =
CALCULATE(
    DISTINCTCOUNT(fact_orders[customer_unique_id]),
    fact_orders[is_qualifying_order] = TRUE()
)

Total Revenue (BRL) =
CALCULATE(
    SUM(fact_orders[order_total_value]),
    fact_orders[is_qualifying_order] = TRUE()
)

Avg Order Value (BRL) =
DIVIDE([Total Revenue (BRL)], [Qualifying Orders])
```

## Customer measures (dim_customers)

```dax
Customers = COUNTROWS(dim_customers)

Repeat Customers =
CALCULATE([Customers], dim_customers[is_repeat_customer] = TRUE())

Repeat Purchase Rate % =
DIVIDE([Repeat Customers], [Customers]) * 100

Avg Customer Spend (BRL) = AVERAGE(dim_customers[monetary_brl])

Avg Recency (days) = AVERAGE(dim_customers[recency_days])
```

## Delivery measures (fact_orders)

```dax
Delivered Orders With Timestamps =
CALCULATE(
    [Total Orders],
    fact_orders[order_status] = "delivered",
    NOT ISBLANK(fact_orders[delivered_date]),
    NOT ISBLANK(fact_orders[estimated_delivery_date])
)

Late Orders =
CALCULATE([Total Orders], fact_orders[is_late_delivery] = TRUE())

Late Delivery % =
DIVIDE([Late Orders], [Delivered Orders With Timestamps]) * 100

Avg Delivery Days =
CALCULATE(
    AVERAGE(fact_orders[delivery_days]),
    fact_orders[order_status] = "delivered",
    NOT ISBLANK(fact_orders[delivery_days])
)

Avg Review Score =
CALCULATE(
    AVERAGE(fact_orders[review_score]),
    fact_orders[order_status] = "delivered"
)
```

## Cohort page (cohort_retention table)

The matrix is precomputed — visualise `retention_pct` in a matrix visual
with `cohort_month` on rows and `months_since_first` on columns, filtered
to `is_observed = TRUE`.

```dax
Cohort Size =
SUMX(
    VALUES(cohort_retention[cohort_month]),
    CALCULATE(MAX(cohort_retention[cohort_size]))
)

Retention % (observed) =
CALCULATE(
    AVERAGE(cohort_retention[retention_pct]),
    cohort_retention[is_observed] = TRUE()
)
```

## Design notes

* `DIVIDE` is used everywhere so empty denominators return BLANK, never
  an error.
* All revenue/AOV measures are pinned to `is_qualifying_order = TRUE`
  (delivered orders only) — the same rule the SQL pipeline applies.
* A measure on a *precomputed* table (e.g. `Retention %`) averages an
  already-computed percentage; it is a display convenience, not a
  re-derivation.
* Validation: `Qualifying Orders` must equal 96,478, `Unique Customers`
  93,358, `Total Revenue (BRL)` 15,419,773.75, `Late Delivery %` ~6.77.
  Check these against `outputs/reports/reconciliation.md` after loading.
