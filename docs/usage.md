# FoodNet Trends: Usage

## Introduction

FoodNet Trends is a Bayesian spline modeling pipeline for estimating incidence rate trends from FoodNet surveillance data. It processes MMWR case data and census population files to fit penalized spline models for each pathogen, producing trend estimates with uncertainty quantification.

## Input data

The pipeline requires three input files:

| Parameter      | Description                                      | Format          |
| -------------- | ------------------------------------------------ | --------------- |
| `--mmwrFile`   | FoodNet MMWR case data                           | SAS (.sas7bdat) |
| `--censusFileB`| Census population data for bacterial pathogens   | SAS (.sas7bdat) |
| `--censusFileP`| Census population data for parasitic pathogens   | SAS (.sas7bdat) |

If you have already preprocessed the data, you can skip the preprocessing step by providing:

| Parameter          | Description                                  |
| ------------------ | -------------------------------------------- |
| `--preprocessed`   | Set to `true` to use a pre-cleaned CSV file  |
| `--cleanFile`      | Path to the preprocessed CSV file            |
| `--skip_preprocessing` | Set to `true` to skip preprocessing      |

## Running the pipeline

The typical command for running the pipeline is:

```bash
nextflow run FoodNetTrends \
    --mmwrFile /path/to/mmwr.sas7bdat \
    --censusFileB /path/to/census_bacterial.sas7bdat \
    --censusFileP /path/to/census_parasitic.sas7bdat \
    --outdir ./results \
    -profile singularity
```

### Key parameters

#### Pathogen selection

```bash
--pathogen 'Campylobacter,Salmonella,Shigella'   # Comma-separated list of pathogens
--pathogen_grouping 'SALMONELLA~Enteritidis|SALMONELLA~Typhimurium'  # Subgroup definitions
```

#### Data filtering

```bash
--states 'CT,GA,MD,MN,NM,OR,TN,CO,NY'   # States to include (null = all)
--travel 'NO,UNKNOWN,YES'                 # Travel status filter
--cidt 'CIDT+,CX+,PARASITIC'             # CIDT classification filter
```

#### Model parameters

```bash
--chains 4              # Number of MCMC chains (default: 2)
--iterations 2000       # Iterations per chain (default: 500)
--adapt_delta 0.99      # HMC adaptation target (default: 0.95)
--max_treedepth 15      # Maximum HMC tree depth (default: 10)
--seed 123              # Random seed (default: 123)
--stan_backend rstan     # Stan backend: "rstan" or "cmdstanr" (default: rstan)
```

#### Configuration files

```bash
--serotype_config /path/to/serotype_config.csv      # Serotype recoding rules
--catchment_config /path/to/catchment_config.csv    # Catchment area definitions
--matching_sensitivity MEDIUM                        # Name matching: STRICT, MEDIUM, or RELAXED
```

#### Output options

```bash
--outdir ./results       # Output directory (default: output)
--projID my_analysis     # Project identifier (default: timestamp)
--skip_dashboard true    # Skip dashboard generation
```

### Using a params file

Rather than specifying each flag on the command line, you can provide parameters in a YAML file:

```bash
nextflow run FoodNetTrends -profile singularity -params-file params.yaml
```

With `params.yaml` containing:

```yaml
mmwrFile: '/path/to/mmwr.sas7bdat'
censusFileB: '/path/to/census_bacterial.sas7bdat'
censusFileP: '/path/to/census_parasitic.sas7bdat'
outdir: './results'
pathogen: 'Campylobacter,Salmonella'
chains: 4
iterations: 2000
```

### Profiles

The pipeline supports the following profiles:

- `test` - Minimal test configuration with reduced iterations for fast validation
- `singularity` - Run with Singularity containers (recommended for HPC)
- `production` - Production settings with 4 chains, 2000 iterations, and stricter adaptation
- `debug` - Enable verbose logging and hash dumping

Multiple profiles can be combined: `-profile test,singularity`

### Updating the pipeline

When you run the above command, Nextflow automatically pulls the pipeline code from GitHub and stores it as a cached version. When running the pipeline after this, it will always use the cached version if available - even if the pipeline has been updated since. To make sure that you're running the latest version of the pipeline, make sure that you regularly update the cached version of the pipeline:

```bash
nextflow pull FoodNetTrends
```

