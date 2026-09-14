# Reproducing monthly posterior diagnostics

The monthly diagnostics at source commit `5336bcb`, including the running spline
factorial snapshot, use the legacy sampling convention. INLA 26.08.07's
`inla.posterior.sample` uses R's RNG to select hyperparameter configurations
and its supplied seed for latent Gaussian draws. Consequently, the recorded
base seed alone is insufficient to guarantee exact regeneration of the legacy
draws after changing the ambient R random state.

Independent saved-fit checks reproduced this behavior: changing R's random seed
with the same INLA seed changes sampled configurations; repeating both states
reproduces the samples in the tested environment. This does not show biased
sampling, incorrect exposure, a changed posterior or invalid original results.
It is a reproducibility limitation. Preserve the saved original reports/draws;
do not restart the current model batch for this issue.

## Optional future diagnostic protocol

`audit_monthly_saved(..., rng_protocol='explicit_config_v2')` selects a new,
explicit protocol for diagnostics from an existing fit. The default remains
`legacy_v1`, so existing callers and current cluster snapshots keep their
sampling convention. V2 changes neither the fitted model nor its posterior.
It requires a new diagnostic output directory and does not overwrite original
results. Do not silently mix versions or claim a regenerated report is the
same Monte Carlo realization as its legacy source.

For stream `s` in 1 through 4, let `B = base_seed + (s - 1) * 50000`.
For each batch beginning at draw index `j` (1, 101, ...):

| Random component | Seed |
|---|---|
| R configuration selection, set immediately before posterior sampling | `B + 20000 + j` |
| INLA latent Gaussian draws | `B + j` |
| R negative-binomial predictive replication | `B + 10000 + j` |

The existing batch size of 100, four streams, draw limits and density/annual
aggregation calculations remain unchanged. V2 writes `rng_protocol.csv`
with its version, base seed, stream stride, batch size and component offsets.
It also records the R RNG kind and R/INLA versions. The saved fit, input
checksums, INLA/R environment and row order remain essential
parts of a reproducibility record; this is not a guarantee of bitwise identity
across different libraries, architectures or versions.

No new jobs are submitted by this change. Use v2 only in a separately identified
future diagnostic run if one is warranted. Additional draws may clarify Monte
Carlo variability but do not fix model bias or approximation errors, and do
not create an independent validation dataset.
