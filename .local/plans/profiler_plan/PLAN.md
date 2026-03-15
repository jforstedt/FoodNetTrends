# HPC Resource Management Improvement Plan

**Date:** 2026-03-14
**Scope:** Resource allocation, h_vmem fix, error handling, cmdstanr backend
**Authority:** Based on `definitive_hpc_review.md` (verified against execution logs), with corrections to findings from reviews 1, 2, and arbitration.

**Key premise:** The dynamic resource allocation system WORKS. Execution logs prove CPUs scale per-pathogen (4/8/12/16). Three prior reviewers incorrectly called it dead code. This plan does NOT propose fixing the dynamic allocation mechanism itself.

---

## Change Order Summary

| # | Change | File(s) | Priority | Affects Results? |
|---|--------|---------|----------|-----------------|
| 1 | Fix h_vmem to track actual memory | `nextflow.config` | HIGH | No |
| 2 | Add exit code 140 to retry list | `nextflow.config`, `trendy.nf` | HIGH | No |
| 3 | Remove exit code 139 from retry list | `nextflow.config`, `trendy.nf` | MEDIUM | No |
| 4 | CPU allocation: use chain count | `conf/modules.config` | MEDIUM | No |
| 5 | Add `stan_backend` parameter | `nextflow.config` | Enhancement | No* |
| 6 | Plumb `--backend` through trendy.nf | `modules/local/trendy.nf` | Enhancement | No* |
| 7 | Accept `--backend` in trendy.R | `bin/trendy.R` | Enhancement | No* |
| 8 | Use backend parameter in functions.R | `bin/functions.R` | Enhancement | No* |
| 9 | Expose backend in run_workflow.sh | `run_workflow.sh` | Enhancement | No* |
| 10 | Container: verify CmdStan binary | `foodnet.def` | Enhancement | No |

*Both backends produce statistically equivalent posteriors. See Section 10.5.

---

## Change 1: Fix h_vmem to Track Actual Memory Allocation (HIGH)

### Why

The execution trace shows peak vmem of 85.9-86.0 GB for most pathogens, exceeding the hardcoded `h_vmem=80G` limit (`nextflow.config` line 146). Jobs completed only because SGE on Rosalind either uses soft limits or missed the peak in a polling interval. This is a latent failure: a slightly larger dataset, more chains, or stricter SGE enforcement will trigger SIGKILL (exit 137).

**Execution evidence:**
- CAMPYLOBACTER: peak vmem 86.0 GB (exceeds 80G)
- SALMONELLA: peak vmem 86.0 GB (exceeds 80G)
- SHIGELLA: peak vmem 85.9 GB (exceeds 80G)
- All 6 pathogens with 8+ CPUs hit 85.9-86.0 GB vmem

### What to Change

**File:** `nextflow.config`, line 146

**Old code (line 146):**
```groovy
        clusterOptions = '-l h_vmem=80G'
```

**New code:**
```groovy
        clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 16}G" }
```

**Also fix the process-level default at line 137:**

**Old code (line 137):**
```groovy
    clusterOptions = '-l h_vmem=8G'
```

**New code:**
```groovy
    clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 4}G" }
```

### Rationale for +16 GB headroom on TRENDY

- Peak RSS was 25.9 GB, peak vmem was 86.0 GB for 96 GB allocated memory
- The gap between allocated memory and peak vmem is ~10 GB (96 - 86 = 10)
- +16 GB provides a comfortable margin above the actual vmem usage
- This follows the same pattern as `cdc-dev.config` line 150 (which uses +20 GB)

### Affects Result Accuracy?

No. h_vmem is a scheduler enforcement limit. It either allows the job to complete (producing correct results) or kills it. There is no middle ground where incorrect results are produced.

### Conflict with Model Fixes?

None. Model fixes modify `functions.R` and `trendy.R`. This change is purely in `nextflow.config`.

### Test Strategy

1. Run a single-pathogen test (e.g., CAMPYLOBACTER with 6 chains) and verify:
   - `qstat -j <jobid>` shows h_vmem = (task.memory + 16) GB
   - Job completes without SIGKILL
