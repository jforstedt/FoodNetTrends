# Exploratory county spline candidate

This candidate changes the temporal family of the experimental county forecast, leaving the accepted state model and existing county random-walk code unchanged. It is not an exact reproduction of Daniel's fitted model or prior distribution.

## Training-only construction

`prepare_county_spline_basis(years, cutoff, k=6)` requires mgcv. It constructs a univariate thin-plate regression spline using **training years only**, with rank min(6, number of training years). Prediction uses that saved basis. Penalized eigenvectors are whitened by their penalty eigenvalues; their training intercept and linear projections are removed. The remaining nonlinear design is scaled so its geometric mean training pointwise variance is one at coefficient precision one. Appending future years therefore cannot alter the training basis or the prior for earlier predictions.

The null-space intercept is represented by existing state and static county effects. The remaining linear component is centered at the mean training year and divided by the training-year range. Each state and county has a proper independent slope prior N(0, 0.5²). This means a training-span log-rate difference has prior SD 0.5. It is an explicit new modeling assumption, not a paper-derived prior. Nonlinear state coefficients share one PC precision hyperparameter, and nonlinear county coefficients share another: P(SD > 0.5)=0.01. These match the random-walk candidate's nominal standardized nonlinear SD bound, but they do not make the functional priors equivalent. State and county temporal contributions overlap and are distinguished through proper pooling priors; their individual decompositions must not be interpreted as separately identified causal effects.

The state fixed-effect, static county spatial/IID, and negative-binomial size priors are retained from the county random-walk comparator. There are no independent annual innovation terms outside the spline basis. Consequently extrapolation uncertainty may differ materially from a random walk. Historical hindcast calibration must assess that difference.

## Two-container execution

Prepare numeric basis RDS files in the existing main FoodNet container, which supplies mgcv. Fit using the existing fixed INLA container: `fit_county_spline(obj, variant, cutoff, basis=..., threads=4)`. A basis contains numeric matrices and mgcv-version provenance; INLA fitting does not require mgcv. The supplied basis must match the complete prediction-year domain and origin.

INLA stack models use exposure `E=population`. Their observation predictor is **APredictor**, a log rate. `sample_county_spline` samples this predictor jointly and multiplies rates by saved populations to obtain expected counts. The existing random-walk sampler must not be used for this fit. The candidate sampler returns the same mu/replicated/size/indices structure for downstream diagnostics.

## Numerical gate

`Rscript tests/test_county_spline_candidate.R prepare DIR` builds H1/H3 numeric fixtures with mgcv and checks exact horizon-prefix invariance, training centering, and orthogonality to the linear null space. `Rscript tests/test_county_spline_candidate.R run DIR OUT` uses actual INLA for spatial and IID candidates. It checks shared posterior means and SDs under appended prediction-only years, invariance to poisoned held-out outcomes, correct observation-scale posterior sampling, and finite count predictions. A predeclared tolerance of 0.02 posterior SD for mean differences and 2% relative SD accounts for numerical integration variation; basis invariance tolerance is 1e-12. Outputs are `spline_gate_checks.csv` and `status.txt` containing `SPLINE_NUMERICAL_GATE_PASS` only after all checks pass.

The gate also compares an A-matrix Gaussian spline model with known coefficient and observation precisions against its exact linear-algebra posterior. Mean and SD errors must each be below 1e-4; results are written to `spline_gaussian_reference.csv`. This checks the basis/design implementation, not the full negative-binomial posterior approximation.

These are numerical checks, not a full negative-binomial posterior-reference or predictive calibration study. Real-data spline candidates remain exploratory and must be paired with existing county random-walk fits at the same pathogen, training origin, forecast horizon, geographic variant, and audited input panel. Accepted state outputs must not be overwritten or used as forecast calibration targets.

Local validation: basis preparation passed with system mgcv. Actual pinned INLA passed spatial and IID horizon/masking/count-scale checks. The exact Gaussian reference gave maximum mean error below 1e-14 and maximum SD error below 3e-7. Local numerical success does not replace executing the same gate in the cluster containers.

The local production diagnostics integration also passed: an actual IID candidate fit followed by all 4,000 joint predictive draws produced finite cell log scores and expected counts for 18 synthetic held-out cells, plus aggregate/score CSVs, forecast PDF, and specification CSV. Expected-count medians remained on the count scale (approximately 12 cases with populations of 100,000), verifying the APredictor-to-count sampler connection.
