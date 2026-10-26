# Interview Preparation

Everything you need to explain and defend this project in a Data Analyst
interview, in plain English. Project-specific answers use the real
numbers from the executed analysis; general questions are marked as such.

---

## A. Business understanding

**Q1. What problem does this project solve?**
Olist is a marketplace where 97% of customers buy exactly once. The
project answers: why don't customers return, which segment should be
targeted first for retention, and whether delivery experience is
associated with repeat purchasing.

**Q2. Why does customer retention matter commercially?**
Acquiring a new customer usually costs far more than getting an existing
one to buy again, and repeat customers carry no acquisition cost on the
second order. Even a small absolute lift on a large base of one-time
buyers outweighs effort spent on a tiny group of loyal customers.

**Q3. Why this dataset?**
It is real (not synthetic), large enough (~100k orders, ~93k customers)
to be credible, messy enough to demonstrate real data-quality work
(duplicate reviews, timestamp gaps, payment mismatches), and it contains
the full order lifecycle — purchase, payment, delivery, review — which
enables retention, RFM and experience analysis in one place.

**Q4. What is the single headline finding?**
Repeat purchase rate is 3.0% — but late first deliveries depress it
further (2.5% vs 3.0%, or 3.0% vs 4.0% on the fair-window cut) and late
orders average a 2.27 review score vs 4.29 on-time. The recommended
target is the 36k "Recent One-Time Buyers" segment.

**Q5. What would you do with more data?**
Margin/cost data (to move from revenue to profit), marketing-touch data
(to measure campaign lift), and post-2018 data (to validate that
patterns persist).

---

## B. SQL

**Q6. Why `customer_unique_id` instead of `customer_id`?**
In this dataset `customer_id` is generated per order — every order gets
a new one. `customer_unique_id` is the person's stable identity. Using
`customer_id` for retention would wrongly show a 0% repeat rate. This is
the dataset's biggest trap.

**Q7. How do you avoid double counting when joining items and payments?**
Never join two one-to-many tables at once and then sum. I aggregate each
to the order grain first (`SUM` per order_id for items, and separately
for payments), then join those single-row-per-order results to orders.
Verification: `order_total_value = items_value + freight_value` holds on
all 99,441 rows — it's an enforced test.

**Q8. What is a CTE and where did you use them?**
Common Table Expression — a named subquery (`WITH x AS (...)`) that
makes layered logic readable. Used everywhere: first orders, activity,
cohort sizes, RFM scoring, segment assignment — e.g.
`sql/04_cohort_retention.sql` chains 4 CTEs.

**Q9. Where did you use window functions?**
`ROW_NUMBER() OVER (PARTITION BY customer ORDER BY purchase_ts)` to find
each customer's 2nd order; `ROW_NUMBER` again to keep one review per
order; `NTILE(5)` for R and M quintile scores; `SUM() OVER ()` for
percentage-of-total columns; `SUM() OVER (ORDER BY month)` for
cumulative revenue.

**Q10. What does `NTILE(5)` do, and why not use it for Frequency?**
It splits ordered rows into 5 equal groups (bucket 1..5). Frequency is
~97% the value 1 — quintiles would slice identical customers into
arbitrary buckets, so F uses fixed bins (1,2,3,4,5+).

**Q11. How did you compute cohort retention?**
First find each customer's first qualifying purchase month (cohort);
list the distinct months they purchased afterward; compute
`months_since_first`; then `DISTINCT customers active / cohort_size`.
Month 0 is the acquisition month = 100%.

**Q12. How do you handle incomplete cohorts?**
Each cohort-month is flagged `is_observed` — whether that calendar month
exists inside the data window. Unobserved months are excluded from
summaries, never filled with zero. A month a cohort could have been
active in but wasn't is a real observation (counts as 0 activity).

**Q13. Explain `LEFT JOIN ... WHERE right.key IS NULL`.**
Anti-join pattern for finding orphans — e.g. order items whose order_id
doesn't exist in orders. Result in this dataset: zero orphans on all
checked keys.

**Q14. INNER vs LEFT JOIN — when did each matter?**
INNER when both sides must exist (orders -> customers, enforced by data).
LEFT when preserving the left side: orders -> reviews (not every order
has a review — INNER would drop valid orders), orders -> payments.

**Q15. What does `DISTINCT ON` do (Postgres)?**
Keeps the first row per group per the ORDER BY — used to pick each
order's primary category (the category of its highest-value item).

**Q16. What is `FILTER (WHERE ...)` vs CASE inside aggregates?**
`COUNT(*) FILTER (WHERE condition)` counts only matching rows —
cleaner than `SUM(CASE WHEN cond THEN 1 ELSE 0 END)`. Same result; FILTER
is more readable and standard in Postgres.

