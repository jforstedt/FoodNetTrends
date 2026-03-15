# Pre-Implementation Questions for FoodNetTrends Pipeline Overhaul

**Date:** 2026-03-14
**Purpose:** Every decision point requiring user input before implementation begins.
**Source:** All five plans (Model, Profiler, Container, Cleanup, UX) plus architect reviews.

**How to use this document:** Each question has a recommended default. If you agree with all defaults, you can say "go with defaults on everything" and we proceed immediately. Otherwise, flag specific questions you want to override.

---

## BLOCKING Questions

These affect multiple plans or fundamental architecture. Cannot proceed without answers.

---

### B1. Pixi vs. Conda: Approve the container migration?

**Source:** Container Plan, `pixi_vs_conda.md`
**Recommended:** Yes, migrate to pixi.

The Container Plan proposes replacing the conda-based container build (`continuumio/miniconda3` + `foodnet.yml`) with a pixi-based build (`ubuntu:22.04` + `pixi.toml` + `pixi.lock`). This is the single largest infrastructure change across all plans.

**Why input needed:** This changes the container build toolchain, affects the Profiler Plan (Change 10 becomes unnecessary if Container Plan is implemented), and requires verifying that all R packages resolve from `conda-forge` + `bioconda` channels only (the current `foodnet.yml` also lists `defaults`, `r`, and `stan` channels). The CDC HPC team may not have pixi experience, which could complicate troubleshooting.

**What depends on the answer:**
- Container Plan: entire plan proceeds or falls back to fixing conda in-place
- Profiler Plan Change 10: becomes unnecessary if pixi is adopted (Container Plan subsumes it)
- Cleanup Plan: `foodnet.yml` maintenance strategy changes
- New files committed to repo: `pixi.toml`, `pixi.lock`

**If we pick recommended:** We migrate to pixi. The `foodnet.yml` is kept as a fallback for the `conda` profile in `cdc-dev.config`. Container builds gain a lock file for full reproducibility. Build times improve 3-10x. Container base image shrinks from ~400 MB to ~107 MB.

---

### B2. Channel verification: Can all packages resolve from conda-forge + bioconda only?

**Source:** Container Plan (Architect Review Issue 2), `pixi_vs_conda.md` Section 7
**Recommended:** Verify before implementation (this is a prerequisite, not a choice).

The current `foodnet.yml` lists five channels: `defaults`, `r`, `stan`, `conda-forge`, `bioconda`. The `defaults` channel has Anaconda licensing implications for organizational use. Before pixi migration, we must verify that all 14+ R packages (including the new `r-stringdist` and `r-base64enc`) resolve from just `conda-forge` and `bioconda`. If any require the `stan` or `r` channels, those channels must be added to `pixi.toml`.

**Why input needed:** If packages require the `stan` or `r` channels, pixi.toml needs those channels added. If the `defaults` channel is required, there are licensing implications for CDC organizational use.

**What depends on the answer:** `pixi.toml` channel configuration; whether Anaconda licensing needs to be addressed.

**If we pick recommended:** We run `pixi init --import foodnet.yml` and verify resolution. If any packages fail, we add the necessary channels. This is a technical verification step that happens during implementation.

---

### B3. Implementation order: Approve the phased sequence?

**Source:** All plans, Architect Review unified sequence (UX Plan Section 6)
**Recommended:** Yes, follow the architect's unified sequence.

The architect recommends this order:
1. Model Plan (statistical fixes -- highest priority, results-changing)
2. Profiler Plan Phase 1-2 (h_vmem, exit codes, CPU allocation -- config only)
3. Container Plan (rebuild -- subsumes Profiler Change 10)
4. Profiler Plan Phase 3 (cmdstanr backend -- needs working container)
5. UX Plan (run_workflow.sh fixes, monitor script, local executor)
6. Cleanup Plan (orphan removal, schema fixes, documentation)

Each phase has a checkpoint for testing before proceeding.

**Why input needed:** If you have different priorities (e.g., want UX fixes before container changes, or want cleanup first), the sequence changes.

