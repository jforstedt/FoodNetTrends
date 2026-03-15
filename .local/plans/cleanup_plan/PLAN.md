# FoodNetTrends Repository Cleanup Plan (Corrected)

**Date**: 2026-03-14
**Branch**: feature/results-dashboard
**Correction note**: This plan supersedes and corrects the previous cleanup plan, which incorrectly recommended removing nf-core scaffolding files. This pipeline is INTENTIONALLY built on the nf-core template and is meant to be nf-core compliant. The nf-core modules directory, Groovy libraries, assets, and scaffolding are part of the intended architecture and should be retained and customized -- NOT removed.

---

## Executive Summary

FoodNetTrends is a Bayesian epidemiological modeling pipeline built on the nf-core Nextflow template. The pipeline has been customized for FoodNet surveillance data analysis, but the nf-core scaffolding was left in place intentionally to maintain template compliance and enable future features (email notifications, software version tracking, institutional configs, etc.).

The actual cleanup needs fall into four categories:

1. **nf-core files that need CUSTOMIZATION** (not removal) -- they currently reference FastQC/FASTQ/genomics concepts that do not apply to this epidemiological pipeline
2. **Genuine orphan files** -- backup files, output artifacts, and legacy scripts that are not part of nf-core compliance and are not used by the pipeline
3. **Files that need relocation** -- files in the wrong directory
4. **The source/ directory** -- historical reference material that needs a clear policy

**Pipeline execution flow (ACTIVE)**:
```
main.nf
  -> workflows/spline.nf
    -> modules/local/preprocess.nf    (calls bin/preprocess.R)
    -> modules/local/resource_profiler.nf  (inline R script)
    -> modules/local/trendy.nf        (calls bin/trendy.R, copies bin/functions.R)
    -> modules/local/dashboard.nf     (calls dashboard/generate_dashboard.R)
```

**Summary counts**:
- KEEP AS-IS: 44 files/directories
- UPDATE NEEDED: 15 files (nf-core compliant but referencing wrong domain concepts)
- GENUINE ORPHAN: 14 files (safe to remove)
- RELOCATE: 1 file
- NEEDS REVIEW: 2 items

---

## Key Differences from Previous Plan

The previous cleanup plan was fundamentally incorrect:
- **Recommended removing**: 36 files including all nf-core scaffolding (lib/, assets/, modules/nf-core/, pyproject.toml, tower.yml, modules.json)
- **This plan instead**: Removes only 14 genuine orphans, preserves 22 nf-core files that require customization, not deletion
- **Critical insight**: This pipeline is nf-core-compliant BY DESIGN. The scaffolding enables features like email notifications, version tracking, and institutional config management that will be activated in future development.

---

## Section 1: nf-core Modules (modules/nf-core/)

### 1a. modules/nf-core/fastqc/ (entire directory)

- **Status**: UPDATE NEEDED
- **Analysis**: FastQC is a genomics QC tool. This pipeline processes tabular epidemiological data (SAS/CSV), not FASTQ sequencing reads. The module is installed but never included in workflows/spline.nf. However, rather than deleting it, the team should decide whether to:
  - (A) Replace it with a relevant QC module (e.g., a custom data validation module for the SAS/CSV inputs), OR
  - (B) Remove it via `nf-core modules remove fastqc` to keep modules.json in sync
- **Recommendation**: UPDATE NEEDED -- Replace with a domain-appropriate QC module or remove via nf-core tooling (not manual deletion). If removed, update modules.json accordingly.
- **Risk**: Zero functional risk either way. But manual deletion without updating modules.json would break nf-core module management.
- **Confidence**: 100%

### 1b. modules/nf-core/multiqc/ (entire directory)

