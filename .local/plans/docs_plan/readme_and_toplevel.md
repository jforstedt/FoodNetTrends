# Documentation Audit: README and Top-Level Files

Audit performed against the current codebase state (main.nf, nextflow.config, workflows/spline.nf, run_workflow.sh, conf/, foodnet.def).

---

## 1. README.md

### Accuracy vs Current Code

**ACCURATE:**
- Pipeline description (spline-based Bayesian modeling of FoodNet MMWR data) matches code.
- Input data descriptions (mmwrFile, censusFileB, censusFileP) match `nextflow.config` params.
- Model parameters (chains, iterations, adapt_delta, max_treedepth, seed) match defaults in `nextflow.config`.
- Output directory structure matches what spline.nf and the PREPROCESS_ONLY workflow produce.
- Production profile values (chains=4, iterations=2000, adapt_delta=0.99, max_treedepth=15) match `nextflow.config`.
- Supported pathogens list matches `run_workflow.sh` ALL_PATHOGENS variable.
- Configuration file formats (serotype_config, catchment_config) and example paths are accurate.
- Interactive mode features described match `run_workflow.sh` functionality.

**INACCURATE:**
1. **`--censusFile_B` vs `--censusFileB` mismatch in main.nf help text:** The `main.nf` help message uses `--censusFile_B` and `--censusFile_P` (with underscores), but the actual params in `nextflow.config` are `censusFileB` and `censusFileP` (camelCase). The README correctly uses the camelCase versions, but this inconsistency in `main.nf` itself could confuse users who run `--help`.
2. **Default pathogen value:** README says default is `CAMPYLOBACTER,CYCLOSPORA` but `nextflow.config` sets `pathogen = null`. The defaults of CAMPYLOBACTER,CYCLOSPORA are only fallback defaults inside `spline.nf` logic when pathogen is null and not AUTO_DISCOVER. The README should clarify this is a workflow-level fallback, not a config default.
3. **Test mode invocation:** README says `./run_workflow.sh test` but `run_workflow.sh` uses an interactive menu to select "Test" mode -- it does not accept `test` as a command-line argument (the script initializes variables and then presents interactive prompts). This needs verification against the full script, but the first 50 lines show no argument parsing.
4. **`-profile production` mentioned in Performance section:** The README says "use `-profile production`" but the actual profile name in `nextflow.config` is `production` (correct), however the README does not mention that `production` must be combined with `singularity` profile (e.g., `-profile singularity,production`).
5. **Missing `stan_backend` parameter:** `nextflow.config` has `stan_backend = "rstan"` which is not documented in the README Parameters section.
6. **Missing `skip_dashboard` parameter:** `nextflow.config` has `skip_dashboard = false` which is not documented.
7. **Missing `cpus` parameter:** `nextflow.config` has `cpus = 16` which is not documented.
8. **Missing `whichScript`/`trendyScript` parameters:** These exist in config but are not documented (reasonable since they are internal).

### Completeness

**MISSING FROM README:**
1. **Container setup:** No instructions on how to build the Singularity container from `foodnet.def`. Users need to know to run `singularity build foodnet.sif foodnet.def` before running the pipeline. The `nextflow.config` hardcodes `process.container = 'foodnet.sif'` in the singularity profile.
2. **Stan backend option:** The `stan_backend` param (rstan vs cmdstanr) is not documented. The container builds CmdStan, so both backends are available.
3. **DASHBOARD module:** The pipeline includes a DASHBOARD step that generates a dashboard after TRENDY jobs complete, controlled by `skip_dashboard`. This feature is not mentioned anywhere in the README.
4. **RESOURCE_PROFILER module:** The pipeline runs resource profiling to estimate computational needs per pathogen. This is mentioned indirectly but not explained.
5. **AUTO_DISCOVER mode:** The code supports `pathogen = 'AUTO_DISCOVER'` to automatically detect pathogens from data. This is not documented as a parameter option.
6. **Environment setup:** The README Requirements section mentions SGE but does not mention the specific module versions needed (nextflow/24.10.4, singularity/4.1.4, java/17.0.6) -- these are in `run_workflow.sh`.
7. **CDC SciComp-specific profiles:** The `fnt.scicomp.config` defines several profiles (singularity, conda, local, scicomp_rosalind, training, debug) that are not documented in the README.
8. **Pixi-based container:** The container uses pixi for R environment management, which is not mentioned.
9. **No mention of `bin/` scripts:** The pipeline relies on `bin/trendy.R`, `bin/preprocess.R`, `bin/functions.R`, and `bin/monitor_pipeline.sh`. These are not documented.
10. **Missing CDC-required README sections:** Per `open_practices.md`, the README should include Public Domain Standard Notice, License Standard Notice, Privacy Standard Notice, Contributing Standard Notice, Records Management Standard Notice, and Additional Standard Notices. The README has a License section and SHARE IT Act section but is missing several required notice sections.

