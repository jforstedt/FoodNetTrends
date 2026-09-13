# County forecast prior fixed at the training origin

New forecast fits use `scripts/county_forecast_model.R`, version
`training_origin_rw1_v1`. This is a correction to the **county forecast model**,
not a change to the published state spline, the historical county sensitivity
fits, or previously saved results. Earlier forecasts used a centered/scaled RW1
over the entire training-plus-future domain. Changing that endpoint changed the
prior over the already observed years.

## Parameterization

For an origin with `T` consecutive training years, let `Q_T` be the unscaled RW1
precision structure and let `c_T` be the geometric mean of the diagonal of its
generalized inverse under a sum-to-zero constraint. The prior for each state
temporal process, and for each county temporal process when present, retains
`P(standardized SD > 0.5) = 0.01` on the **training-domain** scale.

The implementation uses an unscaled RW1 over the requested domain. Its PC prior
has `P(innovation SD > 0.5 / sqrt(c_T)) = 0.01`. Equivalently, the innovation
precision is the standardized precision multiplied by `c_T`. An explicit linear
constraint sets the average over the first `T` coefficients to zero; every future
coefficient has weight zero in that constraint. INLA applies this constraint to
each replicated state/county process. Consequently, future values continue from
the last training value by independent zero-mean Gaussian increments conditional
on the shared precision. No future drift term is introduced.

Appending future increments leaves the prior covariance on the existing domain
unchanged. The scale may legitimately differ between **training origins** with
different training windows; it must not differ merely because more future
prediction rows are requested at the same origin. The existing state-intercept,
BYM2/IID county, negative-binomial size, and other prior specifications remain as
in the county comparator. Precision summaries for the temporal terms are now on
the innovation scale, so they must not be directly compared with the old scaled
precision summaries without conversion.

The [INLA RW1 specification](https://www.inla.r-inla-download.org/r-inla.org/doc/latent/rw1.pdf)
defines the process through independent increments and describes its intrinsic
rank deficiency and scaling. This project's training-only centering and fixed
origin scaling are explicit implementation choices.

## Numerical gate and provenance

`tests/test_county_forecast_invariance.R REPORT_DIR` checks exact prior covariance
invariance at three training-window lengths. It also fits spatial/IID models,
with and without county temporal effects, to identical synthetic training data
with one versus three future years. It checks shared predictor marginals,
hyperparameter summaries, the actual saved constraint matrices and conditional
latent means, and joint predictive aggregates. Tolerances are recorded before
fitting: 2% for standardized marginal/relative differences, and a distribution-free
two-sample empirical-CDF bound with alpha 0.001 for 1,000 joint draws. Every model
check must pass; missing checks cannot satisfy the gate.

Separate Laplace-corrected marginal means are not an exact test of a joint linear
constraint. The gate therefore checks INLA's saved constraint matrix and
conditional latent means, alongside the predictive invariance checks. It does not
loosen the constraint test because marginal corrections differ slightly.

Each new forecast exports `forecast_specification.csv` and
`temporal_constraint.csv`. `run_forecast(..., horizon=3)` first validates the full
source panel and then restricts the experiment to the origin plus three years.
The historical default `horizon=NULL` retains the available held-out period for
callers that have not requested a shorter horizon. All predictions still
condition on recorded future population denominators and known geography.

Passing this gate establishes numerical consistency on its checked cases. It
does **not** establish posterior-tail accuracy, predictive calibration, independent
validation, or scientific adoption. Joint sampling still uses
`skew.corr=FALSE`; the separate calibration workstream must assess that
approximation for the intended sparse and dense settings.
