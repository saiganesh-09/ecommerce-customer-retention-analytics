# Business Recommendations

Primary question: **which customer segment should the business prioritize
for retention, and what evidence supports that decision?**

## The candidate segments (from `analytics.segment_opportunity`)

| Segment | Customers | Historical revenue | Avg spend | Avg recency | Avg freq | Nature of opportunity |
|---|---|---|---|---|---|---|
| Recent One-Time Buyers | 36,141 | R$5.94M | R$164 | 91 d | 1.0 | convert 1st -> 2nd order |
| High-Value Inactive | 13,782 | R$4.24M | R$308 | 395 d | 1.0 | win-back big spenders |
| Other One-Time Buyers | 18,064 | R$2.74M | R$152 | 220 d | 1.0 | late conversion attempt |
| Inactive One-Time Buyers | 22,570 | R$1.64M | R$73 | 396 d | 1.0 | low value, cold |
| Potential Loyalists | 1,080 | R$321k | R$297 | 89 d | 2.0 | nurture into habit |
| At Risk | 992 | R$293k | R$295 | 382 d | 2.1 | win-back proven repeaters |
| Needs Attention | 571 | R$165k | R$289 | 217 d | 2.0 | prevent full lapse |
| Champions | 116 | R$66k | R$571 | 91 d | 3.5 | VIP treatment |
| Loyal Customers | 42 | R$20k | R$466 | 194 d | 3.4 | keep engaged |

## Prioritisation logic

Retention economics ≈ **reachable customers × probability of response ×
value per response**. The data constrains each factor:

1. **The return window is short.** Median time to a second order is 29
   days (F5); cohort retention never strengthens over time (F4). The
   best time to win a second purchase is soon after the first.
2. **Repeat-capable customers are a rounding error.** All customers with
   frequency >=2 together number exactly 2,801 (3.0%). Even a perfect
   win-back cannot move the business at that scale.
3. **Value follows the one-time buyers.** ~95% of revenue sits in
   frequency-1 customers — the upside is in creating the *second* order,
   not rescuing the fifth.

## Recommendation

### Primary target: **Recent One-Time Buyers**

36,141 customers — the largest, freshest and most reachable pool. They
purchased ~3 months ago on average, are still near the historical
repeat-purchase window, and represent R$5.9M of proven spend.

* **Recommended action:** a second-purchase incentive program (e.g.
  category-relevant offer or free-shipping voucher on the next order),
  triggered ~30-60 days post-purchase — aligned with the observed 29-day
  median return gap.
* **Sub-priority within the segment:** the ~2,329 Recent One-Time Buyers
  whose first order arrived **late** (`segment_experience` table).
  F6/F7 show late delivery is the clearest dissatisfaction signal in the
  data; a service-recovery gesture to this group is the most
  evidence-backed micro-target in the project.
* **Success KPI:** second-purchase conversion rate — share of targeted
  customers placing a 2nd *delivered* order within 90 days of the touch,
  vs a holdout control group.
* **Why not the alternatives:**
  * *At Risk / Needs Attention / Loyal* — proven repeaters, but only
    ~1,605 customers combined; high per-customer confidence, negligible
    absolute upside. Appropriate for a low-cost automated win-back, not
    the flagship initiative.
  * *High-Value Inactive* — tempting (R$308 avg spend), but avg recency
    ~13 months and no demonstrated repeat intent; response probability
    is the weakest of the viable targets. Test with a small pilot, don't
    lead with it.
  * *Inactive/Other One-Time Buyers* — older and/or lower-value pools;
    same effort, worse expected yield than the recent pool.

### Scenario illustration (assumptions, not forecasts)

If the second-purchase program converted at hypothetical rates on Recent
One-Time Buyers at their R$164 avg order value:

| Assumed lift | Converted customers | Indicative order value |
|---|---|---|
| 1% | ~361 | ~R$59k |
| 2% | ~723 | ~R$119k |
| 5% | ~1,807 | ~R$297k |

These are scenario arithmetic on stated assumptions — not expected
revenue. Even the conservative 1-2% band exceeds anything achievable on
the tiny repeat segments.

### Secondary actions (cheap, supportive)

1. **Delivery-promise hygiene in high-lateness states.** AL/MA/SE/PI/CE
   run 14-21% late vs 6.8% nationally — extending estimates for those
   lanes would cut "late" complaints without faster logistics, at the
   cost of longer shown ETAs. A/B test before deciding.
2. **Automated win-back** for At Risk + Needs Attention (~1,563
   customers): low-cost email/voucher flow; small but highest-confidence
   audience.

## What is needed before claiming impact

* **Experiment design** — holdout/control to measure true lift; the
  observational repeat rate is not a campaign baseline.
* **Margin data** — the analysis uses gross order value; profitability
  requires contribution margin per order and voucher cost.
* **Contactability/consent data** — can these customers legally be
  marketed to?
* **Post-window data** — the dataset ends Oct-2018; any real deployment
  needs current data.

## Ranked summary

| # | Recommendation | Evidence strength | Effort | Upside |
|---|---|---|---|---|
| 1 | Second-purchase program on Recent One-Time Buyers | strong (scale + timing evidence) | medium | largest |
| 2 | Service-recovery for late-first-order customers inside that segment | strong (F6, F7) | low | medium |
| 3 | Delivery-estimate fix for high-lateness states | moderate (F9) | low | medium |
| 4 | Automated win-back for At Risk / Needs Attention | moderate | low | small |
| 5 | Pilot on High-Value Inactive | weak-moderate (cold but high value) | medium | unknown — test |
