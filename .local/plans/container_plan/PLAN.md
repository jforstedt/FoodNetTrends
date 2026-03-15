# Container Environment Plan

**Date:** 2026-03-14
**Scope:** `foodnet.def`, `foodnet.yml`, `nextflow.config` (env block), `conf/cdc-dev.config`

---

## Current State

The pipeline uses a Singularity container built on `continuumio/miniconda3` with a conda environment from `foodnet.yml`. This is standard practice for HPC bioinformatics but has reproducibility gaps (no lock file for transitive deps) and some issues.

### Known Issues

| Issue | Severity | Details |
|-------|----------|---------|
| Typo: `FootNetTreands_R` | LOW | Consistent across 3 files so it works, but maintenance hazard |
| `apt-get` runs AFTER `conda env create` | MEDIUM | Packages needing compilation during install may fail |
| Missing `r-stringdist` | MEDIUM | Used by preprocess.R fuzzy matching, loaded via tryCatch |
| Missing `r-base64enc` | LOW | Needed for dashboard generation |
| No lock file | MEDIUM | Transitive deps unpinned — two builds can differ |
| CmdStan binary not compiled | LOW | r-cmdstanr installed but binary missing — cmdstanr backend won't work |
| Authorship line in def | LOW | Should be removed for professionalism |
| `build-essential` order | MEDIUM | Must precede conda env creation |

---

## Recommended Approach: Migrate from Conda to Pixi

See `pixi_vs_conda.md` for the full comparison. Summary:

- **Pixi uses the same packages** from conda-forge/bioconda — all 14 R packages work
- **Built-in lock file** (`pixi.lock`) — pins every transitive dependency with hashes automatically, solving the reproducibility gap without extra tooling
- **3-10x faster** builds than conda
- **Smaller base** — 30 MB pixi binary vs 400 MB Miniconda image
- **Migration** — `pixi init --import foodnet.yml`, one command
- **No `FootNetTreands_R` problem** — pixi environments are anonymous and project-local, the typo becomes irrelevant

---

## Implementation Plan

### Phase 1: Pixi Migration + Def Cleanup (single container rebuild)

All changes are done together since they all require a rebuild.

#### Step 1: Create `pixi.toml` from existing `foodnet.yml`

```bash
pixi init --import foodnet.yml
```

Then edit `pixi.toml` to:
- Add missing packages: `r-stringdist`, `r-base64enc`
- Verify channels: ensure `conda-forge` and `bioconda` are listed (drop `defaults` to avoid Anaconda licensing)
- Verify the `stan` and `r` channels resolve correctly — test with `pixi install`
- Keep cmdstanr in the manifest (will compile binary in def)

Generate lock file:
```bash
pixi install  # creates pixi.lock automatically
```

Commit both `pixi.toml` and `pixi.lock` to the repo.

#### Step 2: Rewrite `foodnet.def`

**Current:**
```
Bootstrap: docker
From: continuumio/miniconda3

%labels
    author Ethan H
    date 2025-1-14
    version 1.0.0
    description FoodNet container with Rscript support

%files
    foodnet.yml

%post
    conda env create -f foodnet.yml
    conda clean --all --yes

    apt-get update
    apt-get install -y build-essential

%environment
    export PATH="/opt/conda/envs/FootNetTreands_R/bin:$PATH"

%runscript
    exec "$@"
```

**New:**
```
Bootstrap: docker
From: ubuntu:22.04

%labels
    version 2.0.0
    description FoodNet Trends pipeline container with R, brms, and Stan

%files
    pixi.toml
    pixi.lock

%post
    apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

    # Install pixi
    curl -fsSL https://pixi.sh/install.sh | PIXI_HOME=/opt/pixi bash
    export PATH="/opt/pixi/bin:$PATH"

    # Create environment from lock file (fully reproducible)
    cd /opt/pipeline
    cp /pixi.toml /pixi.lock .
    pixi install --locked

    # Compile CmdStan binary for optional cmdstanr backend
    pixi run Rscript -e "cmdstanr::install_cmdstan(cores = 4, quiet = TRUE)"

    # Clean up
    rm -rf /tmp/* /root/.cache

%environment
    export PATH="/opt/pixi/bin:/opt/pipeline/.pixi/envs/default/bin:$PATH"
    export PIXI_PROJECT_MANIFEST=/opt/pipeline/pixi.toml
    export R_LIBS="/opt/pipeline/.pixi/envs/default/lib/R/library"

%runscript
    exec "$@"
```

