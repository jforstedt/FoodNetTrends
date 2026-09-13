# County forecast simulation screen

This gate checks the new forecast implementation before running exploratory real-data comparisons. It does not establish that INLA's Gaussian joint posterior approximation has accurate tails in every county model, and it does not authorize adoption.

## Fixed experiment

The predeclared first batch contains 80 independent fitted datasets: 20 replicates for each of two count-density scenarios and two county-effect structures. Within each scenario, the synthetic panel has 12 counties, two disconnected six-county chain graphs, eight training years, and three future years. Each fit uses at least 1,000 joint posterior draws.

The sparse and dense scenarios share the incidence scale and differ through exposure: base populations of 500 and 50,000, with fixed modest variation between counties. The generating log rate is log(20/100,000), negative-binomial size is 8, county SD is 0.35, state temporal SD is 0.12, and county temporal SD is 0.08. The spatial version uses BYM2 mixing 0.5; the comparator uses independent county effects. These fixed truths are representative stress tests, not draws from the fitting prior or a survey of all plausible disease processes.

Temporal effects are scaled and constrained using only the eight training years. Future effects continue with independent random-walk increments at the same precision. Extending the forecast horizon preserves the identical training data and common simulated future prefix. The fitted model masks held-out outcomes internally.

## Outputs and gate

Each task writes `metrics.csv`, `task_summary.json`, `simulation_truth.csv`, `fit_INTERNAL.rds`, and a status file. Metrics include 95% predictive interval coverage, width, mean absolute error, and predictive-mean Monte Carlo SE for county cells, annual aggregate counts, and annual aggregate zero counts at each horizon.

A known-parameter oracle uses the true training effects and hyperparameters but draws new future innovations and observations. It checks the generator and predictive-scoring calculation with more information than the fitted model. It is **not** a higher-accuracy posterior reference for INLA.

The collector requires all 80 task identities and all expected metrics. The predeclared gross-undercoverage screen flags any scenario/method/horizon/unit with empirical coverage below 0.85. Replicate-level Monte Carlo SE and conservative distribution-free 95% Hoeffding bounds accompany the estimates; counties within one simulation are not treated as independent simulation replicates. The empirical 0.85 cutoff is a screening decision, not a nominal-coverage hypothesis test. With 20 replicates, aggregate-coverage uncertainty is substantial.

A complete batch without a gross-undercoverage flag receives `NUMERICAL_SCREEN_PASS`; otherwise it receives `REVIEW_REQUIRED`. In both cases, `scientific_status` remains `REVIEW_REQUIRED`. A screen pass permits only exploratory comparisons after the separate horizon-invariance gate also passes. It does not certify 95% coverage, prove posterior-approximation equivalence, select a pathogen model, or replace the reviewed state analysis.

## Commands

One task:

```bash
Rscript scripts/county_forecast_calibration.R task OUTPUT sparse iid 1 1000 2
```

Collect the root containing all task output directories:

```bash
python3 scripts/collect_county_forecast_calibration.py ROOT --replicates 20
```

The collector writes `ROOT/calibration_summary.json` and exits zero only for `NUMERICAL_SCREEN_PASS`. Existing task destinations are never overwritten. The R task requires the pinned INLA environment; the collector uses Python's standard library and supports Python 3.6.