2. Verify the closure syntax by checking `nextflow.log` for the clusterOptions value
3. Test with different chain counts (2, 4, 6) to confirm h_vmem scales

---

## Change 2: Add Exit Code 140 to Retry List (HIGH)

### Why

Exit code 140 corresponds to SIGALRM, which SGE sends when wallclock time exceeds the `-l h_rt` limit. This is a recoverable failure -- retrying with more time (via `task.attempt` multiplier) can succeed. The `cdc-dev.config` rosalind profile (line 153) already includes 140, but the TRENDY-specific error handling in `nextflow.config` and `trendy.nf` does not.

### What to Change

**File 1:** `nextflow.config`, line 144

**Old code:**
```groovy
        errorStrategy = { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
```

**New code:**
```groovy
        errorStrategy = { task.exitStatus in [143,137,104,134,140] ? 'retry' : 'finish' }
```

Note: this also removes 139 (see Change 3); if implementing separately, first add 140 to the list.

**File 2:** `modules/local/trendy.nf`, line 32

**Old code:**
```groovy
    errorStrategy { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
```

**New code:**
```groovy
    errorStrategy { task.exitStatus in [143,137,104,134,140] ? 'retry' : 'finish' }
```

### Affects Result Accuracy?

No. This only determines whether a timed-out job is retried or reported as failed. Stan either completes correctly or fails.

### Conflict with Model Fixes?

None.

### Test Strategy

1. Submit a TRENDY job with an artificially low time limit (e.g., 1 minute) and verify it retries
2. Confirm in `nextflow.log` that exit code 140 triggers retry, not finish

---

## Change 3: Remove Exit Code 139 from Retry List (MEDIUM)

### Why

Exit code 139 is SIGSEGV (segmentation fault). Segfaults indicate memory corruption or code bugs, not resource insufficiency. Retrying with more resources will not fix the underlying issue and wastes cluster time (up to 3 retries x hours of queue wait).

### What to Change

Combined with Change 2 above. The exit code lists in both files change from `[143,137,104,134,139]` to `[143,137,104,134,140]`.

### Affects Result Accuracy?

No. A segfaulting job produces no output. Removing the retry just makes the failure surface faster.

### Conflict with Model Fixes?

None.

### Test Strategy

If a SIGSEGV occurs during testing, verify the pipeline reports `finish` rather than retrying.

---

## Change 4: CPU Allocation Based on Chain Count (MEDIUM)

### Why

The execution trace proves Stan uses at most ~5 cores for a 6-chain run (peak %CPU = 476%, i.e., ~4.8 cores). Row-count-based CPU tiers cause two problems:

1. **Over-provisioning:** SALMONELLA/CAMPYLOBACTER/SHIGELLA get 16 CPUs but only use ~5, wasting 10-11 SMP slots per job.
2. **Under-provisioning:** CYCLOSPORA/VIBRIO/LISTERIA get 4 CPUs for 6 chains, forcing 2 chains to serialize. CYCLOSPORA took 27 minutes (vs 11 min for CRYPTOSPORIDIUM with 12 CPUs and 5x more data).

**Execution evidence:**
```
CAMPYLOBACTER:   16 CPUs allocated, 476% CPU used (~4.8 cores), 14m 24s
CYCLOSPORA:       4 CPUs allocated, 245% CPU used (~2.5 cores), 27m 12s
CRYPTOSPORIDIUM: 12 CPUs allocated, 411% CPU used (~4.1 cores), 11m 15s
```

### What to Change

**File:** `conf/modules.config`, lines 29-43

**Old code:**
```groovy
        cpus = {
            def rows = task.ext.dataMetrics?.rows ?: 10000
            def complexity = task.ext.dataMetrics?.complexity ?: 100000

            // CPU allocation based on row count
            if (rows > 50000) {
                return check_max(16 * task.attempt, 'cpus')
            } else if (rows > 20000) {
                return check_max(12 * task.attempt, 'cpus')
            } else if (rows > 10000) {
                return check_max(8 * task.attempt, 'cpus')
            } else {
                return check_max(4 * task.attempt, 'cpus')
            }
        }
```

