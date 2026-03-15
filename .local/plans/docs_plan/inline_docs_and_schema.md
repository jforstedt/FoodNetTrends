# Inline Documentation, Help Text, Error Messages, and Schema Audit

Audited on: 2026-03-14

## 1. Schema vs Config Inconsistencies (`nextflow_schema.json` vs `nextflow.config`)

### 1.1 `max_cpus` default mismatch
- **Schema** (`nextflow_schema.json` line 253): `"default": 16`
- **Config** (`nextflow.config` line 67): `max_cpus = 32`
- **Impact**: Users reading the schema or `--help` will see 16 as the default, but the pipeline actually uses 32.

### 1.2 Missing params in schema
The following params exist in `nextflow.config` but are absent from `nextflow_schema.json`:
- `whichScript` (line 19) -- path to the R modeling script
- `trendyScript` (line 20) -- alias for `whichScript`; used by `spline.nf` when calling TRENDY
- `cpus` (line 22) -- default CPU count for logging
- `validationSchemaIgnoreParams` (line 73) -- schema validation ignore list

These are internal/advanced params, so omitting them from the schema is arguably intentional, but `trendyScript` and `cpus` appear in user-visible log output (spline.nf line 73: "Cores: ${params.cpus}"), so their absence from the schema is misleading.

### 1.3 Schema `$id` references old repo name
- **Schema** (`nextflow_schema.json` line 3): `"$id": "https://raw.githubusercontent.com/cdc/spline/master/nextflow_schema.json"`
- Should reference `FoodNetTrends`, not `cdc/spline`.

## 2. Pipeline Name Inconsistencies ("cdc/spline" vs "FoodNetTrends")

### 2.1 Groovy libs still reference "cdc/spline"
- `WorkflowMain.groovy` (line 2): `"specific to the main.nf workflow in the cdc/spline pipeline"`
- `WorkflowMain.groovy` (line 20): citation URL `"https://github.com/${workflow.manifest.name}/blob/master/CITATIONS.md"` -- this dynamically uses manifest name (OK), but the comment on line 2 is hardcoded.
- `WorkflowSpline.groovy` (line 2): `"specific to the workflow/spline.nf in the cdc/spline pipeline"`

### 2.2 Email templates hardcode "cdc/spline"
- `email_template.html` (line 7): `<meta name="description" content="cdc/spline: Spline Modeling">`
- `email_template.html` (line 8): `<title>cdc/spline Pipeline Report</title>`
- `email_template.html` (line 15): `<h1>cdc/spline ${version}</h1>`
- `email_template.html` (line 21): `cdc/spline execution completed unsuccessfully!`
- `email_template.html` (line 30): `cdc/spline execution completed successfully!`
- `email_template.html` (line 47): `<p>cdc/spline</p>`
- `email_template.html` (line 48): `<p><a href="https://github.com/cdc/spline">https://github.com/cdc/spline</a></p>`
- `email_template.txt` (lines 4, 6-8, 30-31): All reference `cdc/spline`
- `sendmail_template.txt` (line 12): References `cdc-spline_logo.png` and `cdc-spline_logo_light.png`

All of these should use "FoodNetTrends" (the manifest name is `FoodNetTrends` per `nextflow.config` line 183).

### 2.3 "FoodNet Preprocessing Only" (with space) in spline.nf
- `spline.nf` (line 425): Log banner reads `"FoodNet Preprocessing Only"` -- inconsistent with the project name "FoodNetTrends". Should be `"FoodNetTrends - Preprocessing Only"`.

## 3. main.nf Help Text Inconsistencies

### 3.1 Wrong param names in `--help` output
- `main.nf` (line 15): `--censusFile_B` -- actual param name is `censusFileB` (no underscore before B)
- `main.nf` (line 16): `--censusFile_P` -- actual param name is `censusFileP` (no underscore before P)

### 3.2 Missing params from help text
The `--help` output in `main.nf` omits several user-facing params that are in the schema:
- `--states`
- `--skip_preprocessing`
- `--skip_dashboard`
- `--serotype_config`
- `--catchment_config`
- `--matching_sensitivity`
- `--stan_backend`

### 3.3 Incomplete param descriptions
- `--preprocessed` help says "TRUE/FALSE" but the actual type is boolean, and it should clarify the relationship: when true, `--cleanFile` must also be provided.

## 4. sendmail_template.txt References Missing Asset Files

- `sendmail_template.txt` (line 12): Content-Type says `name="cdc-spline_logo.png"`
- `sendmail_template.txt` (line 14): Content-Disposition says `filename="cdc-spline_logo_light.png"`
- `sendmail_template.txt` (line 17): Tries to read `"$projectDir/assets/cdc-spline_logo_light.png"`

These reference `cdc-spline_logo_light.png` which likely does not exist with that name. If the file has been renamed to match "FoodNetTrends", the template will fail at runtime.

Additionally, `sendmail_template.txt` (lines 28-50) references a MultiQC report attachment, but this pipeline does not run MultiQC. The block will be harmless if `mqcFile` is null, but it is dead code that adds confusion.

