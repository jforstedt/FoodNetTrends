# Diagnostic classification with temporal, seasonal and spatial structure

Implementation update: monthly preparation has been reviewed, and the shared RW1/AR1 prior and synthetic execution checks are complete. The next candidate batch contains 48 site fits and 96 county fits (144 total), covering all six supported pathogens and both prespecified origins. Spline arms remain part of the registered extension but await their separate gate. See [model specification](monthly_classification_model.md), [launcher](monthly_classification_launch.md), and [independent review](monthly_classification_adversarial_review.md). The original protocol below records the target and gates; no fitted model is accepted by this update.

## Target and immediate action

The estimand is the probability of a CIDT+ label conditional on an eligible record
being labelled CX+ or CIDT+. CX+ can include combined-positive records. These
models describe the recorded diagnostic mix; they do not estimate test positivity,
detection probability, testing volume, adoption dates, or an incidence correction.
A case-derived monthly CIDT share must not become a same-month incidence predictor:
that would incorporate information from the outcome-generating case set and would
not establish a testing adjustment.

Prepare six pathogens simultaneously: Salmonella, Campylobacter, Shigella, STEC,
Vibrio and Yersinia. Keep the existing 486-county footprint, travel/geography
filters, literal classification definitions and specimen-date convention. The
monthly classification window is 2012–2019. The annual classification audit already
establishes these six have usable annual category contrasts, but does not establish
monthly or county-level support. Listeria and the two parasites are excluded on the
previously documented category-support grounds, not on favorable model results.

`prepare_classification_monthly.R` wraps the established raw-to-clean monthly
preparation and intercepts its already-selected records in memory. It reconciles
county-year totals, literal CX/CIDT site-year totals against the completed eligible
audit, and assigned plus unassigned category counts. It never exports case rows.
It saves a county-month classified-count RDS internally and portable aggregate
site/month, annual and date-by-category reports. This is six preparation jobs,
not six new model fits. A completed preparation status is not fit approval.

Existing total-count monthly panels cannot reconstruct the joint month/category
counts. Existing annual classification fits also cannot serve as monthly seasonal
controls. Re-reading source files to recover that joint table is necessary, while
reprocessing all MMWR or rerunning annual models is not.

## Prespecified comparison after the input gate

Use the same conditional-binomial outcome and denominator across every arm within
a comparison block. Zero-denominator cells have undefined observed share and no
binomial information: keep their locations in the latent prediction grid, mask
the likelihood, and exclude them from predictive scoring. Never interpret them as
zero CIDT probability or zero incidence. Retain the observed future classified-case
denominator as a conditioning quantity and explicitly call results conditional
hindcasts. Mask every post-cutoff CIDT outcome before fit/basis construction.

Two development origins are December 2015 and December 2016, each with exactly
36 subsequent months for scoring (through 2018 and 2019 respectively). Training
starts January 2012. These overlapping and previously examined periods are not
independent final validation. No cutoff is selected to favor a model.

The site/month block has shared temporal structure RW1, AR1 or the constrained
spline candidate, crossed with absent or common cyclic seasonality. This is
6 pathogens × 2 origins × 3 temporal forms × 2 seasonal settings = **72 fits**.
Keep partially pooled site intercepts and site/month extra-binomial latent effects
in every arm. Do not describe a site IID effect as county spatial smoothing.

The separate county/month block uses the identical conditional-binomial target
on county/month cells, with a static county IID effect versus a scaled BYM2 effect,
crossed with the same three shared temporal forms and seasonal presence/absence.
Keep site intercepts and county/month extra-binomial effects constant. This is
6 × 2 × 3 × 2 × 2 = **144 fits**, including its own IID controls. The ten graph
components and county identities must match the audited graph. BYM2 scaling and
constraints must handle disconnected components explicitly. Sparse county support
is a reason to inspect posterior identification and prior sensitivity, not to
pretend adjacency supplies laboratory/testing-denominator information.

These counts define the planned blocks, **not authorization to auto-fit every
block after file creation**. First verify monthly date/category reconciliation,
nonzero-denominator support, and synthetic fitting/scoring of the binomial
implementations. Spline fitting additionally inherits the saved-fit failure and
extrapolation review. Components already ready can run concurrently; an unresolved
spline gate must not hold RW1/AR1 preparation or implementation work. Do not compare
raw site/month and county/month log scores as interchangeable observations.

## Priors, diagnostics and decision rule

