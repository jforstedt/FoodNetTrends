# FoodNetTrends

A Nextflow pipeline for Bayesian hierarchical spline modeling of CDC FoodNet surveillance data. FoodNetTrends fits pathogen-specific incidence models using `brms`/Stan, producing trend estimates, site-level comparisons, and relative risk calculations across FoodNet catchment areas.

**Primary citation:** Weller DL, et al. Enhanced Bayesian Spline Regression Approach for Modelling Trends in Infections Caused by Pathogens Commonly Transmitted Through Food. *Zoonoses*. 2026;6:3. doi: [10.15212/ZOONOSES-2025-0030](https://doi.org/10.15212/ZOONOSES-2025-0030)

## Features

1. Preprocesses raw MMWR surveillance data with configurable pathogen name standardization
2. Automatic detection of available pathogens from input data (`AUTO_DISCOVER` mode)
3. Flexible pathogen grouping for STEC (O157 / non-O157) and Salmonella (by serotype)
4. Bayesian hierarchical models with splines via `brms` (RStan or CmdStanR backend)
5. Incidence rate estimates with uncertainty intervals per catchment site
6. Relative risk and percent-change calculations across reference periods
7. Interactive HTML dashboard summarizing results across pathogens
8. Resource profiling to estimate compute requirements per pathogen
9. Configurable serotype recoding and catchment area definitions
10. Real-time terminal monitoring of pipeline progress

## Requirements

- Nextflow >= 23.04.0
- Singularity >= 4.0.0 (or Apptainer)
- Java >= 17

On CDC SciComp (Rosalind), load the required modules:

```bash
module load nextflow/24.10.4 singularity/4.1.4 java/17.0.6
```

## Container Setup

The pipeline runs inside a Singularity container built from `foodnet.def`. Build it before your first run:

```bash
singularity build foodnet.sif foodnet.def
```

The container includes R, brms, RStan, CmdStan, and all dependencies, managed via [pixi](https://pixi.sh). The built image must be in the launch directory (or update `process.container` in `nextflow.config`).

## Input Data

| Parameter | Description |
|-----------|-------------|
| `--mmwrFile` | Path to FoodNet MMWR SAS data file (`.sas7bdat`) |
| `--censusFileB` | Census data for bacterial pathogens (`.sas7bdat`) |
| `--censusFileP` | Census data for parasitic pathogens (`.sas7bdat`) |

## Parameters

### Input / Output

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--outdir` | `output` | Base output directory |
| `--projID` | auto-generated timestamp | Project identifier for this run |
| `--pathogen` | `null` | Comma-separated list of pathogens, or `AUTO_DISCOVER` |
| `--pathogen_grouping` | `null` | Pipe-separated groupings (e.g., `STEC~O157\|STEC~nonO157`) |
| `--skip_dashboard` | `false` | Skip HTML dashboard generation |
| `--skip_preprocessing` | `false` | Skip the preprocessing step entirely |

Supported pathogens: `CAMPYLOBACTER`, `CYCLOSPORA`, `SALMONELLA`, `SHIGELLA`, `STEC`, `VIBRIO`, `YERSINIA`.

When `--pathogen` is `null` and not `AUTO_DISCOVER`, the workflow defaults to `CAMPYLOBACTER,CYCLOSPORA`.

### Data Filtering

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--travel` | `NO,UNKNOWN,YES` | Travel status values to include |
| `--cidt` | `CIDT+,CX+,PARASITIC` | Diagnostic method types to include |
| `--states` | `null` (all) | Comma-separated state filter |
| `--matching_sensitivity` | `MEDIUM` | Pathogen name matching: `STRICT`, `MEDIUM`, or `RELAXED` |

### Preprocessing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--preprocessed` | `false` | Set `true` to supply a pre-cleaned CSV instead of raw SAS |
| `--cleanFile` | `null` | Path to cleaned CSV (when `--preprocessed true`) |

### Model

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--chains` | `2` | Number of MCMC chains |
| `--iterations` | `500` | Iterations per chain |
| `--adapt_delta` | `0.95` | HMC adaptation target |
| `--max_treedepth` | `10` | Maximum HMC tree depth |
| `--seed` | `123` | Random seed |
| `--stan_backend` | `rstan` | Stan backend: `rstan` or `cmdstanr` |

### Optional Configuration Files

| Parameter | Description |
|-----------|-------------|
| `--serotype_config` | CSV with custom serotype recoding rules |
| `--catchment_config` | CSV with custom catchment area definitions |

Example configurations are in `analysis_configs/examples/`.

## Running the Pipeline

### Interactive Launcher (Recommended)

```bash
./run_workflow.sh
```

The launcher walks you through selecting pathogens, configuring STEC/Salmonella groupings, setting model parameters, and choosing whether to reuse existing preprocessed data. It submits the Nextflow command for you.

### Direct Nextflow Command

```bash
nextflow run main.nf \
  -profile singularity \
  -entry FOODNETTRENDS \
  --mmwrFile "/path/to/mmwr.sas7bdat" \
  --censusFileB "/path/to/census_b.sas7bdat" \
  --censusFileP "/path/to/census_p.sas7bdat" \
  --pathogen "CAMPYLOBACTER,SALMONELLA" \
  --chains 2 \
  --iterations 500
```

### Preprocessing Only

Run the `PREPROCESS_ONLY` entry point to clean and validate data without fitting models:

```bash
nextflow run main.nf \
  -profile singularity \
  -entry PREPROCESS_ONLY \
  --mmwrFile "/path/to/mmwr.sas7bdat" \
  --censusFileB "/path/to/census_b.sas7bdat" \
  --censusFileP "/path/to/census_p.sas7bdat"
```

## Profiles

| Profile | Description |
|---------|-------------|
| `singularity` | Run with the Singularity container (required for most use cases) |
| `production` | Production MCMC settings: 4 chains, 2000 iterations, adapt_delta=0.99, max_treedepth=15 |
| `test` | Quick validation with minimal resources |
| `scicomp_rosalind` | CDC SciComp Rosalind HPC with SGE queue routing |
| `training` | Routes jobs to `training.q` (combine with `scicomp_rosalind`) |
| `local` | Local execution for interactive sessions (4 CPUs, 16 GB) |
| `conda` | Conda-based environment instead of container |
| `debug` | Verbose logging, hash dumps, hostname echo |

Combine profiles as needed, e.g.:

```bash
nextflow run main.nf -profile singularity,scicomp_rosalind,production ...
```

## Monitoring

Use the monitor script to track progress of a running pipeline:

```bash
bin/monitor_pipeline.sh output/<projID>
bin/monitor_pipeline.sh -i 10 output/<projID>   # 10-second refresh
bin/monitor_pipeline.sh -1 output/<projID>       # single snapshot
```

The monitor parses Nextflow trace files and displays per-pathogen status, runtime, and peak memory in a terminal dashboard.

## Output

```
output/<projID>/
├── pipeline_info/
│   ├── execution_report_*.html
│   ├── execution_trace_*.txt
│   ├── execution_timeline_*.html
│   └── pipeline_dag_*.html
├── preprocessed/
│   ├── clean_mmwr.csv
│   ├── clean_mmwr_preprocessing_report.csv
│   ├── resource_profile.csv
│   ├── metadata_states.csv
│   ├── metadata_cidt.csv
│   └── metadata_travel.csv
├── spline_results/
│   ├── <PATHOGEN>_brm.Rds
│   ├── <PATHOGEN>_IRCatch.csv
│   ├── <PATHOGEN>_IRSite.csv
│   ├── <PATHOGEN>_summary.txt
│   ├── <PATHOGEN>_convergence_diagnostics.csv
│   ├── <PATHOGEN>_site_trends.png
│   ├── <PATHOGEN>_overall_trend.png
│   ├── <PATHOGEN>_EstIRRCatch_*.csv
│   └── <PATHOGEN>_error.txt          # only if model fitting fails
└── dashboard/                    # unless --skip_dashboard true
    └── dashboard.html
```

## Troubleshooting

1. **Convergence warnings** -- increase `--adapt_delta` (try 0.99) and `--iterations`
2. **Memory errors** -- reduce chain count or run fewer pathogens per batch
3. **Failed jobs** -- resume with `nextflow run main.nf -resume`
4. **Pathogen not found** -- check spelling or try `--matching_sensitivity RELAXED`
5. **STEC grouping issues** -- confirm `stec_class` column is present in the data

## Credits

FoodNetTrends was developed by Josh Forstedt (CDC/OAMD SciComp) and Daniel Weller (CDC/DFWED/EDEB), with support from Beau Bruce (CDC/DFWED/EDEB) and Erica Billig Rose (CDC/DFWED/EDEB).

This pipeline uses code and infrastructure developed and maintained by the [nf-core](https://nf-co.re) community, reused here under the [MIT license](https://github.com/nf-core/tools/blob/master/LICENSE).

## Contributing

If you would like to contribute to this pipeline, please see the [contributing guidelines](CONTRIBUTING.md).

## Citations

See [`CITATIONS.md`](CITATIONS.md) for a full list of references.

## Public Domain Standard Notice

This repository constitutes a work of the United States Government and is not subject to domestic copyright protection under 17 USC 105. This repository is in the public domain within the United States, and copyright and related rights in the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/). All contributions to this repository are accepted under the Apache License, Version 2.0, or any later version.

## License Standard Notice

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

## Privacy Standard Notice

This repository contains only non-sensitive, publicly available data and information. All material and community participation is covered by the [Disclaimer](DISCLAIMER.md) and [Code of Conduct](code-of-conduct.md). For more information about CDC's privacy policy, please visit https://www.cdc.gov/other/privacy.html.

## Contributing Standard Notice

Anyone is encouraged to contribute to the repository by [forking](https://help.github.com/articles/fork-a-repo) and submitting a pull request. (If you are new to GitHub, you might start with a [basic tutorial](https://help.github.com/articles/set-up-git).) By contributing to this project, you grant a world-wide, royalty-free, perpetual, irrevocable, non-exclusive, transferable license to all users under the terms of the [Apache License v2](https://www.apache.org/licenses/LICENSE-2.0) or later.

All comments, messages, pull requests, and other submissions received through CDC, including this GitHub page, may be subject to applicable federal law, including but not limited to the Federal Records Act, and may be archived. Learn more at https://www.cdc.gov/other/privacy.html.

## Records Management Standard Notice

This repository is not a source of government records but is a copy to increase collaboration and code sharing. All government records will be published through the [CDC web site](https://www.cdc.gov).

## SHARE IT Act Compliance

```
Organization: NCEZID/AMD

Contact email: ncezid_shareit@cdc.gov

Exemption: NA

Exemption Justification: NA

Description fields:
```

## Additional Standard Notices

Please refer to [CDC's Template Repository](https://github.com/CDCgov/template) for more information about [contributing to this repository](https://github.com/CDCgov/template/blob/master/CONTRIBUTING.md), [public domain notices and disclaimers](https://github.com/CDCgov/template/blob/master/DISCLAIMER.md), and [code of conduct](https://github.com/CDCgov/template/blob/master/code-of-conduct.md).
