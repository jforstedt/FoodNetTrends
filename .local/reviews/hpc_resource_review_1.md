# HPC Resource Allocation Review: FoodNetTrends Pipeline

**Reviewer:** Senior HPC Systems Engineer / Computational Scientist
**Date:** 2026-03-13
**Scope:** Cluster resource management, job scheduling (SGE), dynamic resource allocation, MCMC workload profiling
**Target environment:** Rosalind HPC (Sun Grid Engine) at CDC

**Files reviewed:**
- `modules/local/resource_profiler.nf` (resource profiling process)
- `conf/modules.config` (dynamic resource allocation logic)
- `conf/base.config` (base resource templates)
- `conf/cdc-dev.config` (HPC profiles)
- `nextflow.config` (process defaults, executor config, `check_max`)
- `modules/local/trendy.nf` (TRENDY process definition)
- `workflows/spline.nf` (data flow from profiler to TRENDY)
- `bin/functions.R` (PROPOSED_BM function, memory scaling comments)
- `run_workflow.sh` (user-facing resource/chain options)

---

## 1. Resource Profiler Accuracy

### 1.1 Complexity Score: rows x sites x years

**Assessment: Poor predictor of actual MCMC resource needs.**

The resource profiler (`resource_profiler.nf`, lines 51-52) computes:

```groovy
complexity = rows * sites * years
```

This is a measure of raw data volume, not computational complexity. For Bayesian MCMC modeling with brms/Stan, the actual resource drivers are:

1. **Number of chains** -- each chain is an independent Markov chain running in a separate thread. Memory scales nearly linearly with chains (see `functions.R` lines 337-342: 2 chains ~ 24GB, 4 chains ~ 48GB, 6 chains ~ 56GB, 8 chains ~ 72GB).
2. **Number of iterations per chain** -- the default is 500 (`nextflow.config` line 38), but publication settings use 2000 (`nextflow.config` line 104) or up to 10,001 (per `functions.R` line 330). Wall-clock time scales linearly with iterations.
3. **Number of model parameters** -- the model formula `count ~ s(year, by = state) + state + offset(log(population))` (`functions.R` line 402) generates spline basis coefficients per state. With 10 FoodNet states, this creates ~90-100 parameters (9 knots per spline x 10 states + 10 state intercepts + dispersion). Stan must compute gradients over all parameters per leapfrog step.
4. **Data size (rows in the design matrix)** -- this affects likelihood evaluation time per leapfrog step, but less dramatically than parameter count or iteration count.
5. **adapt_delta and max_treedepth** -- higher adapt_delta (0.99 vs. 0.95) increases the number of leapfrog steps per iteration (often 2-4x more). Higher max_treedepth permits longer trajectory exploration.

The `rows * sites * years` score conflates data volume metrics that are already correlated (more sites and years naturally produce more rows). It does not capture chains, iterations, adapt_delta, or max_treedepth -- the parameters that dominate actual resource consumption.

**Example of the mismatch:** A dataset with 5,000 rows run with 6 chains and 10,000 iterations at adapt_delta=0.99 will consume far more memory and time than a 50,000-row dataset run with 2 chains and 500 iterations at adapt_delta=0.95. The profiler would allocate more resources to the latter.

### 1.2 Size Categories

**Assessment: Misleading granularity.**

The size categories (`resource_profiler.nf`, lines 54-60) are based solely on row count:

| Category | Threshold |
|----------|-----------|
| tiny | <= 5,000 rows |
| small | 5,001 - 10,000 rows |
| medium | 10,001 - 20,000 rows |
| large | 20,001 - 50,000 rows |
| extra_large | > 50,000 rows |

For FoodNet data with 10 states over ~28 years, the design matrix for `PROPOSED_BM` is the `complete(year, state, pathogen)` expansion -- roughly 10 states x 28 years = 280 rows per pathogen (after aggregation by year-state in `PATH_ANALYSIS`). The raw row count from the profiler (case-level rows before aggregation) bears little relationship to the model's actual design matrix size. A pathogen with 50,000 raw cases and one with 5,000 raw cases both produce ~280-row design matrices for the GAM.

