# Final validation plan for spatial incidence forecasts

Status: planning only. No independent final-validation period is currently
established, no new data availability is asserted, and this document launches no
jobs. Daniel's accepted state model and existing outputs remain unchanged.

## What can and cannot be concluded now

The completed spatial × temporal × seasonality comparisons support exploratory
model development. They ask whether replacing a static IID county intercept with
static BYM2 borrowing improves forecasts within otherwise matched model/prior
packages. They do not establish independent forecast reliability. Reusing an
origin with a different spatial effect, seasonal term or temporal family does not
make its outcomes unseen.

The [monthly evaluation inventory](monthly_validation_inventory.md) records that
the prepared domain is 2004–2019 for eight pathogens and 2004–2017 for
Cryptosporidium. Historical evaluated years collectively cover 2012–2019 and
2012–2017, respectively; the earlier years have informed training and input
exploration. Annual county analyses and later annual/state analyses also count
in the outcome-access history. Changing from annual to monthly resolution does
not erase that history. The existing origins must not be relabelled independent
final validation.

Keep the present comparisons, recoveries and diagnostic follow-ups in the
**development** ledger. Final validation requires an eligible, sufficiently
protected evaluation period and a frozen decision protocol. If such a period
cannot be established, the honest next deliverable is an explicitly exploratory
external-period assessment or a prospective validation plan, not a confirmatory
label on another historical run.

## Resolve the evaluation domain without revealing outcomes

First create a metadata-only extension inventory using the source vintages and
access history already available. This is a proposed audit, not evidence that
new county panels exist. Record geography keys, eligible dates, denominator
availability, reporting-rule evidence, source hashes and previous outcome access.
Do not export held-out case totals, rates, forecast errors or model rankings
while deciding whether outcomes can be protected. An analyst who has already
seen relevant aggregates must record that exposure rather than call themselves
blinded.

The known constraints are:

| Scope | Constraint for a proposed later-period evaluation |
|---|---|
| Cryptosporidium | The current surveillance contract ends in 2017. There is no eligible later holdout established by the present inputs. Do not extend this endpoint to obtain a validation sample. |
| Other pathogens after 2019 | Later years are outside the current monthly input contract. The annual/state work used newer outcomes, so access history must be reviewed before assigning independence. |
| A possible 2020–2022 interval | This is an unassessed candidate interval, not an available or reserved holdout. It requires new county/exposure reconciliation and a prespecified pandemic-era interpretation. |
| Connecticut after 2019 | Reconcile historical counties and planning regions using one consistent geographic system. The town-derived historical-county population candidate is not automatically adopted or surveillance-certified. Never add historical-county and planning-region populations together. |
| Campylobacter | The existing trend ceiling is 2023 pending a separate diagnostic-reporting comparability assessment. A validation plan cannot bypass it. |
| Colorado and Yersinia | Preserve the historical county scope and existing pathogen-specific safeguards. Expanded coverage requires an explicitly justified target and matching denominator. |
| Optional reporting in 2025 | Availability of records does not establish a complete reporting window. Do not treat these years as automatically eligible. |
| Monthly continuity | EXPLORATORY_ASSUMED_CONTINUOUS remains an acknowledged assumption. Nonzero case records do not certify uninterrupted reporting, and missing records are not automatically zero cases. |

These constraints follow the [input safeguards](surveillance_input_safeguards.md),
[coverage reconciliation](county_coverage_reconciliation.md) and
[monthly protocol](monthly_comparison.md). A public denominator source cannot
establish pathogen surveillance coverage by itself. Population vintages and
reporting delays must be recorded explicitly. Known eligibility gaps must be
resolved or excluded according to a rule fixed before outcomes are inspected.

If protection is possible, record who can access the evaluation outcomes, what
has already been seen, and when predictions and decision rules were frozen.
An independent evaluator or sealed scoring workflow can reduce further leakage;
neither retroactively makes previously inspected outcomes independent. If all
eligible later outcomes have informed model development, freeze forecasts for
future eligible observations with an explicit reporting-completeness lag instead.

## Freeze the comparison before scoring

Use the completed development evidence to nominate candidates, then create a
hashed candidate register. For each pathogen it must identify the scientific
question, candidate and comparator, exact temporal family, seasonality setting,
county structure, priors, formula/basis, training start and end, graph,
observation policy, exposure policy, software/container versions, seeds and
numerical recovery rules. Explain a pathogen-specific choice using the rationale
register; a favorable average score alone is insufficient justification.

A primary spatial test compares a nominated BYM2 package against its **matched
IID package** on identical outcomes, training data and exposures. Keep all other
terms fixed to isolate the spatial change. A separate simpler historical-rate
benchmark can provide context, but its likelihood and interpretation must be
specified. Weak standalone components remain documented combination candidates;
they need not all enter a final validation batch. Any additional factorial
contrasts must be declared secondary in advance, with no post-score choice of
which comparisons count as primary.

Retain three annual horizon blocks within a 36-month forecast when that full
eligible window exists. If it does not, specify the shorter intended horizon
before scoring; never silently drop a difficult final year. Choose a common
primary weighting convention before analysis: retain the existing mean
county-month log score within state/horizon and equal weighting across states.
Report pathogens and horizons separately. Do not let high-incidence states,
county counts or selectively available origins redefine the comparison.

