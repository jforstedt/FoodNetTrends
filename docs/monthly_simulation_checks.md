# Monthly simulation stress checks and prior audit

This is a local synthetic-only extension of the [monthly prototype](monthly_seasonal_prototype.md). No FoodNet records are loaded and no cluster or production fitting entry point is added.

`run_monthly_simulation_checks.R TASK OUTPUT_DIR` runs one paired reference/seasonal check. Tasks 1–8 cover four scenarios with two fixed simulation seeds each: flat rate, recurring seasonality, sparse seasonal counts, and a trend plus seasonality. Each task fits the same two monthly candidates to six years, forecasts the following year, and draws 400 joint posterior predictive samples. The generating negative-binomial size is 20. The training data and forecast targets are identical within a pair.

Outputs report prediction error against both generated observations and the known mean, 95% predictive interval coverage and width, and the Monte Carlo negative-binomial mixture log score. The collector must retain numerical failures rather than treat them as a candidate losing a score comparison. The task status certifies execution, not calibrated forecasts or real-data acceptance. Two replicates per scenario are engineering checks, not enough for precise coverage estimates or a claim of superiority. Sparse counts and dependent cells make naive confidence intervals especially misleading.

`check_monthly_prior_predictions.R OUTPUT_CSV` samples 20,000 marginal prior realizations for each of two intercept settings, two exposures and two time points (training endpoint and 12 months ahead). It uses the prototype's actual PC SD priors, constrained cyclic Gaussian effect, training-centered RW1, county effect, and log-normal negative-binomial size. The two intercept rate centers are 20 and 200 per 100,000 person-years; the latter is the synthetic prototype setting, not an approved surveillance prior. Exposure is person-years, not population: a county's monthly exposure is roughly its population divided by 12.

The audit summarizes rates and counts, including zero fractions. Finite draws only certify computational behavior. Scientific plausibility requires a rate target and training-origin review; neither setting is automatically accepted. Samples across scenarios reuse common random latent draws intentionally for comparisons and are not independent evidence. This marginal audit does not establish joint geographic calibration, sensitivity to all prior choices, or adequacy of the full county spatial model.

Example commands from the repository, using an R environment with INLA 26.08.07:

```bash
Rscript scripts/run_monthly_simulation_checks.R 1 /tmp/monthly-task-1
Rscript scripts/check_monthly_prior_predictions.R /tmp/monthly-prior.csv
```

Independent task IDs can run concurrently. Results belong in local output directories, not in Git. Real-data seasonal fitting still requires the explicit monthly observation-calendar decision and a frozen production specification.