### Reproducibility

It is a good idea to specify a pipeline version when running the pipeline on your data. This ensures that a specific version of the pipeline code and software are used when you run your pipeline. If you keep using the same tag, you'll be running the same version of the pipeline, even if there have been changes to the code since.

First, go to the releases page and find the latest pipeline version - numeric only (eg. `1.3.1`). Then specify this when running the pipeline with `-r` (one hyphen) - eg. `-r 1.3.1`.

To further assist in reproducibility, you can use share and re-use [parameter files](#using-a-params-file) to repeat pipeline runs with the same settings without having to write out a command with every single parameter.

## Core Nextflow arguments

These options are part of Nextflow and use a _single_ hyphen (pipeline parameters use a double-hyphen).

### `-profile`

Use this parameter to choose a configuration profile. Profiles can give configuration presets for different compute environments.

We highly recommend the use of Singularity containers for full pipeline reproducibility.

The pipeline also dynamically loads configurations from [https://github.com/nf-core/configs](https://github.com/nf-core/configs) when it runs, making multiple config profiles for various institutional clusters available at run time. For more information and to see if your system is available in these configs please see the [nf-core/configs documentation](https://github.com/nf-core/configs#documentation).

Note that multiple profiles can be loaded, for example: `-profile test,singularity` - the order of arguments is important!
They are loaded in sequence, so later profiles can overwrite earlier profiles.

If `-profile` is not specified, the pipeline will run locally and expect all software to be installed and available on the `PATH`. This is _not_ recommended, since it can lead to different results on different machines dependent on the computer environment.

### `-resume`

Specify this when restarting a pipeline. Nextflow will use cached results from any pipeline steps where the inputs are the same, continuing from where it got to previously. For input to be considered the same, not only the names must be identical but the files' contents as well. For more info about this parameter, see [this blog post](https://www.nextflow.io/blog/2019/demystifying-nextflow-resume.html).

You can also supply a run name to resume a specific run: `-resume [run-name]`. Use the `nextflow log` command to show previous run names.

### `-c`

Specify the path to a specific config file (this is a core Nextflow command). See the [nf-core website documentation](https://nf-co.re/usage/configuration) for more information.

## Custom configuration

### Resource requests

The default requirements set within the pipeline will work for most analyses. The TRENDY process dynamically allocates CPUs based on the number of chains and memory based on data complexity. If a job exits with a retriable error code, it will automatically be resubmitted with higher resource requests (up to 3 retries).

To change the resource requests, please see the [max resources](https://nf-co.re/docs/usage/configuration#max-resources) and [tuning workflow resources](https://nf-co.re/docs/usage/configuration#tuning-workflow-resources) section of the nf-core website.

### nf-core/configs

In most cases, you will only need to create a custom config as a one-off but if you and others within your organisation are likely to be running nf-core pipelines regularly and need to use the same settings regularly it may be a good idea to request that your custom config file is uploaded to the `nf-core/configs` git repository. Before you do this please can you test that the config file works with your pipeline of choice using the `-c` parameter. You can then create a pull request to the `nf-core/configs` repository with the addition of your config file, associated documentation file (see examples in [`nf-core/configs/docs`](https://github.com/nf-core/configs/tree/master/docs)), and amending [`nfcore_custom.config`](https://github.com/nf-core/configs/blob/master/nfcore_custom.config) to include your custom profile.

See the main [Nextflow documentation](https://www.nextflow.io/docs/latest/config.html) for more information about creating your own configuration files.

## Running in the background

Nextflow handles job submissions and supervises the running jobs. The Nextflow process must run until the pipeline is finished.

The Nextflow `-bg` flag launches Nextflow in the background, detached from your terminal so that the workflow does not stop if you log out of your session. The logs are saved to a file.

Alternatively, you can use `screen` / `tmux` or similar tool to create a detached session which you can log back into at a later time.
Some HPC setups also allow you to run nextflow within a cluster job submitted your job scheduler (from where it submits more jobs).

## Nextflow memory requirements

In some cases, the Nextflow Java virtual machines can start to request a large amount of memory.
We recommend adding the following line to your environment to limit this (typically in `~/.bashrc` or `~./bash_profile`):

```bash
NXF_OPTS='-Xms1g -Xmx4g'
```