- **Status**: UPDATE NEEDED
- **Analysis**: MultiQC aggregates reports from other tools. The pipeline uses a custom dashboard (modules/local/dashboard.nf) instead. The module is installed but never included in workflows. However, MultiQC could potentially be integrated in the future to aggregate the pipeline_info reports (execution_timeline, execution_report, etc.). The team should decide whether to:
  - (A) Wire MultiQC into the workflow to aggregate pipeline execution reports, OR
  - (B) Remove it via `nf-core modules remove multiqc`
- **Recommendation**: UPDATE NEEDED -- Either integrate or remove via nf-core tooling.
- **Risk**: Zero functional risk. Same modules.json concern as 1a.
- **Confidence**: 100%

### 1c. modules/nf-core/custom/dumpsoftwareversions/ (entire directory)

- **Status**: UPDATE NEEDED
- **Analysis**: This is a standard nf-core module that collects software version information for reproducibility reporting. It is not currently wired into the workflow, but it SHOULD be -- version tracking is an nf-core best practice. The module collects version info from each process's `versions.yml` output. The existing config in conf/base.config (line 67-69) and conf/modules.config (lines 77-83) should be KEPT in anticipation of integration, not removed.
- **Recommendation**: UPDATE NEEDED -- Wire this module into workflows/spline.nf to collect R package versions, cmdstan version, etc. This is a genuine nf-core compliance gap.
- **Risk**: None currently. Integration would improve reproducibility.
- **Confidence**: 100%

---

## Section 2: modules/local/

### 2a. modules/local/samplesheet_check.nf

- **Status**: UPDATE NEEDED
- **Analysis**: This is the standard nf-core samplesheet validation module. It currently references a `check_samplesheet.py` script (which does not exist in bin/) and validates FASTQ-format samplesheets. The pipeline uses direct file path parameters instead. However, this module represents an nf-core pattern that SHOULD be adapted: the pipeline would benefit from input validation for its mmwrFile, censusFileB, and censusFileP inputs.
- **Recommendation**: UPDATE NEEDED -- Rewrite this module to validate the FoodNetTrends input files (SAS format, expected columns, etc.) instead of FASTQ samplesheets. Add a corresponding bin/check_inputs.py or bin/check_inputs.R script.
- **Risk**: None. Not currently in the execution path.
- **Confidence**: 100%

### 2b. modules/local/trendy.nf.bak

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Backup file already covered by .gitignore.
- **Risk**: NONE.

### 2c. modules/local/trendy.nf.old

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Backup file already covered by .gitignore.
- **Risk**: NONE.

---

## Section 3: lib/ (Groovy Libraries)

The previous plan recommended removing the entire lib/ directory. This was INCORRECT. These Groovy classes are standard nf-core template components. Nextflow automatically loads all classes from lib/, making them available to workflows. They provide infrastructure for email notifications, version reporting, logging, conda channel validation, and parameter validation.

### 3a. lib/NfcoreTemplate.groovy

- **Status**: KEEP AS-IS (with future activation)
- **Analysis**: Provides email notification on pipeline completion, Slack/Teams webhook notifications, parameter dumping, version string generation, and colored logging. Standard nf-core features. The `params.email`, `params.email_on_fail`, `params.hook_url`, and `params.monochrome_logs` parameters ARE already defined in nextflow.config (lines 48-52), indicating intent to use these features.
- **Recommendation**: KEEP AS-IS. Wire into the workflow in a future update to enable email and webhook notifications on pipeline completion.
- **Risk**: None. Dead code has zero runtime impact.
- **Confidence**: 100%

### 3b. lib/Utils.groovy

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Will become active when WorkflowMain.initialise() is wired in.
- **Risk**: None.

### 3c. lib/WorkflowMain.groovy