**What depends on the answer:** Order of all implementation work; which plans can be parallelized.

**If we pick recommended:** We implement in the order above, testing at each checkpoint. This minimizes risk because higher-priority, results-affecting changes come first.

---

### B4. HDI computation: Log-scale (match source) or response-scale (arguably more interpretable)?

**Source:** Model Plan Step 3, Architect Review Section 4
**Recommended:** Log-scale (match the source code and published paper).

The statistical justification review concluded that both approaches are defensible and that response-scale HDI is "arguably more interpretable." However, the published paper's results were computed using log-scale HDI (compute HDI on `log(.value)`, then exponentiate back). The Model Plan overrides the statistical review's finding to match the source.

**Why input needed:** This is a scientific methodology choice. Log-scale HDI produces narrower right tails and wider left tails compared to response-scale HDI. The published paper used log-scale. If you want to deviate from the published methodology, response-scale HDI is also defensible.

**What depends on the answer:** Model Plan Step 3 implementation; all `_hdi` and `_hdi_ir` columns in output CSVs; visual appearance of uncertainty bands in plots.

**If we pick recommended:** HDI is computed on the log scale and back-transformed, matching the original source code and published results. All 8 HDI computation sites in `functions.R` are modified.

---

### B5. Convergence failure behavior: Soft failure (warn and continue) or hard failure (stop pipeline)?

**Source:** Model Plan Step 5
**Recommended:** Soft failure (warn and continue).

When a model fails convergence diagnostics (R-hat > 1.05, or ESS < 400, or divergent transitions), the plan proposes emitting warnings and writing a diagnostics CSV but continuing the pipeline. The alternative is to stop the pipeline immediately upon convergence failure.

**Why input needed:** In a production setting with 9 pathogens running in parallel, a hard failure on one pathogen would halt the entire run. Soft failure lets the other 8 pathogens complete successfully while flagging the problematic one. However, soft failure means potentially unreliable results are produced and published to the output directory.

**What depends on the answer:** Model Plan Step 5 implementation; whether convergence failure produces output files or not.

**If we pick recommended:** Pipeline continues on convergence failure. A `{PATHOGEN}_convergence_diagnostics.csv` file is written alongside each model output. Console warnings are emitted. Users must review diagnostics files before using results.

---

### B6. Local executor for lightweight processes: Approve running PREPROCESS, RESOURCE_PROFILER, and DASHBOARD on the login node?

**Source:** UX Plan, Architect Review Section 5
**Recommended:** Yes, implement as an opt-in profile (`-profile singularity,local_lightweight`).

Currently all processes (including lightweight ones like preprocessing and dashboard generation) are submitted to SGE, adding 30s-5min queue wait per job. Running these on the login node eliminates that wait. The architect recommends making this opt-in via a separate Nextflow profile.

**Why input needed:** Some HPC systems have strict no-compute policies on login nodes. CDC's Rosalind cluster may have such a policy. These processes are lightweight (< 2 GB memory, < 2 min runtime) but running anything on login nodes requires institutional approval.

**What depends on the answer:** Whether a `local_lightweight` profile is added to `nextflow.config`; perceived pipeline startup speed.

**If we pick recommended:** A `local_lightweight` profile is added. Users activate it with `-profile singularity,local_lightweight`. PREPROCESS, RESOURCE_PROFILER, and DASHBOARD run locally; TRENDY still goes to SGE. Startup latency drops by 2-15 minutes.

---

## PREFERENCE Questions

These have clear recommended defaults but you might want something different.

---

### P1. Stan backend default: rstan or cmdstanr?

**Source:** Profiler Plan Changes 5-9
**Recommended:** Default to `rstan`, with `cmdstanr` as opt-in via `--stan_backend cmdstanr`.

The plan adds a `--stan_backend` parameter. Both backends produce statistically equivalent posteriors. cmdstanr has faster compilation and better model caching. rstan is the current (tested) backend.

**Why input needed:** If you want cmdstanr as the default (or want to skip adding backend selection entirely and keep rstan hardcoded), the implementation changes.