**New code:**
```groovy
        cpus = {
            // Allocate one CPU per chain -- Stan runs one chain per core.
            // On retry, do NOT multiply CPUs (more cores won't help a failing model).
            check_max(params.chains ?: 2, 'cpus')
        }
```

**Also update the static fallback in `nextflow.config` line 141:**

**Old code:**
```groovy
        cpus = { check_max(16 * task.attempt, 'cpus') }
```

**New code:**
```groovy
        cpus = { check_max(params.chains ?: 2, 'cpus') }
```

### Design Decision: Do NOT scale CPUs on retry

Stan cannot use more cores than chains. On retry, the `task.attempt` multiplier on CPUs serves no purpose. Only memory and time should scale with `task.attempt`.

### Affects Result Accuracy?

No. Stan uses `cores` to run chains in parallel. Giving it exactly `params.chains` cores is optimal. Results are identical regardless of CPU count (parallelism only affects wall-clock time).

### Conflict with Model Fixes?

None. Model fixes do not change `params.chains` handling.

### Test Strategy

1. Run with `--chains 6` and verify each TRENDY job gets 6 CPUs in `nextflow.log`
2. Run with `--chains 2` and verify each job gets 2 CPUs
3. Compare runtimes: small pathogens (CYCLOSPORA, VIBRIO) should drop from ~27 min to ~11-15 min with proper CPU allocation
4. Confirm peak CPU in the execution trace matches chain count

---

## Change 5: Add `stan_backend` Parameter to nextflow.config (Enhancement)

### Why

cmdstanr (`r-cmdstanr=0.8.1`) is already installed in the conda environment (`foodnet.yml` line 22). Adding a parameter allows users to select it without code changes. cmdstanr:
- Compiles models faster with more reliable caching
- Enables a future path to within-chain threading (`reduce_sum`)
- Is generally more stable with newer Stan versions

### What to Change

**File:** `nextflow.config`, after line 41 (in the `params` block, after `seed`)

**Insert:**
```groovy
    stan_backend     = "rstan"        // Stan backend: "rstan" or "cmdstanr"
```

**Also add to the `production` profile (after line 106, inside the `production` block):**
No change needed -- the production profile inherits the default `stan_backend` parameter. Users can override with `--stan_backend cmdstanr` on the command line.

### Affects Result Accuracy?

No. Both backends compile the same Stan model, run the same NUTS sampler, and produce statistically equivalent posteriors. Given the same seed, summary statistics (median incidence rates, HDI bounds, IRRs) will be indistinguishable within Monte Carlo error. See definitive review Part 3, Section 3.3.

### Conflict with Model Fixes?

No conflict. The model plan modifies `PROPOSED_BM()` function signature and the `brm()` call in `functions.R`. The `backend` parameter is an additional argument to the same `brm()` call. Both changes touch the same function but different parameters. Implementation order does not matter as long as the final `PROPOSED_BM()` signature includes all new parameters.

Specifically, if the model plan adds parameters like `prior` or `formula` changes, those are orthogonal to the `backend` parameter. The `brm()` call at `functions.R` line 395-411 can accept both sets of changes simultaneously.

### Test Strategy

1. Run with `--stan_backend rstan` (default) -- verify identical behavior to current
2. Run with `--stan_backend cmdstanr` -- verify model fits and produces output
3. Compare output CSVs from both backends for a single pathogen -- summary statistics should agree within Monte Carlo error

---

## Change 6: Plumb `--backend` Through trendy.nf (Enhancement)

### Why

The `stan_backend` parameter from `nextflow.config` must be passed to the R script.

### What to Change

**File:** `modules/local/trendy.nf`, line 88

**Old code (lines 87-90):**
```bash
      --seed ${params.seed} \
      ${catchmentConfigArg} \
      --debug FALSE
```

**New code:**
```bash
      --seed ${params.seed} \
      --backend ${params.stan_backend} \
      ${catchmentConfigArg} \
      --debug FALSE
```

