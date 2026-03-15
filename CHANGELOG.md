# cdcgov/foodnettrends: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.0dev - 2026-03-14

Initial release of cdcgov/foodnettrends.

### `Added`

- Bayesian hierarchical spline modeling of FoodNet MMWR surveillance data via brms/Stan
- PREPROCESS module: SAS data ingestion, pathogen name standardization (STRICT/MEDIUM/RELAXED), census merging
- TRENDY module: per-pathogen brms model fitting with configurable MCMC parameters
- RESOURCE_PROFILER module: data complexity estimation for compute planning
- DASHBOARD module: interactive HTML summary of results across pathogens
- PREPROCESS_ONLY entry point for data validation without model fitting
- AUTO_DISCOVER mode to detect available pathogens from input data
- Pathogen grouping support for STEC (O157/non-O157) and Salmonella (by serotype)
- Configurable serotype recoding and catchment area definitions via CSV
- Relative risk calculations across multiple reference periods
- Interactive launcher script (run_workflow.sh) with guided configuration
- Terminal-based pipeline monitor (bin/monitor_pipeline.sh)
- Singularity container definition (foodnet.def) with R, brms, RStan, and CmdStan via pixi
- Support for rstan and cmdstanr backends (--stan_backend)
- CDC SciComp profiles: scicomp_rosalind, training, local, conda, debug
- Production profile with optimized MCMC settings (4 chains, 2000 iterations, adapt_delta=0.99)
- Nextflow execution reports, traces, timelines, and DAG visualizations

### `Fixed`

### `Dependencies`

- Nextflow >= 23.04.0
- R with brms, rstan, cmdstanr, tidybayes, haven
- Singularity >= 4.0.0
- Java >= 17

### `Deprecated`
