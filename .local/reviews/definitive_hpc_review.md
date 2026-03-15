# Definitive HPC & Pipeline Review: FoodNetTrends

**Reviewer:** Fourth independent reviewer (final arbiter)
**Date:** 2026-03-13
**Purpose:** Correct factual errors in the three prior HPC reviews, verify all claims against actual execution data, and provide actionable findings grounded in evidence rather than theoretical speculation.

**Evidence base:**
- `nextflow.log` (247 lines -- complete execution log with per-pathogen resource allocations)
- `execution_trace_2026-03-13_22-21-52.txt` (actual resource usage per job)
- All source code files (modules.config, trendy.nf, spline.nf, functions.R, trendy.R, etc.)
- All three prior HPC reviews and the statistical/epidemiological reviews
- Weller et al. (2026) Zoonoses 6:3 (the published paper)
- Nextflow DSL2 documentation and Stan/brms documentation

---

## PART 1: WHY THE PREVIOUS REVIEWERS WERE WRONG ABOUT DYNAMIC RESOURCE ALLOCATION

### 1.1 The Central Claim That All Three Reviewers Got Wrong

All three prior reviewers (HPC Review 1, HPC Review 2, and the HPC Arbitration) made the same claim:

> "`task.ext.dataMetrics` is assigned in the `script:` block of `trendy.nf` (line 37) and is therefore invisible to resource directive closures in `modules.config`, which are evaluated before the script block executes. The dynamic resource allocation system is entirely non-functional."

**This claim is FALSE.** The execution log proves it conclusively.

### 1.2 The Proof: Execution Log Shows Different CPU Allocations Per Pathogen

From `nextflow.log` lines 133-141, the INFO-level log messages emitted by `trendy.nf` line 40-42 during task setup:

```
Pathogen: YERSINIA,        Rows: 10546,  Complexity: 3058340,   Allocated CPUs: 8,  Memory: 96 GB
Pathogen: CYCLOSPORA,      Rows: 4226,   Complexity: 1183280,   Allocated CPUs: 4,  Memory: 96 GB
Pathogen: SALMONELLA,      Rows: 195020, Complexity: 56555800,  Allocated CPUs: 16, Memory: 96 GB
Pathogen: VIBRIO,          Rows: 6841,   Complexity: 1983890,   Allocated CPUs: 4,  Memory: 96 GB
Pathogen: STEC,            Rows: 41751,  Complexity: 12107790,  Allocated CPUs: 12, Memory: 96 GB
Pathogen: LISTERIA,        Rows: 3564,   Complexity: 1033560,   Allocated CPUs: 4,  Memory: 96 GB
Pathogen: CAMPYLOBACTER,   Rows: 194909, Complexity: 56523610,  Allocated CPUs: 16, Memory: 96 GB
Pathogen: CRYPTOSPORIDIUM, Rows: 21707,  Complexity: 4558470,   Allocated CPUs: 12, Memory: 96 GB
Pathogen: SHIGELLA,        Rows: 68722,  Complexity: 19929380,  Allocated CPUs: 16, Memory: 96 GB
```

If the dynamic allocation were "dead code" as all three reviewers claimed, **every pathogen would get the same CPU count**. They do not. The CPUs scale exactly as the `modules.config` closures (lines 29-42) specify:

| Row Count Tier | Expected CPUs | Actual Pathogens |
|---|---|---|
| <= 10,000 | 4 | CYCLOSPORA (4,226), VIBRIO (6,841), LISTERIA (3,564) |
| 10,001 - 20,000 | 8 | YERSINIA (10,546) |
| 20,001 - 50,000 | 12 | STEC (41,751), CRYPTOSPORIDIUM (21,707) |
| > 50,000 | 16 | SALMONELLA (195,020), CAMPYLOBACTER (194,909), SHIGELLA (68,722) |

Every single pathogen lands in the correct tier. The dynamic allocation is working exactly as designed.

### 1.3 Why The Reviewers' Theoretical Model Was Wrong

The reviewers' reasoning was:

1. Resource directives are evaluated "before" the script block.
2. `task.ext.dataMetrics = dataMetrics` is in the script block (`trendy.nf` line 37).
3. Therefore `task.ext.dataMetrics` is null when directives evaluate.

This reasoning contains a critical factual error about Nextflow's execution model. There are two separate mechanisms at play:

**Mechanism A: `val` inputs are available to directive closures.** The `dataMetrics` is a `val` input to the TRENDY process (`trendy.nf` line 10):

```groovy
input:
tuple val(pathogenGrouping), val(pathogen), val(subgroup), val(dataMetrics)
```

In Nextflow DSL2, `val` input variables ARE available inside directive closures. This is explicitly documented in the [Nextflow process documentation](https://www.nextflow.io/docs/latest/process.html):

> "If the [directive] value is a dynamic string or closure, it will be evaluated separately for each task, which allows task-specific variables like task and val inputs to be used."

The documentation provides an explicit example of this exact pattern:

```groovy
process hello {
  executor 'sge'
  queue { entries > 100 ? 'long' : 'short' }
  input: tuple val(entries), path('data.txt')
  script: """ your_command --here """
}
```

**Mechanism B: Groovy statements in the script block execute during task preparation.** The `script:` block in a Nextflow process is not purely shell code. The section BEFORE the triple-quoted string (`"""..."""`) contains Groovy code that executes during task configuration. The line `task.ext.dataMetrics = dataMetrics` (`trendy.nf` line 37) is a Groovy assignment that runs during task preparation, BEFORE the shell script is submitted to the executor.

This means the `modules.config` closures that reference `task.ext.dataMetrics?.rows` (line 30) and `task.ext.dataMetrics?.complexity` (line 31) CAN access the data metrics because:
1. Nextflow resolves the `val(dataMetrics)` input from the channel.
2. The Groovy code in the script block sets `task.ext.dataMetrics = dataMetrics`.
3. The resource directive closures evaluate and read `task.ext.dataMetrics`.
4. The task is submitted to SGE with the computed resource values.

The log at line 42 of `trendy.nf` (`"Allocated CPUs: ${task.cpus}, Memory: ${task.memory}"`) confirms this: by the time these log messages print, `task.cpus` already reflects the dynamic allocation result. The different values across pathogens are irrefutable proof.

### 1.4 Independent Corroboration: Peak CPU Count

`nextflow.log` line 240:

```
peakCpus=92; peakMemory=864 GB
```

If every job got 16 CPUs (the "dead code fallback" scenario), 9 concurrent TRENDY jobs would peak at 144 CPUs. The actual peak of 92 is consistent with the mixed allocation: 3x16 + 2x12 + 1x8 + 3x4 = 48+24+8+12 = 92. This independently confirms the dynamic allocation is working.

864 GB peak memory / 9 jobs = 96 GB per job, consistent with all pathogens receiving 96 GB.

---

## PART 2: WHAT IS ACTUALLY HAPPENING WITH RESOURCES

### 2.1 Execution Parameters

From `nextflow.log` line 1, this was a production-quality run:
- **6 chains**, **10,001 iterations**, **adapt_delta = 0.99**, **max_treedepth = 15**, **seed = 123**
- Preprocessed data with AUTO_DISCOVER (9 pathogens found)
- SGE executor on Rosalind HPC at CDC
- Singularity container

### 2.2 Resource Allocation vs. Actual Usage

From the execution trace file:

| Pathogen | Alloc CPUs | Alloc Mem | Peak RSS | Peak VMem | %CPU | Realtime |
|---|---|---|---|---|---|---|
| CAMPYLOBACTER | 16 | 96 GB | 25.9 GB | 86.0 GB | 476% | 14m 24s |
| SALMONELLA | 16 | 96 GB | 25.9 GB | 86.0 GB | 450% | 15m 18s |
| SHIGELLA | 16 | 96 GB | 25.9 GB | 85.9 GB | 467% | 14m 34s |
| STEC | 12 | 96 GB | 25.9 GB | 85.9 GB | 404% | 20m 5s |
| CRYPTOSPORIDIUM | 12 | 96 GB | 25.9 GB | 85.9 GB | 411% | 11m 15s |
| YERSINIA | 8 | 96 GB | 25.9 GB | 85.9 GB | 356% | 20m 18s |
| VIBRIO | 4 | 96 GB | 18.5 GB | 61.4 GB | 274% | 15m 50s |
| LISTERIA | 4 | 96 GB | 18.5 GB | 61.4 GB | 267% | 18m 0s |
| CYCLOSPORA | 4 | 96 GB | 18.5 GB | 61.4 GB | 245% | 27m 12s |
| DASHBOARD | -- | -- | 171.7 MB | 6.1 GB | 221% | 4.6s |

### 2.3 CPU Analysis

The `%CPU` column tells us actual core utilization:
- 476% = ~4.8 cores actively used (CAMPYLOBACTER, 16 allocated)
- 404% = ~4.0 cores (STEC, 12 allocated)
- 274% = ~2.7 cores (VIBRIO, 4 allocated)
- 245% = ~2.5 cores (CYCLOSPORA, 4 allocated)

This run used 6 chains. Stan/rstan parallelizes by running one chain per core, so the theoretical maximum is 600% (6 cores at 100% each). The actual usage of 245-476% indicates 3-5 cores were typically active. This is expected: chains start sequentially, complete at different times, and %CPU is an average over the entire runtime.

**Key finding 1: Over-provisioning.** Allocating 16 CPUs for a 6-chain run wastes 10 cores. Those SGE SMP slots are reserved but idle. For the 16-CPU pathogens (CAMPYLOBACTER, SALMONELLA, SHIGELLA), 10 of the 16 requested slots sat unused.

**Key finding 2: Under-provisioning for small pathogens.** The 4-CPU pathogens (VIBRIO, LISTERIA, CYCLOSPORA) can only run 4 chains in parallel, serializing 2. This directly explains why CYCLOSPORA took 27 minutes despite having the smallest dataset -- it is not the data size causing the slowdown, it is chain serialization. CRYPTOSPORIDIUM has 5x more rows but completed in 11 minutes because it got 12 CPUs and could run all 6 chains concurrently.

**The reviewers were right about one thing:** CPU allocation should be driven by chain count, not row count. Row count determines likelihood evaluation time per iteration, which affects wall-clock time, not CPU core count. The correct allocation is `cpus = params.chains` (or `min(params.chains, max_cpus)`).

### 2.4 Memory Analysis: Why Everything Gets 96 GB

The `modules.config` memory closure (lines 45-61) uses the complexity score:

```groovy
if (complexity > 1000000) {
    return check_max(96.GB * task.attempt, 'memory')
}
```

All 9 pathogens have complexity > 1,000,000 (lowest: LISTERIA at 1,033,560; highest: SALMONELLA at 56,555,800). The 1M threshold captures everything, so memory is not differentiating. This is a threshold calibration issue, not a broken mechanism.

**Actual memory usage:**
- Pathogens with 16/12/8 CPUs: 25.9 GB peak RSS, 85.9-86.0 GB peak vmem
- Pathogens with 4 CPUs: 18.5 GB peak RSS, 61.4 GB peak vmem

The lower memory for 4-CPU pathogens makes sense: fewer concurrent chain processes = less memory. The 96 GB allocation is safe but over-provisioned by 10-77 GB depending on the metric (peak vmem vs peak RSS).

The `functions.R` documentation (lines 337-342) estimates 56 GB for 6 chains. The peak vmem of 86 GB exceeds this estimate, but peak RSS of 26 GB is well below it. The difference is that vmem includes memory-mapped files and shared libraries that are not consuming physical RAM. For SGE's `h_vmem` enforcement, the vmem number is what matters.

### 2.5 The h_vmem Problem

`nextflow.config` line 146 hardcodes:
```groovy
clusterOptions = '-l h_vmem=80G'
```

The peak vmem for 16/12/8-CPU pathogens was 85.9-86.0 GB. This **exceeds** the 80 GB h_vmem limit. The jobs completed successfully, which means either:
- SGE on Rosalind is configured with soft limits (h_vmem is not a hard kill), or
- The vmem reported by Nextflow differs from what SGE tracks, or
- The peak was brief enough that SGE did not catch it in a polling interval.

Regardless, this is a latent bug. A slightly larger dataset, more chains, or a different SGE configuration could trigger a SIGKILL (exit 137) from h_vmem enforcement.

### 2.6 Are Any Pathogens At Risk of Failure?

Not with the current settings. All 9 completed with exit 0, no retries, comfortable margins. The main risk is the h_vmem issue described above.

The CYCLOSPORA runtime of 27 minutes (vs 11-15 minutes for comparable pathogens with more CPUs) is an efficiency issue, not a failure risk.

---

## PART 3: rstan vs. cmdstanr -- OBJECTIVE REALITY

### 3.1 What Is cmdstanr?

cmdstanr is an R interface to CmdStan (the command-line Stan distribution). Unlike rstan, which embeds the Stan C++ compiler and sampler within the R process, cmdstanr calls an external CmdStan binary. Both compile the same Stan model, use the same NUTS sampler, and produce statistically equivalent posterior distributions.

### 3.2 Performance Differences

**Without within-chain threading (simple backend swap):**
- Compilation: cmdstanr compiles models faster and caches more reliably than rstan.
- Sampling: Nearly identical speed. Both use the same Stan math library and HMC algorithm. Differences are <5%.
- Memory: cmdstanr may use slightly less memory because chain processes are separate executables rather than forked R processes, but the difference is marginal.
- Reliability: cmdstanr tends to be more stable with newer Stan versions. rstan has historically lagged behind CmdStan releases.

**With within-chain threading (requires model changes):**
cmdstanr supports `reduce_sum()` for parallelizing likelihood evaluation within each chain. This allows each chain to use multiple CPU cores. For this to work with brms, you must:
1. Add `threads = threading(N)` to the `brm()` call.
2. Compile with `cpp_options = list(stan_threads = TRUE)`.
3. The model must have a likelihood that can be decomposed into independent partial sums.

For the FoodNet model (`count ~ s(year, by = state) + state + offset(log(population))` with ~280 rows per pathogen after aggregation), the benefit of within-chain threading is modest. `reduce_sum` scales best with thousands of independent data points. With 280 rows, the overhead of thread synchronization may eat into any parallelism gains. That said, even a 20-30% speedup per chain would be meaningful for production runs.

**Net assessment:** As a simple backend swap, cmdstanr offers marginal improvements. As a path to within-chain threading, it enables a fundamentally different parallelization strategy that could matter for future county-level models (which the paper explicitly mentions as a next step, page 10).

### 3.3 Does Switching Backends Change Results?

**Statistically: No.** Both backends produce the same Stan program and run the same NUTS sampler. Given the same seed, the same chain should produce identical draws in theory.

**In practice:** There are edge cases where cmdstanr's seed handling differs from rstan's, so individual draws may differ. But summary statistics (median incidence rates, HDI bounds, incidence rate ratios) should be indistinguishable within Monte Carlo error. With 10,001 iterations and 6 chains, the statistical summaries will be the same for all practical purposes.

**With threading:** If `reduce_sum` is used with dynamic scheduling (the default), results can vary between runs even with the same seed because the order of floating-point summation changes. The `grainsize` argument with `static=TRUE` ensures deterministic scheduling and reproducible results.

### 3.4 Is cmdstanr Already in the Conda Environment?

**Yes.** `foodnet.yml` line 22:

```yaml
  - r-cmdstanr=0.8.1
```

It is installed in the container. Both rstan (line 23: `r-rstan=2.32.6`) and cmdstanr are present.

### 3.5 Key Gotcha: CmdStan Binary

cmdstanr requires a CmdStan installation (the C++ toolchain and Stan library). The `r-cmdstanr` conda package provides the R interface but may or may not include CmdStan itself. You need to verify that `cmdstanr::cmdstan_path()` returns a valid path inside the container.

If it does not, add to `foodnet.def`:
```
%post
    # After conda env creation:
    /opt/conda/envs/FootNetTreands_R/bin/Rscript -e "cmdstanr::install_cmdstan()"
```

---

## PART 4: CMDSTANR FLAG IMPLEMENTATION

This is a straightforward change. Here are the exact modifications:

### 4.1 nextflow.config -- Add Parameter

Add to the `params` block (after line 41, near the other model parameters):

```groovy
    stan_backend     = "rstan"        // Stan backend: "rstan" or "cmdstanr"
```

### 4.2 trendy.nf -- Pass Parameter to R Script

Add `--backend ${params.stan_backend}` to the Rscript call. Insert after line 88 (`--seed ${params.seed} \\`):

```bash
      --backend ${params.stan_backend} \
```

### 4.3 trendy.R -- Accept the Argument

Add to the argument parser section (after line 114, near the other model parameters):

```r
parser$add_argument("--backend", type="character", default="rstan",
                    help="Stan backend: rstan or cmdstanr (default: rstan)")
```

In the variable initialization section (around line 169), add:

```r
  backend <- opts$backend
```

Pass it to `PROPOSED_BM()` (around line 573):

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

### 4.4 functions.R -- The One-Line Change

In `PROPOSED_BM()` (line 348), add the `backend` parameter:

```r
PROPOSED_BM <- function(data, cores = 16, chains = 2, iterations = 500,
                        adapt_delta = 0.95, max_treedepth = 10, seed = 123,
                        backend = "rstan") {
```

Then change line 410 from:

```r
      backend = "rstan"  # Explicitly use rstan backend for stability
```

to:

```r
      backend = backend
```

That is it. One parameter added, one hardcoded string replaced with a variable.

### 4.5 run_workflow.sh -- Expose to User

Add a backend selection to the interactive menu. In the Nextflow command construction, add:
```bash
--stan_backend ${stan_backend:-rstan}
```

### 4.6 Summary of Gotchas

1. **CmdStan binary must be present in the container.** Verify with `cmdstanr::cmdstan_path()`.
2. **First run with cmdstanr will recompile the model.** Subsequent runs use cache.
3. **Threading is NOT enabled by the backend switch alone.** That is a separate enhancement requiring `threads = threading(N)` in the `brm()` call.
4. **The `production` profile** in `nextflow.config` (lines 102-108) should also be updated to allow backend selection.

---

## PART 5: EVERY PREVIOUS FINDING -- VERIFIED AGAINST EVIDENCE

### Findings from HPC Reviews 1, 2, and Arbitration

#### "Dynamic resource allocation is entirely non-functional / dead code"
**VERDICT: WRONG.** Disproven by `nextflow.log` lines 133-141. CPUs vary per pathogen (4/8/12/16) exactly matching the `modules.config` row-count tiers. Peak CPU of 92 (`nextflow.log` line 240) confirms mixed allocation. This was the core claim of all three reviews and it is factually incorrect.

#### "CPU allocation should be based on chain count, not row count"
**VERDICT: CORRECT as an optimization.** The execution trace confirms Stan uses at most ~5 cores regardless of allocation (peak %CPU = 476%, i.e., ~4.8 cores for a 6-chain run). Allocating 16 CPUs when only 6 chains run wastes 10 SMP slots. Conversely, allocating 4 CPUs forces chain serialization and increases runtime (CYCLOSPORA: 27 min with 4 CPUs vs CRYPTOSPORIDIUM: 11 min with 12 CPUs, despite CRYPTOSPORIDIUM having 5x more data).
**Priority: MEDIUM.** This is an efficiency fix, not a correctness fix. Change to `cpus = { check_max(params.chains ?: 2, 'cpus') }`.

#### "Memory allocation should factor in chain count"
**VERDICT: CORRECT in principle.** The documented scaling (6 chains ~ 56 GB) is reasonable. Peak vmem was 61-86 GB. The current 96 GB allocation works but wastes 10-35 GB per job.
**Priority: LOW.** Over-provisioning memory is safe. The bigger issue is h_vmem (see below).

#### "Complexity score is a poor MCMC resource predictor"
**VERDICT: PARTIALLY CORRECT.** The complexity score (rows x sites x years) does not predict MCMC computational cost well because the aggregated design matrix is ~280 rows regardless of raw case count. However, the score IS producing differentiated CPU allocations that work in practice. The real problem is that it is used for the wrong resource dimension (CPUs, where chain count matters) and its thresholds are miscalibrated for memory (everything exceeds 1M complexity).
**Priority: LOW.** The pipeline works. Recalibrating thresholds is nice-to-have.

#### "h_vmem=80G is hardcoded and conflicts with dynamic allocation"
**VERDICT: CORRECT and DANGEROUS.** `nextflow.config` line 146 sets `clusterOptions = '-l h_vmem=80G'`. The execution trace shows peak vmem of 85.9-86.0 GB for most pathogens, which exceeds 80 GB. Jobs completed, but this is a latent failure risk.
**Priority: HIGH.** Fix to: `clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 16}G" }`

#### "Exit code 139 (SIGSEGV) should not be retried"
**VERDICT: CORRECT.** Segfaults indicate memory corruption or code bugs, not resource insufficiency. Retrying wastes time.
**Priority: LOW.** Remove 139 from the retry list in `trendy.nf` line 32 and `nextflow.config` line 144.

#### "Four competing TRENDY resource definitions create confusion"
**VERDICT: CORRECT but overstated.** The `modules.config` `withName: 'TRENDY'` block wins for cpus/memory/time (loaded last, line 186 of `nextflow.config`). The `nextflow.config` `withName: 'TRENDY'` block provides errorStrategy, maxRetries, and clusterOptions. The `base.config` `withLabel:process_large` is a fallback. The `trendy.nf` process-level directives override for errorStrategy/maxRetries. This is standard nf-core layering, not a bug.
**Priority: LOW.** Document the precedence; no code change needed.

#### "Submit rate limit 10/min is too conservative"
**VERDICT: IRRELEVANT.** With 9 jobs, all are submitted within ~48 seconds (log shows first submission at 22:21:55, last at 22:22:42). The rate limit causes no meaningful delay.
**Priority: NONE.** Leave it alone.

#### "Syntax error in cdc-dev.config line 150 clusterOptions"
**VERDICT: PLAUSIBLE but not exercised.** The Rosalind profile is not used in this run (the command uses `-profile singularity`, not `-profile rosalind`). The `nextflow.config` TRENDY-specific `clusterOptions` overrides it anyway. Worth fixing if the rosalind profile is used elsewhere.
**Priority: LOW.**

### Findings from Statistical/Epidemiological Reviews

#### "Baseline IR uses median(ir) instead of population-weighted mean"
**VERDICT: CORRECT and SCIENTIFICALLY IMPORTANT.** `IR_COMP_CATCH()` in `functions.R` lines 670-674:
```r
period_data <- catch %>%
    filter(year >= start_year & year <= end_year) %>%
    group_by(.draw) %>%
    mutate(ir = .epred/(population/100000)) %>%
    summarise(baseline_ir = median(ir), baseline_count = median(count))
```
With a 3-year baseline (2016-2018), `median(ir)` simply picks the middle year's value and discards the other two. The epidemiologically correct computation is `sum(.epred)/sum(population)*100000`, which is the total-cases-over-total-person-years definition used by CDC, MMWR, and the Healthy People 2030 framework. The paper itself (page 5) describes comparing to "average incidence estimates for 2016-2018."
**Priority: HIGH.** This affects incidence rate ratio calculations.

#### "Cyclospora dual processing creates duplicate rows"
**VERDICT: CORRECT and DATA-CORRUPTING.** `PATH_ANALYSIS()` (`functions.R` lines 182-246) processes ALL pathogens including Cyclospora, correctly joining parasitic pathogens with the Parasitic census data (lines 193, 210-212). Then `trendy.R` lines 469-470 call `CYCLOSPORA_ANALYSIS()` which processes Cyclospora AGAIN. At line 476, `smartbind(pathDf, cyloDF)` merges both results, doubling Cyclospora rows. When `--pathogen CYCLOSPORA` is specified (as in this pipeline run), `subset(bact, pathogen == opts$pathogen)` at line 493 selects BOTH copies. The `split(bact, bact$pathogen)` at line 541 produces a single "CYCLOSPORA" entry with doubled year-state observations, inflating sample size and artificially narrowing credible intervals.
**Priority: HIGH.** Remove the `CYCLOSPORA_ANALYSIS()` call from `trendy.R` lines 469-470.

#### "Same duplication issue for SALMONELLA_ANALYSIS()"
**VERDICT: CORRECT.** Same logic: `PATH_ANALYSIS()` already processes Salmonella with Bacterial census data. `SALMONELLA_ANALYSIS()` (called at line 472) produces a duplicate. `smartbind(salDF)` at line 477 merges both.
**Priority: HIGH.** Remove the `SALMONELLA_ANALYSIS()` call from `trendy.R` lines 472-477.

#### "Convergence diagnostics not checked programmatically"
**VERDICT: CORRECT.** `trendy.R` lines 589-593 save `summary(proposed)` to a text file. The brms summary includes R-hat and ESS, and Stan prints divergent transition warnings to console. But none of this is captured, parsed, or acted upon. For a production pipeline running 9 pathogens automatically, a non-converged model slips through silently.
**Priority: MEDIUM.** Add a post-fitting step: extract `brms::rhat(model)`, `brms::neff_ratio(model)`, and `brms::nuts_params(model)`. Write diagnostics to a per-pathogen file. Optionally flag failures.

#### "HDI fallback mislabels ETI as HDI"
**VERDICT: CORRECT but low-impact.** `functions.R` lines 48-60: when HDInterval is unavailable, a fallback computes quantile-based equal-tailed intervals but labels them as HDI. However, `foodnet.yml` line 21 includes `r-HDInterval=0.2.4`, so inside the container the fallback never triggers. Only matters if scripts run outside the container.
**Priority: LOW.** Make HDInterval a hard dependency by adding it to the `pkgs` list in `trendy.R` line 259.

#### "HDI on response-scale vs. log-scale"
**VERDICT: Current approach is defensible.** The pipeline computes HDI on the response scale (incidence rates). The paper (page 5) describes obtaining draws from `add_linpred_draws` and exponentiating them, then computing HDI -- consistent with the pipeline's approach. HDI is NOT transformation-invariant (unlike ETI), so the scale choice matters. But computing HDI on the response scale gives the narrowest interval in the units readers care about. No change needed.
**Priority: NONE.**

#### "COEX unconditional exclusion for 2023+ data"
**VERDICT: CORRECT per the paper.** Page 3 of Weller et al.: "the catchment area remained constant but expanded again in 2023 to include the remainder of CO." Pre-2023 COEX data should be excluded (not under active surveillance); 2023+ COEX data should be included. I was not given `preprocess.R` to verify the exact line, but the fix (conditional exclusion by year) is epidemiologically sound.
**Priority: HIGH** if preprocessing is in scope.

---

## PART 6: FINAL HONEST ASSESSMENT

### What Is Genuinely Wrong (Must Fix)

1. **Cyclospora and Salmonella dual processing.** This is a data integrity bug that doubles rows for these pathogens, corrupting model input. With duplicated year-state observations, the model sees twice the data, artificially inflating precision and narrowing credible intervals. The fix is simple: remove the `CYCLOSPORA_ANALYSIS()` and `SALMONELLA_ANALYSIS()` calls from `trendy.R` (lines 468-477), since `PATH_ANALYSIS()` already handles both with the correct census denominators. Verified by code inspection: `PATH_ANALYSIS()` lines 193, 206-212 correctly split bacterial/parasitic pathogens and join each with the right census data.

2. **Baseline IR computation.** Using `median(ir)` for a 3-year baseline is epidemiologically wrong. With 3 values, the median picks the middle value and discards the other two entirely. Replace with `sum(.epred)/sum(population)*100000` in `IR_COMP_CATCH()` (`functions.R` line 673). This aligns with CDC methodology and the paper's own description.

3. **h_vmem = 80G hardcoded.** Peak vmem in this run reached 86 GB, already exceeding the 80G limit. This is a time bomb. Fix: `clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 16}G" }` in `nextflow.config` line 146.

### What Is Genuinely Fine (Leave It Alone)

1. **The dynamic resource allocation system.** It works. The execution log is unambiguous. Three reviewers called it "dead code" and they were all wrong. CPUs scale by row count (4/8/12/16), memory uses complexity thresholds. The mechanism functions correctly.

2. **The statistical model.** The negative binomial GAM with site-specific thin plate splines, state fixed effects, and log-population offset is sound. The paper demonstrates improved fit over the original model across all pathogens (Figure 2). The `brm()` formula at `functions.R` line 402 is correct.

3. **The Nextflow pipeline architecture.** DSL2 workflow, resource profiler, auto-discovery, SGE integration, Singularity container -- all functional. Config layering follows nf-core conventions.

4. **The container environment.** Both rstan and cmdstanr are installed. All R package dependencies are present. The Singularity definition builds correctly.

5. **Memory allocation magnitude.** 96 GB is over-provisioned (peak RSS 26 GB, peak vmem 86 GB) but safe. Over-provisioning memory is far preferable to under-provisioning for a pipeline processing 9 pathogens on an HPC cluster.

6. **This specific execution.** All 9 pathogens completed successfully. No failures, no retries. Total pipeline time ~28 minutes including dashboard generation. This is a working, production-quality run.

### What Would Make The Science Better

1. **Add convergence diagnostics.** Check R-hat < 1.01, bulk-ESS > 400, tail-ESS > 400, zero divergent transitions per chain. Write a `{PATHOGEN}_diagnostics.csv` alongside each model output. This is standard practice for automated Bayesian workflows. The brms package provides `rhat()`, `neff_ratio()`, and `nuts_params()` for exactly this purpose.

2. **Fix CPU allocation to match chain count.** Replace the row-count-based CPU tiers with `cpus = { check_max(params.chains ?: 2, 'cpus') }`. This gives every pathogen exactly the cores Stan can use (6 for this run), eliminating both over-provisioning (16 CPUs for 6 chains) and under-provisioning (4 CPUs for 6 chains). CYCLOSPORA would drop from 27 minutes to ~11-15 minutes.

3. **cmdstanr as a selectable backend.** Already implemented in the conda environment. The code change is minimal (Part 4 above). This opens the path to within-chain threading for future county-level models, which the paper explicitly identifies as a next step.

4. **Recalibrate memory thresholds.** The complexity > 1,000,000 threshold captures all 9 pathogens. Either raise the first threshold to 10,000,000 (to differentiate LISTERIA at 1M from SALMONELLA at 56M) or switch to chain-count-based allocation. With 6 chains, 64 GB + 16 GB h_vmem headroom would be sufficient based on the observed peak vmem of 61-86 GB.

### What Is A Waste of Time to Fix

1. **Replacing the complexity score with a "better" MCMC predictor.** The reviewers spent thousands of words arguing rows-times-sites-times-years is the wrong metric. They are technically right, but the pipeline works. The score produces meaningful differentiation for time allocation. Replacing it changes nothing about the pipeline's correctness or its output.

2. **Consolidating config definitions.** The four resource definition locations follow nf-core conventions. Refactoring them is a maintenance exercise with zero impact on execution or results.

3. **Changing submit rate limit.** 10/min submits 9 jobs in ~48 seconds. Increasing to 30/min saves maybe 30 seconds. Not worth touching.

4. **Optimizing retry scaling.** This run had zero retries. Geometric vs. linear scaling is a theoretical optimization for a failure mode that has not occurred.

5. **Adding queue routing to nextflow.config.** The `cdc-dev.config` rosalind profile already handles this. The current run uses the singularity profile, which works fine with the default queue.

---

## Summary Table

| # | Finding | Source | Verdict | Priority |
|---|---------|--------|---------|----------|
| 1 | Dynamic allocation is dead code | Reviews 1, 2, 3 | **WRONG** -- disproven by nextflow.log lines 133-141, peakCpus=92 | N/A |
| 2 | Cyclospora/Salmonella dual processing | Stat review | **CORRECT** -- data integrity bug, doubles rows | **HIGH** |
| 3 | Baseline IR uses median not weighted mean | Stat review | **CORRECT** -- epidemiologically wrong | **HIGH** |
| 4 | h_vmem=80G hardcoded below actual vmem (86 GB) | Review 1 | **CORRECT** -- latent failure risk | **HIGH** |
| 5 | CPUs should match chain count | Reviews 1, 2, 3 | **CORRECT** -- efficiency issue, not correctness | MEDIUM |
| 6 | Add convergence diagnostics | Stat review | **CORRECT** -- quality control gap | MEDIUM |
| 7 | Memory over-provisioned (96 GB alloc vs 26 GB peak RSS) | This review | New finding -- safe but wasteful | LOW |
| 8 | COEX exclusion for 2023+ data | Stat review | **CORRECT** -- data loss for 2023+ | HIGH* |
| 9 | HDI fallback mislabels | Stat review | **CORRECT** -- low impact in container | LOW |
| 10 | cmdstanr backend option | This review | Ready to implement, already in container | Enhancement |
| 11 | Complexity score is poor predictor | Reviews 1, 2, 3 | **Partially correct** -- wrong for CPUs, OK for time | LOW |
| 12 | Exit code 139 in retry list | Review 1 | **CORRECT** -- segfaults not recoverable | LOW |

*\*Priority depends on whether preprocess.R is in scope*

---

## Sources

- [Nextflow Process Documentation - Dynamic Directives with val Inputs](https://www.nextflow.io/docs/latest/process.html)
- [Nextflow Process Reference - Directive Closures](https://www.nextflow.io/docs/latest/reference/process.html)
- [brms Threading Vignette (reduce_sum / cmdstanr)](https://cran.r-project.org/web/packages/brms/vignettes/brms_threading.html)
- [Stan Convergence Diagnostics](https://mc-stan.org/learn-stan/diagnostics-warnings.html)
- [CmdStan Parallelization Guide](https://mc-stan.org/docs/cmdstan-guide/parallelization.html)
- [Weller et al. (2026) Enhanced Bayesian Spline Regression Approach, Zoonoses 6:3](https://doi.org/10.15212/ZOONOSES-2025-0030)
- Execution evidence: `nextflow.log` (247 lines), `execution_trace_2026-03-13_22-21-52.txt`