Insert `--backend ${params.stan_backend} \` between the `--seed` line and the `${catchmentConfigArg}` line.

### Affects Result Accuracy?

No. This is pure plumbing.

### Conflict with Model Fixes?

Minimal. Both this change and model fixes add arguments to the Rscript call in `trendy.nf`. As long as new arguments are appended before the `${catchmentConfigArg}` line, there is no ordering conflict. If the model plan also adds arguments here, simply ensure both sets are present.

### Test Strategy

1. Run with `--stan_backend rstan` and verify `trendy.nf` passes `--backend rstan` to Rscript
2. Check the `.command.sh` file in the Nextflow work directory to confirm the argument appears

---

## Change 7: Accept `--backend` in trendy.R (Enhancement)

### Why

The R script must parse the new command-line argument.

### What to Change

**File:** `bin/trendy.R`

**Location 1:** After line 113 (after the `--seed` argument definition), add:

```r
parser$add_argument("--backend", type="character", default="rstan",
                    help="Stan backend: rstan or cmdstanr (default: rstan)")
```

**Location 2:** After line 171 (after `seed <- opts$seed`), add:

```r
  backend <- opts$backend
```

**Location 3:** Around line 573 (the `PROPOSED_BM()` call), change:

**Old code (lines 573-581):**
```r
    proposed <- PROPOSED_BM(
      current_data,
      cores = modelcores,
      chains = chains,
      iterations = iterations,
      adapt_delta = adapt_delta,
      max_treedepth = max_treedepth,
      seed = seed
    )
```

**New code:**
```r
    proposed <- PROPOSED_BM(
      current_data,
      cores = modelcores,
      chains = chains,
      iterations = iterations,
      adapt_delta = adapt_delta,
      max_treedepth = max_treedepth,
      seed = seed,
      backend = backend
    )
```

### Affects Result Accuracy?

No. This is pure plumbing.

### Conflict with Model Fixes?

**This is the key coordination point.** The model plan also modifies `trendy.R` around the `PROPOSED_BM()` call site (line ~573). Both changes add a new argument. Resolution:

- If model plan adds parameters like `formula`, `prior`, or `family` to `PROPOSED_BM()`, the `backend` parameter is simply one more argument in the same call.
- The argument parser section (line ~113) has no overlap -- the model plan adds different arguments.
- The variable initialization section (line ~171) has no overlap.
- **Implementation order:** Either can go first. The final `PROPOSED_BM()` call must include ALL new parameters from both plans.

### Test Strategy

1. Verify `trendy.R --help` shows the new `--backend` argument
2. Verify `trendy.R --backend cmdstanr` does not error on argument parsing

---

## Change 8: Use `backend` Parameter in functions.R (Enhancement)

### Why

The hardcoded `backend = "rstan"` at `functions.R` line 410 must become parameterized.

### What to Change

**File:** `bin/functions.R`

**Location 1:** Line 348 -- function signature

**Old code:**
```r
PROPOSED_BM <- function(data, cores = 16, chains = 2, iterations = 500,
                        adapt_delta = 0.95, max_treedepth = 10, seed = 123) {
```

**New code:**
```r
PROPOSED_BM <- function(data, cores = 16, chains = 2, iterations = 500,
                        adapt_delta = 0.95, max_treedepth = 10, seed = 123,
                        backend = "rstan") {
```

**Location 2:** Line 410 -- the `brm()` call

**Old code:**
```r
      backend = "rstan"  # Explicitly use rstan backend for stability
```

**New code:**
```r
      backend = backend
```

### Affects Result Accuracy?

No, when using `backend = "rstan"` (the default, identical to current behavior). When using `backend = "cmdstanr"`, results are statistically equivalent -- same NUTS sampler, same Stan model, same posterior. Summary statistics agree within Monte Carlo error. See definitive review Part 3, Section 3.3.

### Conflict with Model Fixes?

**This is the primary coordination point with the model plan.** The model plan likely modifies `PROPOSED_BM()` to:
- Change the formula (e.g., adding `t2()` instead of `s()`)
- Add priors
- Adjust the `brm()` call

Both plans modify the same function signature (line 348) and the same `brm()` call (lines 395-411).

**Resolution strategy:**
1. The function signature change is additive -- append `backend = "rstan"` to whatever the model plan's signature becomes.
2. The `brm()` call change is a single-line substitution (`backend = "rstan"` becomes `backend = backend`). This is orthogonal to formula/prior changes. Both can be applied independently.
3. **Recommended implementation order:** Apply model fixes first (since they are higher priority and more complex), then apply the `backend` parameter change. The backend change is two lines and trivially adapts to whatever the model plan does to the function.

### Test Strategy

1. Run with default `backend = "rstan"` -- verify output is identical to current pipeline
2. Run with `backend = "cmdstanr"`:
   a. Verify `cmdstanr::cmdstan_path()` returns a valid path
   b. Verify model compiles and fits
   c. Compare posterior summaries to rstan output for a single pathogen
3. Run with an invalid backend value -- verify `brm()` produces a clear error message

---

## Change 9: Expose Backend in run_workflow.sh (Enhancement)

### Why

Users should be able to select the Stan backend from the interactive menu.

### What to Change

**File:** `run_workflow.sh`

**Location 1:** After the MCMC parameters section (around line 917, after the `max_treedepth` input in the custom block), add a backend selection:

```bash
    # Stan backend
    echo ""
    echo -e "${BLUE}Stan Backend:${NC}"
    echo "1) rstan (default, well-tested)"
    echo "2) cmdstanr (faster compilation, newer Stan versions)"
    echo ""
    read -p "Select backend [1]: " backend_choice
    backend_choice=${backend_choice:-1}

    case "$backend_choice" in
        1) stan_backend="rstan" ;;
        2) stan_backend="cmdstanr" ;;
        *)
            echo -e "${YELLOW}Invalid choice. Using rstan.${NC}"
            stan_backend="rstan"
            ;;
    esac
