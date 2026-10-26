# Limitations

Honest constraints on what this analysis can and cannot claim.

## Data-window limitations

* **Dataset ends 2018-10-17.** Cohorts from mid-2018 onward have short
  observation windows; late-2018 cohort claims are restricted by
  `is_observed` flags rather than silently zero-filled.
* **Left-censoring:** first observed purchase ≠ first-ever purchase.
  Some "new" customers may have bought before Sep-2016.
* **No data after Oct-2018** — nothing here describes the current
  business. Numbers are historical evidence, not present-day KPIs.
* **Truncated final month:** Oct-2018 is a partial month; trend claims
  exclude the boundary.

## Identity and coverage limitations

* `customer_unique_id` is Olist's de-duplication of people across
  orders — reasonably reliable but not guaranteed perfect (address/card
  changes could split one person; shared accounts could merge people).
* Repeat rate (3.0%) is **within-Olist only** — customers may buy the
  same products elsewhere; we cannot see cross-retailer behaviour.
* `is_qualifying_order` = 'delivered' excludes ~1.7% of orders in
  ambiguous lifecycle states — a documented choice, not the only
  defensible one.

## Metric limitations

* **Revenue = items + freight**, not payment totals (246 mismatched
  orders). It is a merchandise+shipping revenue proxy, not necessarily
  the platform's commission/take-rate revenue — Olist's actual business
  model monetises seller fees, which this dataset does not expose.
* **Reviews** — one review per order kept (latest creation date);
  ~0.5% of orders have multiple rows. Review text is not analysed.
* **RFM is descriptive** — quintile thresholds are conventions, not
  behavioural truths; small threshold changes move borderline customers
  between segments (hence deterministic tie-breaking and validation).
* **Cohort 'retention'** measures marketplace repurchase, not
  subscription retention — the metric is correct for this business
  model but not comparable to SaaS retention benchmarks.

## Causal limitations

* **Late delivery ↔ low review/repeat is associational.** Candidate
  confounders: delivery distance/region (late rates reach 21% in some
  states), product category, order size, season (Black Friday), seller
  quality, and self-selection (dissatisfied customers may also be less
  likely to return regardless of cause).
* The windowed repeat-rate cut (F7) reduces but does not remove
  follow-up-time bias; no propensity matching or regression adjustment
  was performed.
* **No causal claims are made anywhere in this project.** A proper lift
  estimate needs an A/B test or a quasi-experimental design.

## Process limitations

* The Power BI report ships as a **generated `.pbip` project**
  (`powerbi/project/OlistRetention.pbip`, built by
  `scripts/build_powerbi_project.py`). PBIR/TMDL are text formats, so the
  project is fully reproducible in git — but Desktop GUI polish (exact
  positions, theme tweaks) should be reviewed on first open; see
  `powerbi/README.md`.
* Dockerised PostgreSQL 16 was used because no native PostgreSQL server
  was installed; behaviour is equivalent for this workload.
* Geolocation table (1M rows) was profiled but not used — city-level
  mapping adds cost without changing the conclusions.
