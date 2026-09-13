# Review of the first real-data county fits

The exploratory spatial fit is promising relative to the IID comparison, but the
county estimates are **not ready for dashboard interpretation**. Both fits tend
to underproduce zero-case county/years, and some county estimates depend strongly
on the spatial-pooling choice. No model or prior was changed during this review.

Archive: `county_pilot_fit_20260912_212322_668317.tar.gz`.
SHA256: `32fa9dba167e011dc8fd76fa07b8304026aeeb43a4c2c427498f44c48e695fed`.

## Execution and output consistency

Both models completed with zero CPO computation failures and 1,000 joint posterior
draws. Both report the same panel MD5, `fc7969a4eb1133b7b4e6b745c3402470`, and the
archived fitting script matches the reviewed source. Each contains 7,776 county
and 160 state incidence/ratio rows, with unique keys, positive finite summaries,
and ordered intervals. All 2019 reference summaries equal one.

Using the audited populations, county posterior means aggregate to exported state
posterior means within 8e-14 per 100,000. County reference-ratio point estimates
are identical within each state/year to numerical precision, as expected from the
shared state temporal shape. These checks support reporting consistency, not
independent county trend estimation or equivalence to Daniel's model.

## Posterior predictive checks

Observed total: 122,024 cases. Observed zeros: 655 of 7,776 county/years (8.423%).
The following are replicated-data medians and central 95% intervals:

| Statistic | Spatial | IID |
|---|---|---|
| Total cases | 122,559 (120,669–124,374) | 122,607 (120,625–124,494) |
| Percentage zero-case county/years | 7.729% (7.163–8.269%) | 7.845% (7.305–8.398%) |
| Fraction of replicates with zero percentage at least observed | 0.011 | 0.021 |

Totals are well reproduced. Zero percentages tend to be too low, more clearly
for the spatial fit; the observed value is just above the IID central interval.
These are descriptive posterior-predictive tail fractions from 1,000 draws, not
calibrated hypothesis-test p-values. Monte Carlo uncertainty matters, especially
for the IID result near the interval boundary. The discrepancy does not by itself
establish a structural-zero process or justify switching to a zero-inflated model.
Inspect its concentration by county, year, state, and population size first.

The archived global predictive summaries cannot localize the mismatch. The saved
fits and internal panel on HPC can provide that diagnostic without re-estimating
model parameters.

## Spatial versus IID comparison

WAIC is 39,824.46 for spatial and 39,888.38 for IID: a 63.92 reduction for spatial.
This favors spatial under this criterion, but the archive lacks pointwise WAIC
contributions needed to assess uncertainty in the paired difference. There is
also no temporal holdout evaluation. Do not call this a demonstrated forecasting
advantage or a definitive model-selection result. See
[paired comparison uncertainty](https://mc-stan.org/loo/reference/loo_compare.html).

The spatial mixing parameter has posterior median 0.849, with 95% interval
0.727–0.929, conditional on this model and its priors. It is not the fraction of
infections caused by spatial processes. NB size is approximately 25.3 in both
models; temporal precision estimates are also similar.

Across all state/years, median incidence differs by at most 1.36%; median reference
ratios differ by at most 1.37%. County incidence differences are larger: median
absolute relative difference 2.33%, 95th percentile 14.88%, maximum 74.40%
(spatial relative to IID). These are differences between exported posterior
medians and also contain Monte Carlo error.

For example, Grant County, Oregon in 2015 is 8.66 per 100,000 (95% interval
5.80–12.39) with spatial pooling, versus 4.97 (2.64–9.50) with IID effects. The
intervals overlap substantially. This is a sensitivity flag, not evidence that
either point estimate is the true county rate. State agreement can conceal
substantial county differences.

## Prior and remaining validation

The cluster prior checks agree with the local assessment: the observed pooled
incidence of 16.04 is near the low end of the revised prior distribution. About
3.5–3.6% of simulated prior pooled rates are below it. Prior sensitivity remains
relevant, especially for sparse counties.

Next: use the **saved fits** to localize zero-count discrepancies, inspect county
residuals and CPO/PIT behavior, and extract pointwise comparison diagnostics.
Then decide which temporal structure, prior, or observation-model sensitivity
actually needs fitting. Temporal holdout and matched-data comparison with
Daniel's model remain outstanding. No refit or dashboard publication is warranted
solely by this review.

A comparison figure was generated locally at
`.local/county_pilot_fit_review/predictive_checks.pdf` (with a PNG preview).
The underlying fit RDS files and exact county counts remain on HPC and were not
included in the downloaded archive.