**Key insight:** The profiler measures the wrong quantity. It should measure the dimensions of the aggregated design matrix (n_states x n_years), not raw case counts.

---

## 2. Dynamic Resource Allocation in modules.config

### 2.1 CPU Tiers

**Assessment: Over-provisioned and misaligned with Stan's threading model.**

The CPU allocation (`modules.config`, lines 29-43):

| Row count | CPUs |
|-----------|------|
| <= 10,000 | 4 |
| 10,001 - 20,000 | 8 |
| 20,001 - 50,000 | 12 |
| > 50,000 | 16 |

Stan (via rstan backend, as specified at `functions.R` line 410) parallelizes by running each chain on a separate core. The `cores` argument passed to `brm()` (`functions.R` line 407, `trendy.nf` line 83: `--cores ${task.cpus}`) controls how many chains run simultaneously. With the default of 2 chains (`nextflow.config` line 37), only 2 cores are used regardless of how many are allocated. With publication settings of 4 chains (`nextflow.config` line 103), only 4 cores are used.

**Problem 1:** Allocating 8-16 CPUs for a 2-chain run wastes 6-14 cores. SGE charges against the parallel environment slot count, so this directly reduces cluster throughput.

**Problem 2:** On retry (`task.attempt` > 1), CPUs are multiplied by the attempt number (e.g., attempt 2 with 16 CPUs = 32 CPUs requested). With `max_cpus = 32` in `nextflow.config` line 66 (but `max_cpus = 16` in `cdc-dev.config` line 42), the second retry would request 32 CPUs (clamped to 32 or 16 depending on which config takes precedence). This still far exceeds what Stan can use.

**Problem 3:** The `penv = 'smp'` setting (`nextflow.config` line 131; `cdc-dev.config` line 138) requests a shared-memory parallel environment. Stan's rstan backend uses forked processes (one per chain), not threads. The `smp` PE is correct for shared-memory parallelism, but requesting 16 SMP slots when only 2-4 chains run is wasteful.

**Correct allocation:** CPUs should equal `min(params.chains, max_cpus)`. No more, no less.

### 2.2 Memory Tiers

**Assessment: Not linked to the actual memory driver (chain count).**

The memory allocation (`modules.config`, lines 45-61):

| Complexity | Memory |
|------------|--------|
| <= 100,000 (rows <= 5,000) | 16 GB |
| <= 100,000 (rows > 5,000) | 32 GB |
| 100,001 - 500,000 | 48 GB |
| 500,001 - 1,000,000 | 64 GB |
| > 1,000,000 | 96 GB |

Compare with the empirical memory scaling documented in `functions.R` (lines 337-342):

| Chains | Memory needed |
|--------|---------------|
| 2 | 24 GB |
| 4 | 48 GB |
| 6 | 56 GB |
| 8 | 72 GB |

The complexity-based tiers have no relationship to chain count. A user running `--chains 6` (publication quality) with a "tiny" dataset would get 16 GB allocated but actually needs 56 GB. This will cause an out-of-memory kill (signal 137) on the first attempt. With retry scaling (16 GB x 2 = 32 GB on attempt 2, 16 GB x 3 = 48 GB on attempt 3), it would still fail after all 3 retries, because 48 GB < 56 GB needed.

Conversely, a 2-chain run on a "large" dataset gets 64-96 GB but only needs ~24 GB.

### 2.3 Time Tiers

**Assessment: Drastically underestimated for production settings.**

The time allocation (`modules.config`, lines 63-74):

| Complexity | Time |
|------------|------|
| <= 500,000 | 12 h |
| 500,001 - 1,000,000 | 24 h |
| > 1,000,000 | 48 h |

For brms/Stan, wall-clock time scales approximately as:

```
time ~ (iterations * avg_leapfrog_steps * likelihood_eval_time) / chains_in_parallel
```

With default settings (500 iterations, adapt_delta=0.95, ~10 leapfrog steps), a typical FoodNet model fits in 1-4 hours. But with publication settings (2000 iterations, adapt_delta=0.99, ~40-100 leapfrog steps), the same model can take 24-72 hours. The `run_workflow.sh` publication preset (lines 821-828) sets 6 chains and 2000 iterations but does not adjust time allocation.

