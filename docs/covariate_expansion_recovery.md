# County covariate sampling recovery

The original expansion seed schedule began at 900,000,000 and advanced by
1,000,000 per task. Task 102 crossed the saved-posterior sampler's permitted
base-seed maximum of 1,000,000,000. The missing boundary test was a launcher bug,
not evidence against the affected pathogen models. The original archive, plans,
fits, warnings and failures remain unchanged.

New expansion launches start at 200,000,000, and R rejects unsupported seeds
before loading source helpers or fitting. Regression tests enumerate every
task, posterior stream, batch and RNG role, and verify the original immutable
plans remain readable for recovery. Changing posterior-sampling seeds does not
change fitted model parameters or the statistical specification.

The targeted recovery preserves 173 completed results. It rescores 186 saved
fits, provided their original task, numerical status, priors, masked training
data, held-out truth, exposure, covariates and predictor mapping all validate.
Source checkpoint hashes are recorded and checked on HPC; those private fits
are not included in the portable archive and were not reopened on the PC.
Recovery scores use four 1,000-draw streams and bounded, disjoint base seeds
starting at 600,000,000. Original fitted objects are never rewritten.

One Vibrio model (RW1, origin 2016, regional seasonality off, lagged weather,
age off) failed the numerical gate before saving a valid checkpoint. It receives
one explicit new attempt using a single fitting thread. Formula, priors,
likelihood, data and acceptance gates remain unchanged; an aborted numerical
correction is still rejected. This is an isolated numerical retry, not automatic
retry-until-success or model selection. If it fails, report the remaining gap.

`scripts/launch_covariate_recovery.py` submits a visible preparation job before
heavy hashing. Preparation then submits one uncapped 187-task array: 186 scoring
tasks and the isolated numerical retry. Each requests two CPU slots and the
existing 52 GB RSS/68 GB virtual-memory resources; the retry fits with one
thread. Scoring tasks never call a fitter. A held collector combines these with
the preserved results, validates paired truth, and writes matched contrasts and
a portable archive even if some tasks fail. No container rebuild is needed.

```bash
git pull --ff-only personal feature/county-covariates-seasonality && module load singularity && python3 scripts/launch_covariate_recovery.py
```

Do not relaunch the full expansion to recover scoring. The completed results
and existing comparisons are retained. Recovered historical conditional scores
remain development evidence, not independent validation or a production-model
acceptance. Patient data and internal checkpoints stay on the cluster.
