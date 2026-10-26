# Agent notes — how to work on this project

## Environment
- Windows + Git Bash. Python venv at `.venv/` (use
  `.venv/Scripts/python.exe`). pandas 3.x — avoid deprecated APIs.
- PostgreSQL 16 runs in Docker container `olist-postgres` on
  **localhost:5434** (ports 5432/5433 belong to other projects — do not
  touch them). DB/user = `olist` / `olist_analytics`.
- Run SQL files via:
  `docker exec -i olist-postgres psql -U olist -d olist_analytics < sql/XX.sql`

## Commands
- Rebuild DB: `python scripts/setup_database.py --scripts sql/02_staging_tables.sql`
- Analysis SQL: run `sql/03`→`sql/09` in order (03→04/05, 05→08, 09 last)
- Python pipeline: `python scripts/run_analysis.py`
- Power BI exports: `python scripts/export_powerbi_data.py`
- Tests: `pytest` (55 tests; DB tests skip if postgres is down)
- Rebuild notebooks: `python scripts/build_notebooks.py` then
  `python -m nbconvert --to notebook --execute --inplace notebooks/0*.ipynb`

## Conventions
- Customer identity = `customer_unique_id` (never `customer_id`).
- Qualifying order = `order_status = 'delivered'`.
- Revenue = items + freight (`order_total_value`), not `payment_total`.
- Aggregate to the order grain before joining; never join two 1:N tables
  raw then sum.
- Cohort windows beyond the data range are `is_observed=FALSE`, never 0.
- NTILE tie-break on `customer_unique_id` — must stay identical in SQL
  and pandas (checked by reconciliation).
- Raw data lives in `data/raw/` and is gitignored; never commit CSVs or
  `.env`.
