# SQL scripts

Run order (each file is idempotent — `DROP TABLE IF EXISTS` + `CREATE`):

| File | Purpose | Outputs |
|---|---|---|
| `00_database_setup.sql` | schemas `raw`/`staging`/`analytics` + raw landing tables | raw.* |
| `01_data_quality_checks.sql` | ~40 DQ checks, printed as a report | report only |
| `02_staging_tables.sql` | cleaned typed tables, order-grain fact | staging.* |
| `03_customer_metrics.sql` | headline KPIs + customer-level metrics | analytics.kpi_overview, monthly_orders, customer_metrics, customer_purchase_frequency |
| `04_cohort_retention.sql` | acquisition-cohort retention matrix | analytics.cohort_retention, cohort_sizes, cohort_summary |
| `05_rfm_segmentation.sql` | RFM scores + 9 segments | analytics.rfm_customers, rfm_segments |
| `06_delivery_analysis.sql` | delivery performance vs reviews & repeat rate | analytics.delivery_summary, review_by_delivery, repeat_by_first_delivery, late_by_* |
| `07_revenue_analysis.sql` | revenue mix: category, state, AOV, payments | analytics.revenue_by_*, order_value_distribution, payment_mix |
| `08_business_recommendations.sql` | segment prioritisation inputs | analytics.segment_opportunity, segment_experience |
| `09_validation_tests.sql` | 16 reconciliation/invariant checks | PASS/FAIL report |

Executing with the Docker container:

```bash
docker exec -i olist-postgres psql -U olist -d olist_analytics < sql/03_customer_metrics.sql
```

Scripts 03–08 must run in order (03 before 04/05; 05 before 08;
09 last). `scripts/setup_database.py --scripts sql/02_staging_tables.sql`
chains the staging step to the raw load.
