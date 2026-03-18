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
- Interactive launcher script (run_workflow.sh) with guided configuration and Stan backend selection
- Singularity container definition (foodnet.def) with R, brms, RStan, and CmdStan via pixi
- Container build helper script (build_container.sh) with dependency verification
- Pre-compiled Stan headers in container for faster runtime model compilation
- CmdStan installed to /opt/cmdstan in container (avoids /root access issues on compute nodes)
- Support for rstan and cmdstanr backends (--stan_backend) with backend-aware memory allocation
- Difficulty-based resource profiling: TRENDY dynamically allocates CPUs, memory, and wall time per pathogen based on data complexity (easy/moderate/hard/very_hard)
- Per-state individual trend plots alongside site-level and overall trend charts
- Convergence diagnostics export (R-hat, bulk ESS, tail ESS, divergent transitions) per model
- Data cleaning rules via --data_rules CSV (county fixes, exclusions, pathogen filters); bundled default in analysis_configs/data_rules.csv
- Subgroup-level resource profiling (resource_profile_subgroups.csv) for serotype-split analyses
- Parameter presets: params/publication.yml, params/cmdstanr.yml, params/test.yml
- Synthetic test data (test_data/) and test profile for CI validation
- GitHub Actions CI workflow: shellcheck, R syntax validation, Nextflow config check
- CDC SciComp profiles: scicomp_rosalind (short.q routing), training, local, conda, debug
- Production profile with optimized MCMC settings (4 chains, 2000 iterations, adapt_delta=0.99)
- Nextflow execution reports, traces, timelines, and DAG visualizations

### `Fixed`

### `Dependencies`

- Nextflow >= 23.04.0
- R with brms, rstan, cmdstanr, tidybayes, haven
- Singularity >= 4.0.0
- Java >= 17

### `Deprecated`
