# FoodNetTrends: Usage

## Introduction

FoodNetTrends is a Bayesian spline modeling pipeline for estimating incidence rate trends from FoodNet surveillance data. It processes MMWR case data and census population files to fit penalized spline models for each pathogen, producing trend estimates with uncertainty quantification.

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
nextflow run main.nf \
    --mmwrFile /path/to/mmwr.sas7bdat \
    --censusFileB /path/to/census_bacterial.sas7bdat \
    --censusFileP /path/to/census_parasitic.sas7bdat \
    --outdir ./results \
    -profile singularity
```

When pulling from GitHub, use `nextflow run cdcgov/foodnettrends` instead of `nextflow run main.nf`.

### Interactive launcher

The `run_workflow.sh` script provides an interactive menu-driven launcher for the pipeline on CDC HPC systems. It handles module loading (Nextflow, Singularity, Java), prompts for pathogen selection and subgroup options (e.g., STEC O157/non-O157 split, Salmonella serotype selection), Stan backend choice, and optional configuration files. It can also launch the pipeline in the background and start the monitor script automatically.

```bash
./run_workflow.sh
```

The launcher supports `AUTO_DISCOVER` mode: if the `--pathogen` parameter is left empty, all pathogens present in the preprocessed data are discovered automatically.

### Pipeline monitor

The `bin/monitor_pipeline.sh` script provides a real-time terminal dashboard that tracks per-pathogen progress by reading the Nextflow execution trace file.

```bash
./bin/monitor_pipeline.sh output/20260313_160520           # 5s refresh (default)
./bin/monitor_pipeline.sh -i 10 output/20260313_160520     # 10s refresh
./bin/monitor_pipeline.sh -1 output/20260313_160520        # single snapshot, no loop
```

Options:
- `-i SECONDS` -- refresh interval (default: 5)
- `-1` -- print a single snapshot and exit
- `-h` -- show help

### Key parameters

#### Pathogen selection

```bash
--pathogen 'CAMPYLOBACTER,SALMONELLA,SHIGELLA'   # Comma-separated list of pathogens
--pathogen_grouping 'STEC~O157|STEC~nonO157|SALMONELLA~Enteritidis'  # Subgroup definitions
```

When `--pathogen` is omitted and preprocessed data is provided, the pipeline can auto-discover all pathogens present in the dataset.

#### Data filtering

```bash
--states 'CT,GA,MD,MN,NM,OR,TN,CO,NY'   # States to include (null = all)
--travel 'NO,UNKNOWN,YES'                 # Travel status filter (default: NO,UNKNOWN,YES)
--cidt 'CIDT+,CX+,PARASITIC'             # CIDT classification filter (default: CIDT+,CX+,PARASITIC)
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
--matching_sensitivity MEDIUM                        # Pathogen name matching: STRICT, MEDIUM, or RELAXED (default: MEDIUM)
```

See [configuration.md](configuration.md) for details on the CSV formats and matching sensitivity levels.

#### Output options

```bash
--outdir ./results       # Output directory (default: output)
--projID my_analysis     # Project identifier (default: auto-generated timestamp)
--skip_dashboard true    # Skip dashboard generation (default: false)
```

### Using a params file

Rather than specifying each flag on the command line, you can provide parameters in a YAML file:

```bash
nextflow run main.nf -profile singularity -params-file params.yaml
```

With `params.yaml` containing:

```yaml
mmwrFile: '/path/to/mmwr.sas7bdat'
censusFileB: '/path/to/census_bacterial.sas7bdat'
censusFileP: '/path/to/census_parasitic.sas7bdat'
outdir: './results'
pathogen: 'CAMPYLOBACTER,SALMONELLA'
chains: 4
iterations: 2000
```

### Profiles

The pipeline supports the following profiles, defined across `nextflow.config` and `conf/fnt.scicomp.config`:

| Profile | Source | Description |
|---------|--------|-------------|
| `test` | nextflow.config | Minimal test run: 2 chains, 50 iterations, CAMPYLOBACTER only, dashboard skipped |
| `singularity` | nextflow.config + fnt.scicomp.config | Run with Singularity containers (recommended for HPC) |
| `production` | nextflow.config | Production settings: 4 chains, 2000 iterations, adapt_delta 0.99, max_treedepth 15 |
| `debug` | nextflow.config + fnt.scicomp.config | Verbose logging, hash dumping, NXF_DEBUG=3, bash -x tracing |
| `conda` | fnt.scicomp.config | Use Conda environments instead of containers; loads miniconda module |
| `local` | fnt.scicomp.config | Run all processes on the local machine (4 CPUs, 16 GB); useful for interactive qlogin testing |
| `scicomp_rosalind` | fnt.scicomp.config | CDC Rosalind HPC cluster: SGE executor, queue routing (short.q/all.q/long.q), scratch dirs |
| `training` | fnt.scicomp.config | Routes all jobs to `training.q`; combine with `scicomp_rosalind` |

Multiple profiles can be combined with commas. Order matters -- later profiles override earlier ones.

```bash
# CDC HPC with Singularity containers
-profile singularity,scicomp_rosalind