The static fallback in `nextflow.config` (line 143) allocates 72 hours, which is more realistic for production runs but conflicts with the dynamic allocation (see Section 3).

### 2.4 Data Flow: Is task.ext.dataMetrics Actually Populated?

**Assessment: Critical timing bug -- `task.ext.dataMetrics` is set too late to affect resource allocation.**

Tracing the data flow:

1. `RESOURCE_PROFILER` generates `resource_profile.csv` (`resource_profiler.nf`, line 13).
2. `spline.nf` parses the CSV into a metrics map (lines 98-108 or 126-142).
3. The metrics map is combined with pathogen groupings into a tuple: `tuple(grouping, pathogen, subgroup, pathogenMetrics)` (line 217).
4. This tuple is passed to `TRENDY` as the first input (`trendy.nf`, line 10: `tuple val(pathogenGrouping), val(pathogen), val(subgroup), val(dataMetrics)`).
5. Inside TRENDY's `script:` block, `task.ext.dataMetrics = dataMetrics` is set (`trendy.nf`, line 37).

**The problem:** In Nextflow, process resource directives (cpus, memory, time) are evaluated at task submission time, BEFORE the script block executes. The `task.ext.dataMetrics` assignment at line 37 of `trendy.nf` occurs during script execution, which is after the scheduler has already requested resources. The closures in `modules.config` that reference `task.ext.dataMetrics` (lines 30-31, 46-47, 64) will always see `null`, causing the `?:` operator to fall through to defaults (rows=10000, complexity=100000).

**This means the dynamic resource allocation in modules.config never actually works.** Every TRENDY job gets the default tier: 8 CPUs, 48 GB memory, 12 hours. The entire resource profiling infrastructure -- the RESOURCE_PROFILER process, the metrics parsing in spline.nf, the dynamic closures in modules.config -- is dead code from a resource allocation perspective.

The `dataMetrics` values passed as a `val` input to TRENDY are available as a Groovy variable in the script block, but they are NOT available via `task.ext` during the directive evaluation phase. To make this work, the `ext.dataMetrics` would need to be set in the workflow scope using `process.ext.dataMetrics` or via `withName` in a config, before the process is invoked.

---

## 3. Conflict Between Static and Dynamic Allocation

### 3.1 Config Precedence

**Assessment: Three competing TRENDY resource definitions; the static one wins.**

There are three places where TRENDY resources are defined:

1. **`base.config`** (line 62-66): `withLabel:process_large` -- 16 CPUs, 64 GB, 24 h
2. **`nextflow.config`** (lines 140-147): `withName: 'TRENDY'` -- 16 CPUs, 64 GB, 72 h
3. **`modules.config`** (lines 21-75): `withName: 'TRENDY'` -- dynamic allocation based on `task.ext.dataMetrics`

Nextflow config loading order (`nextflow.config` lines 78-79, 186):

```groovy
includeConfig 'conf/base.config'       // loaded first
includeConfig 'conf/cdc-dev.config'    // loaded second
// ... then nextflow.config's own process block (lines 129-148)
// ... then:
includeConfig 'conf/modules.config'    // loaded last (line 186)
```

In Nextflow, later config declarations override earlier ones for the same selector. `modules.config` is loaded last, so its `withName: 'TRENDY'` block should take precedence over `nextflow.config`'s `withName: 'TRENDY'` block for cpus, memory, and time.

However, `nextflow.config` lines 140-147 also set `errorStrategy`, `maxRetries`, and `clusterOptions` for TRENDY. Since `modules.config` does not redefine these, the static values from `nextflow.config` persist. This means:

- **`clusterOptions = '-l h_vmem=80G'`** is hardcoded regardless of actual memory allocation (see Section 4.1).
- **`errorStrategy`** is defined in `nextflow.config` but NOT in `modules.config`, so the static definition applies.

Additionally, `trendy.nf` itself (lines 32-33) defines `errorStrategy` and `maxRetries` as process-level directives, which override config-level `withName` settings. So the actual error handling comes from the process definition file, not any config.