- **Status**: UPDATE NEEDED
- **Analysis**: The `initialise()` function checks for `params.input` (samplesheet), which this pipeline does not use -- it uses `params.mmwrFile` instead. The citation function references `workflow.manifest.name` which IS correctly set. This file should be updated to validate FoodNetTrends-specific parameters instead of `params.input`.
- **Recommendation**: UPDATE NEEDED -- Change `params.input` check to validate `params.mmwrFile`, `params.censusFileB`, `params.censusFileP`. Then wire `WorkflowMain.initialise()` into main.nf.
- **Risk**: None currently. The update enables proper parameter validation.
- **Confidence**: 100%

### 3d. lib/WorkflowSpline.groovy

- **Status**: UPDATE NEEDED
- **Analysis**: Pipeline-specific workflow library. The `initialise()` function body is empty. The `toolCitationText()` and `toolBibliographyText()` functions reference FastQC and MultiQC instead of brms, cmdstanr, dplyr, etc. The `methodsDescriptionText()` function is commented out. This file needs to be customized for the actual tools used.
- **Recommendation**: UPDATE NEEDED -- Fill in `initialise()` with FoodNetTrends parameter validation. Update citation text to reference brms (Buerkner 2017), Stan (Carpenter et al. 2017), and other actual R packages used. Uncomment and test `methodsDescriptionText()`.
- **Risk**: None. Updates improve compliance.
- **Confidence**: 100%

---

## Section 4: bin/ (R Scripts and Utilities)

### 4a. bin/trendy.R -- KEEP AS-IS

- **Status**: ACTIVE. Called by modules/local/trendy.nf via params.trendyScript.

### 4b. bin/functions.R -- KEEP AS-IS

- **Status**: ACTIVE. Copied into TRENDY work directory and sourced by trendy.R.

### 4c. bin/preprocess.R -- KEEP AS-IS

- **Status**: ACTIVE. Called by modules/local/preprocess.nf.

### 4d. bin/functionsWeller.R

- **Status**: RELOCATE
- **Analysis**: This is NOT a duplicate of functions.R. A diff reveals meaningful differences: functionsWeller.R is the ORIGINAL version of functions.R before subgroup support was added. Key differences:
  - Lacks the `subgroup` parameter in `PLOT_SITE_TRENDS()` and `PLOT_OVERALL_TREND()`
  - Includes inline `ggsave()` calls that were removed in the current functions.R
  - Has hardcoded year ranges (`2016 & year <= 2018`) vs parameterized `start_year`/`end_year`
  - The file is attributed to Weller, D. -- listed as a contributor
  This is a reference copy of the original analytical code before pipeline refactoring.
- **Recommendation**: RELOCATE -- Move to `source/functionsWeller.R` alongside other reference materials. It does not belong in bin/ (which is for executable pipeline scripts) since this file is never called.
- **Risk**: NONE. Never sourced by any pipeline code.
- **Confidence**: 100%

### 4e. bin/calcIR.R

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Superseded by preprocess.R.

### 4f. bin/load_packages.R

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Container handles dependencies.

### 4g. bin/grab_snippet.R

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove or move to dev/.

### 4h. bin/extract_file_headers_simple.R

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove.

### 4i. bin/file_headers_output.txt

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove.

### 4j-4l. bin/input_snippet_*.txt

- **Status**: GENUINE ORPHAN (3 files: census_b.txt, census_p.txt, mmwr.txt)
- **Recommendation**: GENUINE ORPHAN -- Safe to remove.

### 4m. bin/run_trendy.sh

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Legacy launcher superseded by run_workflow.sh.

---

## Section 5: assets/

### 5a. assets/Renv.yaml

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Superseded by foodnet.yml.

### 5b. assets/samplesheet.csv

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Rewrite to show FoodNetTrends example input format or replace with example parameter file.

### 5c. assets/schema_input.json

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Either populate with FoodNetTrends input schema or keep as placeholder.

### 5d-5g. assets/adaptivecard.json, email_template.html, email_template.txt, sendmail_template.txt

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Standard nf-core infrastructure for notifications.

### 5h. assets/methods_description_template.yml

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Update text to mention Bayesian spline modeling methodology.

---

