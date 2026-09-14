# Decision checklist for the monthly spline comparison

Prepared 2026-09-14 while the cluster run is in progress, before examining its
real-data spline results. This checklist implements the existing
[frozen protocol](monthly_spline_factorial.md); it adds no score threshold,
significance test, candidate arm or model change. Use it with the result-review
tables, plots and [rationale register](model_change_rationale.md).

## What this experiment can decide

The target is retrospective county-month incidence prediction, with joint
annual site and catchment summaries. It compares three specified temporal
model/prior packages, each with seasonality off/on. It does not test county
temporal splines, spatial adjacency, diagnostic ascertainment correction or
replacement of Daniel's accepted state model.

The available decisions are: retain as an exploratory candidate; unsupported in
this comparison; defer for a specified combination; block pending input or
numerical evidence; or no practical preference established. A candidate can be
useful without a positive interaction contrast. Weak standalone performance
does not justify permanently excluding it from combinations. This development
comparison alone cannot establish final independent validation or authorize
production promotion.

## 1. Establish which results are interpretable

- Verify the exact 162-cell design: 54 new spline fits and 108 reused RW1/AR1
  controls, with no duplicated or substituted cells. Preserve any missing
  tasks in the inventory; absence is not a poor predictive score.
- Check archive, source snapshot, complete basis-file and per-task bindings.
  Merged metrics must reproduce their bound portable source reports. A fresh
  archive manifest alone does not prove that copied controls are unchanged.
- Confirm that every comparison uses matching eligibility, training origin,
  event-date definitions, forecast years, exposure and held-out truth. Preserve
  the established Cryptosporidium endpoint and Shigella date resolution.
- Check optimizer/approximation completion and count-scale adapter identity.
  A process exit of zero is necessary but is not evidence of forecast adequacy.
- Block numerical interpretation after an integrity or paired-truth failure.
  A clean partial archive may support complete four-arm comparisons; label
  those partial and state which planned comparisons are unavailable.
- State what cannot be verified from the portable archive: the local reader
  cannot freshly inspect cluster-only case panels or internal fitted objects.
  Checksums establish consistency, not independent authenticity.

## 2. Compare all components without choosing a favorable reference

For each pathogen, origin and forecast year, examine spline versus **both** RW1
and AR1, first without seasonality and then with it. Also examine seasonality
within each temporal package and the corresponding difference-in-differences.
Keep the absolute scores for all six arms visible. Do not report only the
reference or horizon against which spline looks best.

Start with the specified equal-site contrasts, then inspect site-level effects.
Record whether improvements recur across origins/horizons or are concentrated
in one place or period. A broad descriptive average may help navigation, but
must not replace those comparisons. Comparisons across pathogens with different
incidence scales are not a competition for the largest numerical score gain.

The interaction is on the predictive log-score scale. A positive value does
not prove a biological interaction; a negative value does not mean the combined
model is worse than its component-only models. Temporal contrasts include
different priors as well as different correlation/extrapolation assumptions.

## 3. Check annual predictions alongside county-month scores

For each origin/horizon and arm, record:

- Direction and magnitude of annual count bias at each site and the catchment.
- Coverage and width of the supplied 95% predictive intervals. High coverage
  from very broad intervals is not automatically useful; narrower intervals
  accompanied by missed outcomes are not automatically better.
- Whether median predictions and uncertainty tell the same story as arithmetic
  means. Inspect upper tails and the top-one-percent contribution to means.
- Whether the third forecast year deteriorates relative to the first. This is
  especially relevant to the spline's disclosed wider extrapolation prior.
- Cases in which an overall summary hides systematic underprediction at
  particular sites or opposite biases that cancel in an average.

Use joint-draw catchment intervals from the report. Never sum site interval
endpoints to construct a catchment interval. For zero observed counts, relative
bias and relative width are undefined: retain absolute counts/widths and identify
the missing denominator rather than replacing the ratio with zero. Descriptive
site coverage is based on dependent observations, not independent trials.