**The net result is a confusing layering:** TRENDY's resources come from `modules.config` (dynamic, but broken due to the timing bug in Section 2.4), its error strategy comes from `trendy.nf` (process-level), its `clusterOptions` come from `nextflow.config`, and its label-based defaults come from `base.config`. This is fragile and difficult to reason about.

### 3.2 The `process_large` Label

TRENDY declares `label 'process_large'` (`trendy.nf`, line 3). The `base.config` (lines 62-66) defines `withLabel:process_large` as 16 CPUs, 64 GB, 24 h. In Nextflow, `withName` selectors take precedence over `withLabel` selectors, so the label serves as a fallback only if all `withName: 'TRENDY'` blocks are removed. This is correct but adds another layer of indirection.

---

## 4. SGE-Specific Issues

### 4.1 h_vmem Mismatch

**Assessment: Hardcoded h_vmem conflicts with dynamic memory allocation.**

In `nextflow.config` (line 146):

```groovy
clusterOptions = '-l h_vmem=80G'
```

This requests 80 GB of virtual memory from SGE, regardless of what `memory` is set to. If the dynamic allocation in `modules.config` sets memory to 16 GB (for a small dataset), SGE still reserves 80 GB of vmem. This wastes scheduler slots and may cause jobs to be held in queue unnecessarily on nodes with limited vmem.

Conversely, `cdc-dev.config` (line 150) has a dynamic `clusterOptions`:

```groovy
clusterOptions = { "-l h_vmem=${(check_max((task.memory.toGiga())+20), 'memory').toString().replaceAll(/[\sB]/,'')}G" }
```

This attempts to set h_vmem = task.memory + 20 GB, which is the correct pattern. But there is a **syntax error** in this expression: `check_max((task.memory.toGiga())+20), 'memory')` has mismatched parentheses. The `check_max` call takes two arguments but the closing paren after `+20` closes the `check_max` call, and then `'memory'` becomes a separate expression. This would likely cause a Groovy compilation error or produce garbage output. If the Rosalind profile is active, this broken expression may prevent jobs from submitting.

**However**, the TRENDY-specific `clusterOptions` in `nextflow.config` (line 146) overrides this with the hardcoded `'-l h_vmem=80G'`, so the bug in `cdc-dev.config` may be masked for TRENDY specifically.

The +20 GB headroom pattern itself is sound -- Stan and R can have significant overhead beyond the nominal memory allocation, and SGE's h_vmem is a hard limit that kills the process immediately when exceeded.

### 4.2 Parallel Environment

**Assessment: `penv = 'smp'` is appropriate but slots are over-requested.**

The `smp` parallel environment in SGE allocates contiguous slots on a single node with shared memory. This is correct for brms/Stan, which uses `parallel::mclapply` (forked processes with shared memory) when `cores > 1`. The alternative (`mpi`) would be inappropriate.

The issue is not the PE type but the slot count (see Section 2.1). Requesting 16 SMP slots when only 2 chains will run means 14 slots are reserved but idle. On Rosalind, SMP slots are a scarce resource -- each slot represents a core on a single node, and nodes have finite cores.

### 4.3 Submit Rate Limit

**Assessment: `submitRateLimit = '10/1min'` is very conservative.**

In `nextflow.config` (line 153):

```groovy
submitRateLimit = '10/1min'
```

This limits job submission to 10 jobs per minute. For a pipeline analyzing 7 pathogens (each as a separate TRENDY job), this means all jobs are submitted within 1 minute, which is fine. But if pathogen grouping produces more jobs (e.g., SALMONELLA with individual serotypes), submission could bottleneck.

The `cdc-dev.config` Rosalind profile (line 132) uses `submitRateLimit = '2sec'` (one job every 2 seconds = 30/min), which is more aggressive but still conservative by SGE standards. The `nextflow.config` setting overrides this because it is loaded after `cdc-dev.config`.

**Recommendation:** 10/min is unnecessarily conservative for SGE. Rosalind's qmaster can handle 30-60 submissions per minute without issues. Increase to `'30/1min'` or `'2sec'`.

