# Temporal family × seasonality: frozen exploratory comparison

## Question and rationale

Does the predictive value of recurring monthly seasonality depend on the
long-term temporal structure? A temporal method with limited standalone benefit
may help in combination. Use a complete 2×2 comparison, rather than comparing only
a combined candidate with the weakest reference or making pathogen-specific
changes after seeing the outcome.

Every pathogen receives the same four arms: RW1 without seasonality (M00), AR1
without seasonality (M10), RW1 with seasonality (M01), AR1 with seasonality (M11).
The static IID county structure, state intercepts, exposure, monthly negative-
binomial likelihood, eligible rows and evaluation periods are fixed within each
block. No diagnostic-classification covariate is inserted into incidence models:
case-derived labels do not provide independent future testing exposure.

This comparison is ready with existing monthly inputs and implementations. The
state-only spline × seasonality candidate is undergoing separate local engineering
checks; retain it for the next controlled matrix. The older annual spline changed
both state and county trends, so inserting it here would confound interpretation.

## Frozen scope and reuse

All nine pathogens are included, including those whose previous standalone
forecast performance was inadequate. For Cryptosporidium, origins are 2011, 2013,
2014 with data ending in 2017. All others use 2011, 2013, 2016 with data ending in
2019. Each origin predicts 36 months. These are previously examined development
years, not independent final validation. There is no untouched-validation claim.

The matrix contains 108 cells: 9 pathogens × 3 origins × 4 arms. Reuse 54 completed
seasonal fits and 6 completed nonseasonal RW1 fits for Salmonella/Campylobacter.
Fit only the 48 missing nonseasonal cells. Reused metrics must come from the
four-stream, 2,000-draw-per-stream saved-diagnostic reports, not the earlier
lower-precision reports. Verify source plans, task identities, completion status,
input provenance and matching held-out truth before combining metrics. Preserve
all original outputs and do not regenerate existing fits for convenience.

Source families are saved_monthly_diagnostics_20260913_205110_899575,
monthly_ar1_comparison_20260913_215732_614498,
monthly_expansion_20260913_223222_865377, and the completed Shigella recovery
monthly_shigella_recovery_20260914_012243_682311. Source paths and hashes belong
in the executable plan. A missing or altered reference blocks that comparison;
do not silently substitute a different prior, source, or lower-precision result.

## Assumptions held fixed

Coverage remains EXPLORATORY_ASSUMED_CONTINUOUS. No new certification is inferred
from case presence. Existing audited date definitions, the documented Shigella
specimen-month resolution and pathogen-specific end dates are preserved. Future
population exposures are realized retrospective values, not a prospective
population forecast. Outcomes beyond each origin are masked before fitting.

RW1 retains its training-origin scaling and SD upper bound 0.5, tail probability
0.01. AR1 retains marginal SD upper bound 1, tail 0.01, with internal rho Normal
mean log(19), SD1.5. Seasonal arms retain the shared cyclic constrained RW1 effect
with standardized SD upper bound0.5, tail0.01. County IID SD bound1, tail0.01,
state log-rate prior center log(0.0002), SD1, and NB log-size Normal(log20,1²)
remain unchanged. RW1 and AR1 do not have equivalent functional priors; temporal
contrasts compare the specified model/prior packages. Do not attribute differences
solely to one mathematical property of the correlation process.

## Evaluation and decision

Use the same county-month predictive log scores, averaged within each site and
forecast year, and the same four-stream posterior sampling protocol as reused
reports. All methods use explicit held-out prediction. CPO values are not used
for ranking, gating predictive accuracy or model acceptance. Numerical optimizer,
finite-prediction and aborted-approximation checks remain separate requirements.

For higher-is-better score Q, report temporal effects without and with seasonality:
Q10−Q00 and Q11−Q01; seasonal effects under each temporal structure: Q01−Q00 and
Q11−Q10. Also report Q11−Q10−Q01+Q00, the interaction on this predictive score
scale. This is not a biological interaction or significance test. A combined
model may be useful without a positive interaction contrast; inspect its total
performance and calibration too. Preserve all four candidates in the ledger.

Report each pathogen, origin, site and horizon separately. Where summaries are
shown, weight sites equally within pathogen/origin/horizon. Do not turn overlapping
origins, adjacent months or county cells into independent replicates. Stream
contrasts assess Monte Carlo stability, not generalization uncertainty. Aggregate
predictive intervals use joint draws, not sums of marginal endpoints. Examine
coverage, annual count bias, interval width and tail contribution alongside scores.
Reused aggregate-tail reports support these comparisons consistently across arms.

There is no automatic winner or numerical noninferiority threshold for acceptance.
This batch identifies exploratory candidates and limitations. Confirmation would
require a defensible independent evaluation scope, practical-use criteria and
additional evidence. Record why each pathogen-specific disposition is justified
in model_change_rationale.md; do not reject a method universally based on one arm.

## Execution

Run `python3 scripts/launch_monthly_factorial.py` on Rosalind with Singularity
loaded. Submit the missing 48 fits concurrently with no concurrency cap, four
cores per task, with the established monthly limits of 48 hours, h_rss/mem_free
53248M and h_vmem68G. These are limits, not expected runtime. A collector waits for all new tasks, verifies reused controls,
and returns one archive with incomplete cells explicit. Original state models,
accepted dashboards and source files remain unchanged. No new container build.