**What depends on the answer:** Profiler Plan Changes 5-9; default in `nextflow.config`; `run_workflow.sh` menu.

**If we pick recommended:** `rstan` remains the default. Users can opt into `cmdstanr` via the command line or run_workflow.sh menu. No behavioral change for existing users.

---

### P2. CmdStan compilation in container: Include or skip?

**Source:** Container Plan Step 2, Profiler Plan Change 10
**Recommended:** Include CmdStan compilation in the container build.

Compiling CmdStan adds ~200 MB to the container and ~5 min to the build. Without it, `--stan_backend cmdstanr` silently fails at model compilation time.

**Why input needed:** If you never plan to use cmdstanr, this is wasted space. If the container build machine lacks internet access, `install_cmdstan()` cannot download the source code and the build fails.

**What depends on the answer:** Container size; whether cmdstanr backend works out of the box.

**If we pick recommended:** CmdStan is compiled during container build. The `cmdstanr` backend works immediately. Container is ~200 MB larger. Build machine must have internet access.

---

### P3. nf-core module cleanup: Replace FastQC/MultiQC or just remove?

**Source:** Cleanup Plan Section 1 (1a, 1b), Priority 6
**Recommended:** Remove both via `nf-core modules remove` (not manual deletion).

The pipeline has FastQC and MultiQC modules installed from the nf-core template but never used. Options:
- (A) Remove them via nf-core tooling
- (B) Replace FastQC with a custom data validation module for SAS/CSV inputs; integrate MultiQC for pipeline execution reports

**Why input needed:** Option B adds useful validation infrastructure but is significantly more work. Option A is quick and clean.

**What depends on the answer:** Cleanup Plan scope; whether a custom data validation module is created.

**If we pick recommended:** Both modules are removed via `nf-core modules remove fastqc` and `nf-core modules remove multiqc`, keeping `modules.json` in sync. No replacement is created now.

---

### P4. source/ directory policy: Keep in git or add to .gitignore?

**Source:** Cleanup Plan Section 6, Priority 6
**Recommended:** Keep in git.

The `source/` directory contains the original pre-pipeline analysis scripts and historical output data. The reference CSV (`EstRR12Apr2024_MMWRR1_OrCatchment.csv`) is used by Model Plan regression tests.

**Why input needed:** Large binary files in git can bloat the repository. However, these files serve as provenance documentation and validation references.

**What depends on the answer:** Whether regression test reference data is available in the repo.

**If we pick recommended:** `source/` stays in git. It serves as provenance documentation and provides the reference CSV for validation testing.

---

### P5. `nextflow_schema.json` update: Minimal fix or full parameter schema?

**Source:** Cleanup Plan Section 8f (Priority 3)
**Recommended:** Minimal fix now (remove broken reference, fix required params), full schema in follow-up.

The schema has a broken `$ref` to non-existent `reference_genome_options`, and lists `input` as required instead of `mmwrFile`. Options:
- (A) Minimal: fix the broken ref and wrong required params
- (B) Full: also add definitions for all FoodNetTrends-specific parameters (including `stan_backend` from Profiler Plan)

**Why input needed:** Full schema update is more work but enables `nf-core launch` and parameter validation via `nf-schema` plugin. Minimal fix just prevents validation errors.

**What depends on the answer:** Cleanup Plan scope; whether `nf-core launch` works.

**If we pick recommended:** Minimal fix now. The broken reference is removed, `input` is replaced with `mmwrFile` in required. Full parameter definitions are tracked as a follow-up.

---

### P6. Monitor script: Separate `monitor_pipeline.sh` or embedded in `run_workflow.sh`?

**Source:** UX Plan Section 6
**Recommended:** Separate script.

The UX plan proposes a standalone `monitor_pipeline.sh` that reads Nextflow's execution trace file and displays per-pathogen progress. The alternative is embedding the monitoring logic in `run_workflow.sh`.

**Why input needed:** A separate script is more Unix-like (composable, can be started independently) but adds another file to maintain. Embedding keeps everything in one place but limits flexibility.

**What depends on the answer:** Whether a new file is created; how monitoring is launched.

