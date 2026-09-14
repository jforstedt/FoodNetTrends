# Protocol for combined county extensions

Status: planned exploratory comparisons, 13 September 2026. This document defines
what can proceed after the current spline and definition review. It does not
launch jobs, accept a candidate, or alter Daniel's accepted state analysis.

## Questions and targets

Can recurring seasonal structure improve predictions, and does its value depend
on whether the long-term trend uses a random walk or a spline? Can independently
supported testing information add value beyond those components? An addition is
not rejected solely because its standalone comparison is weak: its conditional
contribution must also be assessed in a justified combination.

The initial target is eligible, detected case counts by month, aggregated to site
and catchment forecasts. This is not total infections or a causal effect of a
laboratory method. Start with Salmonella and Campylobacter; broader pathogen
coverage follows separate eligibility and calibration review. Keep the same county
footprint and case rules across each paired comparison. Accepted state results
remain a separate historical reference, not forecast ground truth.

## Readiness gates

| Gate | Required evidence | What stops if unresolved |
|---|---|---|
| Current candidate review | Numerical checks, complete artifacts, sampling stability, exact data identities | Selection or interpretation of the current spline comparison |
| Monthly panel | Defined specimen-date target, explicit missing/imputed-date policy, documented pathogen/site/month observation calendar | Monthly incidence fitting and zero filling |
| Exposure | Positive eligible population; person-years proportional to observed days; annual totals reconciled | Monthly rates and model fitting |
| Testing categories | Public definitions checked against extract derivations; mutually exclusive accounting or a validated joint observation model | Combining category counts into one incidence estimate |
| Testing predictor | Independent measurement, historical availability at each forecast origin, and support across sites/time | Prospective testing-adjusted forecasts |
| Numerical/prior checks | Training-only scaling, masked outcomes, horizon invariance, plausible simulated counts and stable prediction | Real-data combination batch |

The [dictionary review](foodnet_dictionary_review.md) supplies partial definitions,
not proof of monthly observation or extract derivations. The running raw audit
can resolve contradictions but cannot establish an observation calendar from case
presence. If monthly coverage remains uncertain, retain descriptive date summaries
and report the missing evidence instead of manufacturing a complete panel.

Use specimen collection as the proposed monthly target, conditional on its audit.
Do not substitute onset or administrative dates silently. Onset-based results,
if pursued, form a separately documented sensitivity analysis. Excluded or
unassignable dates must appear in reconciliation totals; do not discard them to
force agreement. State the rate unit explicitly. With annual population held
constant within a year, month person-time is population times observed days divided
by days in that year; partial-year eligibility is explicit. A different interpolation
rule is a separately frozen sensitivity analysis.

## First controlled matrix

Once monthly inputs pass, fit these four candidates on exactly the same observations
and forecast targets. Hold the static county structure fixed within a comparison
block; use IID first as a reference and repeat the complete block with spatial
structure if warranted. Do not compare a spatial seasonal model only against a
nonspatial nonseasonal reference and attribute the difference solely to seasonality.

| Candidate | Long-term component | Cyclic month component | Purpose |
|---|---|---|---|
| M00 | Random walk | Absent | Monthly reference |
| M10 | Training-only spline | Absent | Spline contribution |
| M01 | Random walk | Shared constrained seasonal curve | Seasonal contribution |
| M11 | Training-only spline | Same seasonal curve | Joint contribution |

The random walk and spline have the same long-term temporal target; monthly time
scaling, prediction at month boundaries and proper slope priors must be specified
in the implementation manifest. Do not carry the annual negative-binomial shape
parameter into a monthly likelihood unchanged. All four candidates use the same
monthly negative-binomial parameterization and comparable prior-predictive targets.
Prior equivalence is not assumed merely because two numerical SD bounds match.

Begin with one cyclic effect per pathogen, centered over a complete calendar year,
with continuity across December/January. State deviations are a later pooling
sensitivity, not unconstrained county-specific seasonal curves in the first batch.
Document constraints that separate seasonal and long-term contributions; do not
interpret their individual components as causal effects.

For a higher-is-better held-out score Q, record Q10-Q00, Q01-Q00, Q11-Q10 and
Q11-Q01. Also report the contrast Q11-Q10-Q01+Q00. This describes whether the
combined predictive gain exceeds the sum of individual gains on this score scale;
it is not a biological interaction or an independent significance test. Keep all
four candidates in the ledger even when one standalone addition performs poorly.

## Testing information: conditional second matrix

First deliver descriptive diagnostic-category trajectories with explicit unknown
categories. Case-associated test results do not supply a denominator of everyone
tested and must not be used as if they did.

A total-count forecast must not condition on the diagnostic mix observed in its
held-out cases. That mix is unavailable at prediction time and depends on the
outcome. If external laboratory adoption or testing-volume information is obtained,
freeze its release dates, measurement definition and handling of unknown future
values. Only values available at the origin, or a separately validated forecast
with propagated uncertainty, may enter prospective predictions.