## 5. WorkflowSpline.groovy Contains Irrelevant nf-core Boilerplate

### 5.1 MultiQC references
- `WorkflowSpline.groovy` (line 19): Method `paramsSummaryMultiqc` generates MultiQC YAML. This pipeline does not use MultiQC.
- `WorkflowSpline.groovy` (lines 48-101): `toolCitationText` and `toolBibliographyText` reference FastQC and MultiQC -- neither is used in this pipeline.
- These are all leftover nf-core template code that should be updated to reference the actual tools used (brms, Stan, R, etc.) or removed.

### 5.2 Empty initialise method
- `WorkflowSpline.groovy` (line 13): `initialise` method is empty. If it is not performing validation, it should either be removed or populated with FoodNetTrends-specific checks.

## 6. NfcoreTemplate.groovy MultiQC Email Attachment

- `NfcoreTemplate.groovy` (lines 97-113): The email method tries to attach a MultiQC report. Since this pipeline does not produce MultiQC reports, this block will always fail silently and fall through to the catch. This is not harmful but is misleading dead code.

## 7. trendy.R Inconsistencies

### 7.1 `--outDir` vs schema `outdir`
- `trendy.R` (line 60): argparse param is `--outDir` (camelCase)
- `nextflow.config` / schema: param is `outdir` (lowercase)
- The Nextflow process presumably maps `params.outdir` to the R script's `--outDir`, so this works, but the naming divergence is confusing for anyone reading the code.

### 7.2 `--cores` param default vs schema
- `trendy.R` (line 72): `--cores` defaults to 16
- This param is not in the schema. The config has `cpus = 16` but the schema has no `cores` or `cpus` entry. The actual CPU allocation in `nextflow.config` for TRENDY (line 146) uses `params.chains`, not `params.cpus`.

### 7.3 `--backend` vs schema `stan_backend`
- `trendy.R` (line 84): argparse param is `--backend`
- `nextflow_schema.json` / `nextflow.config`: param is `stan_backend`
- The Nextflow process must map between these, but the naming divergence is confusing.

### 7.4 Hardcoded debug paths
- `trendy.R` (lines 143-145): Debug mode hardcodes `/scicomp/groups-pure/OID/NCEZID/DFWED/EDEB/foodnet/trends/data/` paths. These are CDC-internal paths that will not work elsewhere.

### 7.5 SAS import dead code
- `trendy.R` (line 264): When `preprocessed` is FALSE, the script calls `stop("This script is designed to work with preprocessed data...")`. This means the non-preprocessed path is effectively disabled, yet the argparse help for `--mmwrFile` says "Path to FoodNet MMWR SAS data file" -- implying raw SAS input is supported. The help text should clarify that `trendy.R` requires preprocessed CSV input.

## 8. preprocess.R

### 8.1 Generally accurate
- Parameter names (`--mmwrFile`, `--outputFile`, `--serotype-config`, `--matching-sensitivity`) match their actual usage.
- Help strings are accurate and complete.
- No naming inconsistencies found.

### 8.2 Minor: Hyphenated argparse names
- `--serotype-config` and `--matching-sensitivity` use hyphens in preprocess.R, while `nextflow.config` uses `serotype_config` and `matching_sensitivity` (underscores). The Nextflow process module must handle this mapping. This is a minor convention inconsistency.

## 9. run_workflow.sh

### 9.1 Hardcoded data paths
- `run_workflow.sh` (lines 10-13): Hardcodes CDC-specific paths:
  ```
  dataDir="/scicomp/groups-pure/OID/NCEZID/DFWED/EDEB/foodnet/trends/data/"
  MMWR_FILE="${dataDir}/mmwr9624_May2025.sas7bdat"
  CENSUS_FILE_B="${dataDir}/cen9624.sas7bdat"
  CENSUS_FILE_P="${dataDir}/cen9624_para.sas7bdat"
  ```
  These should either be parameterized (e.g., via environment variables or a user config file) or clearly documented as site-specific defaults that need editing.

### 9.2 Hardcoded module versions
- `run_workflow.sh` (lines 21-23): `module load nextflow/24.10.4`, `singularity/4.1.4`, `java/17.0.6` -- hardcoded versions that will break when modules are updated. Should be documented as requiring site-specific editing.

### 9.3 LISTERIA and CRYPTOSPORIDIUM missing from valid_pathogens list
- `run_workflow.sh` (line 685): `valid_pathogens=("CAMPYLOBACTER" "CYCLOSPORA" "SALMONELLA" "SHIGELLA" "STEC" "VIBRIO" "YERSINIA")`
- But `preprocess.R` also recognizes LISTERIA and CRYPTOSPORIDIUM (lines 97-126). Users selecting these in the interactive menu will get an "unrecognized pathogen" error.
- The `ALL_PATHOGENS` list on line 41 also excludes LISTERIA and CRYPTOSPORIDIUM.

### 9.4 Resume mode hardcodes default MCMC params
- `run_workflow.sh` (lines 944-947): Resume mode sets `chains=2, iterations=500, adapt_delta=0.95, max_treedepth=10` regardless of what the original run used. The UI text says "Using parameters from previous run" (line 950) but this is misleading -- it uses hardcoded defaults, not the previous run's actual parameters.

