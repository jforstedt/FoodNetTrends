# Monthly combination prior and extrapolation audit

Local review date: 2026-09-14. This is a data-free engineering review, not
acceptance of a model or a comparison of predictive accuracy. Daniel's state
model, existing results and the running monthly factorial snapshot are unchanged.

## Procedure

`scripts/audit_monthly_combination_priors.R` simulates 20,000 joint prior draws
for each training cutoff (2011, 2013, 2014, 2016), beginning in January 2004,
and extends each trajectory 36 months. It compares RW1, AR1 and the proposed
phase-orthogonal spline, each with and without cyclic month effects. Shared
intercept, county and negative-binomial draws reduce simulation noise between
comparisons. These are representative county/state trajectories, not simulated
whole-surveillance aggregates.

The script reproduces the specified log-rate intercept, county IID, temporal,
seasonal and negative-binomial priors. It evaluates count predictions at 500 and
10,000 person-years, checks training constraints and confirms that appending
prediction months does not change the existing spline basis. No outcomes are
used to select a scale. These model/prior packages are not functionally matched
priors, so differences cannot be attributed to temporal family alone.

Reproduce into a new output directory:

```bash
Rscript scripts/audit_monthly_combination_priors.R output/monthly_combination_prior_review_LOCAL
python3 scripts/plot_monthly_combination_priors.py output/monthly_combination_prior_review_LOCAL
```

## Findings

Central 95% prior ranges for the rate 36 months ahead divided by the final
training-month rate, with seasonality enabled:

| Training cutoff | RW1 | AR1 | Spline |
| --- | --- | --- | --- |
| 2011 | 0.592–1.669 | 0.430–2.352 | 0.187–5.244 |
| 2013 | 0.628–1.585 | 0.422–2.262 | 0.263–3.620 |
| 2014 | 0.637–1.527 | 0.426–2.312 | 0.306–3.281 |
| 2016 | 0.666–1.489 | 0.429–2.275 | 0.357–2.908 |

These are Monte Carlo prior quantiles, not confidence intervals for accuracy.
At a 36-month separation the cyclic seasonal effect cancels in this ratio.
The spline allows wider long-range changes, particularly with shorter training
histories. Its proper slope and nonlinear extrapolation therefore require an
explicit scientific justification before a real-data experiment is frozen.
This does not establish that its forecasts are worse, or that combinations
should be discarded.

The most extreme simulated cell had 99.55% of its sample expected-count total
contributed by the largest 1% of draws. Raw sample prior means must not be
interpreted as stable summaries. With a Gaussian random effect conditional on
an exponentially distributed, unbounded standard deviation, integrating
`exp(sd^2 / 2)` against the exponential density diverges. The shared county
effect alone gives this property to every candidate's unconditional arithmetic
prior rate mean. Finite central quantiles remain useful. This is a prior property,
not a finding that posterior means diverge or existing fitted models are invalid.
No prior was changed in response to these simulations.

## Safeguards and remaining work

Prepared spline bases are now checked on consumption for identity, dimensions,
finite values, exact slope convention, training rank, orthogonality and variance
normalization. Tests reject rescaled nonlinear bases and shifted slopes. These
constraints do not authenticate arbitrary prediction-only rows: a real-data
launcher must also bind the prepared object to its generating inputs and source.

Before real-data spline combinations: record the intended extrapolation and
prior rationale, freeze the comparison protocol and basis provenance, and
retain paired controls with the same eligibility and scoring rules. The current
RW1/AR1 factorial results can be reviewed independently when the cluster returns.