## 4. Separate simulation noise, approximation and scientific fit

Compare the pooled 8,000-draw estimate with the four 2,000-draw streams. Record
whether the direction of a contrast changes across streams, whether stream
variation is material relative to the gap, and whether tails/means fluctuate.
These ranges measure Monte Carlo stability, **not confidence intervals** for
future predictive performance. Stable averages do not establish stable density
estimates in every county-month; inspect the maximum cell-density relative MCSE
and detailed cell reports when available.

If simulation noise obscures a practical comparison, target diagnostics from
the saved fit and retain the original report. More posterior draws do not fix
model bias, an approximation failure, wrong exposure or unavailable input
evidence. Numerical repairs must be described separately from changes to the
scientific model. Do not rank candidates or certify prediction using CPO.

Record the sampling protocol when comparing regenerated diagnostics. The
[R/INLA seed review](monthly_sampling_rng.md) documents why the legacy base seed
alone does not reproduce every draw, and the optional future protocol that
explicitly seeds both components. This is not a reason to discard the current
sampled results or restart model fits.

## 5. Write a pathogen-specific rationale before a recommendation

Complete the [decision worksheet](../analysis_configs/monthly_spline_decision_template.csv)
using exact artifact paths and affected origin/horizon/site labels. Keep the
populated worksheet with private numerical review artifacts, not in the public
source template. Separate the following:

1. The problem or mechanism hypothesized before fitting.
2. What the paired results show, including contrary evidence and uncertainty.
3. Explanations proposed after seeing the results, clearly labeled hypotheses.
4. The provisional disposition, its scope, and the specific evidence that could
   change it. Record any unresolved reference disagreement.

Existing considerations to revisit, without prescribing new winners:

| Pathogen | Concern to carry into the spline review |
|---|---|
| Campylobacter | Does gradual trend extrapolation improve prediction while avoiding the annual undercoverage seen with seasonal AR1? |
| Cryptosporidium | Can the candidate retain useful calibration without the broad RW1 tails, within the documented surveillance window? |
| Cyclospora | Preserve the evidence that temporal and seasonal components can help together; determine whether underprediction and tail instability actually improve. |
| Listeria | Are differences practically useful relative to uncertainty and added complexity, rather than just small score changes? |
| Salmonella | Compare against the promising seasonal AR1 control as well as RW1, and check whether any gain costs calibration or tail stability. |
| Shigella | Does the candidate improve annual bias as well as scores, with the same audited specimen-month convention? |
| STEC | Compare against seasonal RW1's useful performance and check long-horizon bias and missed annual outcomes. |
| Vibrio | Require evidence beyond broad coverage or unstable arithmetic means; examine forecast tails and annual calibration together. |
| Yersinia | Retain the unresolved seasonal/temporal question and distinguish period-specific improvement from a general rule. |

## 6. Decide the smallest justified next action

| Finding | Next action |
|---|---|
| Incomplete execution with intact inputs | Recover only the missing tasks after checking why they failed. |
| Integrity, identity or truth mismatch | Resolve provenance first; do not rank the affected comparison. |
| Material Monte Carlo uncertainty | Diagnose/resample the implicated saved fits together when feasible; do not automatically refit models. |
| Numerical approximation failure | Investigate the approximation, preserving original fits and reporting the distinction from predictive failure. |
| Better scores but worse bias, coverage or unstable tails | Keep the tradeoff explicit; do not promote a default based on scores alone. |
| Consistent useful improvement with acceptable diagnostics | Retain an exploratory candidate and define the independent evaluation/use criteria still needed. |
| Mixed or negligible evidence | Record no practical preference or retain a bounded combination hypothesis; avoid a forced winner. |

Any prior modification or additional structure is a separately named experiment
with a stated mechanism and common controls. Do not relabel reused development
years as independent confirmation. Updating a dashboard or production default
is a later, explicit decision; completing this worksheet does not change either.
