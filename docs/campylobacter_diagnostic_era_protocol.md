# Campylobacter diagnostic-era sensitivity

Prepared after the regional history audit, 15 September 2026. This is an
exploratory outcome-definition sensitivity, not an incidence correction or a
replacement for the state model.

## Question and scope

The supplied Campylobacter extract contains only CX+ labels through 2011 and
additional CIDT+ labels from 2012. The early GA/TN prediction misses overlap that
boundary. These facts do not establish when laboratories first used CIDTs or
which changes are biological. The new question is whether the local-seasonality
comparison behaves differently when the recorded CX+ outcome is considered
separately, with the population, spatial footprint and other model components
held fixed.

Prior monthly classification models predicted the CIDT proportion conditional
on classified cases. They do not answer the same question as a CX+ count model
with a population offset, and are not substituted for these fits.

## Matched design

Six Campylobacter comparison tasks: origins 2011, 2013 and 2016, each with local seasonal
deviations off/on. Both arms retain the common annual seasonal cycle, state
intercepts, state-specific RW1 trajectories with shared smoothing precision,
county IID effects, negative-binomial likelihood and original priors. Weather
and age are disabled to isolate the seasonal comparison. No adjustment is made
only for Georgia or Tennessee; all ten states remain in every comparison.

Training starts in 2004 and ends in December of each origin. Each holdout spans
the following three complete years. CX+ is an exact supplied category label,
not a claim of constant testing sensitivity or a reconstructed culture-only
biological incidence series. Holdout counts remain masked during fitting.

Reuse the six existing combined-outcome fits and their reports. The 2013/2016
origins already include CIDT+ in training, but neither is asserted to represent
stable testing. Comparing origins also changes training length and evaluation
years; it does not isolate an era effect. Existing combined-outcome mean local
seasonality gains are positive at all three origins, so this design investigates
comparability and regional calibration, not an assumption of global failure.

Preparation must bind the original raw/clean source and frozen candidate, retain
the original case eligibility/date logic, and reconcile combined counts before
forming the CX+ subset. County-month CX+ counts must be nonnegative integers
bounded by combined counts. Counts must reconcile with source category summaries;
population exposure and county-month keys must remain unchanged. Missing or
unrecognized source classifications must not be silently assigned to CX+.

## Computation and review

Run the six independent tasks concurrently after a visible preparation job.
Only four require new fits (2013/2016). For 2011, preparation must prove that
CX+ and combined training counts coincide; the worker additionally verifies the
saved fit identity, training counts, keys and exposure. It then reuses that fit
and scores the narrower held-out CX+ outcome. If those checks fail, stop rather
than silently refitting or relaxing the equivalence requirement.
Use the hash-bound original monthly-preparation image for SAS import, with its
own R packages and no INLA-library override. Check the required import packages
before reading data. Fitting and scoring reuse the established INLA container,
compiled library and frozen fitter. Record both runtime identities. Four
streams of 1,000 posterior draws per CX+ task provide an initial numerical check;
the saved combined reports may have more draws. Report this difference rather
than interpreting unequal Monte Carlo noise as a scientific effect. No automatic
retry with changed priors or alternate formulations is allowed.

Review local-minus-common seasonal scores within each target and origin, with
state/horizon intervals, widths and numerical diagnostics. Never compare raw
log-score levels across CX+ and combined counts to select a winner: the target
outcomes differ. Contrast patterns and calibration descriptively; an apparent
benefit on CX+ is not proof of removing ascertainment bias. A CX+ model does not
predict total cases unless a separate, justified observation model is supplied.

If discrepancies remain, consider temporal extrapolation or observation-process
assumptions based on the complete results. No known-future category shares enter
a forecast predictor. No broad refit, automatic model promotion or default
outcome change follows from successful execution.

County-level fitted objects and truth remain INTERNAL on the cluster. Portable
reports contain state-level diagnostics and provenance. The code is intended
for the existing Git workflow; no manual bundle upload is required.

## Launch and local verification

From the cluster repository root after pulling this branch and loading
Singularity, run `python3 scripts/launch_campylobacter_cx_comparison.py`. The
launcher immediately submits a visible preparation job, followed by the six
tasks and a held collector. It prints the preparation job, log and archive paths.

Synthetic tests exercise subset counts, full zero-count support, population
conservation, exact training reuse, metadata and report validation. Actual local
INLA tests exercised the local-seasonality fitter, checkpoint and four posterior
streams, plus the common-seasonality fitter and saved-fit adapter. These do not
replace validation of the real cluster inputs, which must pass before submission.

The optional real-INLA tests require the frozen helper directory from the
completed covariate run. Set `CX_FROZEN_SCRIPTS` to that run's `bundle/scripts`
when running `tests/test_campylobacter_cx_model.R --inla` or
`tests/test_campylobacter_cx_baseline.R` in a checkout without those helpers.
This keeps the diagnostic launch independent of uncommitted local covariate code.
