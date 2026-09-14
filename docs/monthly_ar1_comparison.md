# Monthly stationary temporal comparison

Exploratory follow-up to the temporal-prior sensitivity. The tighter RW1 prior changed fitted temporal variability little and did not resolve Salmonella's elevated long-horizon predictive means. This experiment changes temporal structure; it is not another calibrated strength adjustment or an accepted production model.

## Frozen candidate

Replace each state's monthly RW1 with a proper stationary AR1, sharing temporal hyperparameters across states. Retain state intercepts, static IID county effects, shared cyclic monthly seasonality, negative-binomial likelihood, exposures, observation rules and the existing priors for those terms. Daniel's annual model is unaffected.

The state intercept represents a persistent level. Temporal deviations decay as rho^h, conditional on rho. This does not separate an evolving permanent trend from a temporary shock; a lasting change could be incorrectly pulled back. A rho near one can still imply persistence throughout a three-year forecast. Negative rho is allowed by the prior. Seasonality repeats unchanged into the future.

INLA AR1 precision is **marginal precision**, not innovation precision. Set P(marginal temporal SD > 1)=0.01 using pc.prec. Set log((1+rho)/(1-rho)) ~ Normal(log(19), 1.5^2), with prior median rho=0.9 (roughly 6.6-month half-life at that value). These are exploratory, explicit choices, not equivalent to the RW1 variance prior or selected by optimizing these held-out outcomes. The broad rho prior permits near-unit persistence and some negative correlation. Use stationary initialization and no sum-to-zero temporal constraint. The existing cyclic seasonal constraint remains.

The official parameterization is documented at https://inla.r-inla-download.org/r-inla.org/doc/latent/ar1.pdf. Conditional AR1 forecast variance is bounded; integrating uncertain parameters and exponentiating does not guarantee narrow or well-calibrated count forecasts.

## Paired evaluation

Six new seasonal AR1 fits: Salmonella and Campylobacter at December 2011, 2013 and 2016 origins, forecasting the following 36 months. Reuse the six original seasonal RW1 fits and their 8,000-draw diagnostics from saved_monthly_diagnostics_20260913_205110_899575. No reference refits. Four disjoint streams of 2,000 posterior draws per candidate. These origins already informed development: this is exploratory comparison, not fresh external validation.

Require identical held-out county/month observations, input and source hashes, pinned container, valid numerical completion, masked future outcomes, and complete sampling streams. Compare county predictive log scores aggregated equally across sites, interval coverage and width, means and medians relative to truth, tail concentration, temporal uncertainty by horizon, and rho/precision posteriors. An improvement in means alone is insufficient; check score losses and undercoverage. Monte Carlo streams diagnose simulation stability, not independent replications of forecast skill. No automatic promotion.

## Execution and tests

Run `python3 scripts/launch_monthly_ar1_comparison.py` on the cluster. Six tasks may run concurrently, four cores each, with existing 52 GB RSS request and 48-hour limit. A dependent collector validates completion and produces one portable archive, excluding internal fit/draw checkpoints. Real input coverage remains EXPLORATORY_ASSUMED_CONTINUOUS, not certified.

Local tests cover future masking, analytic stationary covariance and decay, actual pinned-INLA fitting and saved-posterior sampling, rejection of mismatched model/prior identity, and invariance of existing predictions when future months are appended. Existing monthly tests retain the RW1 default. Cluster completion still requires statistical review.
