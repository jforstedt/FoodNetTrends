# Next phase: diagnostic methods, seasonality, and pathogen-specific models

Status: planned, not implemented or authorized for immediate cluster execution.
Start after the current surveillance corrections and targeted refits are reviewed.

## Purpose and scope

Extend the existing state spline and exploratory county models in separately
measured steps. Preserve the reviewed state model as a reference and retain all
input snapshots, fitted objects, and output provenance. Adding an INLA component
is not evidence of equivalence to the published spline.

The [Weller et al. paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13055632/)
proposes diagnostic-method interactions, finer temporal resolution, and
pathogen-specific priors or distributions as extensions. It also calls for
validation of near-term extrapolation. The implementation and acceptance criteria
below are proposed project decisions, not specifications claimed to come from the
paper. Its historical-fit comparison and extrapolation example serve different
purposes; we will evaluate historical trends and future prediction separately.

## Gate before starting

1. Review the current replacement archive: observation windows, baseline values,
   reportability, population alignment, and sampler diagnostics.
2. Record unresolved early-year geography and completeness questions. A candidate
   may proceed only on a verified subset; unresolved periods are not zero counts.
3. Freeze reference data, case definitions, denominators, model code, and outputs.
   Record which reviewed correction replaces each earlier fit.
4. Fix the scientific target for each experiment: reported infection incidence,
   diagnostic-category incidence, standardized estimates, or future observations.
   Agree on metrics and practical acceptance margins before examining test scores.

The entry gate can be satisfied for one pathogen while another remains under
review. Neither success nor failure transfers automatically across pathogens.

## Parallel workstreams

| Workstream | First deliverable | Candidate analysis | Required evidence before adoption |
|---|---|---|---|
| Diagnostic methods | Field inventory and category/coverage audit | Category-specific trends, then site-by-method temporal effects; county extension only if supported | Coherent categories, identifiable target, sensitivity to missingness and method adoption, stable estimates and held-out performance |
| Seasonality | Date completeness and monthly exposure audit | Annual trend plus a constrained cyclic seasonal effect, initially at site level | Reliable dates and observation windows, recovery in simulation, calibrated monthly predictions, coherent annual aggregation |
| Pathogen-specific priors and distributions | Prior-predictive and residual assessment by pathogen | Scale-aware weakly informative priors, then limited alternatives to the negative binomial where justified | Plausible prior predictions, sensitivity results, stable inference, improved calibration without damaging trend estimates |
| Forecast validation | Shared temporal evaluation specification and runner | Reference and eligible candidate models at common forecast origins | Leakage-free comparisons, uncertainty and calibration by horizon, reproducible results across origins |

### A. Diagnostic-method adjustment

Audit culture, CIDT, confirmatory culture, method-unknown, dates, and available
laboratory identifiers or adoption information. Determine whether categories
represent mutually exclusive case outcomes or overlapping tests on the same case.
One illness must not be counted twice. Report missingness by site and period.
Confirm that numerator eligibility and any population denominator are meaningful
for the chosen target; diagnostic categories do not automatically represent
separate population groups.

Begin with descriptive category-specific trends on comparable windows. Compare
an unadjusted reference with a limited method-by-time-by-site candidate. Consider
county interactions only after checking sparsity and computing cost. Audit joint
uncertainty and aggregation if category estimates are combined.

A fixed-method-mix scenario is a possible later output, but only after defining
its reference mix, assumptions, and uncertainty. Do not label it true incidence
or a causal correction: observed testing categories alone may not distinguish
changes in testing, care seeking, ascertainment, and underlying infections. If the
available data do not identify that scenario, deliver stratified trends and a
specific data requirement instead.

### B. Seasonality and finer time resolution

Inventory onset, specimen, and reporting dates. Choose and document the time axis;
measure missing dates and reporting changes before aggregation. Use monthly data
as the first candidate, with weekly resolution deferred unless supported.

Build the observation calendar before counting cases. Represent partial periods
and exposure duration explicitly. Use population and time-at-risk consistently;
annual population cannot simply become twelve full-year exposures. Do not infer
zero incidence from a missing monthly report.

Start with a shared cyclic seasonal effect plus the long-term trend. Constrain
components so the seasonal effect does not absorb the long-term trend. Add
site-specific or pathogen-specific seasonal variation only when supported. Test
known seasonal signals, absent seasonality, trends, isolated outbreaks, and
missing periods in simulation. Compare aggregated monthly posterior draws with
annual estimates, propagating joint uncertainty rather than summing interval
endpoints.