**Q17. How would you find customers whose 2nd order is within 30 days of
the 1st?** *(scenario)*
```sql
WITH o AS (
  SELECT customer_unique_id, purchase_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_unique_id
                            ORDER BY purchase_ts) rn
  FROM staging.orders_enriched WHERE is_qualifying_order)
SELECT a.customer_unique_id
FROM o a JOIN o b ON a.customer_unique_id = b.customer_unique_id
                AND b.rn = 2
WHERE a.rn = 1 AND b.purchase_ts::date - a.purchase_ts::date <= 30;
```

**Q18. Why not just `DELETE` bad rows in raw?**
Raw is preserved so issues stay inspectable and reproducible. Cleaning
happens in staging with documented rules — e.g. 8 delivered orders keep
their NULL delivery timestamp, they're just excluded from duration
metrics.

**Q19. What indexes did you create and why?**
Primary-key lookups (`order_id`, `customer_unique_id`, cohort columns)
because validation joins and Power BI filtering hit them constantly.
Indexes don't change results — only speed.

**Q20. How do you compute "average days between first and second order"?**
`AVG(second_purchase_date - first_purchase_date)` over customers who
have a second order — median preferred (29d) because the distribution is
right-skewed (mean 81d pulled by outliers).

---

## C. Python / pandas

**Q21. How is the Python layer organised?**
`src/` has one module per concern: `config` (connections), `data_loading`
(SQL -> DataFrame), `data_validation`, `customer_metrics`,
`cohort_analysis`, `rfm_analysis`, `delivery_analysis`, `visualization`.
`scripts/run_analysis.py` orchestrates everything and reconciles outputs
against the SQL tables.

**Q22. What is the difference between `groupby().size()` and
`groupby().count()`?** *(general)*
`size()` counts rows per group including NaNs; `count()` counts non-null
values per column. For row counts I use `size()` or `nunique()`.

**Q23. How did you deduplicate reviews in pandas terms?**
The SQL does it with ROW_NUMBER; the pandas equivalent is
`sort_values('review_creation_date').drop_duplicates('order_id',
keep='last')` — though in this project the canonical dedup lives in SQL.

**Q24. How do you handle dates in pandas?**
Parse with `pd.to_datetime`, use `.dt` accessors (`dt.month`,
`dt.normalize`, `dt.days`), `dt.to_period('M')` for month buckets, and
`Timedelta` for windows like the 180-day follow-up filter.

**Q25. Why compute everything twice (SQL and pandas)?**
Two independent implementations are the cheapest correctness check: if
SQL and pandas agree to the cent on revenue and 100% on segment
assignment, the logic is almost certainly right. The reconciliation
report is generated automatically.

**Q26. What bug did the test suite actually catch?**
`GroupBy.nth(1)` keeps the original DataFrame index, not the group key —
so joining the "second purchase" series produced NaT for everyone. A
test asserting `days_to_second_order` failed, and the fix used a sorted
`cumcount` filter instead.

**Q27. `apply` vs vectorised operations?**
Vectorised ops run in C and are far faster; `apply` is a Python loop
used only where logic doesn't vectorise cleanly (segment assignment was
vectorised to `assign_segment` via a list comprehension for clarity at
93k rows — still fast enough).

**Q28. How do you make NTILE in pandas match PostgreSQL?**
Sort by (value, tiebreak key), take positions 1..N, then map positions
to bucket boundaries — remainder rows go to the *first* buckets exactly
like Postgres. Using `qcut` directly fails because it can't split tied
values and NTILE can.

---

## D. Power BI

**Q29. Describe the data model.**
A small star: `fact_orders` (order grain, 99k rows) at the centre;
`dim_customers` (one row per customer_unique_id, with RFM fields) and
`dim_date` filtering it 1:*; plus disconnected precomputed analysis
tables (cohort matrix, segment summaries, delivery tables).

**Q30. Why a star schema instead of one big flat table?**
One row per order prevents fan-out double counting; dimensions make
slicers cheap; measures stay simple. A flat items+payments+reviews table
would inflate revenue by the join multiplication.

**Q31. Measures vs calculated columns?**
Calculated columns are stored per-row and evaluated at refresh (e.g. a
flag). Measures evaluate at query time against the filter context — all
KPIs here are measures so slicers work correctly.

**Q32. What is filter context?** *(general)*
The set of filters applied by visuals, slicers, and relationships when a
measure is evaluated. E.g. `Late Delivery %` recomputes per state
because the state's rows are the filter context.

**Q33. Why `DIVIDE` instead of `/`?**
`DIVIDE` returns BLANK on zero denominators instead of an error — the
right behaviour when a slicer empties a segment.

