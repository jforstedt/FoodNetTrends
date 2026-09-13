# County forecast validation protocol

Status: implementation and gated exploratory evaluation. This protocol does not replace Daniel's state spline or authorize automatic dashboard promotion.

## Fixed experiment

Compare the county spatial-plus-time and county IID-plus-time candidates at the same origin, on the same eligible county-year observations, with the same training outcomes and future population denominators. Each task also computes an analytic historical county-rate reference: a Poisson rate with Jeffreys Gamma(0.5, 0) prior, updated using only training counts and population exposure. Its posterior is proper with positive training exposure, including counties with zero observed training cases. The reference is a simple benchmark, not a claim that its likelihood matches the candidate negative-binomial model.

| Pathogen scope | Training starts | Forecast origins | Evaluated horizons |
|---|---:|---|---|
| Salmonella, Campylobacter, Cyclospora, Listeria, Shigella, STEC, Vibrio, Yersinia | 2004 | 2011, 2013, 2016 | 1, 2, 3 years after each origin |
| Cryptosporidium | 2004 | 2011, 2013, 2014 | 1, 2, 3 years after each origin; never after 2017 |

The matrix has **54 INLA fits**: nine pathogens, three origins, two candidates. The analytic reference is calculated within each task, adding no sampler fit. A pathogen subset may be chosen explicitly before submission; missing prerequisites must block a declared pathogen rather than silently remove it. There is no arbitrary concurrency throttle. Independent numerical tests and independent simulation replicates run concurrently; all eligible real tasks may run concurrently only after their shared gate passes.

These are combined-pathogen county analyses. They are not serotype-specific comparisons and do not add new state-model fits. Comparing the state spline with county models would require separate training-only state fits and a common aggregation target; that comparison is outside this batch.

## Eligibility and provenance

`scripts/county_forecast_protocol.py` generates the fixed matrix and validates the selected audit/reconciliation lineage. Salmonella uses the original pilot panel certified by its raw reconciliation. Other pathogens use their pathogen-specific audits and matching raw reconciliation; Cryptosporidium uses the corrected 2004–2017 panel. An identically named but different panel is not interchangeable.

Preparation verifies input-audit and raw-reconciliation success, panel hashes, recorded raw/clean/census checksums, pathogen/year scope, and a complete positive-population grid of 486 counties in ten states. It fingerprints the supporting reports. The worker must still deserialize the panel and run the independent R checks for counts, keys, population alignment, graph structure and state totals before fitting. A Python provenance pass does not certify the contents of an unread RDS file.

The observation period starts after historical catchment expansion. It stops before the Campylobacter 2024 diagnostic-reporting break, 2025 optional reporting and later Connecticut geography changes. Cryptosporidium's 2017 cutoff is enforced independently. These restrictions reduce known comparability problems; they do not make diagnostic adoption or other historical surveillance changes disappear. Those changes remain limitations of interpretation and can explain poor forecasts.

## Numerical and simulation gate

The temporal-horizon test must show that adding future prediction years does not change the fitted training domain, its centering/scaling or the training posterior. Shared future-horizon prefixes must agree within the declared numerical or Monte Carlo tolerance. Future observed counts may be used only for scoring, never for fitting, prior tuning, model selection or simulation-based adjustment of the current comparison.

Sparse and dense synthetic scenarios test predictive intervals for county counts, aggregate counts and aggregate numbers of zero-count counties, separately by horizon. Independent simulation replicates are the uncertainty units; counties within a replicate are correlated. The known-parameter oracle checks simulation and scoring behavior under additional information. It is **not an exact-posterior reference**, so passing cannot establish that Gaussian joint posterior sampling has accurate tails relative to a more accurate inference method.

A separate scalar reference gate compares the same Gaussian joint sampling path with an independently integrated one-dimensional negative-binomial log-rate posterior, using fixed dispersion and four predeclared sparse/dense scenarios. Its probability-scale discrepancy limit is 0.05. This checks a conditional scalar case; it cannot establish accuracy for the full county latent field or uncertain hyperparameters. Both this reference check and the horizon test must pass before the simulation screen can release exploratory county fits.

The implemented simulation gate is a predeclared gross numerical screen, not certification of nominal interval coverage: at least 20 replicates per scenario, at least 1,000 predictive draws, complete metric inventories, and no empirical coverage below 0.85 for nominal 0.95 intervals. Report simulation uncertainty and every failed scenario. Passing permits the exploratory real-data comparison; adoption still needs scientific review. A failed or incomplete gate blocks real-model workers even if scheduler dependencies have finished.

## Evaluation and reporting

Evaluate exactly the declared three-year window at each origin. Use the true years only for scoring and the known future population as an explicitly conditioned input. The result is a **conditional retrospective hindcast**, not an operational forecast using unknown future denominators. These historical data have already informed development, so the batch is not untouched confirmatory validation.

For each origin and horizon, report proper predictive log scores, point accuracy, interval coverage and width, zero-count calibration, and aggregate totals. Keep expected-incidence uncertainty distinct from predictive uncertainty for future observed counts. Record Monte Carlo error where consequential. Compare spatial versus IID and each candidate versus the historical reference only on identical cell keys, outcomes and exposures.

Forecast origins overlap in training history and sometimes in evaluation years; neighbouring counties and annual totals are dependent. Do not manufacture significance using an independent-cell standard error or declare a universal winner by pooling all pathogens. Paired state/year score sums are descriptive. Any future resampling or model-ranking uncertainty procedure needs an explicitly justified dependence unit and adequate independent replication.

## Recovery and completion

Freeze code, containers, protocol, input fingerprints, seeds and resource settings before submission. Verify actual thread limits inside the compute-node container. Cache only tasks with unchanged identities and validated artifacts; preserve failed attempts and perform targeted recovery rather than repeating successful fits.

The consolidated archive must retain the complete expected task ledger, blocked and failed jobs, prerequisite reports, matching-key comparison results and provenance. Successful process execution is distinct from numerical eligibility, artifact validity and scientific acceptance. No result in this batch automatically replaces the historical dashboard or establishes general forecast reliability.