### C. Pathogen-specific priors and count distributions

Retain the current negative-binomial specification as the comparator. Audit
residual patterns, dispersion, sparsity, and zero-count predictions separately
for each pathogen. Validate eligibility first: non-observation cannot justify a
zero-inflated distribution.

Specify candidate priors on interpretable scales such as incidence, temporal
variation, spatial variation, and dispersion. Check prior-predictive counts and
rates across realistic populations before fitting actual outcomes. Distinguish
brms spline and INLA random-effect parameters; identical numeric priors do not
necessarily imply identical assumptions.

Initially compare a small predeclared set of prior strengths. Consider a hurdle
or zero-inflated alternative only where the observation process and residual
checks support it. Keep separate comparisons for changing priors and changing
likelihoods before combining them. Use simulation and held-out predictive checks;
more flexible models must not win solely through in-sample fit.

### D. Shared forecast and comparison framework

Use rolling temporal origins with the same eligible training and evaluation
observations for each paired comparison. Evaluate annual one-, two-, and
three-year horizons where available; evaluate monthly short horizons separately
when the seasonal workstream is ready. Do not extend evaluation beyond a
pathogen's observation window or across an unresolved reporting break.

Fit transformations, model selection, diagnostic-mix scenarios, and prior tuning
using training data only. Reserve final evaluation windows from repeated tuning;
use inner temporal validation when selecting candidates. Specify how future
population and diagnostic covariates would be known at prediction time. Tests
using subsequently observed populations must be labelled conditional hindcasts.

Report point accuracy, proper predictive scores, interval coverage and width,
zero-count calibration, and aggregate totals. Distinguish uncertainty in expected
incidence from predictive uncertainty for future observed counts. Report paired
score differences and uncertainty across origins, with numerical or Monte Carlo
error where material. Include a simple historical reference as well as the state
spline and eligible county comparators. Do not declare a universal winner from a
single pathogen, split, or average score.

Extrapolation of a completed series is separate from reporting-delay nowcasting.
Estimating incomplete recent periods requires reporting-delay records or data
vintages; without those inputs, do not claim that capability.

## Execution order and resource plan

- After the entry gate, run all three data/model audits and the evaluation-runner
  work in parallel. Build small synthetic examples before expensive real fits.
- Run independent pathogen, candidate, and forecast-origin fits concurrently.
  There is no arbitrary three-task cap. Size CPU and memory requests from measured
  pilot usage; avoid oversubscribing threads within each fit.
- Preserve dependencies: an audit must pass before its fit, training-only tuning
  before final evaluation, and result review before dashboard promotion.
- Begin with a small representative pathogen panel chosen for data completeness,
  diagnostic changes, seasonality, and sparsity. Scale successful experiments to
  remaining pathogens; avoid an unbounded combination of every model option.
- Snapshot commands, code, inputs, seeds, package versions, and resource requests.
  Reuse identical completed tasks and saved draws where valid. Changed inputs or
  specifications require new fits. Retry only failed tasks with a diagnosed cause.
- Produce one consolidated internal review archive per experiment batch, keeping
  large fit checkpoints on the cluster. Container changes are built on the build
  host, then smoke-tested on compute nodes before array submission.

## Review products and completion criteria

Deliver a concise per-pathogen comparison report, machine-readable metrics,
provenance manifest, and candidate-status table. Classify each candidate as
accepted for a stated use, exploratory, or unsupported by available data. A
stable sampler alone is insufficient. Require coherent inputs, synthetic checks,
reasonable prior and posterior predictions, and performance within the predeclared
practical margins for the intended use.

Only accepted or explicitly labelled exploratory outputs enter a separate
candidate dashboard. Planned views include diagnostic-category trends and any
justified standardized scenario; monthly curves and seasonal heatmaps; and
forecast intervals with actual outcomes and horizon-specific performance. Display
observation limits, uncertainty, and the reference model. Preserve the reviewed
historical dashboard and provide a clear path back to it.

This phase does not promise causal testing adjustment, reliable long-range
forecasts, universal pathogen performance, or automatic replacement of Daniel's
model. Each extension must earn its intended use through the checks above.