### 4.4 Queue Selection

The `cdc-dev.config` Rosalind profile (line 139) has intelligent queue routing:

```groovy
queue = { task.time <= 4.h ? 'short.q' : task.time > 7.day ? 'long.q' : 'all.q' }
```

However, `nextflow.config` does not define a queue, so TRENDY jobs submitted via `nextflow.config`'s executor settings (lines 150-154) will go to the default queue. This may cause scheduling delays if the default queue has long wait times compared to `all.q`.

---

## 5. Retry Strategy

### 5.1 Error Codes

**Assessment: Mostly correct but incomplete.**

The error codes in `nextflow.config` (line 144) for TRENDY:

```groovy
errorStrategy = { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
```

| Code | Signal | Cause | Retryable? |
|------|--------|-------|------------|
| 137 | SIGKILL | OOM killer | Yes -- retry with more memory |
| 143 | SIGTERM | Job killed by scheduler (timeout or admin) | Yes -- retry with more time |
| 134 | SIGABRT | Abort (Stan compilation failure, assertion) | Maybe -- may indicate a code bug |
| 139 | SIGSEGV | Segmentation fault | Usually no -- indicates a code bug |
| 104 | -- | Connection reset (NFS/network) | Yes -- transient |

**Issue 1:** Exit code 139 (SIGSEGV) should not be retried. A segfault in Stan/R indicates memory corruption or a code bug that will recur on retry. Retrying wastes cluster time and delays failure notification.

**Issue 2:** Missing exit code 140 (SIGALRM -- SGE wallclock timeout via `-l h_rt`). The `cdc-dev.config` (line 153) includes 140 in its retry list but `nextflow.config` does not.

**Issue 3:** Missing exit code 1 (general R error). When brms/Stan fails to converge or hits a data issue, R exits with code 1. The pipeline wraps this in a tryCatch (`functions.R` line 412-414) that calls `stop()`, which also produces exit code 1. Currently, exit code 1 falls through to `'finish'`, which terminates the pipeline. This is arguably correct (a convergence failure will not be fixed by more resources), but it means the pipeline stops entirely rather than continuing with other pathogens.

The `cdc-dev.config` (line 153) also includes codes 71 (protocol error) and 255 (SSH error), which are appropriate for SGE communication failures on Rosalind.

### 5.2 Retry Scaling with Dynamic Allocation

**Assessment: Scaling works but is moot because dynamic allocation is broken.**

The `task.attempt` multiplier in `modules.config` (e.g., line 35: `16 * task.attempt`) would, if dynamic allocation were functional, escalate resources on retry:

| Attempt | CPUs (>50k rows) | Memory (>1M complexity) |
|---------|-------------------|--------------------------|
| 1 | 16 | 96 GB |
| 2 | 32 (clamped to 32) | 192 GB (clamped to 128 GB) |
| 3 | 48 (clamped to 32) | 288 GB (clamped to 128 GB) |

Since `max_memory = '128.GB'` (`nextflow.config` line 65), the memory ceiling is 128 GB. The `cdc-dev.config` also sets `max_memory = '128.GB'` (line 41). This is reasonable for Rosalind's node sizes.

However, since dynamic allocation is broken (Section 2.4), the actual retry scaling uses the static values from `nextflow.config`: 64 GB x attempt. So attempt 2 = 128 GB (clamped to 128), attempt 3 = 192 GB (clamped to 128). This means retries 2 and 3 are identical, which defeats the purpose of retry escalation.

### 5.3 Retry Count

**Assessment: 3 retries is appropriate, but identical resources on retries 2-3 is wasteful.**

With `maxRetries = 3` (`trendy.nf` line 33), the pipeline makes up to 4 total attempts. For OOM failures (137), if the first attempt at 64 GB fails and the second at 128 GB also fails, the third and fourth attempts at 128 GB will also fail. This wastes 2 job submissions and potentially 24+ hours of wall-clock time waiting in queue.

---

## 6. Chain-Memory Relationship

### 6.1 Memory Scaling Documentation vs. Implementation

**Assessment: The documented scaling is never used for allocation.**