```

**Location 2:** For non-custom modes (test, publication, max), set the default:

After line 806 (before the `if [[ "$flag" == "test" ]]` block), add:
```bash
stan_backend="rstan"  # Default backend for all presets
```

**Location 3:** In the Nextflow command construction (lines 1208-1219), add the backend parameter:

After line 1216 (`--seed 123 \`):
```bash
      --stan_backend \"$stan_backend\" \
```

Also add the same line to the resume command construction (after line 1232).

### Affects Result Accuracy?

No.

### Conflict with Model Fixes?

None. The model plan does not modify `run_workflow.sh`.

### Test Strategy

1. Run `run_workflow.sh` in custom mode, select cmdstanr, verify the Nextflow command includes `--stan_backend cmdstanr`
2. Run in publication mode, verify default `--stan_backend rstan` is passed
3. Dry-run the constructed command and check parameter parsing

---

## Change 10: Container -- Verify CmdStan Binary (Enhancement)

### Why

`r-cmdstanr` (the R interface) is installed in the conda environment, but it requires a CmdStan binary (the C++ toolchain and Stan library) to function. The conda package may or may not bundle CmdStan.

### What to Verify

Run inside the Singularity container:
```bash
singularity exec foodnet.sif Rscript -e "cmdstanr::cmdstan_path()"
```

**If it returns a valid path:** No change needed.

**If it errors:** Add to `foodnet.def` in the `%post` section:

```
%post
    # After conda env creation:
    /opt/conda/envs/FootNetTreands_R/bin/Rscript -e "cmdstanr::install_cmdstan(cores = 4)"
```

### What to Change (conditional)

**File:** `foodnet.def`, in the `%post` section

This is only needed if `cmdstanr::cmdstan_path()` fails inside the container. The `install_cmdstan()` call downloads and compiles CmdStan (~5 min), adding ~200 MB to the container.

### Affects Result Accuracy?

No. This only enables cmdstanr to function.

### Conflict with Model Fixes?

None. Container changes are independent of R code changes.

### Test Strategy

1. Build the container with the addition (if needed)
2. Verify `cmdstanr::cmdstan_path()` returns a valid path
3. Verify `cmdstanr::cmdstan_version()` returns a version string
4. Run a simple brms model with `backend = "cmdstanr"` inside the container

---

## Implementation Order

The changes should be implemented in this order to minimize risk and maximize testability:

### Phase 1: Safety fixes (no behavior change for successful runs)

1. **Change 1** (h_vmem) -- eliminates latent failure risk
2. **Changes 2+3** (exit codes) -- improves retry behavior

