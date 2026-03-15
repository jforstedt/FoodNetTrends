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

- `<projID>/`
  - `clean_mmwr.csv`: Cleaned and filtered MMWR data with calculated incidence rates.

</details>

The preprocessing step reads the raw FoodNet MMWR SAS data file along with census population data, applies filtering based on the `states`, `travel`, and `cidt` parameters, optionally applies serotype recoding from a serotype configuration file, and calculates incidence rates per 100,000 population. The cleaned dataset is passed to the modeling step.

### Spline modeling

<details markdown="1">
<summary>Output files</summary>

- `<projID>/spline_results/`
  - `*_brm.Rds`: Fitted brms model objects (one per pathogen/subgroup).
  - `*_IRCatch.csv`: Estimated incidence rates by FoodNet catchment area.
  - `*_IRSite.csv`: Estimated incidence rates by surveillance site.
  - `*.png`: Trend plots showing fitted splines with credible intervals.

</details>

The core modeling step fits Bayesian penalized spline models using [brms](https://paul-buerkner.github.io/brms/) with the configured Stan backend (`rstan` or `cmdstanr`). Each pathogen or pathogen subgroup is modeled independently. The model estimates year-over-year incidence rate trends with uncertainty quantification.

### Dashboard

<details markdown="1">
<summary>Output files</summary>

- `<projID>/`
  - `dashboard.html`: Interactive HTML dashboard summarizing all pathogen trends.

</details>

The dashboard aggregates results from all pathogen models into a single interactive HTML report. It can be opened in any web browser. Dashboard generation can be skipped with `--skip_dashboard true`.

### Pipeline information

<details markdown="1">
<summary>Output files</summary>

- `<projID>/pipeline_info/`
  - `execution_report_*.html`: Nextflow execution report with task-level resource usage.
  - `execution_timeline_*.html`: Timeline visualization of task execution.
  - `execution_trace_*.txt`: Tab-delimited trace file with per-task metrics.
  - `pipeline_dag_*.html`: Directed acyclic graph of the pipeline workflow.

</details>

[Nextflow](https://www.nextflow.io/docs/latest/tracing.html) provides functionality for generating reports relevant to the running and execution of the pipeline. These reports help troubleshoot errors and provide information about launch commands, run times, and resource usage.
