# Next phase: diagnostic methods, seasonality, and pathogen-specific models

Status: county forecast numerical screening and matched retrospective comparisons
authorized on 13 September, after acceptance of the seven state corrections.
See county_forecast_validation_protocol.md for the executable first batch.
The parallel extension input audit has completed. The user approved the next-phase
comparison plan on 13 September. Model extensions remain separate from the current
forecast batch; their implementation must preserve the gates below.

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
   reportability, population alignment, and sampler diagnostics. Successful
   execution alone is insufficient: check table schemas, finite estimates, ordered
   intervals, unique eligible state-time keys, reconciled totals, and readable
   saved fits. Require regression tests for every supported input path, including
   missing Listeria reportability and incomplete expanded county footprints.
2. Record unresolved early-year geography and completeness questions. A candidate
   may proceed only on a verified subset; unresolved periods are not zero counts.
3. Freeze reference data, case definitions, denominators, model code, and outputs.
   Record which reviewed correction replaces each earlier fit. All workstreams
   must consume one versioned, executable eligibility/exposure contract; do not
   maintain separate hardcoded observation rules in each model launcher.
4. Fix the scientific target for each experiment: reported infection incidence,
   diagnostic-category incidence, standardized estimates, or future observations.
   Agree on metrics and practical acceptance margins before examining test scores.

The entry gate can be satisfied for one pathogen while another remains under
review. Neither success nor failure transfers automatically across pathogens.

## Numerical gates before new county forecasts

Freeze temporal prior scaling and centering for each training origin. Appending
unused future prediction rows must preserve earlier predictive distributions
within predeclared numerical tolerance; resolve the current scaled-RW1 domain
dependence before multi-horizon comparisons. This is a county-model requirement,
not a reason to alter the published state spline.

Calibrate joint posterior uncertainty for the actual sparse and dense county-time
models, including the approximation used when skew correction is disabled. Use
known-truth simulations and a small matched higher-accuracy or MCMC reference.
Successful smoke tests, finite summaries, and CPO flags do not establish tail
accuracy. Set tolerances using simulation uncertainty before real comparisons.

## Planned county spline comparator

Approved for the next phase on 13 September: evaluate a county extension
that retains the published temporal spline approach alongside the exploratory
RW1 county model. This is an approved candidate-development plan, not a replacement for accepted
state results or an automatic launch of unvalidated full-scale fits.

The paper already compared county-year and site-level versions, reporting similar
catchment estimates with over an order of magnitude greater computation for the
county-year versions. That comparison does not establish the performance of a
new, independently varying spline for every county. Reconstruct the paper's exact
county specification first; distinguish it from a proposed shared spline with
regularized county departures.

Keep case eligibility, exposures, years, outcomes, and forecast origins matched.
Separate inference-engine differences from changes in temporal or spatial
assumptions: document spline bases, penalties, priors and constraints, and test
any INLA approximation against a manageable reference before claiming equivalence.
Compare spline and RW1 temporal structures with spatial sharing held fixed, then
compare spatial sharing within each temporal structure. Validate extrapolation,
joint predictive uncertainty, and state-level aggregation as well as historical
fit. Do not combine diagnostic-method, seasonal, and prior changes in the first
comparison; their data audits can proceed independently.

## Approved priorities and input-audit findings

1. Start the county spline/RW1 comparison with Salmonella and Campylobacter,
   retaining matched eligibility, counts, exposures and forecast targets. Audit the
   paper's county specification before implementing shared splines with county
   departures. Preserve the accepted state spline as a separate reference.
2. Develop the monthly-data specification in parallel. The raw inventory contains
   specimen collection, symptom onset, laboratory receipt, site entry and report
   completion dates, plus a month field. Confirm date definitions, imputation and
   month consistency; do not substitute administrative dates for onset or infer
   a complete observation calendar from case presence. Use eligible person-time.
3. Develop diagnostic-method specifications in parallel. The raw inventory contains
   culture/PCR/antigen results, assay-name fields and laboratory names beyond cxcidt.
   Confirm codes, repeated-test semantics, laboratory-name consistency and suitable
   linkage before model adjustment. The initial narrow case/record-ID heuristic
   did not evaluate all patient/specimen/result identifiers present in the full
   inventory; absence of a confirmed key is not absence of identifier fields.
4. Use pathogen-specific sparsity to design pooling and prior-predictive checks,
   without selecting priors from evaluation outcomes. Keep zero-inflated/hurdle
   models conditional on evidence beyond observed zero frequency. The raw census
   inventory must not replace validated eligible denominators.
5. Request the MMWR data dictionary and any date-imputation, laboratory testing or
   monthly observation documentation needed to resolve the preceding points.
   NHSN remains a possible separate complementary source; no counts are pooled.

The current annual county recovery passed the complete 80-task numerical screen
and both numerical prerequisites, but one real-data candidate crashed in INLA.
Execution recovery and review remain separate from scientific acceptance. The
completed Cyclospora forecasts also showed aggregate predictive failures across
the inspected origins; resolving the process crash alone would not validate them.
Some cell tail-density estimates have substantial Monte Carlo uncertainty. Complete
candidate results and numerical sampling uncertainty must be reviewed before
promoting county forecasts or claiming a benefit from spatial sharing.