### 9.5 Seed always hardcoded to 123
- `run_workflow.sh` (lines 1260, 1274): `--seed 123` is always passed. It is not configurable through the interactive menu, despite being a schema parameter. This is a minor omission.

### 9.6 Publication profile values differ from nextflow.config production profile
- `run_workflow.sh` (lines 833-836): Publication mode uses `chains=6, iterations=10001`
- `nextflow.config` production profile (lines 104-107): `chains=4, iterations=2000`
- These are different named presets so the difference may be intentional, but users may be confused by the discrepancy if they compare run_workflow.sh "Publication" with the Nextflow "production" profile.

## 10. monitor_pipeline.sh

- Generally well-documented with accurate help text.
- Usage examples and option descriptions are correct.
- No naming inconsistencies found.

## 11. generate_dashboard.R

- Generally well-documented with accurate help text.
- Parameter names match their usage.
- `--output_dir`, `--projID`, `--output`, `--cleanFile` are all correctly described.
- STATE_INFO (lines 89-100) is hardcoded with FoodNet states and join years. This should be verified against the actual FoodNet participation timeline. Colorado's joinYear is listed as 2001, but preprocess.R (line 271) filters out COEX before 2023 for Colorado expansion, suggesting the catchment definition has changed.

## 12. Email Templates: Structural Issues

### 12.1 GitHub URL is non-functional
- Both email templates link to `https://github.com/cdc/spline` which is likely not a real public GitHub repository. Should be updated to the actual repository URL.

### 12.2 No FoodNetTrends-specific content
- The email templates are generic nf-core boilerplate with `cdc/spline` string-replaced in a few places. They do not mention:
  - Which pathogens were analyzed
  - How many models converged
  - Where to find results
  - Dashboard location
  This is a completeness gap -- the emails provide only generic Nextflow run metadata.

## 13. Schema `required` Fields

- `nextflow_schema.json` (lines 13-15): Only `mmwrFile` and `outdir` are marked required in the `input_output_options` group.
- `censusFileB` and `censusFileP` are NOT marked required, but `spline.nf` (lines 54-58) errors if they don't exist. They should be marked required in the schema (unless the pipeline is run in preprocessing-only mode, where they are not needed).

## 14. Schema `cleanFile` vs `preprocessed` Relationship

- `nextflow_schema.json` describes `cleanFile` (line 153) as "Used when preprocessed is true" but there is no schema-level dependency or conditional requirement. If `preprocessed=true` is set without `cleanFile`, the pipeline will fail at runtime with an unhelpful error.
- Consider adding a `help_text` field to `cleanFile` explaining this dependency.

## 15. Summary of Findings by Severity

### Critical (will cause runtime failures or user confusion)
1. **main.nf help text uses wrong param names** (`--censusFile_B`/`--censusFile_P` vs actual `--censusFileB`/`--censusFileP`) -- Section 3.1
2. **sendmail_template.txt references `cdc-spline_logo_light.png`** which likely doesn't exist -- Section 4
3. **run_workflow.sh excludes LISTERIA and CRYPTOSPORIDIUM** from valid pathogens despite preprocess.R supporting them -- Section 9.3
4. **Resume mode claims to use previous run params but uses hardcoded defaults** -- Section 9.4

### High (naming/branding inconsistencies visible to users)
5. **All email templates hardcode "cdc/spline"** instead of "FoodNetTrends" -- Section 2.2
6. **Groovy lib comments reference "cdc/spline"** -- Section 2.1
7. **Schema `$id` URL references `cdc/spline`** -- Section 1.3
8. **`max_cpus` default mismatch** (schema=16, config=32) -- Section 1.1
9. **`censusFileB`/`censusFileP` not marked required in schema** despite being required at runtime -- Section 13

### Medium (documentation/code quality)
10. **main.nf help text missing many params** (states, skip_*, configs, stan_backend) -- Section 3.2
11. **MultiQC boilerplate in WorkflowSpline.groovy** referencing FastQC/MultiQC -- Section 5
12. **Hardcoded CDC paths** in run_workflow.sh and trendy.R debug mode -- Sections 9.1, 7.4
13. **trendy.R `--mmwrFile` help implies SAS support** but non-preprocessed path is disabled -- Section 7.5
14. **Email templates have no FoodNetTrends-specific content** (pathogens, convergence, results) -- Section 12.2
15. **Empty `WorkflowSpline.initialise()` method** -- Section 5.2

### Low (minor inconsistencies)
16. **Param name style divergence** between R scripts and Nextflow (outDir vs outdir, backend vs stan_backend, hyphens vs underscores) -- Sections 7.1, 7.3, 8.2
17. **Hardcoded module versions** in run_workflow.sh -- Section 9.2
18. **Seed not user-configurable** in interactive launcher -- Section 9.5
19. **Publication vs production profile value differences** -- Section 9.6
20. **`trendyScript` and `cpus` appear in logs but not in schema** -- Section 1.2