**Q34. How is the cohort heatmap done in Power BI?**
The retention matrix is precomputed (cohort_month x months_since_first
with `retention_pct` and `is_observed`). In Power BI it's a matrix
visual + conditional color scale — computing retention natively in DAX
would be fragile and hard to audit.

**Q35. How do you validate a dashboard?**
KPI cards are compared against independently computed values:
Qualifying Orders = 96,478, customers = 93,358, revenue =
R$15,419,773.75, late % = 6.77. If the report disagrees with the
pipeline, the model is wrong — not the other way round.

---

## E. Business analytics

**Q36. What is a repeat purchase rate and how is it defined here?**
Share of customers with a delivered order who placed >1 delivered order:
2,801 / 93,358 = 3.00%. Denominator = customers with at least one
qualifying order, not all people seen in the data.

**Q37. What is RFM and what are its limitations?**
Scores customers on Recency, Frequency, Monetary. Limitations:
descriptive not predictive; quintile boundaries are conventions; ignores
why customers bought; here it mostly segments one-time buyers because
frequency barely varies.

**Q38. Why is retention ~0% in month 1 but repeat rate is 3%?**
Different denominators/windows: cohort month-1 retention requires the
next order *in the following calendar month* (0.48%); the 3% repeat rate
counts a second order *any time* within the ~2-year window.

**Q39. Which segment did you recommend and why?**
Recent One-Time Buyers (36,141 customers, ~R$5.9M historical revenue,
~91 days recency): the return window is short (median 29d), so the
freshest large pool gives the best expected conversions; repeat-capable
segments are too small (~4%) to matter at scale; High-Value Inactive is
colder (~13 months).

**Q40. How would you test whether the campaign actually works?**
A/B test: random eligible customers into treatment (incentive) and
holdout; measure 90-day second-order conversion; lift = treatment minus
control rate. Only a designed experiment isolates campaign effect from
self-selection.

**Q41. Why not claim late delivery *causes* churn?**
Observational association only. Late orders differ by region (up to 21%
late in some states), category and season; those factors could drive
both lateness and lower repurchase. Confounders are listed, never
ignored.

**Q42. What other cuts would strengthen the delivery analysis?**
Propensity-style matching on category/state/order value before comparing
repeat rates; or a logistic model controlling for confounders — noted
as future work, deliberately not overstated.

**Q43. What is a good KPI for the recommended initiative?**
90-day second-purchase conversion rate vs holdout. Guardrail metrics:
voucher redemption cost per converted customer, review-score trend.

---

## F. Project defense

**Q44. What was the hardest data-quality problem?**
Duplicate review_ids/orders and the payment-vs-items mismatches: 246
delivered orders where payment total differs from items+freight >R$1.
Resolution: keep one review per order, define revenue as items+freight,
keep payment_total only as a reconciliation column.

**Q45. Walk me through a mistake you found and fixed.**
RFM quintiles: pandas `qcut` disagreed with Postgres NTILE on ~490
boundary customers (qcut can't split ties; NTILE splits arbitrarily),
then on exactly 4 after adding a deterministic tiebreak — because
`ceil(pos*5/N)` gives remainder to the wrong buckets. Fixed by
replicating NTILE's boundary rule exactly; verified 100% agreement.

**Q46. What would you do differently?**
Add a proper date dimension earlier; compute review sentiment from the
comment text; and add matched-control analysis on the delivery finding
rather than only noting confounders.

**Q47. If a stakeholder says "just tell me the churn rate"?**
Clarify definition first: in a marketplace there is no subscription to
cancel — "churn" here means "never returned within the window", and the
window itself is censored. I'd report the repeat-purchase rate and
cohort curve, and flag that true churn can't be observed.

**Q48. How do you know your numbers are right?**
Three layers: 16 SQL validation checks (uniqueness, reconciliation,
cohort invariants — all PASS), 55 pytest tests (logic + live-DB
reconciliation — all pass), and an automatic SQL-vs-pandas
reconciliation report generated on every run.

**Q49. What's the weakest part of the project?**
Causality — the delivery→retention link is associational, and Power BI
report couldn't be executed in this environment (build pack is fully
specified instead). Both are documented openly rather than hidden.

**Q50. Explain the project in 30 seconds.**
"I analysed ~100k real orders from a Brazilian marketplace to find why
customers don't return. I built a Postgres warehouse with staged data
quality, SQL + Python cohort, RFM and delivery analysis that reconcile
to the cent, and found that 97% buy once, late deliveries coincide with
a 2.3-star experience and ~20% lower repeat rates — so I'd target
recent one-time buyers with a second-purchase program, measured by a
90-day conversion A/B test."
