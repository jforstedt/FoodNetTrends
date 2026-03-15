# HPC Resource Arbitration Review: FoodNetTrends Pipeline

**Reviewer:** Senior Computational Scientist (Nextflow DSL2 + Bayesian Biostatistics)
**Date:** 2026-03-13
**Purpose:** Unify findings from HPC Review 1 (Senior HPC Systems Engineer) and HPC Review 2 (Senior Computational Infrastructure Engineer), verify all claims against source code, and critically assess how resource issues affect statistical result accuracy.

**Reviews arbitrated:**
- `reviews/hpc_resource_review_1.md` (Reviewer 1 / R1)
- `reviews/hpc_resource_review_2.md` (Reviewer 2 / R2)

**Source files verified:**
- `modules/local/resource_profiler.nf`, `modules/local/trendy.nf`
- `conf/modules.config`, `conf/base.config`, `conf/cdc-dev.config`
- `nextflow.config`, `workflows/spline.nf`
- `bin/functions.R`, `bin/trendy.R`
- `run_workflow.sh`, `foodnet.def`, `foodnet.yml`

**Context from biostatistics reviews:**
- `reviews/arbitration_review.md`, `reviews/statistical_justification_review.md`

---

## 1. Verification of Claims

### 1.1 The `task.ext.dataMetrics` Timing Claim

**Both reviewers' claim:** `task.ext.dataMetrics` is assigned in the `script:` block of `trendy.nf` (line 37) and is therefore invisible to resource directive closures in `modules.config`, which are evaluated before the script block executes. The dynamic resource allocation system is entirely non-functional.

**Verification:** This claim is **CORRECT**.

