# County sensitivity experiment

This experiment separates prior sensitivity in persistent county differences from additional county-specific temporal variation. It is exploratory and does not edit Daniel's state model, the original county fit implementation, input data, existing fit checkpoints or dashboards.

Run on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_county_sensitivity.py
```

Four jobs can run concurrently; each requests eight CPUs, `h_rss=32768M`, `mem_free=32768M`, `h_vmem=64G`, and twelve hours. These are scheduler requests, not measured usage or a duration forecast. The array has no added concurrency cap. A held four-slot collection job reuses saved baseline reports and creates one archive. The existing `foodnet-inla-fixed.sif` is used without rebuilding. Failures and logs are archived; there is no automatic retry/refit loop.

## Controlled changes

| New fit | County structure | Single change relative to corresponding saved baseline |
|---|---|---|
| spatial_county_sd2 | BYM2 | County SD prior bound changes from 1 to 2, retaining tail probability 0.01 |
| iid_county_sd2 | IID | Same county SD prior change |
| spatial_county_time | BYM2 | Adds a separate scaled RW1 curve for each county |
| iid_county_time | IID | Same additional county time curves |

The county SD change relaxes the prior penalty on large county differences; it does not force estimates to become less pooled. The BYM2 mixing prior remains unchanged. See the official [BYM2 specification](https://inla.r-inla-download.org/r-inla.org/doc/latent/bym2.pdf).

Each additional county time curve is sum-to-zero over the study years, scaled, independent across counties conditional on one shared precision. Its PC prior has P(SD > 0.5) = 0.01. The original state RW1 curves remain. See the official [RW1 specification](https://inla.r-inla-download.org/r-inla.org/doc/latent/rw1.pdf). These are changes to smooth temporal variation, not an explicit zero-inflated observation process. County curves and state curves can share patterns; their variance decomposition depends partly on regularization. Negative-binomial dispersion can also trade off with added temporal variation. Hyperparameters must therefore be reviewed alongside predictive checks.

All other inputs and assumptions remain fixed: audited panel and population offset, historical graph, state intercept priors, state trend priors, negative-binomial likelihood and size prior, and INLA version. The experiment does not combine both changes in one fit, automatically choose a winner or claim geographic/forecast validation.

## Outputs and checks

Each new fit runs 1,000 full prior simulations and then estimates its posterior. It saves its checkpoint before reporting and produces 2,000 joint posterior predictive draws using the same `skew.corr=FALSE` approximation and grouped zero checks as the saved diagnostics. County fitted means and intervals are read from INLA's response-scale summaries and converted to rates with the population denominator. They are marginal summaries, not new joint state/reference aggregations.

Reports include prior checks, grouped zero-count checks and plots, county fitted incidence/expected count summaries, fixed effects, hyperparameters, CPO diagnostics and paired WAIC changes relative to the matching spatial/IID baseline. The baseline checks are copied from the completed 2,000-draw diagnostic job after verifying checkpoint hashes; baseline models are not refitted or resampled. Baseline fitted summaries use the same marginal-summary method as the sensitivity fits for comparability.

Review will examine county/year and population-group zero discrepancies, county means, estimated temporal variation, dispersion, prior plausibility and local tradeoffs. The paired pointwise WAIC SE is naive under spatial/temporal dependence and is not an independent validation result. Existing reporting-completeness uncertainty remains unresolved by these fits.

The archive contains internal aggregate reports and code snapshots but excludes all fit RDS objects and source datasets. New fit objects remain in their own HPC output directories. No results are published automatically.

Validation includes actual synthetic INLA fits for all four variants, full prior simulation, posterior zero checks, count-scale checks and county time indexing. Collector tests verify baseline hashes/reuse and paired differences; launcher/archive tests verify shell syntax, no extra concurrency cap, failure reporting and exclusion of saved fit objects. Cluster execution and statistical review remain pending.
