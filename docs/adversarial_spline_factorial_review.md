# Independent review of the monthly spline factorial

Reviewed 2026-09-14, published source revision `5336bcb`, while the 54 new spline
fits were running. This review inspected the launcher, saved-fit adapter,
posterior scoring engine, prepared basis, control reuse and comparison algebra.
It did not change the running snapshot, refit real data, or assess results that
have not arrived. Daniel's accepted state model is outside this experiment.

## Disposition

No execution or scientific blocker requiring interruption of this batch was
found. One reproducibility limitation was confirmed in the shared posterior
sampling engine. It affects exact regeneration from a recorded seed, rather
than demonstrating biased forecasts or invalid model fits. Resolve it before
claiming bit-for-bit reproducible diagnostic regeneration. Retain the current
reports, their checksums and their protocol identity.

## Confirmed finding: incomplete RNG specification

Severity: moderate for reproducibility; not a reason to discard current fits.

`scripts/audit_saved_monthly.R:58` passes a nonzero seed to
`INLA::inla.posterior.sample()`, but R's RNG is seeded only afterward for
negative-binomial predictive simulation. The locally installed, pinned INLA
26.08.07 implementation first chooses hyperparameter configurations using R's
`sample()`. Its `seed` argument is subsequently passed to the latent Gaussian
sampler. Thus the first posterior batch inherits the calling process's R RNG
state. Later batches also depend on the preceding predictive simulation state;
the recorded base seed alone does not completely specify initial generation.

This was reproduced against an existing synthetic spline fit, without fitting
another model: 100 draws, observation indices 1:4, INLA seed 640000001,
`num.threads='1:1'`, `skew.corr=FALSE`. Changing R's seed from 100 to 101 changed
both selected hyperparameter configurations and latent draws. Repeating R seed
100 together with the same INLA seed reproduced the entire sampled result
exactly. The local evidence log is `/tmp/audit_spline_rng.log`.

Correction prepared locally as the opt-in `explicit_config_v2` diagnostic protocol
(the default remains `legacy_v1`, and no current caller or snapshot is changed):

- The helper sets R configuration-selection seed `stream_seed + 20000 + start`
  immediately before each posterior call; the latent sampler uses
  `stream_seed + start`, and predictive simulation retains
  `stream_seed + 10000 + start`.
- A separate `rng_protocol.csv` records the opt-in convention, offsets, R RNG
  kind, R version and INLA version. Tests exercise regeneration despite unrelated
  preceding RNG activity. Exact reproduction also requires the same software
  environment and fit artifact.
- Leave this running snapshot unchanged. If exact regeneration is needed,
  resample saved fits under the new protocol and compare Monte Carlo stability;
  this does not require model refitting. Do not silently replace old controls
  with newly sampled reports or claim their original bytes are regenerated.

The same shared engine also generated the reused controls. This finding is not
a spline-specific change to the likelihood, priors, exposure or held-out truth.

## Execution and provenance checks

The matrix has 54 unique new arms, all nine pathogens and three origins each,
seasonality off/on. Reuse brings the experiment to 162 cells. Cryptosporidium's
2011/2013/2014 origins respect the established 2017 endpoint; other origins are
2011/2013/2016. The sampler seeds remain within the engine's integer bounds.

Prepared basis manifests bind the entire prediction and training CSV bytes,
generation session, generator and model/basis sources. Workers hash-check the
copied basis and code before and after execution; consumption checks add domain,
slope, rank, orthogonality and scale validation. This addresses the previously
identified gap where training-only constraints could not authenticate arbitrary
prediction rows. No mgcv rebuild is required on the execution host.

Source controls are validated against task status, source plan digest, output
hashes and canonical held-out truth. New arms use candidate and annual audit
paths from the verified original factorial and retain their runtime hashes.
All 486 county grids and 36 forecast months must match each paired origin.
Changes to original controls or copied reports fail integrity checks.

The collector suppresses contrasts on global integrity failure and removes
stale contrast files. Missing tasks remain explicit; it can emit comparisons
for complete subsets. Such partial reports must not be presented as a complete
162-cell experiment. The independent review tool should verify the expected
matrix, summary status, copied report bindings and derived tables afresh.

## Scientific and scoring checks

The spline arm retains static county IID effects, state intercepts,
negative-binomial observation model and person-year exposures. Its deliberate
change is a state temporal spline with a proper slope prior, optionally combined
with the shared annual cycle. It is not a county temporal spline or a replacement
for Daniel's state model. Temporal families have different prior packages;
comparisons cannot isolate basis shape independently of those priors.

Outcomes after the cutoff are masked before fitting. The adapter verifies
masking, forecast row order, exposure, family, effect identity and spline
specification. Posterior sampling selects APredictor log-rate entries and
multiplies by exposure once. The saved synthetic fixture places observation
APredictor rows first in `summary.linear.predictor`, consistent with the shared
latent-SD report indexing. Existing actual-INLA synthetic tests additionally
compare the audit against the independent exposure-aware sampler and exercise
both seasonal arms. This review did not rerun those model fits.

Each spline-versus-reference comparison uses the same four-arm algebra:
seasonal and nonseasonal temporal contrasts, seasonality within each temporal
family, and their difference-in-differences. Equal-site contrasts require all
ten sites. This preserves the possibility that two components help jointly
without claiming a biological interaction.

Seasonality-off means omission of the free cyclic random effect. Both spline
arms still use the same training-derived projection against calendar month
contrasts. That projection is part of the declared basis construction and must
not be interpreted as an independent estimate of pathogen seasonality.

Acceptance remains pending: review annual bias, interval width and coverage,
tail concentration, per-cell density MCSE, horizon deterioration and competing
model behavior together. Four-stream spread measures simulation variability,
not a confidence interval for generalization. Overlapping origins and repeated
use of these development years prevent treating all evaluations as independent
untouched validation. A score gain alone is insufficient for promotion.

## Verification performed in this review

- `python3 -m unittest discover -s tests -p 'test_monthly_spline_factorial.py'`:
  all nine tests passed, including basis/source tampering, runtime binding,
  contrast algebra, missing arms, corruption suppression and Python 3.6 syntax.
- Inspected the pinned INLA sampler implementation locally and reproduced the
  two-RNG issue on a saved synthetic spline fit.
- `tests/test_monthly_rng_protocol.R` passed with pinned INLA and the saved
  synthetic fixture: explicit v2 invariance to ambient R RNG state, exact legacy
  semantics, rejected unknown protocol, two complete four-stream audits with
  identical scores/tails/joint draws, version metadata and unchanged input
  checksums. No model was refitted.
- Checked synthetic saved-fit APredictor ordering independently.
- Reviewed model/scoring source and existing actual-INLA synthetic test contract;
  no new patient-derived data were read and no cluster jobs were submitted.