### Naming Consistency

- README consistently uses "FoodNetTrends" (correct, matches `manifest.name` in `nextflow.config`).
- No instances of "FoodNet Trends" (with space) found. PASS.

### References to Removed Files/Features

- **No references to FastQC or MultiQC** in the README. PASS.
- **No references to `cdc-dev.config`** in the README. PASS.
- **No references to `source/` directory** in the README. PASS.
- The README references `.github/CONTRIBUTING.md` for contributing guidelines, but this file does NOT exist. The actual `CONTRIBUTING.md` is at the repo root. This is a broken link.

### Profiles, Parameters, Container

- The README mentions `-profile singularity` which exists. PASS.
- Production profile documented correctly. PASS.
- Test profile exists in `conf/test.config`. PASS.
- Container setup is NOT documented (see Completeness above). FAIL.
- The `scicomp_rosalind`, `local`, `training`, and `conda` profiles from `fnt.scicomp.config` are not mentioned.

### nf-core Compliance

- The README follows a reasonable nf-core-like structure (Introduction, Features, Requirements, Parameters, Running, Output, Credits, Citations, License).
- Missing nf-core standard sections: Quick Start, Pipeline Summary diagram, Documentation links.
- The SHARE IT Act section at the bottom has empty Description fields.
- Missing badges (pipeline version, Nextflow version, license) that nf-core pipelines typically display.

### Pipeline Explanation Quality

- **What it does:** Well explained. PASS.
- **How to run it:** Adequately explained with multiple methods. Minor issues with test/full/resume invocation syntax.
- **What inputs are needed:** Well documented. PASS.
- **What outputs are produced:** Well documented with directory tree. PASS.

---

## 2. CHANGELOG.md

### Accuracy
- References pipeline as "cdc/spline" -- this is INACCURATE. The pipeline name is "FoodNetTrends" per `manifest.name` in `nextflow.config`.
- Version listed as "v1.0dev" which matches `nextflow.config` manifest version. PASS.
- The date placeholder `[date]` has never been filled in.

### Completeness
- Completely empty -- no changes have been logged despite significant development. All sections (Added, Fixed, Dependencies, Deprecated) are blank.
- Should document: preprocessing module, resource profiler, dashboard, pathogen grouping, serotype config, catchment config, matching sensitivity, pixi-based container, all current features.

### Removed Files/Features
- No references to removed files. PASS.

### nf-core Compliance
- Follows Keep a Changelog format. PASS.
- Uses Semantic Versioning reference. PASS.

---

## 3. CONTRIBUTING.md

### Accuracy
- Generic CDC boilerplate. Content is accurate for a government open-source project.
- Contact email (surveillanceplatform@cdc.gov) may need verification -- is this the correct contact for this pipeline?

### Completeness
- No pipeline-specific contribution instructions (how to set up dev environment, run tests, code style).
- No mention of Nextflow, R, or any technical requirements for contributors.
- Does not describe the branching strategy or CI/CD setup.

### Naming
- Does not mention "FoodNetTrends" or "FoodNet Trends" at all -- entirely generic. Neutral.

### Removed Files/Features
- No references to removed features. PASS.

---

## 4. CITATIONS.md

### Accuracy
- References pipeline as "cdc/spline" -- INACCURATE. Should be "FoodNetTrends".

### Removed Files/Features -- CRITICAL ISSUES
1. **FastQC citation is listed** but FastQC is NOT used by this pipeline. The pipeline does statistical modeling of surveillance data, not sequencing QC. REMOVE.
2. **MultiQC citation is listed** but MultiQC is NOT used by this pipeline. REMOVE.
3. **Anaconda citation is listed** but Anaconda is not used. The container uses pixi. REMOVE or replace with pixi reference.
4. **Bioconda citation is listed** but Bioconda is not used. REMOVE or replace.
5. **BioContainers citation is listed** but BioContainers is not used. REMOVE.
6. **Docker citation is listed** but Docker is not the primary container runtime (Singularity is). Could keep as an informational reference.