#### Step 3: Update `nextflow.config` env block

**File:** `nextflow.config` lines 117-122

**Old:**
```groovy
env {
    PYTHONNOUSERSITE = 1
    R_PROFILE_USER   = "/.Rprofile"
    R_ENVIRON_USER   = "/.Renviron"
    JULIA_DEPOT_PATH = "/usr/local/share/julia"
    R_LIBS           = "/opt/conda/envs/FootNetTreands_R/lib/R/library"
}
```

**New:**
```groovy
env {
    PYTHONNOUSERSITE = 1
    R_PROFILE_USER   = "/.Rprofile"
    R_ENVIRON_USER   = "/.Renviron"
    R_LIBS           = "/opt/pipeline/.pixi/envs/default/lib/R/library"
}
```

Changes: remove JULIA_DEPOT_PATH (not used), update R_LIBS path.

#### Step 4: Keep `foodnet.yml` as fallback

Don't delete it — the `conda` profile in `cdc-dev.config` references it. Update the typo and add missing packages:

| File | Line | Old | New |
|------|------|-----|-----|
| `foodnet.yml` | 1 | `name: FootNetTreands_R` | `name: FoodNetTrends_R` |
| `foodnet.yml` | after line 22 | (none) | `  - r-stringdist` |
| `foodnet.yml` | after line 22 | (none) | `  - r-base64enc` |

Also update `cdc-dev.config` conda profile if it references the old env name.

### Phase 2: Verify (no rebuild)

1. Build the new container: `singularity build foodnet.sif foodnet.def`
2. Test R packages load: `singularity exec foodnet.sif Rscript -e "library(brms); library(rstan); library(tidybayes); library(HDInterval); library(stringdist); library(base64enc); cat('OK\n')"`
3. Test cmdstanr: `singularity exec foodnet.sif Rscript -e "library(cmdstanr); cmdstan_path(); cat('OK\n')"`
4. Run pipeline with `--skip_dashboard` on a test pathogen
5. Compare results against previous run (should be identical for rstan backend)

### Phase 3: Optional — Remove conda dependency entirely

Once pixi is validated, the `conda` profile in `cdc-dev.config` could be updated to use pixi directly. This is optional — having conda as a fallback is fine.

---

## Files Modified

| File | Change | Rebuild? |
|------|--------|----------|
| `foodnet.def` | Complete rewrite — pixi-based, no authorship, professional | YES |
| `nextflow.config` | Update R_LIBS path, remove JULIA_DEPOT_PATH | No |
| `foodnet.yml` | Fix typo, add r-stringdist + r-base64enc (kept as fallback) | YES (if using conda fallback) |
| NEW: `pixi.toml` | Generated from foodnet.yml import | N/A |
| NEW: `pixi.lock` | Auto-generated lock file | N/A |

---

## Risk Assessment

| Change | Affects Results? | Could Break Pipeline? |
|--------|-----------------|----------------------|
| Pixi migration | No — same packages, same versions | Low — pixi.lock guarantees exact versions |
| Def cleanup | No | No |
| Authorship removal | No | No |
| r-stringdist addition | Only fuzzy matching behavior | No (additive) |
| r-base64enc addition | No | No (additive) |
| CmdStan compilation | No (unless backend switched) | No (additive) |
| R_LIBS path change | No | YES if path is wrong — test immediately |

**No change in this plan affects the statistical model or data processing. Results will be identical.**

---

## Architect Review

**Reviewer:** Senior Nextflow DSL2 Bioinformatics Architect
**Date:** 2026-03-14
**Scope:** Container environment plan validation, cross-plan conflict analysis, DSL2 integration, nf-core compatibility, pixi assessment

---

### 1. Cross-Plan Conflict Analysis

**nextflow.config env block -- shared with Profiler Plan:** Container Plan Step 3 modifies the `env` block (lines 117-122), changing `R_LIBS` path and removing `JULIA_DEPOT_PATH`. The Profiler Plan modifies the process block (lines 137-146) and params block (~line 41). Non-overlapping config sections. No conflict.

