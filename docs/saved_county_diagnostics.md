# Saved county pilot diagnostics

The first pilot reproduced the pooled count but underpredicted zero-count county/year cells. This follow-up locates that discrepancy using the existing spatial and IID checkpoints. It does not estimate model parameters again, change priors, rebuild a container, or update the dashboard.

From the repository on Rosalind, with the Singularity module loaded:

```bash
 git pull --ff-only personal feature/rinla-county && python3 scripts/launch_saved_county_diagnostics.py
```

The launcher reads the original fit manifest to find the audited panel. It defaults to `output/county_pilot_fit_20260912_212322_668317` and `foodnet-inla-fixed.sif`. It submits one two-slot diagnostic job, processes both saved fits, and prints a unique output directory, log and archive path. The two-hour scheduler request is a ceiling, not a runtime estimate. Missing checkpoints stop execution; there is no fitting fallback. Both input directories are mounted read-only. The panel checksum and predictor ordering must agree with the original fit reports, and input checksums are checked again at completion.

Each model gets 2,000 joint posterior draws in batches of 100. These use `skew.corr=FALSE`, the same documented Gaussian conditional latent approximation as the original reports. New negative-binomial replicated counts are generated from each draw. No raw records, saved fit objects, panel RDS, or cell-level draws enter the archive.

Reports include:

- `spatial/zero_checks_INTERNAL.csv` and its IID counterpart: observed zero counts, replicated medians and 95% predictive intervals, posterior mean expected zeros, observed-minus-expected zeros, upper-tail fractions and their Monte Carlo standard errors. Groupings are overall, state, year, state/year, county, and annual population band. Population bands use each county/year's population, so a county can change bands.
- `spatial/zero_checks.pdf` and its IID counterpart: state, year, population-band and top 25 county checks. County rankings use observed-minus-posterior-mean expected zeros; county labels include state and FIPS.
- `paired_comparison.csv`: IID-minus-spatial WAIC, the naive paired pointwise standard error, and spatial-minus-IID sum log CPO when all CPO entries are valid.
- `waic_by_*_INTERNAL.csv`: grouped contributions to the WAIC difference. Positive values favor the spatial model on that criterion.
- Per-model CPO failure/nonpositive counts, input checksums, session information and completion status.

The predictive intervals describe replicated zero counts, not credible intervals for their expectation. Tail fractions are descriptive posterior predictive checks, not calibrated significance tests; county rankings also involve many comparisons. Zero mismatch alone does not establish a structural zero-inflation mechanism.

The [loo model-comparison documentation](https://mc-stan.org/loo/reference/loo_compare.html) motivates paired pointwise differences. Here the reported standard error is explicitly naive: dependence among counties and years limits an independence-based calculation. CPO describes leave-one-cell-out prediction, not withheld counties or future years. These results guide further review, not automatic model selection or dashboard approval.

Local validation uses actual saved synthetic INLA checkpoints with `INLA::inla()` instrumented to fail if called. It checks both variants, zero-count aggregation across all groupings, predictive interval ordering, valid tail fractions, and unchanged checkpoint hashes. The launcher test checks read-only binds, shell syntax and refusal to overwrite an existing output directory. The real pilot diagnostic results still require running the cluster job and reviewing its archive.