The Nextflow execution model, documented in the [Nextflow documentation on processes](https://www.nextflow.io/docs/latest/process.html), evaluates resource directives at task creation time. The evaluation sequence is:

1. Configuration selectors (`withName`, `withLabel`) are resolved and their closures evaluated to determine `task.cpus`, `task.memory`, `task.time`.
2. Input channels are bound to the task.
3. The `script:` block executes.

At step 1, `task.ext.dataMetrics` has not been assigned (it is assigned at step 3, in `trendy.nf` line 37). The safe-navigation operator `task.ext.dataMetrics?.rows` returns `null`, and the Elvis operator `?:` falls through to the hardcoded defaults (`rows = 10000`, `complexity = 100000`).

**Nextflow version consideration:** The manifest in `nextflow.config` (line 180) requires `nextflowVersion = '!>=23.04.0'`. The `run_workflow.sh` loads `nextflow/24.10.4` (line 9). In **all Nextflow versions from DSL2 inception through 24.10.x**, resource directives are evaluated before the script block. There is no version-dependent behavior that would change this. The Nextflow GitHub issues and documentation have been consistent on this point: `task.ext` values set in the `script:` block are not available to directive closures. The correct approach is to set `ext` values in config-level `withName`/`withLabel` blocks, or to use process input values indirectly through `ext` values set in the workflow scope before process invocation.

**One nuance neither reviewer explored:** Nextflow DSL2 process input values (`val(dataMetrics)` at `trendy.nf` line 10) are also not directly available in directive closures. Directives can only access `task.*` properties, `params.*`, and values set in the config scope. Even if `task.ext.dataMetrics = dataMetrics` were moved to a `beforeScript` or `ext` config block, the input variable `dataMetrics` itself would not be resolvable there. The only way to make input-dependent resource allocation work is through one of:
- Process aliases with label-based routing (R2's recommended approach)
- The `resourceLimits` directive (Nextflow 23.11+)
- Setting `ext` values from the workflow scope before process invocation using `process.ext` in a dynamic config

**Conclusion:** Both reviewers are correct. The dynamic allocation is dead code.

### 1.2 The Effective Resource Allocation (Where Reviewers Diverge)

**R1's claim:** TRENDY gets "the default tier: 8 CPUs, 48 GB memory, 12 hours" from modules.config, or alternatively "the static allocation (16 CPUs, 64 GB, 72h from nextflow.config), depending on config loading order."

**R2's claim:** TRENDY gets exactly 4 CPUs, 32 GB memory, 12 hours from modules.config, because the default values (`rows = 10000`, `complexity = 100000`) fall into specific tiers that R2 traces precisely.

**Verification:** R2 is **CORRECT**; R1 is imprecise.

Tracing the actual tier resolution with `rows = 10000` and `complexity = 100000`:

**CPUs (modules.config lines 33-42):**
- `rows > 50000`? No.
- `rows > 20000`? No.
- `rows > 10000`? `10000 > 10000` is **false** (strict inequality).
- Else: `check_max(4 * task.attempt, 'cpus')` = **4 CPUs**.

**Memory (modules.config lines 50-60):**
- `complexity > 1000000`? No.
- `complexity > 500000`? No.
- `complexity > 100000`? `100000 > 100000` is **false**.
- `rows > 5000`? `10000 > 5000` is **true**: `check_max(32.GB * task.attempt, 'memory')` = **32 GB**.

**Time (modules.config lines 66-73):**
- `complexity > 1000000`? No.
- `complexity > 500000`? No.
- Else: `check_max(12.h * task.attempt, 'time')` = **12 hours**.

R1 states "8 CPUs, 48 GB" as the default tier, which corresponds to `rows > 10000` and `complexity > 100000`. But with the actual defaults of `rows = 10000` (not greater than) and `complexity = 100000` (not greater than), these conditions fail. **R1 made an off-by-one error on the strict inequality checks.**

Furthermore, R1 hedges between modules.config and nextflow.config values without clearly resolving which wins. R2 correctly traces the config loading order: `modules.config` is loaded last (at `nextflow.config` line 186), so its `withName: 'TRENDY'` block overrides the earlier `withName: 'TRENDY'` in `nextflow.config` (lines 140-147) for `cpus`, `memory`, and `time`. However, `clusterOptions`, `errorStrategy`, and `maxRetries` are NOT set in modules.config, so the values from `nextflow.config` persist for those directives.

**Effective allocation (attempt 1):**

| Directive | Value | Source |
|-----------|-------|--------|
| cpus | 4 | modules.config (overrides nextflow.config's 16) |
| memory | 32 GB | modules.config (overrides nextflow.config's 64 GB) |
| time | 12 h | modules.config (overrides nextflow.config's 72 h) |
| clusterOptions | `-l h_vmem=80G` | nextflow.config line 146 (not set in modules.config) |
| errorStrategy | retry on [143,137,104,134,139] | nextflow.config line 144 / trendy.nf line 32 |
| maxRetries | 3 | nextflow.config line 145 / trendy.nf line 33 |

**This means modules.config unknowingly DOWNGRADES TRENDY resources from the developer's explicit intent** (16 CPUs, 64 GB, 72 h in nextflow.config) to 4 CPUs, 32 GB, 12 h. R2 correctly identifies this as a critical finding that R1 misses.

### 1.3 The `modules.config` Precedence Claim

**Both reviewers' claim:** `modules.config` overrides `nextflow.config` for TRENDY resource directives because it is loaded last.

**Verification:** **CORRECT**, with a subtlety.

In `nextflow.config`, the loading order is:
1. Lines 10-75: `params` block (processed first)
2. Line 78: `includeConfig 'conf/base.config'` (inline)
3. Line 79: `includeConfig 'conf/cdc-dev.config'` (inline)
4. Lines 82-86: nf-core custom profiles (attempted)
5. Lines 88-108: `profiles` block
6. Lines 117-123: `env` block
7. Lines 129-148: `process` block (contains `withName: 'TRENDY'` at line 140)
8. Lines 150-154: `executor` block
9. Line 186: `includeConfig 'conf/modules.config'` (inline, LAST)

Nextflow merges `withName` blocks: for each directive, the last assignment wins. Since modules.config is loaded after the `process` block in `nextflow.config`, its `cpus`, `memory`, and `time` for TRENDY override those in `nextflow.config`. Directives not set in modules.config (like `clusterOptions`) are inherited from the earlier `withName: 'TRENDY'` block.

**The `withLabel` vs `withName` precedence:** `base.config` defines `withLabel:process_large` (16 CPUs, 64 GB, 24 h). TRENDY has `label 'process_large'`. Per Nextflow documentation, `withName` selectors always take precedence over `withLabel` selectors regardless of load order. So the `withLabel:process_large` in `base.config` is a fallback only if all `withName: 'TRENDY'` blocks are removed.

**Process-level vs config-level:** `trendy.nf` lines 32-33 define `errorStrategy` and `maxRetries` as process-level directives. Per Nextflow documentation, **config-level selectors override process-level directives** (not the other way around, as R1 suggests at one point). The config-level `withName: 'TRENDY'` in `nextflow.config` sets the same values, so the result is the same either way, but the config wins.

### 1.4 The `h_vmem` Conflict

**Both reviewers' claim:** The hardcoded `clusterOptions = '-l h_vmem=80G'` in `nextflow.config` line 146 conflicts with the dynamic memory allocation.

**R2's additional insight:** On retry attempt 3, memory scales to 96 GB (32 GB x 3) but h_vmem stays at 80 GB, creating a hard ceiling that defeats the retry mechanism.

**Verification:** Both are **CORRECT**; R2's analysis is more precise.

On attempt 1: memory = 32 GB, h_vmem = 80 GB. SGE reserves 80 GB vmem. The job can use up to 80 GB before being killed. Since only 32 GB is needed by Nextflow's accounting, there is 48 GB of "shadow" headroom that SGE reserves but Nextflow does not know about.

On attempt 2: memory = 64 GB, h_vmem = 80 GB. The job has 16 GB of headroom. This might work for dev settings but is marginal for production.

On attempt 3: memory = 96 GB, h_vmem = 80 GB. **SGE will either reject the job or kill it when the process exceeds 80 GB vmem.** The retry mechanism is self-defeating.

**R2 also correctly identifies the syntax error in `cdc-dev.config` line 150:**
```groovy
clusterOptions = { "-l h_vmem=${(check_max((task.memory.toGiga())+20), 'memory').toString().replaceAll(/[\sB]/,'')}G" }
```
The expression `(check_max(...), 'memory')` creates a Groovy tuple (a `List`), not a function call. The `.toString()` would produce something like `[128, memory]` rather than the intended integer. This is a genuine bug, though it is masked for TRENDY because the `withName: 'TRENDY'` clusterOptions in `nextflow.config` takes precedence.

### 1.5 The `max_cpus` Conflict

**R1's claim:** `max_cpus = 32` from `nextflow.config` line 66.
**R2's claim:** `max_cpus = 16` from `cdc-dev.config` line 42 may win due to include order.

**Verification:** R2's analysis is **MORE NUANCED** but the conclusion depends on Nextflow's params merging behavior.

The `nextflow.config` params block (lines 10-75) is processed first. At line 66, `max_cpus = 32` is set. Then at line 79, `includeConfig 'conf/cdc-dev.config'` is processed inline. Inside `cdc-dev.config`, line 42 sets `max_cpus = 16`. Since includes are processed inline at their point of inclusion, and `cdc-dev.config`'s params block is processed after `nextflow.config`'s params block has already been parsed, the last assignment wins.

However, `cdc-dev.config` line 42 is inside the `params {}` block at the top level of that file, NOT inside a profile. This means it is processed unconditionally when the file is included. **`max_cpus = 16` from `cdc-dev.config` overrides `max_cpus = 32` from `nextflow.config`.**

But wait -- the `includeConfig` at line 79 occurs **within** `nextflow.config`, whose params block spans lines 10-75. The `includeConfig` is at line 79, which is **after** the params block closes at line 75. So the processing order is:
1. `nextflow.config` params (lines 10-75): `max_cpus = 32`
2. `includeConfig 'conf/base.config'` (line 78): no params
3. `includeConfig 'conf/cdc-dev.config'` (line 79): `max_cpus = 16` -- **this overrides**

**Result: `max_cpus = 16` wins.** R2 is correct. This means the `check_max` ceiling for CPUs is 16, not 32. The retry scaling of `4 * task.attempt` yields 4, 8, 12 for attempts 1-3, all within the 16 cap.

---

## 2. Where Reviewers Agree and Disagree

### 2.1 Points of Agreement

Both reviewers agree on these findings, and my verification confirms them:

| Finding | R1 | R2 | Verification |
|---------|----|----|--------------|
| `task.ext.dataMetrics` timing bug renders dynamic allocation dead | Correct | Correct | Confirmed (Section 1.1) |
| Resource profiler complexity score is a poor predictor of MCMC needs | Correct | Correct | Confirmed -- chains and iterations are the dominant drivers |
| CPU allocation ignores chain count | Correct | Correct | `params.chains` is not referenced in any resource closure |
| Memory allocation ignores chain count | Correct | Correct | Same as above |
| h_vmem is hardcoded and conflicts with dynamic memory | Correct | Correct | Confirmed (Section 1.4) |
| Exit code 139 (SIGSEGV) should not be retried | Correct | Not mentioned | Confirmed -- segfaults indicate code bugs |
| Publication/extreme presets change MCMC params without adjusting resources | Correct | Correct | Confirmed |
| cdc-dev.config line 150 has a syntax error | Correct | Correct | Confirmed (Section 1.4) |
| Environment name typo `FootNetTreands_R` | Not mentioned | Correct | Confirmed in `foodnet.yml`, `foodnet.def`, `nextflow.config` |

### 2.2 Points of Disagreement

| Topic | R1 | R2 | Who is right |
|-------|----|----|--------------|
| Effective TRENDY allocation (attempt 1) | "8 CPUs, 48 GB, 12h" or "16 CPUs, 64 GB, 72h" | 4 CPUs, 32 GB, 12h | **R2 is correct** -- R1 has off-by-one errors on strict inequalities |
| Whether modules.config downgrades resources | Partially noted but not clearly stated | Explicitly identifies the downgrade | **R2 is more precise** |
| Retry attempt 3 h_vmem conflict | Notes the general conflict | Traces the specific attempt-3 failure (96 GB vs 80 GB cap) | **R2 is more precise** -- though at 32 GB base (not 64 GB as R1 assumed), attempt 3 = 96 GB, still above 80 GB |
| rstan vs cmdstanr threading | Notes that Stan parallelizes by chain | Provides detailed waste analysis and recommends cmdstanr switch | **R2 is more thorough** |
| max_cpus resolution | States 32 (from nextflow.config) | States 16 (from cdc-dev.config, due to include order) | **R2 is correct** (Section 1.5) |
| Container analysis | Not covered | Detailed analysis of container size, build optimization, Stan compiler flags | R2 adds value; R1 omits this |
| Process-level vs config-level directive precedence | States trendy.nf directives override config | Correctly states config overrides process-level | **R2 is correct** per Nextflow documentation |

### 2.3 Findings Unique to Each Reviewer

**R1 only:**
- Exit code 139 should not be retried; exit code 140 (SGE timeout) should be added
- Exit code 1 (R error) behavior analysis
- Geometric vs linear retry scaling recommendation
- Detailed MCMC parameter count estimation (~90-100 parameters)

**R2 only:**
- Precise tier resolution with correct inequality evaluation
- The "downgrade" finding (modules.config reduces nextflow.config resources)
- Container optimization recommendations (Stan compiler flags, cmdstanr threading)
- RESOURCE_PROFILER scheduling overhead analysis (30-60s for a 2s task)
- queueSize=100 concern
- Rosalind profile never activated in run_workflow.sh
- Job ordering optimization for wall-clock time
- Detailed cluster impact analysis (92 CPUs, 736 GB total for 23 jobs)
- Target architecture recommendation with process aliases

---

## 3. CRITICAL: How Resource Issues Affect Result Accuracy

This is the central question of this review. For each resource failure mode, I assess whether results would be **wrong** (inaccurate posterior inference), **absent** (job fails cleanly), or **degraded** (slower convergence or reduced precision).

### 3.1 Out-of-Memory (OOM) Kill During MCMC Sampling

**Question:** If a job is killed by OOM (signal 137) partway through MCMC sampling, does Stan/brms produce partial results or fail cleanly?

**Answer:** The job **fails cleanly with no output files**. When the Linux OOM killer sends SIGKILL to the R process, the process terminates immediately. There is no opportunity for R or Stan to write partial results. The `brm()` call at `functions.R` line 394 is wrapped in `tryCatch`, but SIGKILL cannot be caught -- it bypasses all signal handlers. The output files declared in `trendy.nf` (lines 24-30) are all `optional: true`, so Nextflow does not error on missing outputs.

**Impact on result accuracy:** **None.** OOM produces a clean failure, not wrong results. The job either completes with full results or produces nothing. The `errorStrategy 'retry'` will resubmit with more resources.

**However**, there is a subtle concern: if the retry mechanism itself fails (as it does when h_vmem caps at 80 GB on attempt 3), the pathogen is skipped entirely. This means the final dashboard and combined results would be **incomplete** (missing that pathogen) rather than wrong. Whether "incomplete results" constitutes "wrong results" depends on the use case. For MMWR publication, a missing pathogen would be noticed immediately.

### 3.2 Memory Swapping During MCMC Sampling

**Question:** If insufficient physical memory causes the OS to swap, does this affect MCMC convergence or just speed?

**Answer:** Swapping affects **speed only, not accuracy**. MCMC sampling is a purely sequential numerical computation within each chain. The mathematical operations (leapfrog integration, gradient computation) produce identical floating-point results regardless of whether the data resides in RAM or swap. The only effect is that each iteration takes much longer (potentially 10-100x slower) because memory access latency increases by orders of magnitude.

**However**, on SGE with `h_vmem`, the process is killed when it exceeds the virtual memory limit, so swapping to that extent does not occur in practice. The process either fits in memory or gets killed.

**Impact on result accuracy:** **None**, if the job completes. The posterior samples are identical. The practical risk is that swapping makes the job exceed its wall-clock time limit, converting a memory problem into a time problem.

### 3.3 CPU Under-Allocation (Fewer CPUs Than Chains)

**Question:** If a job runs with 4 CPUs but requests 6 chains, what happens? Does brms run chains sequentially? Does this affect results?

**Answer:** brms passes the `cores` argument directly to rstan's `sampling()` function, which controls how many chains execute in parallel via `parallel::mclapply`. With `cores = 4` and `chains = 6`:
- rstan runs 4 chains in parallel (one per core).
- When the first chain completes, the 5th chain starts on the freed core.
- When the next chain completes, the 6th chain starts.
- Total wall-clock time is approximately 1.5x what it would be with 6 cores.

**Impact on result accuracy:** **None whatsoever.** Each chain is an independent Markov chain with its own random number stream derived from the seed. The chain-to-seed mapping in Stan is deterministic: chain `i` uses seed `seed + i - 1` (or a similar deterministic derivation). Whether chains run in parallel or sequentially does not affect the random number sequence within each chain. The posterior samples are **bitwise identical** regardless of CPU allocation.

**The one exception:** If `set.seed(seed)` at `functions.R` line 391 interacts with the chain initialization, the order of chain execution could theoretically affect results. But Stan/rstan handles seed derivation internally and does not use R's `set.seed` for chain-specific randomness. The `seed` argument to `brm()` (line 408) is passed to Stan's sampler, which derives chain-specific seeds deterministically.

### 3.4 Wall-Clock Timeout During MCMC Sampling

**Question:** If a job times out at 12 hours instead of running for the needed 24+ hours, does Stan produce usable partial results?

**Answer:** **No.** When SGE kills the job (SIGTERM/SIGKILL), the process terminates. Stan does not support checkpointing or partial result saving for an in-progress sampling run. The `brm()` call either completes all chains for all iterations, or produces nothing.

With rstan backend (the current configuration), there is no mechanism for incremental saving. With cmdstanr backend, Stan saves CSV output files incrementally, and in principle one could recover partial chains from the CSV files. However, brms does not support assembling a model from partial Stan CSV output.

**Impact on result accuracy:** Clean failure, no wrong results. The pathogen is simply missing from the analysis.

### 3.5 Retry Strategy and Result Reproducibility

**Question:** Does `errorStrategy 'retry'` with increased resources risk producing different results across attempts?

**Answer:** This is the most nuanced question. There are two scenarios:

**Scenario A: Job fails on attempt 1 (OOM), succeeds on attempt 2 with more memory.**
The `seed` parameter (`params.seed = 123`, `nextflow.config` line 41) is passed to `brm()` on every attempt. Stan's random number generation is deterministic given the seed and chain index. More memory does not change the computation -- it merely allows it to complete. **Results are identical** to what attempt 1 would have produced if it had enough memory.

**Scenario B: Job fails on attempt 1 (OOM at chain 3 of 6), succeeds on attempt 2 with more memory and more CPUs.**
With attempt 2, `cpus = 4 * 2 = 8`. This means `--cores 8` is passed to `brm()`. Since `chains = 6` and `cores = 8`, all 6 chains run simultaneously (cores > chains, so all chains start at once). On attempt 1, with `cores = 4`, only 4 of 6 chains would have started initially. But since attempt 1 failed, no results were produced. On attempt 2, the seed is the same, so the same chain-specific seeds are used. **Results are identical** regardless of the number of cores.

**Important clarification:** Nextflow does NOT pass attempt-specific information to the R script. The `--cores ${task.cpus}` in `trendy.nf` line 83 changes between attempts (4 on attempt 1, 8 on attempt 2), but this only affects parallelism, not the computation. The `--seed ${params.seed}` is constant across attempts.

**Impact on result accuracy:** **None.** Retries with different resources produce identical results when the seed is fixed and the computation completes.

### 3.6 The Real Accuracy Risk: Resource Issues That Prevent Detection of Statistical Problems

The resource issues in this pipeline do not directly cause wrong results. They cause one of two outcomes:
1. **Job completes successfully** -- results are correct (assuming the statistical methodology is correct, which is a separate concern addressed in the biostatistics reviews).
2. **Job fails** -- no results are produced.

However, there is an **indirect** accuracy risk: if resource constraints cause the pipeline to default to lower-quality MCMC settings (fewer chains, fewer iterations) to fit within available resources, the results will be **less precise** (wider credible intervals) and potentially **less reliable** (inadequate convergence diagnostics).

The current pipeline does not automatically downgrade MCMC settings based on resources. The user chooses settings via `run_workflow.sh` or `nextflow.config` profiles, and the pipeline either completes with those settings or fails. This is actually the correct behavior from a statistical accuracy standpoint -- it is better to fail than to silently reduce MCMC quality.

**The one genuine accuracy concern from HPC configuration:** The `errorStrategy 'finish'` (not `'terminate'`) for non-resource errors means that if one pathogen fails, the pipeline continues with other pathogens. If the failure is due to a data issue that affects multiple pathogens (e.g., corrupted census data), the pipeline might produce correct results for some pathogens and silently skip others, giving the user a false impression of completeness. This is a workflow design issue, not an HPC resource issue per se.

---

## 4. The Actual Resource Allocation Path (Publication Settings)

### 4.1 Trace: Publication Quality Run

A user runs the pipeline with publication settings: 6 chains, 10001 iterations, adapt_delta 0.99. The pathogen is Campylobacter (~25K rows, 10 states, 28 years).

**Step 1: User invokes `run_workflow.sh`, selects "Publication" preset.**

`run_workflow.sh` (lines 821-828) sets:
```bash
chains=6
iterations=10001
adapt_delta=0.99
max_treedepth=15
```

These are passed to Nextflow as `--chains 6 --iterations 10001 --adapt_delta 0.99 --max_treedepth 15`.

**Step 2: Nextflow configuration loading.**

The config chain resolves TRENDY resources (per Section 1.2):
- cpus: **4** (modules.config, default tier)
- memory: **32 GB** (modules.config, default tier)
- time: **12 h** (modules.config, default tier)
- clusterOptions: **`-l h_vmem=80G`** (nextflow.config)

Note: `params.chains = 6` is set, but no resource directive references `params.chains`.

**Step 3: SGE job submission.**

Nextflow submits to SGE requesting:
- 4 SMP slots (`penv = 'smp'`)
- 32 GB memory
- 12 h wall-clock time
- 80 GB h_vmem

No queue is specified (rosalind profile not active), so SGE uses the default queue.

**Step 4: R script execution.**

`trendy.R` receives `--cores 4 --chains 6 --iterations 10001 --adapt_delta 0.99 --max_treedepth 15 --seed 123`.

`brm()` is called with `cores = 4, chains = 6`. rstan starts 4 chains in parallel, queues 2.

**Step 5: Memory consumption.**

Per the empirical scaling in `functions.R` lines 337-341, 6 chains need approximately **56 GB**. The job has 32 GB allocated. With h_vmem at 80 GB, the process could technically use up to 80 GB of virtual memory before SGE kills it. Whether it survives depends on the physical memory available on the node and the OS's overcommit behavior.

**Most likely outcome:** The R process exceeds 32 GB resident memory. If the node has sufficient physical memory and Linux overcommit is permissive, the process continues (using more memory than Nextflow requested but less than h_vmem). If the OOM killer fires, the process dies with exit code 137.

**Step 6: Wall-clock time.**

With 10001 iterations, adapt_delta 0.99, and 6 chains on 4 cores (so 1.5x serialization), estimated wall-clock time is **16-36 hours**. The 12 h time limit will likely kill the job with exit code 143 (SIGTERM).

**Step 7: Retry (attempt 2).**

Resources scale:
- cpus: `4 * 2 = 8`
- memory: `32 * 2 = 64 GB`
- time: `12 * 2 = 24 h`
- h_vmem: still 80 GB (static)

64 GB is closer to the needed 56 GB + overhead. With 8 cores and 6 chains, all chains run in parallel. Wall-clock time drops to **10-24 hours**. The 24 h time limit may be sufficient.

**Likely outcome:** The job **may succeed on attempt 2** if memory overhead stays below 64 GB and the model converges within 24 hours.

**Step 8: Retry (attempt 3) if attempt 2 fails.**

Resources scale:
- cpus: `4 * 3 = 12`
- memory: `32 * 3 = 96 GB`
- time: `12 * 3 = 36 h`
- h_vmem: still 80 GB (static)

**The h_vmem cap defeats this attempt.** SGE will kill the process when virtual memory exceeds 80 GB, even though Nextflow allocated 96 GB. This is the bug R2 identifies.

### 4.2 Would the Results Be Wrong, or Would the Job Just Fail?

**The job would fail, not produce wrong results.**

In every failure scenario above (OOM, timeout, h_vmem kill), the `brm()` call does not complete, no model object is returned, and no output files are written. The `tryCatch` in `trendy.R` lines 571-688 catches R-level errors (but not SIGKILL), writes an error file, and moves to the next pathogen with `next`.

The statistical results for pathogens that DO complete successfully are unaffected by the failures of other pathogens. Each TRENDY job is fully independent.

### 4.3 What IS Sufficient for This Workload?

For Campylobacter with publication settings (6 chains, 10001 iterations, adapt_delta 0.99):

| Resource | Recommended | Rationale |
|----------|-------------|-----------|
| CPUs | 6 | One per chain (rstan backend) |
| Memory | 72 GB | 56 GB base + 16 GB headroom for R GC, Stan compilation cache |
| Time | 48 h | Conservative estimate for high adapt_delta with 10K+ iterations |
| h_vmem | 92 GB | memory + 20 GB headroom |

For development settings (2 chains, 500 iterations):

| Resource | Recommended | Rationale |
|----------|-------------|-----------|
| CPUs | 2 | One per chain |
| Memory | 24 GB | Empirical from functions.R line 338 |
| Time | 4 h | Conservative for short runs |
| h_vmem | 44 GB | memory + 20 GB headroom |

---

## 5. Unified Priority List

Findings are ranked by impact on **result accuracy** first, then by **operational impact** (job failures, cluster waste).

### Tier 1: Findings That Can Cause Wrong Results

**None of the HPC resource issues directly cause wrong statistical results.** This is an important finding. The pipeline's failure mode is "fail cleanly or succeed correctly." This is the right behavior for a scientific pipeline.

However, there are resource-related issues that contribute to **incomplete results** (missing pathogens) or **reduced result quality** (inadequate MCMC settings used because adequate settings would fail):

### Tier 2: Findings That Cause Job Failures (Operational Accuracy)

**P1. CRITICAL -- Dynamic resource allocation is entirely non-functional, and modules.config unknowingly downgrades TRENDY resources.**
- Source: `trendy.nf` line 37, `modules.config` lines 29-74
- Both reviewers agree; R2 provides the precise tier resolution.
- Effect: All TRENDY jobs get 4 CPUs, 32 GB, 12 h -- far below what the developer intended (16 CPUs, 64 GB, 72 h) and far below what publication-quality runs need (6 CPUs, 56+ GB, 24-48 h).
- **Impact on accuracy:** Indirect. Publication runs will fail, forcing users to fall back to lower-quality MCMC settings that fit within 32 GB (e.g., 2 chains, 500 iterations). If users do this, the results will have wider credible intervals and potentially inadequate convergence. This is the most consequential accuracy impact in the entire HPC review.

**P2. CRITICAL -- Static h_vmem defeats retry mechanism on attempt 3.**
- Source: `nextflow.config` line 146
- R2 identifies this precisely; R1 notes the general conflict.
- Effect: Even when Nextflow scales memory to 96 GB on attempt 3, SGE kills the process at 80 GB.
- **Impact on accuracy:** Indirect. Jobs that need >80 GB cannot succeed at all, not even after retries. Combined with P1, this means large-pathogen publication runs are guaranteed to fail.

**P3. HIGH -- Resource allocation ignores chain count and iteration count.**
- Source: No `params.chains` or `params.iterations` reference in any resource directive.
- Both reviewers agree.
- Effect: A 2-chain development run and a 6-chain publication run get identical resources.
- **Impact on accuracy:** Same indirect effect as P1. The correct resources for 6 chains/10K iterations are dramatically different from 2 chains/500 iterations, but the pipeline makes no distinction.

**P4. HIGH -- Rosalind profile never activated in `run_workflow.sh`.**
- Source: `run_workflow.sh` lines 1201, 1208, 1224 use only `-profile singularity`.
- R2 identifies this; R1 does not.
- Effect: No queue routing (jobs may land in wrong queue), no dynamic h_vmem, oversized queueSize (100 vs appropriate 12-25).
- **Impact on accuracy:** Indirect. Wrong queue can cause unnecessary job rejection or delays.

### Tier 3: Findings That Waste Resources Without Affecting Results

**P5. HIGH -- CPU allocation misaligned with rstan's chain-based parallelism.**
- Source: modules.config allocates CPUs based on row count, not chain count; rstan uses exactly one core per chain.
- Both reviewers agree; R2 provides detailed waste analysis.
- Effect: With 2 chains and 4 allocated CPUs, 50% CPU waste. With development settings across 23 jobs, 46 CPUs reserved but only 46 used (if 2 chains) -- actually this is only 2x waste, not egregious. The real waste is in the developer's intended 16 CPUs per job.
- **Impact on accuracy:** None directly. Wastes shared cluster capacity.

**P6. MEDIUM -- Retry scaling is linear; retries 2 and 3 can be identical after clamping.**
- Source: `memory * task.attempt` with `max_memory = 128 GB`.
- R1 identifies this.
- Effect: If base memory is high enough, retries converge to the same allocation, wasting attempts.
- **Impact on accuracy:** None. Just wastes time and cluster cycles.

**P7. MEDIUM -- Exit code 139 (SIGSEGV) is retried.**
- Source: `nextflow.config` line 144, `trendy.nf` line 32.
- R1 identifies this; R2 does not mention it.
- Effect: Segfaults are retried up to 3 times, wasting cluster time.
- **Impact on accuracy:** None. The retries will fail the same way, and eventually the pathogen is skipped.

**P8. MEDIUM -- Missing exit code 140 (SGE SIGALRM timeout) from retry list.**
- Source: `nextflow.config` line 144 does not include 140.
- R1 identifies this.
- Effect: SGE wall-clock timeout kills are not retried with more time.
- **Impact on accuracy:** Indirect. A job that could succeed with more time is not given the opportunity.

**P9. MEDIUM -- cdc-dev.config line 150 has a syntax error in clusterOptions.**
- Source: Mismatched parentheses creating a Groovy tuple.
- Both reviewers identify this.
- Effect: Masked for TRENDY (nextflow.config clusterOptions wins), but would produce garbage h_vmem for other processes if rosalind profile were activated.
- **Impact on accuracy:** None currently (masked).

**P10. MEDIUM -- RESOURCE_PROFILER runs as SGE job unnecessarily.**
- Source: Global `process.executor = 'sge'` in nextflow.config.
- R2 identifies this.
- Effect: 30-60 seconds of scheduling overhead for a 2-second computation.
- **Impact on accuracy:** None. Just delays pipeline start.

**P11. LOW -- Complexity score (rows x sites x years) is a poor MCMC predictor.**
- Source: `resource_profiler.nf` lines 51-52.
- Both reviewers agree.
- Effect: Even if the dynamic allocation worked, it would allocate resources based on the wrong metric.
- **Impact on accuracy:** None directly, but contributes to the misallocation problem.

**P12. LOW -- Submit rate limit (10/min) is conservative.**
- Source: `nextflow.config` line 153.
- R1 identifies this.
- Effect: For 23 jobs, submission takes ~3 minutes. Negligible.
- **Impact on accuracy:** None.

**P13. LOW -- Environment name typo `FootNetTreands_R`.**
- Source: `foodnet.yml` line 1, `foodnet.def` line 22, `nextflow.config` line 122.
- R2 identifies this.
- Effect: Consistent across files, so functional. Maintainability hazard.
- **Impact on accuracy:** None.

**P14. LOW -- cmdstanr installed but unused in container.**
- Source: `foodnet.yml` line 22.
- R2 identifies this.
- Effect: ~200-300 MB container bloat.
- **Impact on accuracy:** None.

### Findings From Biostatistics Reviews Relevant to HPC

The biostatistics arbitration review identifies several issues that interact with HPC configuration:

**B1. No programmatic convergence diagnostics** (arbitration_review.md, H2). If the pipeline ran with inadequate MCMC settings (forced by resource constraints per P1), the model might produce results with poor convergence that go undetected. This is the primary pathway by which HPC resource issues could lead to published wrong results.

**B2. The `production` profile in `nextflow.config` (4 chains, 2000 iterations) is inadequate** (arbitration_review.md, Section 2.5). Even if resource allocation were correct, the production profile would produce results with fewer post-warmup samples than recommended. Combined with the resource allocation issues, this creates a compounding problem: the "easy" settings are inadequate for publication, and the "correct" settings fail due to insufficient resources.

---

## 6. Recommended Fixes

### Fix 1: Remove Dynamic Allocation From modules.config, Restore Static TRENDY Resources (CRITICAL)

**What to change:** `conf/modules.config` lines 28-74: Remove the `cpus`, `memory`, and `time` closures from the `withName: 'TRENDY'` block. Keep only `publishDir`.

**Why:** The dynamic allocation is dead code that unknowingly downgrades resources. Removing it allows the static `withName: 'TRENDY'` block in `nextflow.config` (lines 140-147) to take effect: 16 CPUs, 64 GB, 72 h. This is not optimal but is far better than the current 4 CPUs, 32 GB, 12 h.

**Affects result accuracy?** Indirectly yes -- this is the most important fix because it allows publication-quality runs to succeed. The statistical results themselves are unchanged for any given successful run, but this fix dramatically increases the probability that publication runs complete successfully.

**Could this change results?** No. The MCMC computation is deterministic given the seed. More memory and time allow the computation to complete; they do not change the computation itself.

**File:** `conf/modules.config`
**Lines:** 28-74 (remove `cpus`, `memory`, `time` definitions only; keep `publishDir`)

### Fix 2: Make h_vmem Dynamic (CRITICAL)

**What to change:** `nextflow.config` line 146: Replace `clusterOptions = '-l h_vmem=80G'` with:

```groovy
clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
```

**Why:** The static 80G h_vmem defeats retry scaling. With this fix, h_vmem tracks `task.memory + 20 GB` headroom on every attempt.

**Affects result accuracy?** No. This only affects whether jobs survive or get killed by SGE.

**Could this change results?** No. Same seed, same computation.

**File:** `nextflow.config`, line 146

### Fix 3: Tie CPU Allocation to Chain Count (HIGH)

**What to change:** `nextflow.config` line 141: Replace `cpus = { check_max(16 * task.attempt, 'cpus') }` with:

```groovy
cpus = { check_max((params.chains ?: 2) * task.attempt, 'cpus') }
```

**Why:** Stan uses exactly one core per chain (rstan backend). Allocating more CPUs than chains wastes SMP slots.

**Affects result accuracy?** No. Fewer idle cores does not change the computation.

**Could this change results?** No. With rstan, the number of cores affects parallelism, not the random number streams. Each chain's seed is derived deterministically from `params.seed` and the chain index, regardless of how many cores are available.

**File:** `nextflow.config`, line 141

### Fix 4: Tie Memory Allocation to Chain Count (HIGH)

**What to change:** `nextflow.config` line 142: Replace `memory = { check_max(64.GB * task.attempt, 'memory') }` with:

```groovy
memory = {
    def base = params.chains <= 2 ? 24 : params.chains <= 4 ? 48 : params.chains <= 6 ? 64 : 80
    check_max((base as int).GB * task.attempt, 'memory')
}
```

**Why:** Memory consumption scales with chain count, not data size (since the design matrix is always ~280 rows regardless of raw case count). The values are derived from the empirical scaling in `functions.R` lines 337-341, with headroom added.

**Affects result accuracy?** No. Same computation, just enough memory to complete it.

**Could this change results?** No.

**File:** `nextflow.config`, line 142

### Fix 5: Tie Time Allocation to Iteration Count and adapt_delta (HIGH)

**What to change:** `nextflow.config` line 143: Replace `time = { check_max(72.h * task.attempt, 'time') }` with:

```groovy
time = {
    def base = params.iterations <= 500 ? 4 : params.iterations <= 2000 ? 24 : 48
    def delta_factor = params.adapt_delta >= 0.99 ? 2.0 : 1.0
    check_max(((int)(base * delta_factor)).h * task.attempt, 'time')
}
```

**Why:** Wall-clock time scales with iterations and adapt_delta. A 500-iteration dev run needs ~1-4 hours; a 10001-iteration production run with adapt_delta=0.99 may need 24-72 hours.

**Affects result accuracy?** No. This only determines whether the job has enough time to complete.

**Could this change results?** No.

**File:** `nextflow.config`, line 143

### Fix 6: Fix Exit Code List (MEDIUM)

**What to change:** `nextflow.config` line 144 and `trendy.nf` line 32: Change `[143,137,104,134,139]` to `[143,137,104,134,140]`.

**Why:** Remove 139 (SIGSEGV -- not recoverable by retry) and add 140 (SGE SIGALRM timeout -- recoverable with more time).

**Affects result accuracy?** No. Segfaults indicate bugs that retries cannot fix. Timeouts indicate insufficient time that retries can fix.

**Could this change results?** No.

**Files:** `nextflow.config` line 144, `modules/local/trendy.nf` line 32

### Fix 7: Activate Rosalind Profile in run_workflow.sh (MEDIUM)

**What to change:** `run_workflow.sh` lines 1201, 1208, 1224: Change `-profile singularity` to `-profile rosalind,singularity`.

**Why:** Enables queue routing, conservative queueSize, and (once the syntax error is fixed) dynamic h_vmem from the rosalind profile.

**Prerequisite:** Fix the syntax error in `cdc-dev.config` line 150 first.

**Affects result accuracy?** No. Queue routing affects scheduling, not computation.

**Could this change results?** No.

**File:** `run_workflow.sh`, lines 1201, 1208, 1224

### Fix 8: Fix cdc-dev.config clusterOptions Syntax Error (MEDIUM)

**What to change:** `conf/cdc-dev.config` line 150: Replace the existing expression with:

```groovy
clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
```

**Why:** The current expression creates a Groovy tuple due to mismatched parentheses, producing unpredictable h_vmem values.

**Affects result accuracy?** No.

**File:** `conf/cdc-dev.config`, line 150

### Fix 9: Consolidate TRENDY Resource Definitions (MEDIUM)

**What to change:** Remove the `withName: 'TRENDY'` block from `nextflow.config` (lines 140-147) for `cpus`, `memory`, and `time`. Keep `errorStrategy`, `maxRetries`, and `clusterOptions` in nextflow.config. Remove process-level `errorStrategy` and `maxRetries` from `trendy.nf` (lines 32-33). Remove the dynamic allocation closures from `modules.config` (per Fix 1).

**Why:** Having TRENDY resources defined in four places (base.config via label, nextflow.config via withName, modules.config via withName, trendy.nf via process-level) is unmaintainable. Consolidate to a single authoritative location.

**Recommended architecture:** Define TRENDY resources in `nextflow.config`'s `withName: 'TRENDY'` block (chain-aware, per Fixes 3-5). Keep `publishDir` in `modules.config`. Remove process-level directives from `trendy.nf`.

**Affects result accuracy?** No. This is a maintenance/correctness fix.

**Could this change results?** No.

### Fix 10: Run RESOURCE_PROFILER Locally (LOW)

**What to change:** Add to `conf/modules.config` or `nextflow.config`:

```groovy
withName: 'RESOURCE_PROFILER' {
    executor = 'local'
    cpus = 1
    memory = '4.GB'
}
```

**Why:** A 2-second R computation does not need SGE scheduling (30-60 seconds overhead).

**Affects result accuracy?** No.

**File:** `conf/modules.config` or `nextflow.config`

### Fix 11: Reduce queueSize (LOW)

**What to change:** `nextflow.config` line 152: Change `queueSize = 100` to `queueSize = 25`.

**Why:** 25 accommodates 23 TRENDY jobs + preprocessing, while preventing accidental submission storms.

**Affects result accuracy?** No.

**File:** `nextflow.config`, line 152

---

## 7. Consensus Action Plan

This section provides the definitive implementation plan. For each fix, a single approach is chosen, justified, and sequenced by dependency order.

### Implementation Sequence

The fixes must be applied in this order because of dependencies between them. Within each phase, changes are independent and can be done in parallel.

---

#### Phase 1: Emergency Fixes (Must Do Now -- Unblocks Publication Runs)

**Action 1.1: Remove broken dynamic allocation from modules.config**

- **The decision:** Remove the `cpus`, `memory`, and `time` closures from `conf/modules.config` lines 28-74 inside the `withName: 'TRENDY'` block. Keep only `publishDir`. Do NOT replace them with anything in modules.config.
- **Why this approach over R2's process-alias recommendation:** R2 proposes creating TRENDY_LARGE, TRENDY_MEDIUM, TRENDY_SMALL process aliases with label-based routing. This is architecturally cleaner but requires restructuring `spline.nf`, creating a new `trendy_sized.nf` module file, and testing the branch operator logic. It is a multi-day effort. The immediate fix (removing the broken closures) takes 5 minutes and restores the developer's intended resources (16 CPUs, 64 GB, 72 h from `nextflow.config` lines 140-143). The process-alias approach is the right long-term architecture but should not block unblocking publication runs.
- **Scope:** `conf/modules.config` (~45 lines removed)
- **Could this change results vs. current behavior?** Yes, but in a beneficial way. Current behavior: all TRENDY jobs get 4 CPUs, 32 GB, 12 h (too little for publication runs, causing failures). After fix: all TRENDY jobs get 16 CPUs, 64 GB, 72 h (sufficient for publication runs). Jobs that previously failed will now succeed. Jobs that previously succeeded will produce **identical results** because the MCMC computation is seed-deterministic -- more resources do not change the output, they just allow the computation to finish.
- **Classification:** Must-do-now.

**Action 1.2: Make h_vmem dynamic in nextflow.config**

- **The decision:** Replace `nextflow.config` line 146 (`clusterOptions = '-l h_vmem=80G'`) with:
  ```groovy
  clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
  ```
- **Why this specific formulation:** R1 proposes `task.memory.toGiga() + 16`, R2 proposes `task.memory.toGiga() + 20`. Use +20 GB because it matches the pattern already present in `cdc-dev.config` (line 150) and provides more headroom for R's garbage collector and Stan's compilation cache. The difference between +16 and +20 is negligible in terms of cluster impact.
- **Scope:** `nextflow.config`, 1 line changed
- **Could this change results?** No. h_vmem only determines whether SGE kills the process; it does not affect the computation.
- **Classification:** Must-do-now.

---

#### Phase 2: Right-Sizing (Must Do Before Next Production Run)

These changes depend on Phase 1 being complete (specifically, Action 1.1 must be done so that `nextflow.config`'s `withName: 'TRENDY'` block is the authoritative source for TRENDY resources).

**Action 2.1: Tie TRENDY resources to MCMC parameters**

- **The decision:** Replace the static resource values in `nextflow.config` lines 141-143 with chain-aware and iteration-aware closures. Specifically:
  ```groovy
  withName: 'TRENDY' {
      cpus = { check_max((params.chains ?: 2) * task.attempt, 'cpus') }
      memory = {
          def base = params.chains <= 2 ? 24 : params.chains <= 4 ? 48 : params.chains <= 6 ? 64 : 80
          check_max((base as int).GB * task.attempt, 'memory')
      }
      time = {
          def base_h = params.iterations <= 500 ? 4 : params.iterations <= 2000 ? 24 : 48
          def delta_factor = params.adapt_delta >= 0.99 ? 2.0 : 1.0
          check_max(((int)(base_h * delta_factor)).h * task.attempt, 'time')
      }
      clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
      errorStrategy = { task.exitStatus in [143,137,104,134,140] ? 'retry' : 'finish' }
      maxRetries = 3
  }
  ```
- **Why chain-count-based over R2's process-alias approach:** Both approaches solve the problem. The chain-count-based approach keeps a single TRENDY process and uses `params.*` in closures, which is architecturally simpler and works because `params.*` values are available in config closures (unlike `task.ext.*` or process input values). R2's process-alias approach with `branch` in `spline.nf` is more Nextflow-idiomatic and would also enable per-pathogen resource differentiation based on data size. However, the data-size dimension is a minor contributor to resource needs (Section 1.1 of both reviews confirms this), while chain count and iteration count are the dominant drivers. The chain-count-based approach directly addresses the dominant drivers with minimal code change (3 lines in one file vs. a new module file, modified workflow, and new config labels). **Choose the chain-count approach for now; revisit process aliases if per-pathogen sizing proves necessary after production calibration runs.**
- **Scope:** `nextflow.config`, ~10 lines modified
- **Could this change results vs. current behavior?** For development runs (2 chains, 500 iter): resources change from 4 CPU/32 GB/12 h to 2 CPU/24 GB/4 h. The job will still succeed (the computation needs ~2 CPU and ~12 GB), but with fewer idle cores. Results are **identical** because the seed and MCMC parameters are unchanged. For publication runs (6 chains, 10001 iter): resources change from 4 CPU/32 GB/12 h (guaranteed failure) to 6 CPU/64 GB/96 h (should succeed). Results will be **new** -- these runs were not producing results before.
- **Classification:** Must-do before next production run.

**Action 2.2: Fix exit code list**

- **The decision:** In both `nextflow.config` line 144 and `trendy.nf` line 32, change `[143,137,104,134,139]` to `[143,137,104,134,140]`. Remove 139 (SIGSEGV), add 140 (SGE timeout SIGALRM).
- **Scope:** `nextflow.config` line 144, `trendy.nf` line 32 (2 lines across 2 files)
- **Could this change results?** No. This only affects which failures trigger retries.
- **Classification:** Must-do before next production run.

---

#### Phase 3: Operational Improvements (Can Wait -- Do Within 2 Weeks)

These changes are independent of each other and of Phase 1/2.

**Action 3.1: Fix cdc-dev.config clusterOptions syntax error**

- **The decision:** Replace `cdc-dev.config` line 150 with:
  ```groovy
  clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
  ```
  Also fix line 181 (training profile) with the same pattern.
- **Scope:** `conf/cdc-dev.config`, 2 lines changed
- **Could this change results?** No.
- **Classification:** Can wait, but must be done before Action 3.2.

**Action 3.2: Activate Rosalind profile in run_workflow.sh**

- **The decision:** Change all three Nextflow invocations in `run_workflow.sh` to use `-profile rosalind,singularity` instead of `-profile singularity`.
- **Prerequisite:** Action 3.1 (fix cdc-dev.config syntax error). If the rosalind profile is activated with the broken clusterOptions, non-TRENDY processes (which do not have a `withName` override for clusterOptions) would get garbage h_vmem values.
- **Scope:** `run_workflow.sh`, 3 lines (~1201, ~1208, ~1224)
- **Could this change results?** No. Queue routing and queueSize affect scheduling, not computation.
- **Classification:** Can wait.

**Action 3.3: Remove process-level directives from trendy.nf**

- **The decision:** Remove lines 32-33 from `trendy.nf` (`errorStrategy` and `maxRetries`). These are redundant with the config-level `withName: 'TRENDY'` block and create confusion about which source is authoritative.
- **Scope:** `modules/local/trendy.nf`, 2 lines removed
- **Could this change results?** No.
- **Classification:** Can wait.

**Action 3.4: Remove `task.ext.dataMetrics` assignment from trendy.nf**

- **The decision:** Remove line 37 from `trendy.nf` (`task.ext.dataMetrics = dataMetrics`). This is dead code -- the assignment executes but the value is never read by anything that matters (resource closures have already evaluated). Keep the log statement at lines 40-42 since it provides useful debugging output, but change it to reference `dataMetrics` directly (which it already does) rather than suggesting `task.ext.dataMetrics` is meaningful.
- **Scope:** `modules/local/trendy.nf`, 1 line removed
- **Could this change results?** No.
- **Classification:** Can wait.

**Action 3.5: Run RESOURCE_PROFILER locally**

- **The decision:** Add to `nextflow.config` or `modules.config`:
  ```groovy
  withName: 'RESOURCE_PROFILER' {
      executor = 'local'
      cpus = 1
      memory = '4.GB'
  }
  ```
- **Scope:** `nextflow.config` or `conf/modules.config`, ~4 lines added
- **Could this change results?** No.
- **Classification:** Can wait.

**Action 3.6: Reduce queueSize**

- **The decision:** Change `nextflow.config` line 152 from `queueSize = 100` to `queueSize = 25`.
- **Scope:** `nextflow.config`, 1 line changed
- **Could this change results?** No.
- **Classification:** Can wait.

---

#### Phase 4: Future Architecture (Plan, Don't Execute Yet)

**Action 4.1: Consider process-alias architecture**

R2's recommended target architecture (TRENDY_LARGE, TRENDY_MEDIUM, TRENDY_SMALL, TRENDY_TINY with branch-based routing) is the right long-term design. It should be planned and implemented after:
1. At least one production run with the Phase 2 chain-count-based allocation, to collect actual resource utilization data from Nextflow trace files.
2. Calibration of the resource tiers based on empirical `peak_rss` and `realtime` from the trace files.
3. A decision on whether to switch from rstan to cmdstanr (which would change the CPU-per-chain calculus).

**Do not implement this now.** The chain-count-based approach from Phase 2 is sufficient and correct for the immediate term.

**Action 4.2: Evaluate cmdstanr backend switch**

R2 recommends switching from rstan to cmdstanr for within-chain threading. This would enable better CPU utilization but requires container rebuild, Stan threading flags (`-DSTAN_THREADS`), and testing to verify numerical equivalence. This is a meaningful improvement but not urgent.

**Important:** Switching backends may produce **slightly different numerical results** due to floating-point ordering differences between rstan and cmdstanr's Stan implementations, even with the same seed. The differences would be within MCMC sampling noise and would not affect scientific conclusions, but they would make results non-bitwise-reproducible compared to previous runs. This should be communicated to the team if the switch is made.

---

### Summary: What Exactly To Do

| # | Action | Files | Lines Changed | Must-Do-Now? | Changes Results? |
|---|--------|-------|---------------|-------------|-----------------|
| 1.1 | Remove broken dynamic allocation from modules.config | `conf/modules.config` | ~45 lines removed | **YES** | No (but previously-failing jobs will now succeed) |
| 1.2 | Make h_vmem dynamic | `nextflow.config` | 1 line | **YES** | No |
| 2.1 | Tie resources to MCMC params | `nextflow.config` | ~10 lines | Before next production run | No (same seed = same results when job completes) |
| 2.2 | Fix exit code list | `nextflow.config`, `trendy.nf` | 2 lines | Before next production run | No |
| 3.1 | Fix cdc-dev.config syntax | `conf/cdc-dev.config` | 2 lines | Within 2 weeks | No |
| 3.2 | Activate rosalind profile | `run_workflow.sh` | 3 lines | Within 2 weeks (after 3.1) | No |
| 3.3 | Remove trendy.nf process directives | `modules/local/trendy.nf` | 2 lines removed | Within 2 weeks | No |
| 3.4 | Remove dead task.ext assignment | `modules/local/trendy.nf` | 1 line removed | Within 2 weeks | No |
| 3.5 | Run RESOURCE_PROFILER locally | `nextflow.config` or `modules.config` | 4 lines added | Within 2 weeks | No |
| 3.6 | Reduce queueSize | `nextflow.config` | 1 line | Within 2 weeks | No |

**Total immediate effort:** 2 files, ~46 lines changed. Estimated time: 15 minutes.
**Total Phase 2 effort:** 2 files, ~12 lines changed. Estimated time: 30 minutes + testing.
**Total Phase 3 effort:** 4 files, ~13 lines changed. Estimated time: 1 hour + testing.

---

## 8. Overall Assessment

### Both Reviewers Are Fundamentally Correct

The core finding -- that the dynamic resource allocation system is non-functional -- is identified and correctly diagnosed by both reviewers. R2 provides the more precise analysis, correctly tracing the exact tier resolution (4 CPUs, 32 GB, 12 h) and identifying the unintended downgrade from the developer's static values. R1 provides better analysis of the MCMC-specific implications (chain-memory scaling, adapt_delta effects, error code semantics).

### The Most Important Conclusion

**Resource issues in this pipeline cannot cause wrong statistical results.** They can only cause job failures (which are clean and detectable) or force users to use lower-quality MCMC settings (which is an indirect accuracy risk). The pipeline's design -- where `brm()` either completes fully or fails entirely, with fixed seeds for reproducibility -- is robust against resource-induced inaccuracy.

The real danger is operational: publication-quality runs (6 chains, 10001 iterations) are **guaranteed to fail** with the current resource allocation (32 GB memory, 12 h time) for large pathogens. Users will either give up on publication-quality settings or work around the pipeline's resource management entirely by manually editing config files. Both outcomes are unacceptable for a production CDC pipeline.

The two emergency fixes (Actions 1.1 and 1.2) can be implemented in 15 minutes and immediately unblock publication-quality runs. There is no reason to delay them.