**foodnet.def -- shared with Profiler Plan (Change 10):** Container Plan rewrites `foodnet.def` entirely (pixi-based). Profiler Plan Change 10 conditionally adds `cmdstanr::install_cmdstan()` to the `%post` section. The Container Plan's new def already includes `pixi run Rscript -e "cmdstanr::install_cmdstan(cores = 4, quiet = TRUE)"`, so **the Container Plan subsumes Profiler Change 10**. If this plan is implemented, Profiler Change 10 becomes unnecessary.

**foodnet.yml -- not modified by other plans.** Container Plan is the only one that updates the typo and adds packages.

**No conflicts with Model Plan or Cleanup Plan.** Container Plan does not touch R scripts or Nextflow module definitions.

### 2. DSL2 Integration Validation

**R_LIBS path change:** The new path `/opt/pipeline/.pixi/envs/default/lib/R/library` must exactly match where pixi installs R packages. The pixi default environment path IS `.pixi/envs/default/`, so the path construction is correct given `cd /opt/pipeline` and `pixi install --locked` in the def. **This is the single most critical path in the entire plan -- if wrong, every R process fails with "package not found."**

**Environment variable precedence:** The `env` block in `nextflow.config` exports `R_LIBS`. The `%environment` section in `foodnet.def` also sets `R_LIBS`. When running via Nextflow+Singularity, Nextflow's `env` block values are injected into the container environment and take precedence over the container's `%environment`. The `nextflow.config` setting is the authoritative one; the def's `%environment` is a fallback for direct `singularity exec` usage. The plan correctly updates both to the same path.

**Resume caching:** Changing the container image (new `foodnet.sif` from rebuilt def) does NOT automatically invalidate `-resume` caches. Nextflow hashes the container name string (`'foodnet.sif'`), not the container contents. If the SIF file is rebuilt, cached results from the old container are stale but will still be used on `-resume`. **Mitigation:** Clear cache after container rebuild (`nextflow clean -f`).

### 3. nf-core Compliance

**pixi and nf-core:** nf-core pipelines traditionally use conda yml files for environment specification. The nf-core template includes `conda` profile support that expects a yml file. The plan correctly retains `foodnet.yml` as a fallback for the conda profile in `cdc-dev.config`.

**However**, as of March 2026, `nf-core lint` does not recognize `pixi.toml` or `pixi.lock` as valid environment specifications. This means:
- `nf-core lint` may warn about missing conda environment definitions in process definitions
- The pipeline remains functionally correct but may not pass automated linting

**Recommendation:** Keep `foodnet.yml` maintained and in sync with `pixi.toml` dependencies. This dual-maintenance has cost, but preserves nf-core tooling compatibility. The nf-core community has been discussing pixi support (there are open issues on the nf-core/tools repo), so this may become a non-issue in a future nf-core release.

### 4. Best Practices Assessment (March 2026)

**Is pixi the right call for 2026?** Yes, with caveats. The pixi research document is accurate: pixi is production-ready (v0.40+), the built-in lock file is the killer feature, and conda-forge/bioconda compatibility is confirmed. Specific assessment:

1. **Maturity:** pixi went through breaking manifest format changes in 2024 but has been stable since. The lock file format is finalized. Acceptable risk for production use.
2. **HPC adoption:** Oregon State and DESY have official HPC documentation for pixi. Several bioinformatics groups (QuantCo, various Carpentries workshops) use pixi in production. CDC's HPC team may not have pixi experience, which could complicate troubleshooting.
3. **nf-core tooling:** As noted above, `nf-core lint` does not recognize pixi. This is a compliance gap, not a functional gap.