These can be implemented and tested independently. They do not touch R code and cannot affect results.

### Phase 2: Efficiency fix

3. **Change 4** (CPU = chains) -- reduces SMP waste, speeds up small pathogens

This changes resource allocation but not results. Test by comparing outputs before/after.

### Phase 3: cmdstanr backend (all 5 changes together)

4. **Change 10** (container verification) -- do this first to confirm cmdstanr works
5. **Changes 5-9** (parameter plumbing) -- implement as a single commit

These must be deployed together. The parameter must flow from `nextflow.config` through `trendy.nf` to `trendy.R` to `functions.R` for the feature to work. Partial deployment will cause argument-not-found errors.

**Important:** If the model plan is also being implemented, coordinate on `functions.R` and `trendy.R`. The recommended approach is:
1. Apply model plan changes first (higher priority, more complex)
2. Then apply cmdstanr changes (additive, simpler)
3. Test both independently and together

---

## Changes NOT in This Plan (and Why)

### "Fix" the dynamic resource allocation mechanism

The definitive review proved it works. Execution logs show CPUs scaling per-pathogen (4/8/12/16). Peak CPU of 92 across 9 jobs confirms mixed allocation (vs. 144 if all got 16). No fix needed.

### Replace complexity score with a "better" MCMC predictor

The complexity score drives time allocation, which is reasonable (larger datasets do take longer per iteration). The real problem was CPU allocation using row count instead of chain count, which Change 4 addresses.

### Recalibrate memory thresholds

All 9 pathogens exceed the 1M complexity threshold, so they all get 96 GB. Peak RSS was only 26 GB, and peak vmem was 86 GB. The current 96 GB allocation is over-provisioned but safe. Over-provisioning memory is far preferable to under-provisioning for a production pipeline. Change 1 (h_vmem fix) addresses the actual risk.

### Consolidate config definitions

The four resource definition locations (base.config, nextflow.config, modules.config, trendy.nf) follow nf-core conventions. The definitive review confirms the layering works correctly. Refactoring is pure tech debt with no execution impact.

### Change submit rate limit

With 9 jobs, all are submitted within ~48 seconds. The 10/min limit causes no meaningful delay.

### Geometric retry scaling

This run had zero retries. The theoretical benefit of geometric vs. linear scaling is not worth the testing overhead.

### Add queue routing to nextflow.config

The `cdc-dev.config` rosalind profile already handles queue routing. The current run uses the singularity profile and works fine with the default queue.

### Fix syntax error in cdc-dev.config line 150

The Rosalind profile's `clusterOptions` expression has mismatched parentheses, but TRENDY's `clusterOptions` from `nextflow.config` overrides it. The bug is masked for the primary use case. If the rosalind profile is used directly (without the TRENDY-specific override), it should be fixed separately.

---

## Verification Checklist

After implementing all changes, verify:

- [ ] `nextflow.log` shows h_vmem values that are (task.memory + 16) GB for TRENDY jobs
- [ ] `nextflow.log` shows each TRENDY job gets `params.chains` CPUs (not row-based tiers)
- [ ] Exit code 140 triggers retry (test with artificially short time limit)
- [ ] Exit code 139 does NOT trigger retry
- [ ] `--stan_backend rstan` produces identical output to current pipeline
- [ ] `--stan_backend cmdstanr` produces output with summary statistics matching rstan within Monte Carlo error
- [ ] Peak vmem stays below h_vmem for all pathogens
- [ ] CYCLOSPORA runtime drops from ~27 min to ~11-15 min (with proper CPU allocation)
- [ ] All 9 pathogens complete successfully with no retries
- [ ] `run_workflow.sh` correctly constructs Nextflow command with `--stan_backend` parameter

---

## Architect Review

**Reviewer:** Senior Nextflow DSL2 Bioinformatics Architect
**Date:** 2026-03-14
**Scope:** HPC resource management plan validation, cross-plan conflict analysis, DSL2 integration, best practices

---

### 1. Cross-Plan Conflict Analysis

