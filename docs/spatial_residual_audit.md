# Saved spatial forecast-error audit

This descriptive audit reads the 162 completed BYM2 monthly fits across all nine pathogens, three existing origins and six temporal/seasonality combinations. It uses the verified Listeria recovery and final Shigella restart for those two cells. It performs no fitting, posterior resampling, model selection or outcome-driven retuning. Cryptosporidium's existing origins and observation cutoff remain unchanged.

The portable reports already support paired state-level score comparisons. County forecast-error geography requires the saved fit and matched internal county/month truth on the cluster. This bounded audit examines BYM2 fits only: it has no matched county IID residual control and therefore cannot attribute remaining spatial association, or its absence, to a benefit from smoothing. Overlapping development origins are not independent replications.

## What is measured

Only the 36 held-out forecast months are examined. These are forecast errors, not training residuals. Expected counts come from saved INLA marginal fitted means. RW1/AR1 summaries are already on the count scale; the existing spline adapter supplies the exposure multiplier for its rate-scale summary. These deterministic marginal means can differ slightly from the finite posterior-draw means in previous scoring reports. No new draws or predictive intervals are produced.

The working residual is `log1p(observed count) - log1p(expected count)`. This stabilizes the scale and handles observed zeros; it is not a standardized negative-binomial residual. Because of the nonlinear transformation (Jensen’s inequality), it need not have mean zero even under a correct negative-binomial model. Its distribution varies with sparsity and population, so geographic association can arise from differing count distributions rather than model misspecification. It is a descriptive trigger for review, never an automatic recommendation to add model complexity. Moran's I summarizes neighbor association using the actual frozen adjacency. Reports contain both raw global Moran's I and a version centered within each state, because shared state-wide forecast bias can otherwise appear as county neighbor association. Site-specific annual indices and monthly whole-catchment indices are included. Undefined indices are `NA` when there are no edges or near-zero residual variance. Moran's I is not assumed to be bounded by -1 and 1 on an irregular graph.

Temporal persistence uses exact consecutive months within the same county, after subtracting that county's mean forecast error over the held-out window. Gaps are never bridged. Insufficient pairs or zero centered variance produce `NA`. These summaries have no null-distribution calculation, p-values or posterior uncertainty. They identify patterns for scientific review, not a formal test of independence or a new acceptance threshold.

## Execution and integrity

Run from the cluster repository after loading Singularity:

```bash
python3 scripts/launch_spatial_residual_audit.py
```

The command immediately submits a visible preparation job. Large input verification occurs there, with stage messages in `preparation.log`, rather than invisibly on the login host. Preparation merges repeated lineage bindings and rejects conflicting hashes. It validates consumed portable source metadata and reports, recovery lineage, task identities and the exact frozen graph. It preserves ancestral raw-data and unrelated-control hashes as `HISTORICAL_NOT_REHASHED`; those files are not consumed or re-read. Large saved-fit and truth payloads are bound from their completed source records, then verified by their own workers before and after auditing, rather than serially hashing all fits during preparation. It snapshots the original validation scripts and new audit code. A copied read-only container is hashed during preparation; workers check its snapshot metadata, and collection rehashes its content. This avoids hashing all other fits or the large container in every worker.

After preparation, all 162 independent read-only jobs may enter the scheduler together. Each requests one CPU, 24 GB RSS, 32 GB virtual memory and an eight-hour ceiling; requests are not runtime estimates. Workers verify only their selected fit/truth and frozen shared evidence, then recheck after execution. The held collector checks output hashes, complete state/year and month domains, settings and numeric ranges before reporting completion. Global integrity failures prevent successful collection. Preparation failures also create an explicit failure record and diagnostic archive, without hiding a missing array behind a blank log.

County/month counts and residuals remain in `county_month_residuals_INTERNAL.csv` on the cluster. The archive excludes that file, internal fit objects and the copied container. It exports aggregate state/year counts and residual indices, monthly global indices, settings, logs and lineage evidence. It does not export case-level rows or county result tables.

## Validation

The first cluster audit exposed a reporting defect: saved model state columns
are factors, and the R state loop converted their labels to integer codes.
All 162 reports were rejected by the state/year-domain validator, with empty
state summaries; these are not accepted audit results. Geographic identifiers
are now converted explicitly to character before aggregation. A regression test
uses reversed factor levels and checks equality with character inputs, correct
state labels and reconciliation with the whole-catchment totals. The correction
changes only reporting, not fitted models or expected counts. Rerun the command
above to create a fresh audit directory; retain the failed directory as evidence.
No model refitting or container rebuild is required.

Pure-R tests exercise graph degeneracy, uniform state bias, within-state centering, reordered rows, invalid means, duplicate cells and temporal gaps. Python tests exercise digest-pinned preparation, original graph identity, archive exclusions, unsafe output paths and final container-hash verification. Actual pinned-INLA synthetic seasonal AR1/BYM2 and spline/BYM2 saved fits passed the complete audit interface. The spline check caught the appended latent Predictor rows in its fitted summary; the final adapter explicitly selects and validates the observation APredictor IDs before applying exposure. Python checks also verify that preparation defers fit-byte reads to workers and that altered fit payloads are rejected before audit execution. These checks verify implementation; actual source-file availability and the 162 completed reports are cluster checks.