If this gate passes, add a testing-information version of each M00/M10/M01/M11
candidate: a complete eight-candidate matrix within the chosen geographic block.
Start with a limited, pooled site-level effect. This allows testing-by-seasonality
and testing-by-trend comparisons without searching arbitrarily through interactions.
If only case categories are available, keep descriptive/category-joint modeling
as a separate target; do not label it ascertainment-corrected incidence or insert
it into the total-count comparison as an equivalent adjustment.

## Held-out evaluation and leakage controls

Use identical cutoffs, eligible cells, exposure and truth for every candidate in a
block. The already explored 2011/2013/2016 annual origins can support monthly
hindcasts only if monthly eligibility is established. Their reuse makes this
exploratory: they are not newly untouched validation data. Do not extend beyond a
pathogen's documented observation window to obtain another origin.

Evaluate 1-12, 13-24 and 25-36 months ahead separately, as well as annual aggregates.
Dates, basis construction, scaling, covariate transformations and hyperparameter
choices use training data only. Future population assumptions must be shared and
labelled: using realized populations is a conditional retrospective experiment,
not proof of fully prospective performance. Preserve the data vintage; without
historical extracts, do not claim real-time backtest accuracy or validated nowcasting.

Primary accuracy reporting: paired monthly predictive log scores, shown by
pathogen, site and horizon, plus a catchment summary with weights frozen before
fitting. Report both counts of scored cells and the weighting rule; a summed score
can conceal weak performance in small sites. Secondary reporting: predictive
interval score, 50%/95% coverage and width, absolute error, aggregate count bias,
and zero-frequency checks. Compute annual/catchment predictive intervals by
summing each joint predictive draw, never by adding marginal interval endpoints.
Keep seasonal month and sparse-site breakdowns to reveal failures hidden by totals.

Numerical uncertainty and forecast uncertainty are separate. Repeat posterior
sampling where it could change conclusions. Overlapping origins, adjacent months
and counties are not independent replicates. Paired block-based uncertainty
summaries may be used only with a documented block scheme and enough blocks;
three origins alone cannot justify precise generalization claims. Show origin-wise
results and avoid converting thousands of dependent cells into artificial certainty.

## Decision rules and remaining freeze points

No candidate is promoted because it has the highest single score. Require valid
inputs, passed numerical checks, adequate calibration, stable comparisons and no
material degradation at the intended forecast horizon. Persist crashes and
unsupported candidates instead of reporting only successful fits.

Before launching the monthly matrix, record exact prior parameters, seasonal rank,
forecast weights, simulation scenarios and practical noninferiority margins in a
versioned manifest. These numerical choices are pending the input/numerical review;
this document is not a fully executable preregistration. Choose margins in count,
coverage and interval-width units appropriate to the intended use, using training
information and simulation, before examining new comparison outcomes. Do not set
a threshold retrospectively to accept the preferred model.

Distinguish three outcomes: exploratory improvement requiring more validation;
accepted for a narrowly stated use with documented limits; or unsupported. Seek an
untouched eligible period or other external validation before claiming confirmatory
improvement. Failure to obtain it limits the claim rather than justifying invented
future observations.

## Parallel execution and review product

While the present recovery runs: finish this protocol and review public definitions.
After its archive arrives: review the spline results and definition audit in
parallel. Once the monthly panel is certified, basis/prior checks and implementation
unit checks can proceed independently. Only then submit all eligible candidate/origin
fits concurrently, with scheduler dependencies and worker-side validation gates.
Posterior scoring and aggregation follow each completed fit; the final collector
waits for all candidates and records partial failures. Reuse validated artifacts
by fingerprint and never rerun successful models just to regenerate a dashboard.

Deliver a candidate matrix, per-origin/horizon metrics, Monte Carlo diagnostics,
interval and seasonal plots, input/definition limitations and a status table.
Dashboard integration follows review and keeps an explicit experimental label
where appropriate. This protocol requires no extra HPC submission today.

## Recovery-review follow-up

The current standalone spline specification is not promoted. A
[read-only checkpoint inspection](saved_spline_inspection.md) compares the unstable
spatial fit with its matched IID fit. Retain spline plus seasonality in the planned
matrix, but require resolution or isolation of this numerical failure before
running or interpreting that combination. Poor standalone performance does not
by itself rule out a useful combination; numerical failure is a separate gate.

Monthly preparation is implemented in [the preparation launcher](monthly_preparation.md), with a separate [public coverage evidence review](monthly_coverage_evidence.md). Completion creates a reconciled candidate inventory; it does not certify monthly observation eligibility or authorize automatic zero filling.

The [synthetic monthly prototype](monthly_seasonal_prototype.md) implements the IID-county monthly RW1 reference and shared cyclic-seasonal addition for local engineering checks. It has no production entry point, does not implement the spline pair, and does not satisfy the monthly observation or production prior gates by itself.

The first [real-data monthly batch](monthly_comparison.md) freezes the IID-county RW1 reference/seasonal pair, priors, horizons and equal-site score weights. It proceeds conditionally under a recorded continuity assumption, not independently certified monthly coverage. The spline/spatial pairs and confirmatory acceptance remain outside this batch.

The [temporal-prior sensitivity](monthly_temporal_sensitivity.md) tests one stronger shrinkage setting in the seasonal models while reusing the completed seasonal references. It is an exploratory response to the calibration review, not an automatic replacement or renewed spline comparison.
