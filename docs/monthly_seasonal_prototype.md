# Synthetic monthly seasonal prototype

This module implements and tests the monthly random-walk reference and its paired seasonal extension. It is not connected to a production launcher or dashboard. It requires synthetic input markers and rejects unverified observation statuses. It does not load FoodNet data or modify accepted annual analyses.

## Model

Both candidates use a negative-binomial count likelihood, log person-years offset, state intercepts, static IID county effects and a state-specific monthly RW1. The seasonal candidate adds one shared 12-month cyclic RW1. December and January are neighbors. An explicit mean-zero constraint over all 12 seasonal coefficients separates their overall level from the intercept.

The cyclic precision is the graph Laplacian of the 12-month ring. Its generalized marginal variance is scaled analytically to one; an explicit constraint is supplied rather than relying on cyclic default constraints. The [INLA RW1 documentation](https://inla.r-inla-download.org/r-inla.org/doc/latent/rw1.pdf) describes the cyclic graph construction. See also [INLA scaling guidance](https://www.inla.r-inla-download.org/r-inla.org/doc/vignettes/scale-model.pdf).

Trend scale and centering use only months at or before the forecast origin. Forecast months are excluded from the constraint and have internally masked outcomes, even if the caller supplies future counts. The repeated seasonal curve has a fixed 12-coefficient domain independent of forecast horizon. It is a shared recurrent curve, not a time-varying seasonal process.

The RW1 can still absorb some recurring variation. Centering fixes levels, not a unique scientific decomposition into trend and seasonality. Evaluate paired forecasts; do not interpret components causally. The prototype omits county-specific temporal deviations, spatial effects and splines to isolate the first implementation check. Those structures require separately matched comparisons; the full four-candidate combination matrix is not implemented here.

## Synthetic engineering priors

These are explicit test settings, not approved production monthly priors:

- State log-rate intercept: Normal(log(0.002), 1).
- County effect SD: PC upper bound 1 with tail probability 0.01.
- Training-scaled trend and cyclic seasonal SD: PC upper bound 0.5 with tail probability 0.01; raw RW1 precision bounds incorporate the corresponding analytical scaling.
- Negative-binomial log size: Normal(log(20), 1), variance convention `mu + mu^2/size`.

Monthly production priors still require prior-predictive review. This module does not copy the annual negative-binomial shape as an accepted monthly choice.

## Local tests

Run from the repository with pinned INLA 26.08.07 available:

```bash
Rscript tests/test_monthly_seasonal_prototype.R --fit
```

Without `--fit`, the test checks domain validation, rejection of unverified/production inputs, masking of future values, training constraints, ring adjacency and generalized-variance scaling. With `--fit`, it additionally checks recovery of a known seasonal curve, forecast error against the known synthetic mean, numerical invariance when extending the forecast domain, finite joint predictive samples, and shrinkage of the seasonal curve on data generated without seasonality.

Synthetic fixtures use four counties, two states, six training years and one forecast year. Fixed engineering tolerances are in the test source. These examples detect implementation errors; they are not a broad calibration study, proof of adequate interval coverage or evidence that FoodNet forecasts will improve. No real-data fit should be submitted based on these tests alone.

The next steps remain review of the month-definition comparison, an explicit observation-calendar decision, production prior-predictive checks and a frozen paired evaluation manifest. The [monthly assumptions](monthly_analysis_assumptions.md) and [combination protocol](extension_combination_protocol.md) govern that transition.