The existing historical-rate reference uses a Poisson/Gamma formulation, whereas
county candidates use negative-binomial observation models. Gains over that
reference do not isolate the benefit of time structure, geography or computation.
Include a matched-dispersion reference where appropriate when defining the next
controlled comparison. Keep exploratory score differences distinct from evidence
of significance, especially for overlapping forecast origins and noisy tail
probability estimates. Preserve failed candidates in the evaluation ledger.

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
One illness must not be counted twice. Mutually exclusive categories, including
unknown methods, must reconcile exactly to eligible case totals. Report missingness
by site and period; do not confuse the mix of diagnoses among detected cases with
the proportion of the population tested by each method.
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
specific data requirement instead. Specify what independent testing/adoption
information identifies the proposed standardization weights, check support across
sites and periods, and document sensitivity to ascertainment assumptions. Failure
of that identifiability check stops standardized/counterfactual output; descriptive
category-specific trends may still proceed.

### B. Seasonality and finer time resolution

Inventory onset, specimen, and reporting dates. Choose and document the time axis;
measure missing dates and reporting changes before aggregation. Use monthly data
as the first candidate, with weekly resolution deferred unless supported. Freeze
a date-precedence rule, missing-date handling, reporting-lag treatment, and data
vintage before fitting. Do not silently substitute reporting date for onset date.

Build the observation calendar before counting cases. Represent partial periods
and exposure duration explicitly. Use population and time-at-risk consistently;
annual population cannot simply become twelve full-year exposures. Do not infer
zero incidence from a missing monthly report. State the rate unit, month-length
and leap-year treatment, and population interpolation convention. Preserve total
person-time and baseline definitions when aggregating to years. Recalibrate
dispersion and prior assumptions for monthly counts; an annual negative-binomial
shape parameter is not automatically transferable to monthly observations.

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

Define a common scoring target before comparisons: state versus county models
can be compared on shared state-year outcomes after aggregating joint predictive
draws; monthly candidates need the same treatment for annual comparisons. Do not
compare scores calculated at different resolutions or sum interval endpoints.
Specify whether weighting targets counties, people, or surveillance-wide totals.
Coherent aggregation does not require different models to yield identical rates.

Use rolling temporal origins with the same eligible training and evaluation
observations for each paired comparison. Evaluate annual one-, two-, and
three-year horizons where available; evaluate monthly short horizons separately
when the seasonal workstream is ready. Do not extend evaluation beyond a
pathogen's observation window or across an unresolved reporting break.

Maintain an evaluation-use registry documenting which outcomes have already been
inspected or used to choose candidates. More rolling origins or nested fitting
cannot erase prior human selection. Reserve genuinely unexamined or prospective
evidence where possible; otherwise keep conclusions explicitly exploratory.

Fit transformations, model selection, diagnostic-mix scenarios, and prior tuning
using training data only. Reserve final evaluation windows from repeated tuning;
use inner temporal validation when selecting candidates. Specify how future
population and diagnostic covariates would be known at prediction time. Tests
using subsequently observed populations must be labelled conditional hindcasts.
Keep an as-of ledger for outcomes and covariates, including release dates,
revisions, reporting completeness, and unavailable future diagnostic covariates.
Use training-selected scenarios or forecasts for unavailable covariates and
propagate their uncertainty rather than substituting later observations.

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
  pilot usage, including difficult cases and memory headroom. Pass thread limits
  explicitly into containers and verify the resulting environment there; ordinary
  host exports can be removed by a clean container environment.
- Preserve dependencies: an audit must pass before its fit, training-only tuning
  before final evaluation, and result review before dashboard promotion.
- Begin with a small representative pathogen panel chosen for data completeness,
  diagnostic changes, seasonality, and sparsity. Scale successful experiments to
  remaining pathogens; predeclare the complete candidate/origin/seed matrix and
  total fit count. Bound unnecessary experiment combinations, not scientifically
  independent concurrency. Report failed candidates rather than dropping them
  from comparisons or selecting a lucky seed.
- Snapshot commands, code, inputs, seeds, package versions, and resource requests.
  Reuse identical completed tasks and saved draws where valid. Changed inputs or
  specifications require new fits. Define task identity from content hashes, not
  directory names; verify input/container/source fingerprints at worker start.
  Reuse only complete validated artifacts through an atomic completion record.
  Workers must verify prerequisite success and matching identities even when the
  scheduler dependency has completed. Maintain a complete task ledger and collect
  partial failures into the report. Recovery must be idempotent and retry only
  failed tasks with a diagnosed cause, preserving previous attempts.
- Produce one consolidated internal review archive per experiment batch, keeping
  large fit checkpoints on the cluster. Container changes are built on the build
  host, then smoke-tested on compute nodes before array submission.

## Review products and completion criteria

Deliver a concise per-pathogen comparison report, machine-readable metrics,
provenance manifest, and candidate-status table. Classify each candidate as
accepted for a stated use, exploratory, or unsupported by available data. Record
execution status, artifact validity, and scientific acceptance separately, with
explicit evidence for each gate and the frozen protocol defining acceptance
metrics, margins, and dependency-aware uncertainty across overlapping origins. A
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

## Prepared parallel investigation batch

The [parallel county batch](next_phase_parallel_batch.md) implements the immediate
investigations: saved-posterior stability, raw definitions, controlled Cyclospora
execution diagnostics and a numerically gated spline pilot. Its explicit candidate
priors and unequal posterior sample sizes are documented. These are exploratory
comparisons; monthly seasonality, testing adjustment and model promotion still
require the definition and validation gates above.

The [public dictionary review](foodnet_dictionary_review.md) now resolves several
event-date and testing-field meanings using the 2016/2020/2024 variable lists.
It narrows the remaining requirements to extract derivations, date handling,
identifier relationships and monthly observation coverage. Public schema matches
are not authorization to recode the current extract or replace accepted results.
