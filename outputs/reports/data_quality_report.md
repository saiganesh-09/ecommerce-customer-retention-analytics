# Data Quality Report

Checks executed by `src/data_validation.py` against `raw.*` and `staging.*`. Severity: INFO = fact, WARN = handled quirk, FAIL(0) = hard invariant that must equal zero.

| Area | Check | Severity | Result |
|---|---|---|---|
| row_counts | raw.category_translation | INFO | 71 rows |
| row_counts | raw.sellers | INFO | 3,095 rows |
| row_counts | raw.products | INFO | 32,951 rows |
| row_counts | raw.order_payments | INFO | 103,886 rows |
| row_counts | raw.customers | INFO | 99,441 rows |
| row_counts | raw.orders | INFO | 99,441 rows |
| row_counts | raw.order_items | INFO | 112,650 rows |
| row_counts | raw.order_reviews | INFO | 99,224 rows |
| row_counts | raw.geolocation | INFO | 1,000,163 rows |
| referential | orders -> customers orphans | FAIL(0) | 0 |
| referential | order_items -> orders orphans | FAIL(0) | 0 |
| referential | order_payments -> orders orphans | FAIL(0) | 0 |
| referential | order_reviews -> orders orphans | FAIL(0) | 0 |
| referential | order_items -> sellers orphans | FAIL(0) | 0 |
| dates | delivered before carrier handover | WARN | 23 |
| dates | status=delivered but no delivery timestamp | WARN | 8 |
| dates | non-delivered status with delivery timestamp | WARN | 6 |
| reviews | duplicate review_ids | WARN | 789 |
| reviews | orders with >1 review row | WARN | 547 |
| money | zero-value payment rows | WARN | 9 |
| money | delivered orders where payments != items+freight (>R$1) | WARN | 246 |