**If we pick recommended:** A new `monitor_pipeline.sh` script is created. `run_workflow.sh` prints the monitor command after launching the pipeline. Users can start the monitor from any terminal.

---

### P7. Quick-run fast path for test mode?

**Source:** UX Plan Section 2
**Recommended:** Yes, add it.

When test mode is selected, offer a "proceed with all defaults" shortcut that skips 6-7 prompts. Experienced users iterating on the pipeline save significant time.

**Why input needed:** Some teams prefer explicit confirmation of every parameter, even in test mode.

**What depends on the answer:** UX Plan implementation scope; number of prompts in test mode.

**If we pick recommended:** After selecting test mode, user is offered "Proceed with defaults (y) or customize (c)?". Choosing 'y' skips directly to the confirmation summary, reducing the flow from 8-9 prompts to 2.

---

### P8. Data file paths: Hard-coded or configurable?

**Source:** UX Plan Appendix item 3
**Recommended:** Define once at top of `run_workflow.sh`, use variables throughout.

The MMWR file (`mmwr9624_May2025.sas7bdat`) and census files are hard-coded in 3+ places in `run_workflow.sh`. When the data file is updated (e.g., next year's data), all instances must be changed manually.

**Why input needed:** If the file names are expected to change frequently, parameterization is more important. If they rarely change, the fix is cosmetic.

**What depends on the answer:** How `run_workflow.sh` constructs the Nextflow command; maintenance burden.

**If we pick recommended:** File paths are defined as variables at the top of `run_workflow.sh` and referenced throughout. A single edit updates all uses.

---

### P9. CUSTOM_DUMPSOFTWAREVERSIONS integration: Now or later?

**Source:** Cleanup Plan Section 1c, Priority 5
**Recommended:** Later (track as follow-up).

The `dumpsoftwareversions` module is an nf-core standard for collecting R/tool versions for reproducibility. Integrating it requires each process (TRENDY, PREPROCESS, RESOURCE_PROFILER, DASHBOARD) to emit a `versions.yml` output, which is a nontrivial change to 4 process definitions.

**Why input needed:** If reproducibility reporting is urgent, this should be prioritized. Otherwise, it is deferred to a follow-up.

**What depends on the answer:** Whether 4 process definitions are modified now; Cleanup Plan scope.

**If we pick recommended:** Deferred. The module stays installed but unwired. A future PR integrates it.

---

### P10. Container base image: ubuntu:22.04 or ubuntu:24.04?

**Source:** Container Plan Step 2 (implicit assumption)
**Recommended:** ubuntu:22.04 (as specified in the plan).

The plan specifies `ubuntu:22.04` as the base image. Ubuntu 22.04 LTS is supported until April 2027. Ubuntu 24.04 LTS is available and supported until April 2029.

**Why input needed:** 22.04 is well-tested on HPC systems. 24.04 has a longer support window but may have untested interactions with R/Stan packages.

**What depends on the answer:** Container base image in `foodnet.def`.

**If we pick recommended:** ubuntu:22.04 is used. Stable, well-tested, and sufficient for the pipeline's lifetime.

---

### P11. Convergence diagnostics output: Add to trendy.nf outputs or leave in work directory?

**Source:** Model Plan Step 5, Architect Review Section 3
**Recommended:** Add to `trendy.nf` outputs so it gets published to `spline_results/`.

Model Plan Step 5 creates `{PATHOGEN}_convergence_diagnostics.csv` but does not add it to `trendy.nf`'s output declarations. Without a matching `path` declaration, the file stays in the Nextflow work directory and is not published.

**Why input needed:** If diagnostics files are only needed for debugging (not for permanent records), leaving them in the work directory is fine. If they should be part of the published results, they need an output declaration.

**What depends on the answer:** Whether `trendy.nf` is modified (coordinate with Profiler Plan which also modifies `trendy.nf`).

**If we pick recommended:** A `path` output declaration is added to `trendy.nf` for the diagnostics CSV. The file is published alongside other results in `spline_results/`.

---

### P12. Dead code removal: Remove CYCLOSPORA_ANALYSIS() and SALMONELLA_ANALYSIS() now or in cleanup?

**Source:** Model Plan Step 2, Cleanup Plan Architect Review Issue 3
**Recommended:** Remove during Cleanup Plan (Phase 6), not during Model Plan.

After Model Plan Step 2 removes the calls to these functions from `trendy.R`, the function definitions in `functions.R` (lines 260-316) become dead code. Also, `gtools::smartbind` is no longer called anywhere.

**Why input needed:** Removing dead code during the Model Plan reduces diff noise in the statistical fixes commit. Deferring to Cleanup Plan keeps the Model Plan focused on correctness.

**What depends on the answer:** Whether `functions.R` lines 260-316 are removed in the Model Plan or the Cleanup Plan.

**If we pick recommended:** Dead code stays during Model Plan implementation. It is removed in the Cleanup Plan, which adds it to the orphan list.

---

### P13. Resume cache invalidation: Document-only or add automated cache clearing?

**Source:** Model Plan Architect Review Section 2, Container Plan Architect Review Section 2
**Recommended:** Document the requirement and add a warning to `run_workflow.sh`.

Changes to `functions.R` content are NOT reflected in Nextflow's task hash (because `functions.R` is copied via `cp` in the script block, and Nextflow hashes the template, not the referenced files). After deploying Model Plan fixes, a `-resume` run would use stale cached results. Similarly, rebuilding the container does not invalidate caches.

**Why input needed:** Options:
- (A) Document-only: README/CHANGELOG note saying "run `nextflow clean -f` after updating"
- (B) Add a warning in `run_workflow.sh` that detects code changes and warns about stale caches
- (C) Refactor `functions.R` to be a `path` input to TRENDY (makes its content part of the cache key) -- broader refactoring

**What depends on the answer:** Whether `run_workflow.sh` gets additional logic; whether `trendy.nf` is refactored.

**If we pick recommended:** Document it in the CHANGELOG and add a one-line warning in `run_workflow.sh` when resume mode is selected: "Note: if pipeline code has been updated since the last run, use a fresh work directory."

---

## INFORMATIONAL Questions

Need to verify something about the environment or setup.

---

### I1. Does the CDC HPC build machine have internet access for container builds?

**Source:** Container Plan Architect Review Section 4
**Recommended:** Verify before container build.

The Container Plan's `foodnet.def` runs `pixi install --locked` (downloads packages) and `cmdstanr::install_cmdstan()` (downloads CmdStan source from GitHub) during the `%post` section. If the build machine is air-gapped or has restricted internet, these steps fail.

**Why input needed:** If no internet, CmdStan source must be pre-downloaded and provided as a local file. Pixi packages could potentially be pre-cached.

**What depends on the answer:** Container Plan `%post` section; whether CmdStan tarball needs to be bundled.

**If we pick recommended:** We verify internet access before the first container build. If unavailable, we adjust the build process to use local package caches and pre-downloaded CmdStan.

---

### I2. Does the Rosalind login node allow lightweight computation?

**Source:** UX Plan Architect Review Section 5b
**Recommended:** Check CDC HPC acceptable use policy.

Running PREPROCESS, RESOURCE_PROFILER, and DASHBOARD on the login node (via local executor) saves queue wait time. These are lightweight (< 2 GB memory, < 2 min runtime). Some HPC systems prohibit any computation on login nodes.

**Why input needed:** If login node computation is prohibited, the local executor feature cannot be used.

**What depends on the answer:** Whether the `local_lightweight` profile is usable in practice.

**If we pick recommended:** We check the policy. If allowed, the profile is available. If not, we skip the local executor feature and all processes continue to use SGE.

---

### I3. Is `.gitignore` currently excluding `pixi.lock` or `.pixi/`?

**Source:** Container Plan Architect Review Issue 1
**Recommended:** Verify before pixi migration.

`pixi.lock` must be committed to the repo (it is the lock file that guarantees reproducibility). The `.pixi/` directory (local environment cache) must NOT be committed. If `.gitignore` has blanket exclusions that catch these, the pixi migration breaks.

**Why input needed:** If `.gitignore` needs updating, it must be done before committing pixi files.

**What depends on the answer:** Whether `.gitignore` needs modification.

**If we pick recommended:** We check `.gitignore` during implementation and add `.pixi/` to it if not already excluded. We ensure `pixi.lock` is NOT excluded.

---

### I4. Are there any scripts or processes that reference the conda env name `FootNetTreands_R` directly?

**Source:** Container Plan Architect Review Issue 6
**Recommended:** Verify before env name fix.

The Container Plan fixes the typo from `FootNetTreands_R` to `FoodNetTrends_R` in `foodnet.yml`. If any scripts (beyond the three files already identified: `foodnet.yml`, `foodnet.def`, `nextflow.config`) reference the old name, they will break.

**Why input needed:** If additional references exist, they need to be updated simultaneously.

**What depends on the answer:** Whether additional files need the typo fix.

**If we pick recommended:** We grep the entire repo for `FootNetTreands_R` and update all occurrences. The pixi migration makes the env name irrelevant for the primary build path, but the conda fallback still needs the correct name.

---

### I5. What Nextflow version is installed on Rosalind?

**Source:** UX Plan Architect Review Sections 2c, 3
**Recommended:** Verify.

The UX plan and architect review reference Nextflow 25.x features (`workflow.onComplete` hooks, `trace.overwrite`, `nf-schema` plugin). The pipeline currently uses Nextflow (version unknown). Some features may not be available on older versions.

**Why input needed:** If Nextflow < 25.x, some UX features (like `nf-schema` enum validation for `stan_backend`) are unavailable. The core pipeline works on Nextflow 22+.

**What depends on the answer:** Whether `nf-schema` plugin is used; whether `workflow.onComplete` hooks are available.

**If we pick recommended:** We verify the version and use only features available in the installed version. Core changes work on any modern Nextflow version.

---

### I6. Does the current data include COEX records for 2023?

**Source:** Model Plan Step 6
**Recommended:** Verify.

Model Plan Step 6 changes the COEX exclusion from unconditional to year-conditional (`!(siteid == "COEX" & year < 2023)`). This only matters if the MMWR data file actually contains COEX records for 2023+. If the data only goes through 2022, this fix is correct but has no immediate effect.

Additionally, the census population files must include the expanded Colorado population for 2023+. If they don't, the fix retains COEX case data but without matching population denominators.

**Why input needed:** If census files lack 2023 COEX population data, the fix creates a data mismatch (cases without population denominators).

**What depends on the answer:** Whether Step 6 is fully effective immediately or requires census data updates.

**If we pick recommended:** We implement the fix regardless (it is correct for future-proofing). We verify census data coverage during testing.

---

### I7. What seed value should be used for regression testing?

**Source:** Model Plan Validation Plan
**Recommended:** `seed = 123` (matches current default and publication settings).

The Model Plan validation requires running the pipeline with specific settings and comparing output to the reference CSV. The seed affects MCMC sampling and thus the exact numerical results.

**Why input needed:** If the published results used a different seed, the comparison will show larger discrepancies.

**What depends on the answer:** Regression test configuration; how closely results should match the reference.

**If we pick recommended:** Use seed 123 for regression testing. Results should be closer to the reference than pre-fix output, but exact matches are not expected due to iteration and chain differences.

---

## Summary Table

| ID | Category | Question | Plan | Recommended |
|----|----------|----------|------|-------------|
| B1 | BLOCKING | Pixi vs Conda migration? | Container | Yes, migrate |
| B2 | BLOCKING | Channel verification prerequisite | Container | Verify first |
| B3 | BLOCKING | Implementation order | All | Follow architect sequence |
| B4 | BLOCKING | HDI log-scale vs response-scale | Model | Log-scale (match source) |
| B5 | BLOCKING | Convergence failure: soft or hard? | Model | Soft (warn, continue) |
| B6 | BLOCKING | Local executor for lightweight processes? | UX | Yes, opt-in profile |
| P1 | PREFERENCE | Stan backend default | Profiler | rstan default, cmdstanr opt-in |
| P2 | PREFERENCE | CmdStan in container? | Container/Profiler | Yes, include |
| P3 | PREFERENCE | FastQC/MultiQC: replace or remove? | Cleanup | Remove via nf-core tooling |
| P4 | PREFERENCE | source/ directory policy | Cleanup | Keep in git |
| P5 | PREFERENCE | Schema fix: minimal or full? | Cleanup | Minimal now, full later |
| P6 | PREFERENCE | Monitor: separate script or embedded? | UX | Separate script |
| P7 | PREFERENCE | Quick-run fast path for test mode? | UX | Yes |
| P8 | PREFERENCE | Data file paths: hard-coded or vars? | UX | Variables at top |
| P9 | PREFERENCE | DUMPSOFTWAREVERSIONS: now or later? | Cleanup | Later |
| P10 | PREFERENCE | Container base image version | Container | ubuntu:22.04 |
| P11 | PREFERENCE | Convergence diagnostics in outputs? | Model/Profiler | Yes, add to trendy.nf |
| P12 | PREFERENCE | Dead code removal timing | Model/Cleanup | During Cleanup Plan |
| P13 | PREFERENCE | Resume cache invalidation strategy | Model/Container | Document + warning |
| I1 | INFORMATIONAL | Build machine internet access? | Container | Verify |
| I2 | INFORMATIONAL | Login node computation policy? | UX | Check policy |
| I3 | INFORMATIONAL | .gitignore pixi compatibility? | Container | Verify |
| I4 | INFORMATIONAL | Other refs to old env name? | Container | Grep and update |
| I5 | INFORMATIONAL | Nextflow version on Rosalind? | UX | Verify |
| I6 | INFORMATIONAL | COEX data + census for 2023? | Model | Verify |
| I7 | INFORMATIONAL | Regression test seed value? | Model | seed = 123 |

---

## Implicit Assumptions Made by the Plans

These are not explicitly flagged as questions in any plan, but they are assumptions that could be wrong.

### A1. The pipeline will continue to target SGE (Sun Grid Engine) as the primary scheduler.

All resource management changes (h_vmem, exit codes, CPU allocation) are SGE-specific. If CDC is migrating to SLURM or another scheduler, the Profiler Plan changes would need different syntax.

### A2. The publication settings (6 chains, 10001 iterations, adapt_delta 0.99) remain correct.

The Model Plan uses these for regression testing. If you want to change the publication defaults (e.g., fewer iterations, different adapt_delta), the validation criteria change.

### A3. R 4.3.2 is the target R version.

The `foodnet.yml` pins `r-base=4.3.2`. R 4.4.x and 4.5.x are available. The pixi migration would pin the same version unless you want to upgrade.

### A4. The 95% credible interval width is correct.

All HDI computations use `credMass = 0.95`. The plans do not question this. If a different credible interval width is desired (e.g., 89% as recommended by some Bayesian statisticians), all HDI calls need updating.

### A5. The pipeline runs on Linux x86_64 only.

The `pixi.toml` specifies `platforms = ["linux-64"]`. If anyone needs to run on ARM (e.g., Apple Silicon for development), the platform list needs expanding.

### A6. The `cdc-dev.config` rosalind profile syntax error (line 150) is out of scope.

The architect identified mismatched parentheses in `cdc-dev.config` line 150's `clusterOptions` expression. It is masked for TRENDY but could affect other processes using the rosalind profile directly. All plans explicitly exclude this fix.

### A7. The `base.config` errorStrategy (retrying SIGSEGV for non-TRENDY processes) is acceptable.

The Profiler Plan removes exit code 139 (SIGSEGV) from TRENDY's retry list but `base.config` line 18 still retries SIGSEGV for other processes via the range `(130..145)`. This is technically wrong but out of scope for all plans.

### A8. No CI/CD pipeline exists or is planned for the immediate future.

The Cleanup Plan mentions adding `.github/workflows/` CI files as Priority 5 (future). If CI is needed sooner, it should be prioritized.