`functions.R` (lines 337-342) clearly documents the chain-memory relationship:

```
# Memory scaling (approximate):
# - 2 chains: 24GB RAM
# - 4 chains: 48GB RAM
# - 6 chains: 56GB RAM (publication quality)
# - 8 chains: 72GB RAM
```

Neither the dynamic allocation in `modules.config` nor the static allocation in `nextflow.config` references `params.chains`. The chain count is only passed to the R script (`trendy.nf` line 84: `--chains ${params.chains}`), not used for resource calculation.

### 6.2 User-Facing Presets

The `run_workflow.sh` offers presets that change chain count without adjusting resources:

| Preset | Chains | Iterations | Resource adjustment |
|--------|--------|------------|---------------------|
| Quick test (line 808) | 1 | 100 | None |
| Publication (line 821) | 6 | 2000 | None |
| Extreme (line 834) | 8 | 5000 | None |
| Custom (line 853) | user-specified | user-specified | None |

**Critical failure scenario:** A user selects "Publication" settings (6 chains, 2000 iterations). The pipeline allocates 64 GB (static from `nextflow.config`). The model needs ~56 GB for 6 chains plus overhead. With R's garbage collector and Stan's compilation cache, actual peak memory can reach 65-70 GB. The job is killed by SGE's h_vmem=80G limit or by the OOM killer if physical memory is exhausted. After 3 retries (all at 128 GB due to clamping), the job may succeed -- but only because the retry escalation accidentally provides enough memory.

**Worse scenario:** "Extreme" settings (8 chains, 5000 iterations) need ~72 GB base + overhead. The first attempt at 64 GB fails. Retries at 128 GB succeed but waste 64 GB.

### 6.3 The `nextflow.config` Production Profile

The production profile (`nextflow.config` lines 102-107) sets 4 chains and 2000 iterations but does not adjust process resources:

```groovy
production {
    params.chains           = 4
    params.iterations       = 2000
    params.adapt_delta      = 0.99
    params.max_treedepth    = 15
}
```

With 4 chains at adapt_delta=0.99, memory needs are ~48 GB (within the 64 GB default) but time needs increase dramatically. The default 72h in `nextflow.config` may be sufficient, but the dynamic allocation's 12h (via the broken `modules.config`) would not be. Since the dynamic allocation is broken, the 72h static value applies, which is adequate.

---

## 7. Recommendations

### 7.1 Fix the Dynamic Resource Allocation Timing (CRITICAL)

The `task.ext.dataMetrics` assignment in `trendy.nf` line 37 occurs too late. To make dynamic allocation work, move the metrics into the process configuration. One approach:

```groovy
// In spline.nf, before calling TRENDY:
pathogenGroupingWithMetrics.map { grouping, pathogen, subgroup, metrics ->
    // Set ext values that will be available during directive evaluation
    // This requires restructuring to use process directives, not script-level assignment
}
```

Alternatively, abandon the dynamic allocation approach and use chain-based allocation:

```groovy
// In modules.config or nextflow.config
withName: 'TRENDY' {
    cpus = { check_max(params.chains, 'cpus') }
    memory = {
        def base = params.chains <= 2 ? 24 : params.chains <= 4 ? 48 : params.chains <= 6 ? 56 : 72
        check_max((base + 16).GB * task.attempt, 'memory')  // +16 GB headroom
    }
    time = {
        def base = params.iterations <= 500 ? 4 : params.iterations <= 2000 ? 24 : 48
        def delta_factor = params.adapt_delta >= 0.99 ? 2.0 : 1.0
        check_max((base * delta_factor).h * task.attempt, 'time')
    }
}
```

This directly ties resource allocation to the parameters that actually drive resource consumption.

### 7.2 Fix h_vmem to Track Actual Memory (HIGH)

Replace the hardcoded `clusterOptions = '-l h_vmem=80G'` in `nextflow.config` line 146 with:

```groovy
clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 16}G" }
```

This ensures h_vmem is always 16 GB above the Nextflow memory allocation, providing headroom without over-reserving. Fix the syntax error in `cdc-dev.config` line 150 as well.