Realized future population produces an exposure-conditional retrospective
hindcast. Operational validation instead needs a population/exposure forecast
or vintage available at the forecast date, with its uncertainty and target
stated. These are different experiments and must not share an unqualified
"forecast validated" label.

A comparison with Daniel's model would require new, training-only state fits and
predictions on a common state-level target, common eligibility and common
exposure convention. Existing full-period state fits cannot serve as a leakage-free
forecast comparator. Such a comparison is optional and separate from testing the
incremental county spatial effect; county models do not automatically replace
Daniel's model.

## Geography and latent structure remain part of the hypothesis

The current structural reference is the audited 486-county graph with 1,210
undirected edges and ten components. It uses the documented historical adjacency
and edge rules. Retain exact node identifiers, county/state mapping, graph hash,
scaling, constraints and BYM2 mixing prior in the frozen package. The current
spatial term is a **static county intercept**; state-specific temporal terms
remain distinct. Neither this term nor a common seasonal effect supplies
county-specific changing trends or missing ascertainment information.

Any later-period geographic change needs an explicit crosswalk and exposure
reconciliation. Do not silently induce a subgraph, reuse area indices on a
changed map, or treat a new county as if its effect had been estimated. Require
permutation-invariant mapping, disconnected-component scaling/constraints and an
explicit isolated-node policy. A changed footprint or time-varying graph changes
the estimand and requires a new specification and engineering/prior checks.

This plan tests temporal forecasting in the declared observed county footprint.
Generalization to unobserved counties is a different spatial holdout experiment;
it is not established by good temporal forecasts in previously observed counties.

## Scores, calibration and practical reliability

Evaluate proper predictive log scores for future observed county-month counts.
Use matched cell keys and the same predictive target within each pair. These are
marginal count scores; their averages are not joint log densities of an entire
state or year. Keep Monte Carlo error and stream stability visible.

Report predictive interval coverage and width, interval scores, point error,
annual bias, zero-count calibration, and state/catchment predictive totals by
horizon. Annual intervals must be formed by summing the same joint predictive
draws, not by summing interval endpoints. Expected-incidence uncertainty is not a
predictive interval for future counts. Include medians alongside means, the
mean-to-median relationship, high quantiles and the influence of extreme draws.
More coverage obtained only through very wide or unstable tails is not sufficient
for acceptance.

Before final outcomes are scored, the protocol must fix a minimum practically
useful score gain, acceptable calibration/interval-width and bias tradeoffs,
tail-stability criteria, numerical precision tolerances, and the intended use
scope. Those values cannot be derived from final-validation results. Where the
current development evidence and intended use do not justify a value, mark it
unresolved and keep scientific promotion blocked; do not fill the gap with an
arbitrary pass threshold. The present document does not assert that these
application-specific decision margins have already been agreed.

Use paired comparisons and preserve state/horizon heterogeneity. Counties,
neighbors, months, overlapping origins and posterior streams are not independent
replicates. Streams estimate Monte Carlo variation, not uncertainty in future
performance. Any confidence interval or formal superiority claim needs a
prespecified dependence-aware method and adequate evaluation replication.
Otherwise report effect sizes and calibration descriptively and limit the claim.
Do not manufacture a universal pathogen winner by pooling correlated cells.

## Diagnostics and acceptance are separate gates

Existing numerical checks, provenance validation, training-mask tests, simulation
screens, graph tests and saved-fit sampling diagnostics can run now without a new
holdout. They establish implementation properties, not independent predictive
validity. Preserve failed attempts and apply only prespecified execution recovery;
changing priors or formulas after seeing validation outcomes returns the model to
development and requires a new evaluation opportunity.

CPO is not a ranking or acceptance gate. Successful solver status, more posterior
draws, or agreement between sampling streams does not establish good calibration.
Conversely, a Monte Carlo precision issue should first be assessed from saved
fits, preserving their identities, before commissioning broad refits.

Final reporting must distinguish execution completion, numerical eligibility,
exploratory predictive evidence and scientific acceptance. Acceptance, if earned,
is limited to the validated pathogen, target, footprint, reporting policy and
horizon. Unsupported combinations remain visible in the ledger. No dashboard
promotion is automatic; no accepted state output is overwritten.

## Concrete next actions and blockers

1. Finish the independent saved-result review and candidate rationale register
   from the existing development archives. This uses saved evidence and requires
   no repeat of completed spatial fits.
2. In parallel, specify the metadata-only later-period audit and outcome-access
   ledger. Determine whether eligible county/exposure inputs exist and whether
   any candidate outcomes remain sufficiently protected. Do not assume 2020–2022
   is ready or independent.
3. Resolve the geography/exposure and reporting-policy decisions for any proposed
   extension. Retain the current assumed-continuity status unless better evidence
   supports a stronger statement.
4. Freeze candidate packages, matched comparators, horizons, evaluation metrics,
   dependence treatment and practical acceptance margins. Keep scientific
   promotion blocked if the intended use or decision margins are unresolved.
5. Only after those gates, implement one parallel batch for all eligible frozen
   comparisons, with a complete task ledger and held collector. No jobs are
   authorized or submitted by this planning document. If there is no protected
   eligible period, use an honestly labelled exploratory external-period study
   or reserve prospective outcomes rather than repeat the old origins as proof.

The immediate blockers to **independent final validation** are the absence of an
established protected eligible period, unresolved later-period geographic and
reporting contracts, and an unfrozen final decision rule. They do not prevent a
bounded exploratory release with explicit limitations or independent local
engineering work.
