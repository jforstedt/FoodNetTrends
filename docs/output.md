# FoodNetTrends: Output

## Introduction

This document describes the output produced by the FoodNetTrends pipeline. The pipeline performs Bayesian spline modeling on FoodNet surveillance data to estimate incidence rate trends for foodborne pathogens.

All output directories listed below are created under `<outdir>/<projID>/` after the pipeline finishes. The `projID` defaults to a timestamp if not specified.

## Pipeline overview

The pipeline is built using [Nextflow](https://www.nextflow.io/) and processes data using the following steps:

- [Preprocessing](#preprocessing) - Data cleaning and incidence rate calculation
- [Spline modeling](#spline-modeling) - Bayesian spline trend estimation via brms/Stan
- [Dashboard](#dashboard) - Interactive HTML summary of results
- [Pipeline information](#pipeline-information) - Execution metrics and reports

### Preprocessing

<details markdown="1">
<summary>Output files</summary>

- `<projID>/preprocessed/`
  - `clean_mmwr.csv`: Cleaned and filtered MMWR data with calculated incidence rates.
  - `clean_mmwr_preprocessing_report.csv`: Pathogen standardization report showing how pathogen names were matched and recoded during preprocessing.
  - `resource_profile.csv`: Per-pathogen data metrics (row counts, site counts, complexity scores) used for resource allocation.
  - `metadata_states.csv`: State-level metadata summary (year ranges, case counts).
  - `metadata_cidt.csv`: Diagnostic method (CIDT) distribution summary.
  - `metadata_travel.csv`: Travel status distribution summary.

</details>

The preprocessing step reads the raw FoodNet MMWR SAS data file along with census population data, applies filtering based on the `states`, `travel`, and `cidt` parameters, optionally applies serotype recoding from a serotype configuration file, standardizes pathogen names using the configured `--matching_sensitivity` level, and calculates incidence rates per 100,000 population. The cleaned dataset is passed to the modeling step.

### Spline modeling

<details markdown="1">
<summary>Output files</summary>

- `<projID>/spline_results/`
  - `*_brm.Rds`: Fitted brms model objects (one per pathogen/subgroup).
  - `*_IRCatch.csv`: Estimated incidence rates by FoodNet catchment area.
  - `*_IRSite.csv`: Estimated incidence rates by surveillance site.
  - `*_EstIRRCatch_*.csv`: Estimated incidence rate ratios comparing each year to a baseline period, by catchment area. Used for relative risk and percent change calculations.
  - `*_summary.txt`: Plain-text brms model summary including coefficient estimates, R-hat values, and effective sample sizes.
  - `*_convergence_diagnostics.csv`: Convergence diagnostic metrics including R-hat, bulk ESS, tail ESS, and divergent transition counts for each model parameter.
  - `*_site_trends.png`: Trend plots showing fitted splines with credible intervals by surveillance site.
  - `*_overall_trend.png`: Overall trend plot showing the fitted spline with credible intervals across all sites.
  - `*_error.txt`: Error report for pathogens/subgroups where model fitting failed. Contains the error message and stack trace. Only produced when a model fails.

</details>

The core modeling step fits Bayesian penalized spline models using [brms](https://paul-buerkner.github.io/brms/) with the configured Stan backend (`rstan` or `cmdstanr`). Each pathogen or pathogen subgroup is modeled independently. The model estimates year-over-year incidence rate trends with uncertainty quantification.

Convergence diagnostics are automatically computed for each fitted model. The `*_convergence_diagnostics.csv` file reports R-hat statistics, effective sample sizes, and divergent transition counts, which can be used to assess whether the MCMC sampler converged.

### Dashboard

<details markdown="1">
<summary>Output files</summary>

- `<projID>/`
  - `dashboard.html`: Self-contained interactive HTML dashboard summarizing all pathogen trends.

</details>

The dashboard aggregates results from all pathogen models into a single interactive HTML report. It embeds CSV data as JSON and images as Base64, so the file is fully self-contained and can be opened in any web browser without a server. Dashboard generation can be skipped with `--skip_dashboard true`.

### Pipeline information

<details markdown="1">
<summary>Output files</summary>

- `<projID>/pipeline_info/`
  - `execution_report_*.html`: Nextflow execution report with task-level resource usage.
  - `execution_timeline_*.html`: Timeline visualization of task execution.
  - `execution_trace_*.txt`: Tab-delimited trace file with per-task metrics.
  - `pipeline_dag_*.html`: Directed acyclic graph of the pipeline workflow.

</details>

[Nextflow](https://www.nextflow.io/docs/latest/tracing.html) provides functionality for generating reports relevant to the running and execution of the pipeline. These reports help troubleshoot errors and provide information about launch commands, run times, and resource usage. The trace file is also used by `bin/monitor_pipeline.sh` for real-time progress monitoring.
