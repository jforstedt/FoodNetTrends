# Monthly temporal-prior sensitivity

Status: executable exploratory sensitivity, 2026-09-13. The preceding calibration review motivates stronger control of temporal variability. This batch changes one prior setting, not the seasonal structure, likelihood, case rules or accepted state model.

## Run

From FoodNetTrends on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_monthly_temporal_sensitivity.py
```

Six tasks fit Salmonella and Campylobacter at the existing 2011, 2013 and 2016 origins. The current six seasonal references are reused from completed saved diagnostics; they are not fitted or sampled again. Each new fit is followed by four fresh streams of 2,000 posterior samples, matching the reference's total of 8,000. All six tasks may run concurrently subject to the scheduler.

Each task requests four slots, h_rss/mem_free 53248M, h_vmem 68G and a 48-hour limit. Sampling uses one thread for reproducible seeds; fitting uses four. These limits are not runtime estimates. A held collector combines results into one archive. Once both IDs print, no persistent terminal is required. Missing or changed source artifacts stop execution rather than trigger a replacement reference fit.

## Frozen change and rationale

The temporal PC prior changes from P(training-scaled SD > 0.5) = 0.01 to P(training-scaled SD > 0.25) = 0.01. This halves the prior SD scale while retaining its tail probability. It does not constrain the fitted SD to be below 0.25, halve the fitted SD by construction, cap forecast variance, or change future innovations separately from training innovations. Both training and forecasting use the fitted temporal component consistently.

[INLA's RW1 specification](https://inla.r-inla-download.org/r-inla.org/doc/latent/rw1.pdf) defines independent Gaussian increments and the effect of reducing the PC SD bound. The implementation continues to convert the standardized bound to an innovation bound using training-only RW1 scaling; forecast months do not enter the scaling or centering. All other priors retain their original settings, including the centered cyclic season, static county effects, state intercepts and monthly negative-binomial shape.

The factor-of-two change is selected as one interpretable sensitivity before viewing these new results, after inspecting the original hindcasts. It is not an untouched confirmatory comparison or the winner of a new parameter grid. Learned temporal precision was fairly concentrated in the previous fits; modest prior tightening may have limited influence. No automatic additional tightening follows if this run disappoints. A different temporal structure would be a separately specified experiment.

The shared model's default remains 0.5 for existing callers. The new runner explicitly requests 0.25, and its saved specification records the bound. Saved-fit validation derives the bound from the saved scale/innovation setting, accepting legacy 0.5 checkpoints without requiring a new metadata field and rejecting a mismatched requested prior.

## Comparable outcomes

The start date, origins, three-year horizons, specimen-month convention, assumed coverage and realized population exposures match the original monthly comparison. Worker-side validation checks exact held-out county/state/year/month observations against the original reference. The continuity assumption remains unverified; stronger conclusions still require that limitation to be resolved or clearly retained.

New and reused reference summaries include four streams plus a pooled result. Compare county log predictive scores averaged within site/year, then averaged equally over ten sites, while keeping pathogens, origins and horizons separate. Pooled comparisons use 8,000 samples per model. Sampling streams have disjoint seed ranges from the original models and previous diagnostics. Stream numbers identify independent numerical replicates, not common-random-number pairs or additional datasets.

The combined aggregate-tail table supports site/year and catchment/year comparisons of observed totals, expected-count means and medians, predictive intervals, and top-1% draw contributions. Reference and new-model tables use the same calculations. Lower means or narrower intervals alone do not establish improvement: review score direction, interval coverage and width, stability across streams, site-level exceptions and remaining bias together. No model is automatically promoted.

## Outputs and validation

The archive contains the paired stream/equal-site scores, aggregate-tail summaries, new hyperparameters, seasonal effects, prior settings, provenance and failure status. New fit objects, held-out truth checkpoints and aggregate draws remain on the cluster, bound by hashes and excluded from the portable archive. Existing models, published dashboards and raw files are unchanged.

Tests cover isolated prior changes, unchanged observations and other specification fields, training-only centering under an extended horizon, invalid bounds, rejection of mismatched saved priors, actual new-model fitting and resampling on synthetic data, source changes, six-task dispatch, Python 3.6 and failure archives. Full-scale HPC resource use remains a cluster check.