### 7.3 Align CPU Allocation with Chain Count (HIGH)

```groovy
cpus = { check_max(params.chains ?: 2, 'cpus') }
```

Stan cannot use more cores than chains. Requesting excess cores wastes SMP slots on Rosalind.

### 7.4 Remove Exit Code 139 from Retry List (MEDIUM)

Segfaults are not recoverable by adding resources. Remove 139 from the retry list in `nextflow.config` line 144 and `trendy.nf` line 32. Add exit code 140 (SGE timeout).

### 7.5 Add Chain Count to Resource Profiler Output (MEDIUM)

The resource profiler should report `params.chains` and `params.iterations` alongside the data metrics, so that any downstream resource logic can use them. Currently, the profiler has no visibility into MCMC parameters.

### 7.6 Eliminate Config Duplication (MEDIUM)

TRENDY resources are defined in four places (`base.config` via label, `nextflow.config` via withName, `modules.config` via withName, and `trendy.nf` via process-level directives). Consolidate to a single authoritative location. Recommendation: define resources only in `modules.config` (which is loaded last and is the designated per-process config), and remove the `withName: 'TRENDY'` block from `nextflow.config` (lines 140-147) and the process-level `errorStrategy`/`maxRetries` from `trendy.nf` (lines 32-33).

### 7.7 Scale Retry Resources Geometrically, Not Linearly (LOW)

The current `memory * task.attempt` scaling is linear (64, 128, 192...). For OOM failures, geometric scaling (64, 96, 128) is more efficient because it reaches the target faster at lower attempt counts. Use:

```groovy
memory = { check_max(base_memory * Math.pow(1.5, task.attempt - 1), 'memory') }
```

### 7.8 Increase Submit Rate Limit (LOW)

Change `submitRateLimit = '10/1min'` to `'30/1min'` in `nextflow.config` line 153. SGE's qmaster on Rosalind can handle this rate without issues, and it reduces queue latency when running many pathogen-serotype combinations.

### 7.9 Add Queue Routing to nextflow.config (LOW)

The `nextflow.config` executor block (lines 150-154) does not specify a queue. Add:

```groovy
queue = { task.time <= 4.h ? 'short.q' : 'all.q' }
```

This ensures TRENDY jobs (which typically need 4-72 hours) are routed to `all.q` rather than the default queue.

---

## Summary of Findings

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | `task.ext.dataMetrics` set too late -- dynamic allocation is entirely non-functional | CRITICAL | Broken |
| 2 | Resource allocation ignores chain count, the primary memory driver | HIGH | Design flaw |
| 3 | Hardcoded `h_vmem=80G` conflicts with dynamic memory allocation | HIGH | Misconfigured |
| 4 | CPU allocation (up to 16) far exceeds Stan's chain-based parallelism (2-8) | HIGH | Wasteful |
| 5 | Publication/extreme presets change chains without adjusting resources | HIGH | Missing logic |
| 6 | Four competing TRENDY resource definitions create maintenance burden | MEDIUM | Tech debt |
| 7 | Exit code 139 (SIGSEGV) is retried; exit code 140 (SGE timeout) is not | MEDIUM | Incorrect |
| 8 | Complexity score (rows x sites x years) is a poor MCMC resource predictor | MEDIUM | Design flaw |
| 9 | Retry attempts 2 and 3 request identical resources (both clamped to 128 GB) | MEDIUM | Inefficient |
| 10 | `submitRateLimit = '10/1min'` is unnecessarily conservative | LOW | Suboptimal |
| 11 | Syntax error in `cdc-dev.config` line 150 `clusterOptions` expression | MEDIUM | Bug |

The most critical finding is that the entire dynamic resource allocation system is non-functional due to the `task.ext.dataMetrics` timing issue. All TRENDY jobs fall back to the default tier (8 CPUs, 48 GB, 12h from the broken dynamic closures) or the static allocation (16 CPUs, 64 GB, 72h from `nextflow.config`), depending on config loading order. The recommended fix is to replace the data-metrics-based allocation with a chain-count-based allocation that directly reflects the actual resource drivers of Bayesian MCMC workloads.
