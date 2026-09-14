# Conditional-classification result review

The portable review verifies the completed 144-cell experiment against the
original classification preparation archive. It checks matrix and seeds,
source/output bindings, recorded private-input identity, prior calibration and
source hashes, settings, final numerical diagnostics, RNG records, input
checksums where files are available, aggregate truth and complete score domains.
Raw county panels and saved fits remain on the cluster; their contents are not
independently re-read by this PC review. Recorded hashes and actual byte checks
are reported separately.

```bash
python3 scripts/review_monthly_classification_results.py /path/to/monthly_classification_models_RUN.tar.gz --source-bundle /path/to/broader_combinations_RUN.tar.gz --output output/classification_review_NEW_LOCAL
```

Production validation still requires the saved fit by default. The explicit
portable-review mode omits only that unavailable-file existence check; it retains
all aggregate, support, identity, numerical and sampling checks. No placeholder
fit is created and no archived code is executed.

Component contrasts compare seasonality, temporal structure and static spatial
borrowing only within the same resolution, pathogen, origin, state/year and
support. Two-way and three-way interactions preserve all terms of the declared
factorial comparison. A positive interaction does not establish that its model
beats the better reference. Missing information stays missing, never a favorable
zero score. Site-month and county-month log scores are not directly ranked.

The figure uses matched nonseasonal site models to show recorded annual
classification shares, expected future shares and predictive intervals. It is
not a display of post-hoc best-scoring models. Future denominators are observed;
these are conditional retrospective predictions of CIDT among CX-or-CIDT records,
not incidence, testing positivity, detection probability or assay-adoption dates.

## Disposition

The completed development comparison favors RW1 over the tested stationary AR1
package for this conditional outcome. Seasonal and spatial contributions are
heterogeneous and often small relative to posterior sampling variability.
This is target-specific evidence, not a revision of the separate incidence-model
findings or a reason to discard components from future justified combinations.

Saved annual-share trajectories and site errors reveal persistent calibration
limitations. Better average score does not make every site prediction better,
and broad intervals alone are not reliable prediction. Retain the full factor
comparison, uncertainty diagnostics and poor-performing locations. Do not promote
these fits as an incidence adjustment or production forecasting upgrade.

The numerical history includes a successfully recovered internal INLA attempt.
An empty warning file does not establish an uninterrupted computation; task logs
are reviewed separately. A final passing fit does not itself require refitting,
and this history is preserved rather than hidden.

The next step is targeted interpretation of saved trajectories and the already
prepared, independent county incidence-error audit. No full repeat of the 144
classification fits is warranted. More posterior samples may resolve close
Monte Carlo comparisons, but cannot repair systematic bias or undercoverage.
Any new temporal specification needs a recorded hypothesis, prior checks and a
frozen comparison against these controls before fitting; existing development
periods must not be labelled independent validation.

All numerical findings and plots remain under ignored `output/`. The accepted
state model, fitted classification models, priors and observation rules are
unchanged by this review.