### Missing Citations
- **R** is not cited (the entire pipeline is R-based).
- **brms** (Bayesian Regression Models using Stan) is not cited -- this is the core modeling framework.
- **Stan/RStan** is not cited -- the MCMC backend.
- **haven** (or whatever reads SAS files) is not cited.
- **pixi** package manager is not cited.
- **Singularity/Apptainer** citation exists. PASS.

### nf-core Compliance
- Format follows nf-core citation style. PASS.

---

## 5. DISCLAIMER.md

### Accuracy
- Standard CDC disclaimer. Content is appropriate. PASS.

### Completeness
- Adequate for its purpose. PASS.

### Naming
- Does not reference "FoodNetTrends" or "FoodNet Trends". Neutral.

---

## 6. LICENSE

### Accuracy
- States "MIT License" with copyright "SChill".
- **INCONSISTENCY:** The README says "CDC Public Domain License" but the LICENSE file contains an MIT License. The CONTRIBUTING.md says the project is "in the public domain" with CC0 dedication. These three statements are mutually contradictory.
- The manifest in `nextflow.config` does not specify a license.
- "SChill" copyright holder is unclear -- presumably an individual, not CDC.

### Completeness
- If this is intended to be public domain (per CONTRIBUTING.md and CDC standard practice), the LICENSE file should contain a CC0 or public domain dedication, not an MIT license.

---

## 7. code-of-conduct.md

### Accuracy
- Standard CDC code of conduct adapted from 18F. PASS.

### Completeness
- Adequate. PASS.

### Naming
- Does not reference the pipeline name. Neutral.

---

## 8. open_practices.md

### Accuracy
- Standard CDCGov GitHub practices document. PASS.

### Completeness
- Adequate as a governance document. PASS.

### Relevance
- This is a generic CDCGov document, not specific to FoodNetTrends. Fine to include as reference.

---

## 9. rules_of_behavior.md

### Accuracy
- Standard CDC rules of behavior for GitHub usage. PASS.

### Completeness
- Adequate. PASS.

---

## 10. thanks.md

### Accuracy
- Acknowledges Chris Sandlin and Drewry Morris. These are presumably CDCGov template contributors, not FoodNetTrends-specific contributors.
- The README credits Samantha Sevilla, Josh Forstedt, OAMD SciComp Team, Daniel Weller, Beau Bruce, and Erica Billig Rose -- none of whom appear in thanks.md.

### Completeness
- Should either be updated to acknowledge FoodNetTrends contributors or clarified as a template-level acknowledgment.

---

## Summary of Critical Issues

### HIGH PRIORITY
1. **CITATIONS.md references FastQC and MultiQC** -- these tools are not used by this pipeline. This is misleading.
2. **LICENSE inconsistency** -- LICENSE says MIT (copyright SChill), README says CDC Public Domain, CONTRIBUTING.md says CC0. Must be resolved.
3. **CHANGELOG.md is empty** and references "cdc/spline" instead of "FoodNetTrends".
4. **README links to `.github/CONTRIBUTING.md`** which does not exist (actual file is `./CONTRIBUTING.md`).
5. **No container build instructions** in README -- users cannot run the pipeline without knowing how to build `foodnet.sif`.

### MEDIUM PRIORITY
6. **CITATIONS.md references "cdc/spline"** instead of "FoodNetTrends".
7. **Missing citations for core tools** (R, brms, Stan) in CITATIONS.md.
8. **CITATIONS.md lists Anaconda, Bioconda, BioContainers** which are not used.
9. **README missing `stan_backend` and `skip_dashboard` parameter documentation**.
10. **README missing CDC-required notice sections** per `open_practices.md`.
11. **README does not document scicomp_rosalind, local, training, conda profiles** from `fnt.scicomp.config`.
12. **README test/full/resume invocation syntax** may not match actual `run_workflow.sh` behavior (interactive menu vs CLI args).
13. **thanks.md** does not acknowledge actual FoodNetTrends contributors.

### LOW PRIORITY
14. **main.nf help text** uses `--censusFile_B` (underscore) but actual param is `censusFileB` (camelCase).
15. **README does not mention DASHBOARD or RESOURCE_PROFILER** modules.
16. **README does not document AUTO_DISCOVER** pathogen mode.
17. **CHANGELOG.md date placeholder** `[date]` never filled in.
18. **Missing nf-core badges** in README header.
19. **SHARE IT Act section** has empty Description fields.