## Section 6: source/ Directory

The `source/` directory is NOT nf-core scaffolding. It is a project-specific directory containing the original pre-pipeline analysis scripts and historical output data.

| File | Status | Note |
|------|--------|------|
| `source/splinesmodel_16Mar2024_OrCatch.R` | KEEP AS-IS | Original standalone analysis script, provenance reference |
| `source/EstRR12Apr2024_MMWRR1_OrCatchment.csv` | KEEP AS-IS | Prior analysis results, useful for validation |
| `source/Unspeciated_Shigella.R` | KEEP AS-IS | Historical Shigella-specific analysis |
| `source/Unspeciated_Shigella.sh` | KEEP AS-IS | Historical SGE submission script |
| `source/Unspeciated_Shigella.Rout` | GENUINE ORPHAN | R output log. Already covered by .gitignore. Safe to remove. |
| `source/.gitkeep` | KEEP AS-IS | Ensures directory persistence in git |

---

## Section 7: docs/

### 7a. docs/output.md

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Rewrite to describe FoodNetTrends outputs (spline_results/*.Rds, *_IRCatch.csv, *_IRSite.csv, *.png, dashboard.html, pipeline_info/).

### 7b. docs/usage.md

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Rewrite pipeline-specific sections. Keep generic Nextflow documentation sections as-is.

### 7c. docs/configuration.md

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Accurately describes actual configuration.

### 7d. docs/images/mqc_fastqc_*.png (3 files)

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Replace with FoodNetTrends-specific screenshots when docs/output.md is updated.

### 7e. docs/README.md

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

### 7f. docs/contributions

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Consider renaming to `docs/contributions.md` for consistency.

---

## Section 8: Configuration Files

### 8a. conf/test.config

- **Status**: UPDATE NEEDED (HIGH PRIORITY)
- **Analysis**: References nf-core viralrecon test datasets (SARS-CoV-2 genome, Illumina amplicon samplesheet). The test profile is an nf-core REQUIREMENT.
- **Recommendation**: UPDATE NEEDED -- Rewrite with FoodNetTrends test parameters. Create or reference small test SAS/CSV files. Set `params.mmwrFile`, `params.censusFileB`, `params.censusFileP` to test data.
- **Risk**: The test profile currently fails if used. No impact on production runs.
- **Confidence**: 100%

### 8b. conf/base.config

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. The `withName:CUSTOM_DUMPSOFTWAREVERSIONS` block should be kept for future integration.

### 8c. conf/modules.config

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Keep the CUSTOM_DUMPSOFTWAREVERSIONS block for future integration.

### 8d. conf/cdc-dev.config

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

### 8e. nextflow.config

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

### 8f. nextflow_schema.json

- **Status**: UPDATE NEEDED (HIGH PRIORITY)
- **Analysis**: Has three critical issues:
  1. The `input_output_options.required` array lists `"input"` as required, but this pipeline uses `mmwrFile`
  2. The `allOf` array references `"$ref": "#/definitions/reference_genome_options"` which does NOT exist -- this is a broken JSON Schema reference
  3. Missing definitions for FoodNetTrends-specific parameters
- **Recommendation**: UPDATE NEEDED -- Remove the `input` requirement, remove the broken `reference_genome_options` ref, add definitions for FoodNetTrends parameters. THIS IS THE HIGHEST PRIORITY UPDATE IN THIS PLAN.
- **Risk**: MODERATE. The broken schema reference can cause validation failures.
- **Confidence**: 100%

---

## Section 9: Root-level Files

### 9a. modules.json

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- If modules are removed via `nf-core modules remove`, this file will be auto-updated. Do NOT manually edit or delete this file.
- **Risk**: LOW. Only affects nf-core module management commands.

### 9b. pyproject.toml

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Part of nf-core template compliance. The previous plan was wrong to recommend removal.

### 9c. tower.yml

- **Status**: UPDATE NEEDED
- **Recommendation**: UPDATE NEEDED -- Update to reference the actual pipeline reports (e.g., `dashboard.html` and execution reports from pipeline_info/).

### 9d. .nextflow.pid

- **Status**: GENUINE ORPHAN
- **Recommendation**: GENUINE ORPHAN -- Safe to remove. Runtime artifact.

### 9e. run_workflow.sh

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

### 9f. foodnet.def

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

### 9g. foodnet.yml

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

### 9h. .gitattributes

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS. Standard line ending normalization.

### 9i. .gitignore

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

---

## Section 10-15: Other Directories

### 10. dashboard/

- `dashboard/generate_dashboard.R` -- KEEP AS-IS (ACTIVE)
- `dashboard/template.html` -- KEEP AS-IS (ACTIVE)

### 11. dev/

- `dev/fnt.scicomp.config` -- KEEP AS-IS (ACTIVE)

### 12. analysis_configs/

- `analysis_configs/examples/serotype_config.csv` -- KEEP AS-IS (ACTIVE)
- `analysis_configs/examples/catchment_config.csv` -- KEEP AS-IS (ACTIVE)

### 13. .github/

- Issue and PR templates -- KEEP AS-IS (ACTIVE)
- Note: nf-core pipelines typically also include CI workflow files. Consider adding these in the future.

### 14. Root Documentation Files

All active and should be KEPT: CHANGELOG.md, CITATIONS.md, CONTRIBUTING.md, DISCLAIMER.md, LICENSE, README.md, code-of-conduct.md, open_practices.md, rules_of_behavior.md, thanks.md

### 15. .vscode/settings.json

- **Status**: KEEP AS-IS
- **Recommendation**: KEEP AS-IS.

---

## Prioritized Action Items

### Priority 1: GENUINE ORPHANS -- Safe to Remove (Zero Dependencies)

| # | File | Type |
|---|------|------|
| 1 | `modules/local/trendy.nf.bak` | Backup file |
| 2 | `modules/local/trendy.nf.old` | Backup file |
| 3 | `bin/calcIR.R` | Superseded script |
| 4 | `bin/load_packages.R` | Superseded script |
| 5 | `bin/grab_snippet.R` | Dev utility |
| 6 | `bin/extract_file_headers_simple.R` | Dev utility |
| 7 | `bin/file_headers_output.txt` | Output artifact |
| 8 | `bin/input_snippet_census_b.txt` | Output artifact |
| 9 | `bin/input_snippet_census_p.txt` | Output artifact |
| 10 | `bin/input_snippet_mmwr.txt` | Output artifact |
| 11 | `bin/run_trendy.sh` | Legacy launcher |
| 12 | `assets/Renv.yaml` | Outdated env def |
| 13 | `.nextflow.pid` | Runtime artifact |
| 14 | `source/Unspeciated_Shigella.Rout` | R output log |

**Action**: Safe to delete. Zero functional impact.

### Priority 2: RELOCATE (Wrong Directory)

| # | File | Current | Recommended |
|---|------|---------|-------------|
| 1 | `bin/functionsWeller.R` | `bin/` | `source/functionsWeller.R` |

**Action**: Move functionsWeller.R to source/ where it belongs with other reference materials.

### Priority 3: UPDATE NEEDED -- HIGH PRIORITY (Functional Issues)

| # | File | Issue |
|---|------|-------|
| 1 | `nextflow_schema.json` | Broken reference, wrong required params |
| 2 | `conf/test.config` | References SARS-CoV-2 genome |
| 3 | `lib/WorkflowMain.groovy` | Checks for wrong params |

**Action**: Fix these issues to prevent validation failures and enable test profile.

### Priority 4: UPDATE NEEDED -- MEDIUM PRIORITY (Documentation/Compliance)

| # | File |
|---|------|
| 1 | `docs/output.md` |
| 2 | `docs/usage.md` |
| 3 | `docs/images/mqc_fastqc_*.png` (3 files) |
| 4 | `lib/WorkflowSpline.groovy` |
| 5 | `assets/methods_description_template.yml` |
| 6 | `assets/samplesheet.csv` |
| 7 | `assets/schema_input.json` |
| 8 | `tower.yml` |
| 9 | `modules.json` |

**Action**: Customize for FoodNetTrends domain.

### Priority 5: UPDATE NEEDED -- LOW PRIORITY (Future Integration)

| # | Feature | Action |
|---|---------|--------|
| 1 | `modules/nf-core/custom/dumpsoftwareversions/` | Wire into workflows/spline.nf |
| 2 | `modules/nf-core/fastqc/` | Replace or remove |
| 3 | `modules/nf-core/multiqc/` | Integrate or remove |
| 4 | `modules/local/samplesheet_check.nf` | Rewrite for FoodNetTrends |
| 5 | Email/webhook notification | Wire into workflow |
| 6 | `.github/workflows/` | Add CI workflow files |

**Action**: These are nf-core features that should be activated as the pipeline matures.

### Priority 6: NEEDS REVIEW (Team Decision)

| # | Item | Question |
|---|------|----------|
| 1 | `source/` directory | Keep in git or add to .gitignore? |
| 2 | nf-core module strategy | Replace FastQC/MultiQC or just remove? |

---

## Impact Assessment

### If Priority 1 items are removed:
- **Files removed**: 14 files
- **Pipeline functionality impact**: ZERO
- **nf-core compliance impact**: ZERO
- **Directories that become empty**: None

### If Priority 2 relocation is done:
- **Files moved**: 1
- **Pipeline functionality impact**: ZERO
- **nf-core compliance impact**: ZERO

### If Priority 3 updates are done:
- **Schema validation**: FIXED (broken reference repaired)
- **Test profile**: FUNCTIONAL
- **Parameter validation**: IMPROVED

### Key difference from previous plan:
- **Previous plan removed**: 36 files including ALL nf-core scaffolding
- **This plan removes**: 14 genuine orphans only
- **This plan preserves**: 22 nf-core files that require CUSTOMIZATION, not deletion
- **Net outcome**: Pipeline remains nf-core compliant while removing only true orphans

---

## Summary Table

| Category | Count | Action |
|----------|-------|--------|
| KEEP AS-IS | 44 | No action needed |
| UPDATE NEEDED (High) | 3 | Fix functional issues |
| UPDATE NEEDED (Medium) | 9 | Customize for domain |
| UPDATE NEEDED (Low/Future) | 6 | Wire in nf-core features |
| GENUINE ORPHAN | 14 | Safe to delete |
| RELOCATE | 1 | Move to correct directory |
| NEEDS REVIEW | 2 | Team decision required |

---

## Why the Previous Plan Was Wrong

1. **nf-core compliance is intentional**: The pipeline was built FROM the nf-core template. The scaffolding is the framework that makes this an nf-core pipeline.

2. **Features are meant to be activated**: Email notifications, webhook alerts, version tracking, and parameter validation are all intended features to be wired in as the pipeline matures.

3. **Removing nf-core files breaks tooling**: The `nf-core lint` tool checks for lib/, assets/, modules.json, pyproject.toml, and tower.yml. Removing them causes lint failures.

4. **Template synchronization**: nf-core's `nf-core sync` command updates scaffolding to match latest standards. Removing files breaks sync and prevents upstream improvements.

5. **The correct approach is CUSTOMIZATION**: Files like WorkflowSpline.groovy, docs/output.md, conf/test.config, and assets/samplesheet.csv need REWRITING for FoodNetTrends domain -- but their structure and location must be PRESERVED.

---

## Architect Review

**Reviewer:** Senior Nextflow DSL2 Bioinformatics Architect
**Date:** 2026-03-14
**Scope:** Cleanup plan validation, nf-core compliance assessment, cross-plan coordination

---

### 1. Cross-Plan Conflict Analysis

The Cleanup Plan primarily removes orphan files and flags nf-core files for customization. It does not modify any files that the other three plans modify. **No cross-plan conflicts exist.**

However, the Cleanup Plan's Priority 3 items (HIGH PRIORITY updates) include coordination points:
- **`nextflow_schema.json`:** The Profiler Plan adds `stan_backend` parameter, which should be reflected in the schema when it is updated.
- **`conf/test.config`:** The Container Plan changes the environment, which may affect test profile configuration.

These are not conflicts but dependencies. When implementing Priority 3, incorporate changes from the other plans.

### 2. DSL2 Integration Validation

**Orphan removal (Priority 1):** All 14 files identified as genuine orphans are confirmed safe to remove:
- `trendy.nf.bak`, `trendy.nf.old`: Verified not referenced by any Nextflow `include` statement or workflow.
- `bin/calcIR.R`, `bin/load_packages.R`, `bin/grab_snippet.R`, `bin/extract_file_headers_simple.R`: Verified not referenced in any process script block or workflow. Not sourced by `trendy.R` or `functions.R`.
- `bin/file_headers_output.txt`, `bin/input_snippet_*.txt`: Data artifacts, not pipeline inputs.
- `bin/run_trendy.sh`: Legacy launcher, superseded by `run_workflow.sh`.
- `assets/Renv.yaml`: Superseded by `foodnet.yml` (and soon `pixi.toml`).
- `.nextflow.pid`: Runtime artifact, already in `.gitignore`.
- `source/Unspeciated_Shigella.Rout`: R output log, not a source file.

Removing these has zero impact on pipeline execution.

**Relocation of `bin/functionsWeller.R`:** Moving to `source/` is correct. Verified: not sourced by `trendy.R` (which sources `functions.R` via `file.path(script_dir, "functions.R")`) and not referenced in any Nextflow process.

**nextflow_schema.json fixes (Priority 3):** The broken `$ref: "#/definitions/reference_genome_options"` in the `allOf` array (line 240) is a real issue. This reference points to a non-existent definition. On strict JSON Schema validation (e.g., via `nf-core launch` or `nf-core schema validate`), this produces an error. The fix is to remove this `$ref` entry and replace `"input"` with `"mmwrFile"` in the required array. **This is the highest-impact fix in the Cleanup Plan.**

### 3. nf-core Compliance Assessment

The plan's nf-core assessment is **correct and well-calibrated.** Specific validations:

- **lib/ directory:** Correctly identified as nf-core template infrastructure. `NfcoreTemplate.groovy`, `Utils.groovy`, `WorkflowMain.groovy`, `WorkflowSpline.groovy` are standard nf-core Groovy libraries loaded automatically by Nextflow. Removing them would break `nf-core lint`, `nf-core sync`, and future template updates.

- **modules/nf-core/:** The recommendation to remove FastQC and MultiQC via `nf-core modules remove` (not manual deletion) is correct. Manual deletion leaves stale entries in `modules.json`, which causes `nf-core modules list` and `nf-core modules update` to fail.

- **modules/nf-core/custom/dumpsoftwareversions/:** The recommendation to wire this into the workflow is a genuine nf-core compliance gap. However, integration is nontrivial: each process (TRENDY, PREPROCESS, RESOURCE_PROFILER, DASHBOARD) needs to emit a `versions.yml` output. This is a significant amount of work and should be tracked as a separate follow-up, not bundled with the cleanup.

- **pyproject.toml, tower.yml, modules.json:** Correctly identified as nf-core infrastructure to keep.

- **conf/test.config:** The identification of SARS-CoV-2/viralrecon references is accurate. This is an nf-core template leftover. The test profile is an nf-core requirement, and the current one would fail if invoked. High priority fix.

### 4. Best Practices Assessment (March 2026)

**Nextflow 25.x features relevant to cleanup:**
- Nextflow 25.01+ supports `workflow.onComplete` hooks natively (without the Groovy library wrappers in `NfcoreTemplate.groovy`). However, since the nf-core template still uses the Groovy approach, keep it for template compatibility.
- Nextflow 25.04+ supports the `nf-schema` plugin for parameter validation, which is intended to replace the `nextflow_schema.json` + `lib/` validation approach. The nf-core community is migrating to this. When updating `nextflow_schema.json` (Priority 3), consider whether to adopt the plugin approach instead, but this is a larger refactoring that could be done in a follow-up.

**Source directory policy:** The plan correctly defers this to a team decision. Recommendation: keep `source/` in git. It serves as provenance documentation and validation reference (the reference CSV is used in Model Plan regression tests).

### 5. Issues and Concerns

**Issue 1: Priority ordering dependency.** Priority 3 (fix `nextflow_schema.json`) should be done AFTER the Profiler Plan adds `stan_backend`, so the schema update includes the new parameter. The cleanup plan does not note this dependency.

**Issue 2: CUSTOM_DUMPSOFTWAREVERSIONS integration scope.** The plan recommends wiring this module into `workflows/spline.nf` (Priority 5, Item 1). This requires each process to emit `versions.yml`, which is a nontrivial change to 4 process definitions. Track as a separate feature request, not a cleanup item.

**Issue 3: Model Plan creates dead code.** After Model Plan Step 2 removes the Cyclospora/Salmonella dual processing calls from `trendy.R`, `CYCLOSPORA_ANALYSIS()` and `SALMONELLA_ANALYSIS()` in `functions.R` (lines 260-316) become dead code. Also, `gtools::smartbind` is no longer called anywhere in `trendy.R`. The Cleanup Plan should add these to its orphan/dead-code list once the Model Plan is implemented.

**Issue 4: `base.config` `withName:CUSTOM_DUMPSOFTWAREVERSIONS` block.** If FastQC/MultiQC are removed via `nf-core modules remove`, the `base.config` (line 67-69) and `modules.config` (lines 77-83) blocks for `CUSTOM_DUMPSOFTWAREVERSIONS` remain. These are harmless (the process never runs if not included in the workflow) but are technically dead config. Low priority.

**Issue 5: `.nextflow.pid` removal.** This file is a runtime artifact that Nextflow creates in the launch directory. Removing it once is fine, but it will be recreated on the next run. Ensure it is in `.gitignore` (verified: it is). The removal is cosmetic.

### 6. Implementation Sequencing (cross-plan)

This plan should be implemented **LAST** among all plans:
1. Model Plan (R script fixes)
2. Profiler Plan (config + backend)
3. Container Plan (rebuild)
4. Cleanup Plan (file removal, schema fixes, documentation)

Going last benefits the Cleanup Plan because:
- The schema update can incorporate all new parameters from other plans (`stan_backend`, etc.).
- Dead code from Model Plan (`CYCLOSPORA_ANALYSIS`, `SALMONELLA_ANALYSIS`) can be included in the orphan list.
- The test config update can reflect the final container and parameter state.
- Documentation updates (docs/output.md, docs/usage.md) can describe the final pipeline behavior.

### 7. Verdict

**APPROVE.** The plan is a significant improvement over the previous cleanup plan. The nf-core compliance assessment is accurate. The orphan identification is thorough and conservative. Three items to note: (1) Coordinate `nextflow_schema.json` updates with Profiler Plan's `stan_backend` parameter, (2) Track CUSTOM_DUMPSOFTWAREVERSIONS integration as a separate follow-up, (3) Add Model Plan dead code (`CYCLOSPORA_ANALYSIS`, `SALMONELLA_ANALYSIS`, `smartbind` usage) to the cleanup list after Model Plan is implemented.