**nextflow.config -- shared with Container Plan:** Profiler Plan Changes 1, 2, 3, 5 modify `nextflow.config` process block (lines 137-146) and params block (~line 41). Container Plan Step 3 modifies the `env` block (lines 117-122). Non-overlapping config sections. Merge in either order.

**trendy.nf -- coordination point with Model Plan:** Profiler Plan Change 6 adds `--backend ${params.stan_backend}` to the Rscript call (line 88 area). The Model Plan needs a `_convergence_diagnostics.csv` output declaration added to `trendy.nf`. These are in different sections (script block vs. output block). No conflict. Implement together for a single `trendy.nf` commit.

**functions.R -- shared with Model Plan (Steps 5, 8):** Profiler Change 8 modifies `PROPOSED_BM()` signature (line 348) and `backend` line (line 410). Model Step 8 modifies the error handler (lines 412-414). Model Step 5 adds `CHECK_CONVERGENCE()` after line 417. No overlapping lines. Apply Model Plan changes first (higher priority), then Profiler backend changes.

**trendy.R -- shared with Model Plan (Steps 2, 5, 9):** Profiler Change 7 adds `--backend` argument parsing (~line 113), variable initialization (~line 171), and `backend = backend` to the `PROPOSED_BM()` call (~line 573). Model Plan changes lines 271, 467-480, and inserts after 593. No overlapping lines.

**foodnet.def -- shared with Container Plan:** Profiler Change 10 conditionally adds `cmdstanr::install_cmdstan()` to the def. The Container Plan rewrites the def entirely (pixi-based) and already includes `pixi run Rscript -e "cmdstanr::install_cmdstan(cores = 4, quiet = TRUE)"`. **The Container Plan subsumes Profiler Change 10.** If the Container Plan is implemented, Change 10 becomes unnecessary.

**run_workflow.sh -- not shared.** Only this plan touches it.

### 2. DSL2 Integration Validation

**Change 1 (h_vmem closure):** The syntax `clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 16}G" }` is correct Nextflow DSL2. The closure evaluates per-task, so `task.memory` reflects the dynamically allocated memory from `modules.config`. `MemoryUnit.toGiga()` returns a `long`; string interpolation with arithmetic produces correct output. Verified valid.

**Change 4 (CPU = chains):** The syntax `check_max(params.chains ?: 2, 'cpus')` is valid. The `?:` (Elvis operator) correctly falls back to 2 if `params.chains` is null. **Important:** This change must be applied in BOTH `nextflow.config` line 141 AND `modules.config` lines 29-43. The `modules.config` `withName: 'TRENDY'` block takes precedence because `modules.config` is loaded AFTER `nextflow.config` (line 186: `includeConfig 'conf/modules.config'`). The plan correctly identifies both locations.

**Config precedence chain (verified):** `base.config` -> `cdc-dev.config` -> `nextflow.config` process block -> `modules.config`. The `modules.config` TRENDY block is the final authority for CPU/memory/time. The `nextflow.config` TRENDY block provides errorStrategy, maxRetries, and clusterOptions that modules.config does not override. This layering is correct and follows nf-core conventions.

**Resume caching:** Changes 1-4 modify resource directives only. Nextflow does NOT include resource directives (cpus, memory, time, clusterOptions) in the task hash. These changes do NOT affect `-resume` caching -- correct behavior.

Changes 5-9 (backend parameter) add `--backend ${params.stan_backend}` to the script block. This DOES change the script block hash, which WILL invalidate `-resume` caches. Correct -- a different backend should not reuse cached results.

### 3. nf-core Compliance

- Changes 1-4 follow nf-core patterns for dynamic resource allocation.
- Change 5 adds `params.stan_backend` -- this should be added to `nextflow_schema.json` for full nf-core compliance. Coordinate with Cleanup Plan (which identifies `nextflow_schema.json` as Priority 3).
- The duplicate `withName: 'TRENDY'` blocks in both `nextflow.config` and `modules.config` is technically an nf-core anti-pattern (prefer one location), but the definitive review confirmed this layering works correctly. Refactoring is tech debt, not a bug.

### 4. Best Practices Assessment (March 2026)