**Alternative: mamba/micromamba with conda-lock.** This would provide the lock file benefit without leaving the conda ecosystem. However, it requires an additional tool (`conda-lock`) and is slower than pixi. Given that the conda-lock maintainers themselves have suggested pixi for new work (conda-lock issue #615), pixi is the better forward-looking choice.

**Container base image:** Switching from `continuumio/miniconda3` (~400 MB) to `ubuntu:22.04` (~77 MB) + pixi (~30 MB) is a size win. Ensure the ubuntu base has the necessary C/C++ runtime libraries for R and Stan (libgomp for OpenMP, libgfortran for LAPACK). pixi should pull these as transitive dependencies of `r-base`, so this should be fine. But verify during the first test build.

**CmdStan compilation in container:** The plan includes `pixi run Rscript -e "cmdstanr::install_cmdstan(cores = 4, quiet = TRUE)"`. This is correct -- CmdStan must be compiled once at build time because Singularity containers are typically read-only at runtime. **One concern:** `install_cmdstan()` downloads CmdStan source code from GitHub. Container builds on HPC systems may not have internet access. Ensure the build machine has network access, or pre-download the CmdStan tarball and use `install_cmdstan(dir = "/path/to/local/tarball")`.

### 5. Issues and Concerns

**Issue 1: `pixi install --locked` requires committed lock file.** The plan correctly states to commit both `pixi.toml` and `pixi.lock`. Ensure `.gitignore` does not exclude `pixi.lock` or the `.pixi/` directory (the `.pixi/` directory itself should NOT be committed -- it is the local environment cache -- but `pixi.lock` must be).

**Issue 2: Channel verification before migration.** The current `foodnet.yml` lists channels `defaults`, `r`, `stan`, `conda-forge`, `bioconda`. The `defaults` channel has Anaconda licensing implications for organizational use. The `r` and `stan` channels may provide packages not on conda-forge. **Before migration:** Run `pixi init --import foodnet.yml` and verify all 14 packages resolve from just `conda-forge` and `bioconda`. If any require the `stan` or `r` channels, add them to `pixi.toml`. This is a prerequisite, not a nice-to-have.

**Issue 3: The `PIXI_PROJECT_MANIFEST` environment variable.** The def sets `export PIXI_PROJECT_MANIFEST=/opt/pipeline/pixi.toml`. Inside a Singularity container launched by Nextflow, the working directory is the Nextflow work directory, not `/opt/pipeline`. If any process tries `pixi run`, it needs this variable. Since the pipeline uses `R_LIBS` and direct `Rscript` invocation (not `pixi run`), this is a safety measure, not critical.

**Issue 4: Missing packages `r-stringdist` and `r-base64enc`.** Correctly identified as missing. Adding them to `pixi.toml` is correct. Verify that `preprocess.R`'s `tryCatch` around `stringdist` loading (line 38-40) still works when the package IS installed (it should -- `requireNamespace` returns TRUE, library loads, no issue).

**Issue 5: Singularity bind mounts.** The `singularity.runOptions = '--bind /scicomp'` in `nextflow.config` line 99 mounts CDC data paths. This is unrelated to the container rebuild but must still work with the new base image. Since bind mounts are host-side operations, the container base image is irrelevant. No issue.

**Issue 6: foodnet.yml env name typo fix propagation.** The plan fixes the typo from `FootNetTreands_R` to `FoodNetTrends_R` in `foodnet.yml`. If anyone uses the conda profile from `cdc-dev.config`, the env name must match between the yml and any conda activation commands. The `cdc-dev.config` conda profile (lines 81-101) does not reference the env name directly (it uses `beforeScript = 'source /etc/profile; eval "$(conda shell.bash hook)"'`), so this should be safe. But verify no other scripts reference the old name.

### 6. Implementation Sequencing (cross-plan)

Container Plan should be implemented **THIRD**, after Model Plan and Profiler Plan Phase 1-2:
1. Model Plan (R script fixes)
2. Profiler Plan Phase 1-2 (config changes -- no rebuild needed)
3. Container Plan (rebuild -- subsumes Profiler Change 10)
4. Profiler Plan Phase 3 (cmdstanr backend -- needs working container from step 3)
5. Cleanup Plan

Group ALL container-requiring changes into a single rebuild: pixi migration + missing packages + CmdStan compilation + env name fix. A single rebuild avoids the ~15-20 minute build cycle being repeated.

### 7. Verdict

**APPROVE with verification prerequisites.** The pixi migration is sound and the def rewrite is clean. Before implementation: (1) Verify all 14+ packages resolve from conda-forge + bioconda channels, (2) Ensure `.gitignore` does not exclude `pixi.lock`, (3) Confirm build machine has internet access for CmdStan download, (4) Keep `foodnet.yml` maintained for nf-core conda profile fallback, (5) Test `R_LIBS` path immediately after first container build.
