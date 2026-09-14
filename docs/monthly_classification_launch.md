# Monthly conditional classification experiment

This launcher fits all six supported pathogens simultaneously, using the completed
monthly classification preparation. It describes CIDT+ labels conditional on
eligible CX+/CIDT+ records; it is not an incidence correction or an estimate of
laboratory testing volume, detection, or adoption. Daniel's accepted incidence
model and existing fits remain unchanged.

The fixed matrix has 144 fits: six pathogens × two origins (December2015/2016) ×
RW1/AR1 × seasonality absent/present × three analysis structures. The structures
are site/month with partially pooled site intercepts, county/month with IID county
intercepts, and county/month with static BYM2 county intercepts. Site models use
`spatial=none` to distinguish site pooling from county spatial smoothing. There are
48 site fits and96 county fits. Spline combinations remain planned after their
separate extrapolation and prior checks; no candidate is silently discarded.

Training begins January2012. Each origin predicts the next36 months, conditional
on observed future classified-record denominators. These overlapping development
origins are not independent final validation. All post-cutoff category outcomes
are masked before fitting. Zero-denominator cells contribute no binomial
information and remain in the latent grid. Undefined scores are missing, never
zero. Annual predictions sum joint posterior predictive draws. Site and county
raw log scores describe different observational units and must not be directly
ranked against one another.

The classification source is the completed `classification` branch of
`broader_combinations_20260914_130328_942214`. Preparation verifies its plan identity, frozen preparation code, task status,
annual-support accounting and all derived output hashes. It binds the
source plan and provenance into the new plan; workers verify the actual consumed
panel, associated preparation outputs, annual support, source plan, container,
graph and copied scripts before and after fitting. The original raw SAS file and old preparation container are not model inputs and
are not rehashed during this launch. Their recorded hashes remain historical
lineage bound through the source plan and task completion records; the new plan
explicitly marks them as retained historical hashes rather than newly verified
raw data. Consumed derived panels and the actual INLA runtime container still
receive current content checks. This avoids unnecessary upstream rereads without
skipping the checks relevant to these fits. Complete same-year
specimen dates define months. Missing auxiliary source-month values do not remove
assigned specimen dates; previously reviewed valid-source discrepancies retain
the specimen-month convention and must match the permitted pathogen inventory.

The model and prior-check scripts are frozen with the scorer. Verified launch requires
`analysis_configs/monthly_classification_priors/manifest.json` with
`PRIOR_CHECK_PASS`, unchanged model/prior/graph source hashes, and unchanged
prior-only report hashes. These reports are copied into each experiment snapshot;
this is a prior-check gate, not scientific acceptance. Workers require
fit_ok and mode_status0 and unchanged model identities. New logit-scale temporal
priors and boundary/separation cases must pass local prior/synthetic checks before
publication. Four independent streams of2000 draws use explicit R, INLA and
predictive seeds, plus pooled8000-draw summaries. Collection checks state/year
category totals against the separately bound site panel, score domains, count
bounds, intervals and task checksums. Partial results are archived with failures
explicitly listed. Completion does not confer statistical acceptance, certify
monthly coverage, or promote a dashboard model.

Run `python3 scripts/launch_monthly_classification_models.py` on the SGE host with
Singularity loaded. The command copies only small code, protocol, graph and prior
files, then submits a visible `foodnet_class_prepare` scheduler job and prints its
job ID, preparation log, collector log and archive paths. Preparation requests one
CPU, 8 GiB RSS, 16 GiB virtual memory and 4 hours; it appears in `qstat` while queued or
running. No raw-data, derived-panel or container hashing occurs before that job
is submitted. The preparation snapshot and original code hashes are checked
before and after preparation; source edits while it is queued fail closed. Its
log reports timestamped stages and elapsed times for each pathogen’s input
checks, prior calibration, snapshotting and the runtime container hash.

Once those checks pass, it submits one uncapped 144-task array, each requesting 4 CPUs,
52 GiB RSS, 68 GiB virtual memory and 48 hours, then a held one-CPU collector. These
are resource ceilings, not runtime predictions. Do not resubmit because model-array entries have not appeared while the visible
preparation job is verifying inputs. A sibling `_preparation` directory contains
the pinned preparation code and submission record. The final run folder is
created by preparation. This change applies to new launches; already submitted
experiments continue with their frozen code and should not be restarted. `--prepare-only` creates an
unverified plan that workers refuse to execute. Portable archives exclude
`_INTERNAL` panels, fits and posterior draws.
