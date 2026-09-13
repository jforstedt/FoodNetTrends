# Saved county diagnostics review — 12 September 2026

Reviewed `saved_county_diagnostics_20260912_214414_854891.tar.gz` (SHA256 `5c30a8882baa86a50a58d20df95eabbf725e293b031dd76f72d75b9735964493`). Execution passed. The archived diagnostic R script matches the repository version. Checksums confirm the panel and both saved fits remained unchanged. All six reporting partitions reconcile to 7,776 county/year cells and 655 observed zero cells; expected-zero totals reconcile across groupings. Each model used 2,000 posterior predictive draws. No model was refitted.

## Overall check

| Model | Observed zero cells | Mean expected zeros | 95% replicated-zero interval | Fraction of replications at least as large as observed |
|---|---:|---:|---:|---:|
| Spatial | 655 | 600.51 | 558–643.025 | 0.0075 |
| IID | 655 | 612.05 | 568.975–657 | 0.0320 |

These intervals are empirical quantiles and can have fractional endpoints. The new draws confirm a clearer shortfall for the spatial model. **The IID observed total is now inside its 95% predictive interval**, unlike the earlier 1,000-draw report; it remains near the upper end. The earlier statement that both models exclude the observed zero total at 95% should not be carried forward. Tail Monte Carlo SEs are 0.00193 and 0.00394, respectively. Posterior predictive tails are descriptive, not classically calibrated significance tests; see the [Stan predictive-check guidance](https://mc-stan.org/docs/stan-users-guide/posterior-predictive-checks.html).

## Where the discrepancy lies

For the spatial model, counties with annual population below 25,000 contribute about 53.3 of the 54.5 net excess observed zeros. The 5,000–9,999 band has 230 observed against 206.43 expected; the below-5,000 band has 217 against 202.80. These are county/year population bands, not permanent county categories.

Minnesota is the largest state contributor: 202 observed against 180.08 spatial expected (178.57 IID). New Mexico, Tennessee and Oregon also contribute. Across years, 2007 stands out in both models: 55 observed versus 40.76 spatial and 41.46 IID expected, above both 95% predictive intervals. Minnesota 2006–2008 contributes to the temporal pattern. Group rankings are exploratory and involve multiple comparisons.

Grant County, Oregon (41023), has 15 zero years out of 16. The spatial model expects 9.09 (95% replicated interval 5–13), versus IID 11.50 (7–15). This is consistent with the previously observed sensitivity to spatial pooling, but does not establish its cause. Other large county gaps include Mora County NM, Wallowa County OR, Houston County TN, Hancock County GA and Kanabec County MN. The archive does not contain the county/year nonzero case counts needed to distinguish persistent low incidence, a single large year, or source/reporting patterns.

## Model comparison

Spatial WAIC remains lower by 63.918; the naive paired pointwise SE is 18.425. The spatial sum log CPO is higher by 34.092. Neither model has failed, nonpositive or nonfinite CPO entries. Both criteria favor spatial overall, but neither constitutes held-out geographic or future-year validation. Spatial/temporal dependence limits the naive SE.

Most of the WAIC advantage comes from Georgia (+26.72), Minnesota (+20.45) and Tennessee (+18.26); Oregon favors IID by 4.28. Thus an overall criterion advantage coexists with a worse zero-count check and local sensitivity. It is not a reason to dismiss the latter.

## Next step

Inspect the aggregated county/year case histories and reporting/mapping provenance for the flagged counties, alongside fitted means and neighboring counties. Keep this a read-only review of existing inputs. The completed audit established complete, positive population coverage and matching geographic keys; it did not independently establish that every absence of a record represents a true zero under complete reporting.

Use that review to specify targeted sensitivity comparisons if needed. Do not automatically add a zero-inflation term, delete counties, or change Daniel's state model. These diagnostics alone cannot distinguish a reporting issue from county temporal variation, shrinkage or other model inadequacy. County dashboard publication remains pending this review and predictive validation.