**cmdstanr backend (Changes 5-9):** The optional backend approach is well-designed. cmdstanr 0.8.x with CmdStan 2.35+ is mature and reliable as of 2026. Design correctly makes rstan the default and cmdstanr opt-in. As of Nextflow 25.x, the `nf-schema` plugin can enforce enum constraints on parameters. Consider adding `stan_backend` to the schema with `"enum": ["rstan", "cmdstanr"]` to prevent invalid values at launch time rather than at brm() call time.

**CPU = chains (Change 4):** Correct approach for Stan/brms. Stan runs one chain per core. Execution evidence confirms small pathogens were CPU-starved (CYCLOSPORA: 4 CPUs, 27 min vs. CRYPTOSPORIDIUM: 12 CPUs, 11 min with 5x more data). With `params.chains` CPUs, all chains run in parallel. **One edge case:** The production profile sets `params.chains = 4` but the default is 2. If someone runs with `--chains 1`, they get 1 CPU. brms compilation is single-threaded so this works, just slowly. Acceptable.

**h_vmem fix (Change 1):** The +16 GB headroom is reasonable. Observed: 96 GB allocated, 86 GB peak vmem. Setting h_vmem to `task.memory + 16` gives ~26 GB above peak vmem. The `cdc-dev.config` rosalind profile uses +20 GB -- using +16 for TRENDY and +4 for defaults is sensible.

**Exit codes (Changes 2-3):** Adding 140 (SIGALRM/wallclock) and removing 139 (SIGSEGV) are both correct. Retrying segfaults wastes cluster time. The rosalind profile already includes 140.

### 5. Issues and Concerns

**Issue 1: Duplicate errorStrategy definitions.** The `errorStrategy` for TRENDY is defined in THREE places: `base.config` line 18 (label-based, range 130-145+104), `nextflow.config` line 144 (withName, narrow list), and `trendy.nf` line 32 (process-level directive). Config `withName` blocks override process-level directives in the `.nf` file, so `trendy.nf` line 32 is effectively dead code when configs are loaded. The plan correctly changes both locations, but the `trendy.nf` change is redundant in practice. Still good to keep in sync.

**Issue 2: `base.config` errorStrategy not updated.** `base.config` line 18 uses range `(130..145) + 104`, which already includes both 139 and 140. If a non-TRENDY process gets SIGSEGV, `base.config` will still retry it. Outside plan scope but worth tracking.

**Issue 3: Change 10 is conditional but should be a hard prerequisite.** If `cmdstanr::cmdstan_path()` fails inside the container, the `--stan_backend cmdstanr` parameter accepts but model compilation fails with an unhelpful error. Make Change 10 (or its Container Plan equivalent) a hard prerequisite for Changes 5-9.

**Issue 4: `cdc-dev.config` line 150 syntax error.** The rosalind profile's `clusterOptions` expression has mismatched parentheses: `"-l h_vmem=${(check_max((task.memory.toGiga())+20), 'memory').toString()..."` -- the outer parens create a Groovy list expression, not a function call. This is masked for TRENDY (which uses its own clusterOptions) but would break for other processes using the rosalind profile directly. Outside plan scope.

### 6. Implementation Sequencing (cross-plan)

This plan should be implemented **SECOND**, after the Model Plan:
1. Model Plan (statistical fixes -- highest priority)
2. Profiler Plan Phase 1-2 (Changes 1-3: h_vmem, exit codes -- config only, no result changes)
3. Profiler Plan Change 4 (CPU = chains -- config only)
4. Container Plan (rebuild -- subsumes Profiler Change 10)
5. Profiler Plan Phase 3 (Changes 5-9: cmdstanr backend -- requires working container)
6. Cleanup Plan

### 7. Verdict

**APPROVE.** The plan is well-reasoned and grounded in execution evidence. Changes 1-4 are straightforward safety and efficiency fixes. Changes 5-9 are a clean enhancement. Three items to address: (1) Make Change 10 a hard prerequisite for Changes 5-9, (2) Add `stan_backend` to `nextflow_schema.json` (coordinate with Cleanup Plan), (3) Add the `_convergence_diagnostics.csv` output declaration to `trendy.nf` while modifying it for the backend parameter (coordinate with Model Plan).
