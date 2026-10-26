# E-Commerce Customer Retention & Revenue Intelligence

*An end-to-end customer analytics project using SQL, Python, and Power BI.*

Analysis of ~100k real orders from the [Olist Brazilian E-Commerce Public
Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(Sep-2016 – Oct-2018) answering one question:

> **Why do customers fail to return, which segment should the business
> prioritize for retention, and how are delivery performance and customer
> satisfaction associated with repeat purchasing?**

## Headline results (verified, not estimated)

| Finding | Value |
|---|---|
| Customers with a delivered order | 93,358 |
| One-time customers | 90,557 (**97.0%**) |
| Repeat purchase rate | **3.00%** (2,801 customers) |
| Qualifying revenue | **R$15,419,773.75** (items + freight) |
| Avg order value | R$159.83 (median R$105.28) |
| Cohort month-1 retention | **0.48%** avg (20 observed cohorts) |
| Median time to 2nd order | **29 days** |
| Late delivery rate | **6.77%** of delivered orders |
| Avg review score: late vs on-time | **2.27 vs 4.29** |
| Repeat rate after late vs on-time first order | **2.73% vs 3.30%** (3.09% vs 4.07% on the 180-day-window cut) |

**Recommendation:** prioritize **Recent One-Time Buyers** (36,141
customers, R$5.9M historical revenue, ~91-day avg recency) with a
second-purchase incentive timed to the ~30-day repeat window — with a
service-recovery sub-focus on the ~2.3k of them whose first order
arrived late. Full reasoning and trade-offs:
[docs/business_recommendations.md](docs/business_recommendations.md).

## Tech stack

PostgreSQL 16 (Docker) · SQL (CTEs, window functions, NTILE, validation
suites) · Python 3.13 (pandas, NumPy, Matplotlib, Seaborn, psycopg2,
SQLAlchemy) · Jupyter · pytest (55 tests) · Power BI (model spec, Power
Query M, DAX — see `powerbi/`).

## Repository layout

```
sql/            00 setup · 01 data-quality · 02 staging · 03 customer metrics
                04 cohorts · 05 RFM · 06 delivery · 07 revenue
                08 segment opportunity · 09 validation (16 checks)
src/            config · data_loading · data_validation · customer_metrics
                cohort_analysis · rfm_analysis · delivery_analysis · visualization
scripts/        setup_database.py · run_analysis.py · export_powerbi_data.py
                build_notebooks.py
notebooks/      5 executed notebooks (data understanding, EDA, cohorts, RFM,
                delivery)
tests/          55 pytest tests (unit + live-DB reconciliation)
outputs/        figures/ · summary_tables/ · reports/
powerbi/        README build guide · data_model.md · dax_measures.md ·
                power_query/*.m
docs/           data_dictionary · methodology · kpi_definitions · findings ·
                business_recommendations · limitations · interview_preparation
```

## Reproduce it

```bash
# 1. environment
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # or: pip install -r requirements.txt
cp .env.example .env                                  # set DB_PASSWORD

# 2. database (Docker; native Postgres also fine - adjust .env port)
docker run -d --name olist-postgres -p 5434:5432 \
  -v olist_pgdata:/var/lib/postgresql/data \
  -e POSTGRES_USER=olist -e POSTGRES_PASSWORD=<your-pw> \
  -e POSTGRES_DB=olist_analytics postgres:16-alpine

# 3. download the Olist dataset (Kaggle) into data/raw/ — 9 CSVs
#    (raw data is gitignored; see docs/data_dictionary.md)

# 4. build raw + staging
python scripts/setup_database.py --scripts sql/02_staging_tables.sql

# 5. run the analysis SQL (any client; container example):
for f in sql/03_*.sql sql/04_*.sql sql/05_*.sql sql/06_*.sql \
         sql/07_*.sql sql/08_*.sql sql/09_*.sql; do
  docker exec -i olist-postgres psql -U olist -d olist_analytics < $f
done

# 6. python pipeline: DQ report + reconciliation + tables + figures
python scripts/run_analysis.py

# 7. Power BI exports + tests
python scripts/export_powerbi_data.py
pytest
```

## Analytical approach (short version)

* `customer_unique_id` is the real customer identity; `customer_id` is
  per-order.
* "Qualifying" = delivered orders only for all customer/revenue metrics;
  canceled/unavailable/in-flight orders are excluded per-metric, never
  deleted.
* Revenue = item price + freight (246 orders show payment/item
  mismatches, so payments are a reconciliation column, not revenue).
* Items, payments and reviews are each aggregated to the order grain
  before joining — no one-to-many inflation (verified).
* Cohort month 0 = 100%; incomplete windows flagged, never zero-filled.
* RFM: reference date 2018-10-18; R/M quintiles with deterministic
  tiebreak; F fixed bins; 9 ordered-rule segments; SQL↔pandas agreement
  100%.
* Delivery↔repeat findings are reported as associations, with a
  follow-up-window sensitivity cut; no causal claims.

See [docs/methodology.md](docs/methodology.md) for the full decision log
and [docs/kpi_definitions.md](docs/kpi_definitions.md) for exact
definitions.

## Quality gates

* `sql/01_data_quality_checks.sql` — ~40 checks over raw data
  (keys, orphans, dates, money, reviews, grain)
* `sql/09_validation_tests.sql` — 16 reconciliation checks on analytical
  tables: **16/16 PASS**
* `scripts/run_analysis.py` — SQL vs pandas reconciliation:
  **9/9 PASS** (100% row-level segment agreement)
* `pytest` — **55/55 pass** (unit logic + live-DB integrity)
* `outputs/reports/data_quality_report.md` — rendered DQ report

## Documentation map

| Doc | Content |
|---|---|
| [docs/findings.md](docs/findings.md) | 10 verified findings with populations, artefacts, caveats |
| [docs/business_recommendations.md](docs/business_recommendations.md) | segment prioritisation, scenarios, next steps |
| [docs/methodology.md](docs/methodology.md) | every analytical decision and why |
| [docs/data_dictionary.md](docs/data_dictionary.md) | all tables, grains, columns, quirks |
| [docs/kpi_definitions.md](docs/kpi_definitions.md) | exact KPI formulas and populations |
| [docs/limitations.md](docs/limitations.md) | what this analysis cannot claim |
| [docs/interview_preparation.md](docs/interview_preparation.md) | 50 Q&A to defend the project |
| [powerbi/README.md](powerbi/README.md) | full Power BI build guide + validation values |

## Known limitations

* Data ends Oct-2018 (historical evidence, not current KPIs).
* Repeat rate is within-Olist only; no cross-retailer view.
* All delivery↔retention relationships are observational.
* Power BI `.pbix` is not shipped (Desktop unavailable in this
  environment) — a complete, validated build pack is provided instead.
* Raw dataset is not committed (license + size); download from Kaggle.

## Dataset attribution

Olist Brazilian E-Commerce Public Dataset — published by Olist on Kaggle
under **CC BY-NC-SA 4.0**. Attribution appreciated; non-commercial use
only; share adaptations alike.
