# FoodNetTrends: Configuration

## Table of Contents
- [Nextflow configuration files](#nextflow-configuration-files)
- [Data cleaning rules](#data-cleaning-rules)
- [Serotype configuration](#serotype-configuration)
- [Catchment configuration](#catchment-configuration)
- [Pathogen name matching](#pathogen-name-matching)
- [R environment (pixi)](#r-environment-pixi)
- [Usage examples](#usage-examples)

## Nextflow configuration files

The pipeline's behavior is controlled by several Nextflow config files that are loaded automatically:

| File | Purpose |
|------|---------|
| `nextflow.config` | Main config: default parameter values, SGE executor settings, process resource allocation, Singularity/registry setup, trace/report/timeline/DAG output paths, and profile definitions (`test`, `singularity`, `production`, `debug`). |
| `conf/base.config` | Base resource defaults and retry strategy. Defines process labels (`process_single`, `process_low`, `process_medium`, `process_high`, `process_long`, `process_high_memory`) used by DSL2 modules. |
| `conf/fnt.scicomp.config` | CDC SciComp HPC profiles: `singularity`, `conda`, `local`, `scicomp_rosalind`, `training`, `debug`. Also defines special queue labels (`process_gpu`, `process_extralong`, `process_highmem`). |
| `conf/modules.config` | DSL2 module publishing paths. TRENDY resource allocation (CPUs, memory, time) is defined in `modules/local/trendy.nf` where difficulty metrics are accessible. |
| `conf/test.config` | Test profile overrides: 1 chain, 100 iterations, CAMPYLOBACTER + SALMONELLA, dashboard included, resource limits capped at 2 CPUs / 8 GB / 1 hour for CI. |

To override settings without editing these files, use Nextflow's `-c` flag:

```bash
nextflow run main.nf -profile singularity -c my_overrides.config
```

Or pass individual parameters on the command line with `--` (double hyphen):

```bash
nextflow run main.nf -profile singularity --chains 4 --iterations 2000
```

## Data cleaning rules

The `--data_rules` parameter accepts a CSV file that defines data cleaning operations applied during preprocessing. A bundled default is provided at `analysis_configs/data_rules.csv`.

### CSV format

| Column | Description | Required |
|--------|-------------|----------|
| rule_type | Type of rule: `county_fix`, `county_remove`, `site_exclude`, or `pathogen_filter` | Yes |
| match_column | Column to match against (e.g., `county`, `siteid`, `pathogen`) | Yes |
| match_value | Value to match in that column | Yes |
| replacement | Replacement value (for `county_fix` rules; leave empty for removals) | No |
| condition | Optional condition expression (e.g., `year < 2023`, `cste == 'YES'`) | No |
| notes | Documentation for the rule | No |

### Rule types

- **county_fix**: Corrects county name typos or inconsistencies (e.g., `ST. MARYS` to `ST. MARY'S`).
- **county_remove**: Removes records matching the county value (e.g., `OUT OF STATE`, `UNKNOWN`).
- **site_exclude**: Excludes records for a site ID, optionally with a condition (e.g., exclude COEX before 2023).
- **pathogen_filter**: Applies pathogen-specific filters (e.g., restrict Listeria to invasive cases where `cste == 'YES'`).

### Example

```csv
rule_type,match_column,match_value,replacement,condition,notes
county_fix,county,ST. MARYS,ST. MARY'S,,Apostrophe correction
county_fix,county,PRINCE GEORGES,PRINCE GEORGE'S,,Apostrophe correction
county_remove,county,OUT OF STATE,,,Remove out-of-state records
county_remove,county,UNKNOWN,,,Remove unknown counties
site_exclude,siteid,COEX,,year < 2023,Exclude COEX pre-2023 (CO expansion)
pathogen_filter,pathogen,LISTERIA,,cste == 'YES',Invasive Listeria only (CSTE definition)
```

### Usage

```bash
nextflow run main.nf \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --data_rules analysis_configs/data_rules.csv
```

## Serotype configuration

The serotype configuration feature allows you to customize which serotype values are recoded as "Missing" or mapped to other values during preprocessing.

### Default behavior

By default, the following serotype values are recoded to "Missing":
- NOT SPECIATED
- UNKNOWN
- PARTIAL SERO
- NOT SERO
- (empty string)
- Any value containing "UNDET"

### Custom configuration

Create a CSV file with the following columns:

| Column | Description | Required |
|--------|-------------|----------|
| serotype_value | The original serotype value to match | Yes |
| replacement | What to replace it with | Yes |
| pathogen | Apply to specific pathogen or "all" | Yes |
| match_type | "exact" or "contains" | Yes |
| notes | Optional documentation | No |

Example configuration file (`analysis_configs/examples/serotype_config.csv`):

```csv
serotype_value,replacement,pathogen,match_type,notes
NOT SPECIATED,Missing,all,exact,Default missing value
UNKNOWN,Missing,all,exact,Default missing value
PARTIAL SERO,Missing,all,exact,Default missing value
NOT SERO,Missing,all,exact,Default missing value
"",Missing,all,exact,Empty string missing value
UNDET,Missing,all,contains,Pattern-based rule for undetermined
ROUGH,Missing,SALMONELLA,exact,Salmonella-specific non-informative value
NONTYPEABLE,Missing,SALMONELLA,exact,Salmonella-specific non-informative value
```

### Using the configuration

#### With Nextflow
```bash
nextflow run main.nf \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --serotype_config config/my_serotype_rules.csv
```

#### With R script directly
```bash
Rscript bin/preprocess.R \
  --mmwrFile data/mmwr.sas7bdat \
  --outputFile clean_mmwr.csv \
  --serotype-config config/my_serotype_rules.csv
```

## Catchment configuration

The catchment configuration feature allows you to define custom geographic and temporal boundaries for analysis.

### Default behavior

By default, the pipeline uses the standard FoodNet catchment areas:
- CA: 1996-present
- CO: 2001-present
- CT: 1996-present
- GA: 1996-present
- MD: 1998-present
- MN: 1996-present
- NM: 2004-present
- NY: 1998-present
- OR: 1996-present
- TN: 2000-present

### Custom configuration

Create a CSV file with the following columns:

| Column | Description | Required |
|--------|-------------|----------|
| state | Two-letter state code | Yes |
| start_year | First year to include | Yes |
| end_year | Last year to include (use 9999 for no end) | Yes |
| pathogen_type | "bacterial", "parasitic", or "both" | No |
| notes | Optional documentation | No |

Example configuration file (`analysis_configs/examples/catchment_config.csv`):

```csv
state,start_year,end_year,pathogen_type,notes
CA,1996,9999,both,Original FoodNet site
CO,2001,9999,both,Joined 2001
CT,1996,9999,both,Original FoodNet site
GA,1996,9999,both,Original FoodNet site
MD,1998,9999,both,Joined 1998
MN,1996,9999,both,Original FoodNet site
NM,2004,9999,both,Joined 2004
NY,1998,9999,both,Joined 1998
OR,1996,9999,both,Original FoodNet site
TN,2000,9999,both,Joined 2000
```

### Using the configuration

#### With Nextflow
```bash
nextflow run main.nf \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --catchment_config config/my_catchment_areas.csv
```

#### With R script directly
```bash
Rscript bin/trendy.R \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --projID myproject \
  --catchment-config config/my_catchment_areas.csv
```

## Pathogen name matching

The `--matching_sensitivity` parameter controls how strictly pathogen names in the input data are matched to canonical names during preprocessing. This is handled by `preprocess.R`.

| Level | Behavior |
|-------|----------|
| `STRICT` | Exact case-insensitive match only. No fuzzy matching. |
| `MEDIUM` | Allows minor variations (whitespace, punctuation). Default. |
| `RELAXED` | Uses string distance (Levenshtein) to match similar names. Requires the `stringdist` R package. |

```bash
nextflow run main.nf --matching_sensitivity STRICT ...
```

## R environment (pixi)

The pipeline's R dependencies are managed through [pixi](https://pixi.sh), a conda-compatible package manager. The container image (`foodnet.sif`) ships with a pixi environment pre-installed at `/opt/pipeline/.pixi/envs/default/`. The `nextflow.config` sets `R_LIBS` to point to this environment's R library path:

```
R_LIBS = "/opt/pipeline/.pixi/envs/default/lib/R/library"
```

The environment is defined by `pixi.toml` and locked by `pixi.lock` in the repository root. To rebuild the environment locally (e.g., for development outside the container), run:

```bash
pixi install
```

## Usage examples

### Example 1: Custom analysis for a research study

If you are conducting a study focusing on specific states and years:

1. Create a custom catchment configuration:
```csv
state,start_year,end_year,pathogen_type,notes
CA,2010,2020,both,Study period California
NY,2010,2020,both,Study period New York
TX,2015,2020,both,Added Texas for comparison
```

2. Run the pipeline:
```bash
nextflow run main.nf \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --catchment_config config/study_catchment.csv
```

### Example 2: Pathogen-specific serotype rules

For a Salmonella-focused analysis with custom serotype mapping:

1. Create serotype configuration:
```csv
serotype_value,replacement,pathogen,match_type,notes
TYPHIMURIUM VAR 5-,TYPHIMURIUM,SALMONELLA,exact,Consolidate variants
I 4,[5],12:i:-,TYPHIMURIUM,SALMONELLA,exact,Monophasic variant
ROUGH,Missing,SALMONELLA,exact,Non-typeable
```

2. Run the pipeline:
```bash
nextflow run main.nf \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --serotype_config config/salmonella_serotypes.csv \
  --pathogen SALMONELLA
```

### Example 3: Both configurations together

```bash
nextflow run main.nf \
  --mmwrFile data/mmwr.sas7bdat \
  --censusFileB data/census_b.sas7bdat \
  --censusFileP data/census_p.sas7bdat \
  --serotype_config config/custom_serotypes.csv \
  --catchment_config config/custom_catchment.csv \
  --matching_sensitivity STRICT \
  --projID custom_analysis_2024
```

## Best practices

1. **Test with small datasets**: When using custom configurations, test with a subset of data first using `-profile test`.

2. **Document your rules**: Use the notes column to explain why certain rules exist.

3. **Version control**: Keep your configuration files in version control alongside your analysis code.

4. **Validation**: The pipeline validates configuration files and will provide clear error messages if issues are found.

5. **Backward compatibility**: If no configuration files are provided, the pipeline uses the original hardcoded defaults.