The annual classification priors were on a logit link: intercept Normal(logit(.1),
1.5²), site SD PC upper1.5 with tail.01, and cell SD upper1 with tail.01.
Carry these conventions into the monthly implementation as explicit candidates,
not established biological facts. Calibrate temporal function priors on the
training-only monthly grid and examine logit/probability prior trajectories before
freezing numeric monthly trend, spline and AR1 settings. Do not copy incidence
log-rate priors without this check; changing resolution also changes the meaning
of an independent cell effect. Spatial marginal SD upper1, tail.01 is an initial
prior-check candidate, and the BYM2 mixing prior must be specified and tested
before launch. Thus the model matrix is fixed here while final numeric new-prior
settings remain an engineering/prior-check gate, not an undocumented default.

Score held-out observed category counts with four independent posterior streams
and pooled estimates, using joint posterior draws and conditional binomial
predictive densities. Include relative density Monte Carlo errors, annual observed
and predicted category totals/shares, predictive coverage, site heterogeneity and
boundary probabilities. Annual predictive intervals must aggregate joint draws.
CPO is not an accuracy-ranking or acceptance gate after the earlier crosschecks.
Report temporal, seasonal and spatial component contrasts and interactions; retain
weak-alone candidates if the combination evidence is useful. Do not infer causal
laboratory mechanisms from fitted effects. Model execution is exploratory, and
Daniel's accepted incidence model remains unchanged.

## Integration interface and inputs

Run the new R script in existing `foodnet.sif` (preparation only) with seven args:
`RAW CLEAN MAPPING AUDIT OUT PATHOGEN ANNUAL_SUPPORT`.

- RAW: `/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat`.
- CLEAN: `output/20260911_140750/preprocessed/clean_mmwr.csv`.
- MAPPING: adjacent `clean_mmwr_preprocessing_report.csv`.
- AUDIT: `county_forecast_protocol.source_paths(root)[pathogen]['audit']`, validated
  with `validate_source` before submission; do not invent one shared audit path.
- ANNUAL_SUPPORT:
  `output/eligible_diagnostics_20260914_094654_276977/PATHOGEN/result/support.csv`.
  Validate its source plan, task status and outputs with the existing eligible
  diagnostics validator and hashes before preparing the new run.

Snapshot the new R script plus `prepare_monthly_county.R`, `county_matching.R`,
`reconcile_raw_county.R`, and `fit_county_pilot.R`. Bind raw/clean/mapping, annual
panel/audit evidence, eligible support/evidence, source and container hashes into
the launcher plan. Recheck before and after execution. Require both
`MONTHLY_PREPARATION_COMPLETE` and `CLASSIFICATION_MONTHLY_PREPARATION_COMPLETE`,
plus newly manifested outputs. Zero-unassigned checks and existing reviewed
Shigella specimen/source-month discrepancies need explicit reconciliation to
previous evidence; a category split does not create new date authority.

Portable outputs include `classification_site.csv`, `classification_annual.csv`,
`classification_date_issues_by_category.csv`, `classification_readiness.csv` and
`classification_support_checksum.csv`. `classification_county_month_INTERNAL.rds`
stays on the cluster. The larger launcher should collect these with source
snapshots, status records and SHA256 manifest in its aggregate review archive.

The only immediate input-dependent action is this preparation. It can run in
parallel with incidence spatial combinations and saved spline diagnostics; no
additional user-provided dictionary is required for literal label-mix accounting.
Independent laboratory volume/adoption/detection inputs would be needed for a
subsequent scientifically defensible incidence observation model.

## Preparation launcher

`python3 scripts/launch_classification_monthly_preparation.py` submits the six
preparation tasks together at two CPUs, 8 GB RSS request, 16 GB virtual-memory
limit and four hours per task, followed by one held collector. Scheduler memory
semantics remain those of the cluster. `--prepare-only` writes an unverified plan
that workers cannot execute. The launcher can also be prepared by the bundled
experiment launcher through `prepare(root, dest, verified=True)`.

It verifies the eligible-audit plan/task identity and manifested category support,
in addition to the existing raw/clean county evidence. Collection is fail closed
on global integrity failures, emits a partial summary when tasks are missing,
and excludes `_INTERNAL` artifacts from the portable archive. The completed
archive supports the monthly-support decision; it does not launch binomial fits
automatically or declare monthly surveillance coverage certified.

Local checks: `python3 -m unittest discover -s tests -p
 test_classification_monthly_launcher.py` (five tests) and `Rscript
 tests/test_classification_monthly_preparation.R`. These exercise the six-task
matrix, mocked verified evidence, altered support rejection, unverified-worker
refusal, private-output exclusion, Python 3.6 syntax, category reconciliation and
date/denominator edge cases. Actual SAS ingestion remains a cluster validation.