# CDC HPC on training queue
-profile singularity,scicomp_rosalind,training

# Production settings on CDC HPC
-profile singularity,scicomp_rosalind,production

# Local testing in a qlogin session
-profile singularity,local
```

Note that lightweight processes (PREPROCESS, RESOURCE_PROFILER, DASHBOARD) always run on the local executor regardless of profile, to avoid scheduler overhead.

### Updating the pipeline

If you are running the pipeline from a remote GitHub repository:

```bash
nextflow pull cdcgov/foodnettrends
```

For local checkouts, use `git pull` to update the code.

### Reproducibility

Specify a pipeline version with `-r` (one hyphen) when running from a remote repository to pin a specific release:

```bash
nextflow run cdcgov/foodnettrends -r 1.0.0 -profile singularity
```

To further assist in reproducibility, use [parameter files](#using-a-params-file) to repeat pipeline runs with the same settings.

## Core Nextflow arguments

These options are part of Nextflow and use a _single_ hyphen (pipeline parameters use a double-hyphen).

### `-profile`

Use this parameter to choose a configuration profile. See the [Profiles](#profiles) section above for available options.

### `-resume`

Specify this when restarting a pipeline. Nextflow will use cached results from any pipeline steps where the inputs are the same, continuing from where it got to previously. For input to be considered the same, not only the names must be identical but the files' contents as well. For more info about this parameter, see [this blog post](https://www.nextflow.io/blog/2019/demystifying-nextflow-resume.html).

You can also supply a run name to resume a specific run: `-resume [run-name]`. Use the `nextflow log` command to show previous run names.

### `-c`

Specify the path to a specific config file (this is a core Nextflow command). See the [Nextflow documentation](https://www.nextflow.io/docs/latest/config.html) for more information.

## Resource allocation

The default resource settings work for most analyses. The TRENDY process dynamically allocates CPUs based on the number of chains (one CPU per chain) and memory based on data complexity. If a job exits with a retriable error code, it is automatically resubmitted with higher resource requests (up to 3 retries).

Resource limits vary by profile:
- **Default (SGE)**: up to 32 CPUs, 128 GB memory, 240 hours
- **scicomp_rosalind**: up to 44 CPUs, 356 GB memory, 28 days
- **local**: up to 4 CPUs, 16 GB memory, 4 hours

## Running in the background

Nextflow handles job submissions and supervises the running jobs. The Nextflow process must run until the pipeline is finished.

The Nextflow `-bg` flag launches Nextflow in the background, detached from your terminal so that the workflow does not stop if you log out of your session. The logs are saved to a file.

Alternatively, you can use `screen` / `tmux` or similar tool to create a detached session which you can log back into at a later time. Some HPC setups also allow you to run Nextflow within a cluster job submitted to your job scheduler (from where it submits more jobs).

## Nextflow memory requirements

In some cases, the Nextflow Java virtual machines can start to request a large amount of memory. We recommend adding the following line to your environment to limit this (typically in `~/.bashrc` or `~/.bash_profile`):

```bash
NXF_OPTS='-Xms1g -Xmx4g'
```
