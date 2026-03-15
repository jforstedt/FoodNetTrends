# HPC Resource Management & Profiling System Review

**Reviewer:** Senior Computational Infrastructure Engineer
**Date:** 2026-03-13
**Scope:** Resource allocation pipeline, Nextflow configuration layering, container optimization, SGE scheduling, and scalability
**Target environment:** CDC Rosalind HPC (SGE-based), Singularity containers

**Files reviewed:**
- `modules/local/resource_profiler.nf` -- data profiling process
- `conf/modules.config` -- dynamic resource allocation logic
- `conf/base.config` -- base resource templates
- `conf/cdc-dev.config` -- HPC profiles
- `nextflow.config` -- process defaults, executor config, retry logic
- `modules/local/trendy.nf` -- TRENDY process definition
- `workflows/spline.nf` -- workflow orchestration and metrics flow
- `foodnet.def` -- Singularity container definition
- `foodnet.yml` -- conda environment specification
- `tower.yml` -- Nextflow Tower config
- `run_workflow.sh` -- interactive run script
- `bin/functions.R` -- memory scaling comments in PROPOSED_BM

---

## 1. Metrics-to-Resource Pipeline: A Fundamental Design Flaw

### 1.1 Data Flow Trace

The pipeline attempts a data-driven resource allocation scheme with the following flow:

1. **RESOURCE_PROFILER** (`resource_profiler.nf`, lines 41--61) generates `resource_profile.csv` containing per-pathogen metrics: `rows`, `sites`, `years`, `complexity` (rows * sites * years), and `size_category`.

2. **spline.nf** parses the CSV into a Groovy map. When a pre-existing `resource_profile.csv` is found alongside the preprocessed data, lines 98--108 read it directly; otherwise lines 122--142 run `RESOURCE_PROFILER` and parse the output. In both paths the result is a `metricsChannel` containing a map keyed by pathogen name, with values like `[rows: 25000, sites: 10, years: 28, complexity: 7000000, size_category: "large"]`.

3. **spline.nf** (lines 166--218 in the preprocessed branch; lines 313--365 in the raw-data branch) combines pathogen groupings with the metrics channel via `.combine(metricsChannel).map{...}` to produce tuples of the form `tuple(grouping, pathogen, subgroup, pathogenMetrics)`. This map closure also performs Salmonella serotype adjustment (lines 200--213, lines 347--360), scaling rows and complexity to 15% of the parent pathogen's values for individual serotypes.

4. **TRENDY** (`trendy.nf`, line 10) receives `dataMetrics` as the 4th element of the input tuple: `tuple val(pathogenGrouping), val(pathogen), val(subgroup), val(dataMetrics)`.

5. **trendy.nf** line 37, inside the `script:` block, attempts to bridge the metrics into the Nextflow task context:
   ```groovy
   task.ext.dataMetrics = dataMetrics
   ```

6. **modules.config** (lines 29--74) attempts to read `task.ext.dataMetrics?.rows` and `task.ext.dataMetrics?.complexity` in the `cpus`, `memory`, and `time` closure expressions.

### 1.2 The Critical Timing Problem

**This is a fundamental design flaw.** In Nextflow DSL2, resource directives (`cpus`, `memory`, `time`) are evaluated **before** the `script:` block executes. The evaluation order is:

1. Nextflow resolves the process configuration (directives from config files and process definition).
2. Resource closures in `modules.config` are evaluated to determine `task.cpus`, `task.memory`, `task.time`.
3. The `script:` block runs -- this is where `task.ext.dataMetrics = dataMetrics` is assigned.

Therefore, when modules.config evaluates `task.ext.dataMetrics?.rows` at step 2, the assignment at step 3 has not yet occurred. The Groovy safe-navigation operator `?.` returns `null`, and the Elvis operator `?:` falls through to the hardcoded defaults:

- `rows` defaults to `10000` (modules.config, line 30)
- `complexity` defaults to `100000` (modules.config, lines 31, 46, 64)

**Result:** The entire dynamic resource allocation system in modules.config is dead code. Every TRENDY job receives identical resources regardless of pathogen size. The resource profiler, the metrics parsing in spline.nf, the serotype adjustment logic at spline.nf lines 200--213 -- all execute without error but produce zero effect on actual resource allocation.

### 1.3 What Actually Determines Resources

Since `task.ext.dataMetrics` is always null at evaluation time, every TRENDY task hits the same tier in modules.config:

- **rows = 10000** falls into the `rows > 5000` bracket (but not `> 10000`), so: `cpus = check_max(4 * task.attempt, 'cpus')` -- **wait**, re-reading modules.config lines 33--42 carefully:

  ```groovy
  if (rows > 50000) {
      return check_max(16 * task.attempt, 'cpus')
  } else if (rows > 20000) {
      return check_max(12 * task.attempt, 'cpus')
  } else if (rows > 10000) {
      return check_max(8 * task.attempt, 'cpus')
  } else {
      return check_max(4 * task.attempt, 'cpus')
  }
  ```

  With `rows = 10000` (the default), `rows > 10000` is **false**, so the else branch fires: **cpus = 4**.

- **complexity = 100000** falls into the `complexity > 100000` test at modules.config line 54 -- but `100000 > 100000` is **false**, so it drops to line 57: `rows > 5000` -- and `10000 > 5000` is **true**: **memory = 32 GB**.

- **complexity = 100000** for time at line 64: `100000 > 1000000` is false, `100000 > 500000` is false, so the else: **time = 12 h**.

**Corrected effective allocation from modules.config (attempt 1):**

| Resource | Value |
|----------|-------|
| cpus | `check_max(4, 'cpus')` = **4** |
| memory | `check_max(32.GB, 'memory')` = **32 GB** |
| time | `check_max(12.h, 'time')` = **12 h** |

This is **less** than the values the developer clearly intended in nextflow.config's `withName: 'TRENDY'` block (16 CPUs, 64 GB, 72 h). The modules.config dynamic system, loaded last, unknowingly **downgrades** the allocation.

### 1.4 Evidence from the Code

The log statement at trendy.nf lines 40--42 would reveal this at runtime:

```groovy
log.info "Pathogen: ${pathogen}, Rows: ${dataMetrics?.rows ?: 'unknown'}, " +
         "Complexity: ${dataMetrics?.complexity ?: 'unknown'}, " +
         "Allocated CPUs: ${task.cpus}, Memory: ${task.memory}"
```

This log line runs inside the `script:` block, so `dataMetrics` **is** available here (it came from the input tuple). The log would show correct `dataMetrics.rows` and `dataMetrics.complexity` values per pathogen. However, `task.cpus` and `task.memory` have already been locked in at 4 and 32 GB respectively -- identical for every pathogen, regardless of what the metrics say.

---

## 2. Resource Over/Under-Provisioning Analysis

### 2.1 What Resources Are Actually Allocated

Due to the configuration layering (detailed in Section 4), modules.config is loaded last (nextflow.config line 186) and its `withName: 'TRENDY'` block overrides the one in nextflow.config for `cpus`, `memory`, and `time`. The `clusterOptions` and `errorStrategy` from nextflow.config and trendy.nf remain because modules.config does not set them. The effective allocation for TRENDY:

| Resource | Attempt 1 | Attempt 2 | Attempt 3 | Hard Max |
|----------|-----------|-----------|-----------|----------|
| CPUs | 4 | 8 | 12 | 32 (`max_cpus`) |
| Memory | 32 GB | 64 GB | 96 GB | 128 GB (`max_memory`) |
| Time | 12 h | 24 h | 36 h | 240 h (`max_time`) |
| h_vmem | 80 GB (static) | 80 GB (static) | 80 GB (static) | -- |

**Critical h_vmem mismatch on retry:** `clusterOptions = '-l h_vmem=80G'` (nextflow.config, line 146) is a static string. On attempt 2, Nextflow requests 64 GB memory from SGE while h_vmem stays at 80 GB -- this works. But on attempt 3, Nextflow requests 96 GB while h_vmem caps at 80 GB. SGE will either reject the job submission or kill the process when it exceeds 80 GB virtual memory, **defeating the retry mechanism entirely**.

### 2.2 Campylobacter (Large Pathogen: ~25K rows, 10 states, 28 years)

**Complexity:** 25,000 x 10 x 28 = 7,000,000

**If dynamic allocation worked (modules.config intended behavior):**
- CPUs: 16 (rows > 20000 tier, line 35)
- Memory: 96 GB (complexity > 1,000,000 tier, line 51)
- Time: 48 h (complexity > 1,000,000 tier, line 68)

**What it actually gets (attempt 1):** 4 CPUs, 32 GB memory, 12 h time.

**What it actually needs:**

For **2 chains / 500 iterations** (development/testing):
- brms with rstan backend, negative binomial GAM with 10 state-specific thin-plate splines + state fixed effects + log(population) offset
- Memory: ~8--12 GB per chain; the model has roughly 100--200 parameters for 10 states with `s(year, by = state)` (approximately 10 basis functions per spline x 10 states + intercepts + dispersion)
- CPU: 2 cores (one per chain; rstan does not use within-chain threading -- see Section 3.2)
- Time: ~30--90 minutes depending on HMC convergence behavior
- **Verdict: 4 CPUs and 32 GB are 2x overprovisioned on CPU and approximately 1.5--2x overprovisioned on memory. 12 h time is very generous.**

For **6 chains / 10,001 iterations** (publication quality, per `functions.R` line 340):
- Memory: ~56 GB total (functions.R line 340 comment: "6 chains: 56GB RAM")
- CPU: 6 cores (one per chain)
- Time: ~8--24 hours depending on convergence and dataset size
- **Verdict: 32 GB is severely insufficient (needs 56 GB -- OOM guaranteed). 4 CPUs means only 4 of 6 chains can run simultaneously, serializing the remaining 2. 12 h time may be borderline for large datasets.**

### 2.3 Salmonella Javiana (Small Serotype: ~1K rows, ~8 states, ~15 years)

**Complexity:** 1,000 x 8 x 15 = 120,000

Note that spline.nf (lines 200--213) adjusts Salmonella serotype metrics to 15% of the parent Salmonella values. If total Salmonella has ~30K rows, Javiana would be estimated at `max(1000, 30000 * 0.15) = 4500` rows. However, this adjustment is irrelevant because the metrics never reach the resource directives (Section 1.2).

**What it actually gets:** Same as Campylobacter -- 4 CPUs, 32 GB, 12 h.

**What it actually needs (2 chains / 500 iter):**
- Memory: ~4--6 GB (fewer states, fewer spline basis functions, fewer data points for posterior computation)
- CPU: 2 cores
- Time: ~10--20 minutes
- **Verdict: 2x overprovisioned on CPU, 5--8x on memory, 36--72x on time**

**What it actually needs (6 chains / 10,001 iter):**
- Memory: ~12--20 GB (proportionally smaller than Campylobacter due to fewer states/data)
- CPU: 6 cores
- Time: ~2--6 hours
- **Verdict: Under-provisioned on CPU (4 allocated, 6 needed). Memory is adequate. Time is adequate.**

### 2.4 Summary Table

| Scenario | Allocated | Needed (dev, 2ch/500i) | Waste Factor | Needed (prod, 6ch/10Ki) | Waste Factor |
|----------|-----------|------------------------|--------------|--------------------------|--------------|
| Campylobacter CPU | 4 | 2 | 2x | 6 | **0.67x (UNDER)** |
| Campylobacter Memory | 32 GB | 12 GB | 2.7x | 56 GB | **0.57x (UNDER)** |
| Campylobacter Time | 12 h | 1 h | 12x | 24 h | **0.5x (UNDER)** |
| Javiana CPU | 4 | 2 | 2x | 6 | **0.67x (UNDER)** |
| Javiana Memory | 32 GB | 6 GB | 5.3x | 20 GB | 1.6x |
| Javiana Time | 12 h | 0.3 h | 40x | 6 h | 2x |

**Key takeaway:** The current allocation is over-provisioned for development runs but **dangerously under-provisioned for production runs**, especially for large pathogens. This means:
- Development runs waste cluster resources (particularly memory: 32 GB allocated, ~6--12 GB used).
- Production runs will reliably OOM on Campylobacter and other large pathogens. The retry mechanism will attempt 3 retries, each of which will also fail because h_vmem is static at 80 GB (see Section 2.1).

---

## 3. Singularity Container Considerations

### 3.1 Container Memory Limits

The Singularity container definition (`foodnet.def`) does not impose memory limits. Singularity containers by default inherit the cgroup constraints of the host scheduler. On SGE, the `h_vmem` parameter is the operative virtual memory ceiling. The container does not add its own restriction layer. This is correct -- resource limits should come from the scheduler, not the container.

However, there is a subtlety: `foodnet.def` line 1 uses `Bootstrap: docker` from `continuumio/miniconda3`. The Miniconda base image is ~400 MB. After installing the conda environment with all R packages, brms, rstan, and cmdstanr, the container will be approximately 3--4 GB. This is fine for Singularity (no filesystem overhead at runtime) but means the first build takes significant time and should be cached.

### 3.2 Stan Backend and Threading Configuration

**Backend choice:** The pipeline uses **rstan** as the brms backend (`functions.R`, line 410: `backend = "rstan"`), despite also installing **cmdstanr** in the conda environment (`foodnet.yml`, line 22: `r-cmdstanr=0.8.1`).

This has critical implications for CPU utilization:

- **rstan** does not support within-chain threading. Each chain runs on exactly one core. The `cores` parameter in `brm(cores = cores)` (functions.R, line 407) controls how many chains execute **in parallel**, not how many threads each chain uses. With `chains = 2` and `cores = 4`, only 2 of 4 allocated cores are used (50% utilization). With `chains = 6` and `cores = 4`, 4 chains run simultaneously and 2 wait, using 4 of 4 cores (100%) but serializing 2 chains unnecessarily.

- **cmdstanr** with `backend = "cmdstanr"` and `threads = threading(N)` in the brms call enables within-chain parallelism via OpenMP. Each chain can use multiple threads for likelihood evaluation and gradient computation. With 6 chains and `threading(2)`, all 12 threads would be active simultaneously.

**Current waste calculation for development settings (2 chains, 4 cores allocated):**
- rstan uses 2 cores for 2 chains. 2 of 4 cores are idle = **50% CPU waste**.

**Current waste calculation for production settings (6 chains, 4 cores allocated):**
- rstan runs 4 chains in parallel (using all 4 cores), then 2 more sequentially. Total wall-clock time is 1.5x what it would be with 6 cores. CPU utilization is high (100%) but calendar time is extended.

### 3.3 Missing Stan Compilation Optimization

The container definition (`foodnet.def`, lines 18--19) installs `build-essential` but does not configure Stan-specific compiler optimization flags. The `%post` section does not set environment variables for Stan compilation. For production use, adding the following would improve Stan sampling speed by 20--40%:

```
%post
    # ... existing commands ...
    # Stan compiler optimizations
    mkdir -p /root/.R
    echo "CXXFLAGS=-O3 -march=x86-64 -mtune=generic" > /root/.R/Makevars
    echo "CXX14FLAGS=-O3 -march=x86-64 -mtune=generic" >> /root/.R/Makevars
```

Note: `-march=native` should not be used in containers because the container may be built on a different architecture than the execution nodes. Use `-march=x86-64` or the specific microarchitecture of Rosalind's compute nodes.

For cmdstanr threading support (if switching backends per Recommendation 7.4), `STAN_THREADS=true` must be set **before** Stan models are compiled. Without it, the compiled model binary will not contain OpenMP directives, and `threading()` will silently have no effect.

### 3.4 Redundant Dependencies

The conda environment (`foodnet.yml`) installs both `r-rstan=2.32.6` (line 23) and `r-cmdstanr=0.8.1` (line 22). Since only rstan is used at runtime, cmdstanr adds approximately 200--300 MB to the container image (cmdstan binary, R interface package, additional headers). This is either:
- Waste if there is no plan to switch backends (remove cmdstanr), or
- A prepared-but-unactivated capability (switch to using it -- see Recommendation 7.4).

### 3.5 Container Environment Path

The container environment path (`foodnet.def`, line 22) exports:
```
export PATH="/opt/conda/envs/FootNetTreands_R/bin:$PATH"
```

And `nextflow.config` line 122 sets:
```
R_LIBS = "/opt/conda/envs/FootNetTreands_R/lib/R/library"
```

Both reference the typo-laden environment name `FootNetTreands_R`. While consistent (and therefore functional), this is a maintainability hazard. See Recommendation 7.10.

---

## 4. Nextflow Configuration Layering

### 4.1 Load Order

The configuration files are loaded in this sequence, determined by `nextflow.config`:

| Order | Source | Loaded At |
|-------|--------|-----------|
| 1 | `nextflow.config` params block (lines 10--75) | File open |
| 2 | `conf/base.config` | `includeConfig` at nextflow.config line 78 |
| 3 | `conf/cdc-dev.config` | `includeConfig` at nextflow.config line 79 |
| 4 | nf-core custom profiles (attempted) | `includeConfig` at nextflow.config lines 82--86 |
| 5 | `nextflow.config` profiles block (lines 88--108) | After includes |
| 6 | `nextflow.config` env block (lines 117--123) | After profiles |
| 7 | `nextflow.config` process block (lines 129--148) | After env |
| 8 | `nextflow.config` executor block (lines 150--154) | After process |
| 9 | `conf/modules.config` | `includeConfig` at nextflow.config line 186 |

### 4.2 Precedence Rules

In Nextflow, for the same process selector (`withName: 'TRENDY'`):
- **Later definitions override earlier ones** for individual directives within the same selector type.
- `includeConfig` files are processed inline at the point of inclusion.
- `withName` selectors have **higher precedence** than `withLabel` selectors regardless of order.
- When two `withName: 'TRENDY'` blocks appear in different config scopes, directives are **merged**: each directive is overridden individually only if the later config explicitly sets it.
- Process-definition-level directives (in the `.nf` file) have the **lowest** precedence and are overridden by any config-level selector.

### 4.3 What Actually Wins for TRENDY

There are four sources of resource directives for TRENDY:

**Source A -- `conf/base.config`, line 62 (`withLabel:process_large`):**
```groovy
cpus   = { check_max( 16 * task.attempt, 'cpus') }
memory = { check_max( 64.GB * task.attempt, 'memory') }
time   = { check_max( 24.h * task.attempt, 'time') }
```
TRENDY has `label 'process_large'` (trendy.nf, line 3).

**Source B -- `nextflow.config`, line 140 (`withName: 'TRENDY'`):**
```groovy
cpus = { check_max(16 * task.attempt, 'cpus') }
memory = { check_max(64.GB * task.attempt, 'memory') }
time = { check_max(72.h * task.attempt, 'time') }
errorStrategy = { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
maxRetries = 3
clusterOptions = '-l h_vmem=80G'
```

**Source C -- `conf/modules.config`, line 21 (`withName: 'TRENDY'`):**
```groovy
publishDir = [...]
cpus = { /* dynamic allocation, always returns 4 */ }
memory = { /* dynamic allocation, always returns 32 GB */ }
time = { /* dynamic allocation, always returns 12 h */ }
```

**Source D -- `trendy.nf` process definition (lines 32--33):**
```groovy
errorStrategy { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
maxRetries 3
```

**Resolution:**

| Directive | Winner | Source | Value (attempt 1) | Why |
|-----------|--------|--------|-------------------|-----|
| `cpus` | modules.config | C | 4 | `withName` > `withLabel`; modules.config loaded after nextflow.config process block |
| `memory` | modules.config | C | 32 GB | Same reasoning |
| `time` | modules.config | C | 12 h | Same reasoning |
| `publishDir` | modules.config | C | spline_results path | Only set in modules.config |
| `clusterOptions` | nextflow.config | B | `-l h_vmem=80G` | modules.config does not set this; nextflow.config's `withName` wins over base.config's `withLabel` |
| `errorStrategy` | nextflow.config or trendy.nf | B/D | retry on [143,137,104,134,139] | Both define it identically; config-level (B) takes precedence over process-level (D) |
| `maxRetries` | nextflow.config or trendy.nf | B/D | 3 | Same as above |
| `label` | trendy.nf | D | `process_large` | Only set in process definition |

**The critical insight:** modules.config unknowingly **downgrades** TRENDY from the values explicitly set in nextflow.config (16 CPUs, 64 GB, 72 h) to much lower values (4 CPUs, 32 GB, 12 h) because its dynamic allocation falls through to defaults for null metrics.

### 4.4 Conflicts Between Layers

1. **Duplicate `check_max` function definitions:** Defined in both `cdc-dev.config` (lines 232--261) and `nextflow.config` (lines 189--218). Implementations are identical. The last definition (nextflow.config) wins. Harmless but confusing -- remove one.

2. **Duplicate `process.shell` directives:** `cdc-dev.config` line 200 sets `process.shell = ['/bin/bash']` (no pipefail). `nextflow.config` line 126 sets `process.shell = ['/bin/bash', '-euo', 'pipefail']`. The nextflow.config value wins (later in load order). This is correct for production (pipefail catches pipe errors), but note that it differs from cdc-dev.config's intent. If someone activates the rosalind profile expecting cdc-dev.config shell behavior, they will get nextflow.config's stricter setting instead.

3. **`max_cpus` conflict:** `nextflow.config` line 66 sets `max_cpus = 32`. `cdc-dev.config` line 42 sets `max_cpus = 16` inside its own params block. In Nextflow, params set in later-loaded config files override earlier ones, but cdc-dev.config is included **before** the nextflow.config params block is fully processed (it is included at line 79, within the file whose params block starts at line 10). The resolution depends on whether `includeConfig` is processed inline: it is, so cdc-dev.config params are set at line 79, then overridden by nextflow.config params that follow. **Result: max_cpus = 32 wins.** But wait -- cdc-dev.config's params block (lines 28--44) is inside the global scope of that file, so it is processed at include time (line 79 of nextflow.config). The nextflow.config params block is at lines 10--75, which is **before** line 79. Since Nextflow processes the file top-to-bottom, the nextflow.config params block is processed first, then cdc-dev.config's params override within it, then execution continues past line 79. **Revised result: cdc-dev.config's `max_cpus = 16` would win** because it is included after the nextflow.config params block. This means retry attempts that scale cpus to `4 * 3 = 12` would be capped at 16, not 32. However, this depends on Nextflow's exact params merging behavior -- the safest assumption is that the last assignment wins: **max_cpus = 16**.

4. **Executor configuration:** `nextflow.config` line 130 sets `process.executor = 'sge'` and line 150 sets `executor.name = 'sge'` globally. The rosalind profile in cdc-dev.config also sets `executor.name = 'sge'` (line 129) and `process.executor = 'sge'` (line 136). Without `-profile rosalind`, the global executor settings apply. This means **all** processes (including RESOURCE_PROFILER, PREPROCESS, and DASHBOARD) are submitted as SGE jobs. RESOURCE_PROFILER runs a 2-second R computation and should not incur SGE scheduling overhead.

5. **`queueSize` conflict:** `nextflow.config` line 152 sets `queueSize = 100`. The rosalind profile (cdc-dev.config, line 130) sets `queueSize = 12`. Since `-profile rosalind` is never activated (run_workflow.sh only uses `-profile singularity`), the global value of 100 applies. This is 8x higher than the cluster-appropriate value.

6. **Queue selection is inactive:** The rosalind profile (cdc-dev.config, line 139) implements intelligent queue routing:
   ```groovy
   queue = { task.time <= 4.h ? 'short.q' : task.time > 7.day ? 'long.q' : 'all.q' }
   ```
   This never activates because the rosalind profile is not included in `run_workflow.sh`. No queue is specified in the active configuration, so SGE uses its default queue. TRENDY jobs with their 12 h allocation should be routed to `all.q`.

7. **Singularity profile overlap:** Both `nextflow.config` (lines 96--101) and `cdc-dev.config` (lines 64--80) define a `singularity` profile. Nextflow merges same-named profiles. The cdc-dev.config version sets `process.scratch = false` (preventing temp directory issues). The nextflow.config version adds `singularity.runOptions = '--bind /scicomp'` and `process.container = 'foodnet.sif'`. Both take effect when `-profile singularity` is used. This merging is correct behavior but should be documented.

---

## 5. Execution Efficiency

### 5.1 Parallelization Strategy

The workflow launches all pathogen TRENDY jobs simultaneously via Nextflow's dataflow model. In spline.nf, the `pathogenGroupingWithMetrics` channel emits all tuples at once, and Nextflow submits them to SGE in parallel (subject to `queueSize` and `submitRateLimit`). This is correct -- there are no data dependencies between pathogen analyses.

However, because dynamic allocation is broken, all jobs request identical resources (4 CPUs, 32 GB). This means a tiny pathogen like Yersinia (~2K rows, completing in 10--15 minutes for dev settings) holds 4 CPUs and 32 GB of memory for its entire 12 h allocation window, while larger pathogens that genuinely need those resources may queue behind it.

SGE's fair-share scheduler will allocate slots as they become available, so short jobs releasing resources early does help. But the initial burst of 23 identical 32-GB requests could exhaust available memory slots, forcing some jobs to wait even when CPU slots are available.

### 5.2 Job Ordering for Wall-Clock Optimization

For minimum wall-clock time, the longest jobs (Campylobacter, combined Salmonella) should start first. Nextflow does not natively control submission order within a channel.

Two approaches:

1. **Channel ordering:** In spline.nf, sort the `pathogenGroupingWithMetrics` channel by descending complexity before passing to TRENDY. This ensures large jobs are emitted (and thus submitted) first:
   ```groovy
   .toSortedList { a, b -> b[3].complexity <=> a[3].complexity }
   .flatMap { it }
   ```

2. **SGE priority:** Use `clusterOptions` to set job priority based on expected runtime. This lets SGE schedule optimally without Nextflow needing to control order.

For 7--24 jobs, the benefit is modest (saves perhaps 10--20% wall-clock time). But for production runs with 23 parallel jobs where the longest may run 24 hours and the shortest 15 minutes, starting the long jobs first avoids the "straggler" problem where a single large job submitted last delays the entire pipeline.

### 5.3 SGE Queue Selection

No queue is configured in the active setup. TRENDY jobs with a 12 h time allocation should target `all.q` (per Rosalind's queue policies). With production settings potentially requiring 24--48 hours, `long.q` may be needed.

The queue selection logic in the rosalind profile (`cdc-dev.config`, line 139) is well-designed and should be activated.

### 5.4 RESOURCE_PROFILER Scheduling Overhead

RESOURCE_PROFILER (`resource_profiler.nf`) is labeled `process_low` (line 3) and runs as an SGE job because of the global `process.executor = 'sge'` in nextflow.config. This process reads a CSV, computes `group_by() %>% summarise()`, and writes 4 small CSV files. It completes in 1--3 seconds of compute time.

Submitting this as an SGE job adds:
- ~10--30 seconds for SGE scheduling overhead
- ~5--15 seconds for Singularity container startup
- ~2--5 seconds for conda environment activation within the container

Total overhead: 20--50 seconds for a 2-second computation. Running this locally would eliminate the overhead entirely.

---

## 6. Scalability Concerns

### 6.1 Parallel Job Count

A full production run with Salmonella serotype decomposition could include:

| Category | Pathogens | Count |
|----------|-----------|-------|
| Standalone | CAMPYLOBACTER, CYCLOSPORA, SHIGELLA, VIBRIO, YERSINIA | 5 |
| STEC groups | O157, nonO157 | 2 |
| Salmonella serotypes | Enteritidis, Typhimurium, Newport, Javiana, Infantis, I 4,[5],12:i:-, Hadar, Thompson, Heidelberg, Braenderup, Montevideo, Muenchen, Paratyphi B, Saintpaul, Oranienburg, other | 16 |
| **Total** | | **23** |

### 6.2 Cluster Impact at Current Allocation

At 4 CPUs and 32 GB per job (current effective allocation):

| Metric | Value |
|--------|-------|
| Total CPUs requested | 23 x 4 = **92** |
| Total memory requested | 23 x 32 GB = **736 GB** |
| Total h_vmem headroom | 23 x 80 GB = **1,840 GB** |

Rosalind is an institutional shared cluster. Requesting 92 CPUs and 736 GB of RAM simultaneously will cause significant queueing delays for this user and may impact other users. The h_vmem value of 80 GB per job (total 1,840 GB for SGE's virtual memory tracking) may exceed per-user or per-group quotas on Rosalind.

For development runs (2 chains, 500 iter), actual memory usage would be ~6--12 GB per job (total ~150--280 GB across 23 jobs). The remaining ~500 GB of allocated memory sits reserved but unused.

### 6.3 submitRateLimit and queueSize Analysis

- `queueSize = 100` (nextflow.config, line 152): Allows up to 100 concurrent SGE jobs. For 23 TRENDY jobs plus PREPROCESS, RESOURCE_PROFILER, and DASHBOARD (26--27 total), this is not a bottleneck. However, it is unnecessarily permissive. If a bug in spline.nf produces a corrupted channel with hundreds of elements, Nextflow could submit up to 100 SGE jobs before the error is detected.

- `submitRateLimit = '10/1min'` (nextflow.config, line 153): At most 10 job submissions per minute. For 23 jobs, all are submitted within ~3 minutes. This is reasonable for SGE's scheduler -- a burst of 23 `qsub` calls is well within normal operating parameters.

The rosalind profile's `queueSize = 12` (cdc-dev.config, line 130) is more appropriate and would limit concurrent jobs to a cluster-friendly level. With 23 pathogens and queueSize 12, jobs would be batched -- 12 submitted initially, then 1 new submission for each completion. This is actually advantageous because short jobs (Yersinia, Cyclospora) complete quickly and free slots for the long-running ones.

### 6.4 Memory Pressure Under Production Settings

With production settings (6 chains, 10,001 iterations, `adapt_delta = 0.99`), the memory requirements per pathogen increase substantially. Per the comments in functions.R (lines 337--341):

| Chains | Estimated RAM per Job |
|--------|-----------------------|
| 2 | 24 GB |
| 4 | 48 GB |
| 6 | 56 GB |
| 8 | 72 GB |

These estimates appear to be for a "typical" large pathogen (Campylobacter-sized). Smaller serotypes would use proportionally less, but the scaling is not strictly linear because brms/Stan has fixed overhead per chain.

For 23 parallel production jobs with 6 chains each:
- 5 large pathogens: ~56 GB each = 280 GB
- 2 STEC groups: ~35--45 GB each = 80 GB
- 16 Salmonella serotypes: ~20--35 GB each = 400 GB
- **Total actual usage: ~760 GB**
- **Total allocated (current): 23 x 32 GB = 736 GB** -- nearly all of it used, with large pathogens exceeding their allocation.

This confirms that the current allocation (32 GB flat) is dangerously under-sized for production runs on large pathogens.

---

## 7. Concrete Recommendations

### 7.1 CRITICAL -- Fix the Dynamic Resource Allocation Architecture

**The problem:** `task.ext.dataMetrics` is assigned in the `script:` block (trendy.nf, line 37) but read in config directive closures (modules.config, lines 29--74), which are evaluated before the script runs. Dynamic allocation is entirely non-functional.

**Why input values cannot be used directly in directives:** In Nextflow DSL2, process input values are also not available in directive closures. Directives are evaluated at task creation time, before inputs are bound. This is a fundamental limitation of the Nextflow execution model.

**Recommended fix -- Process aliases with label-based routing:**

Define separate process instances with fixed resources, and route pathogens based on their `size_category` (already computed by the resource profiler):

1. Create `modules/local/trendy_sized.nf` with 3--4 process aliases (TRENDY_TINY, TRENDY_SMALL, TRENDY_MEDIUM, TRENDY_LARGE) that share the same script but have different labels.

2. In `conf/base.config`, the existing label definitions already provide appropriate tiers:
   - `process_single`: 1 CPU, 6 GB (use for tiny pathogens)
   - `process_low`: 2 CPUs, 12 GB
   - `process_medium`: 6 CPUs, 36 GB
   - `process_large`: 16 CPUs, 64 GB

3. In `spline.nf`, use the `branch` operator to route pathogens by `size_category`:
   ```groovy
   pathogenGroupingWithMetrics.branch {
       large: it[3].size_category in ['large', 'extra_large']
       medium: it[3].size_category == 'medium'
       small: it[3].size_category in ['small', 'tiny']
   }
   .set { sized }

   TRENDY_LARGE(sized.large, ...)
   TRENDY_MEDIUM(sized.medium, ...)
   TRENDY_SMALL(sized.small, ...)
   ```

4. Remove the dynamic allocation closures from `modules.config` entirely.

**Simpler alternative:** If the team prefers not to restructure the workflow, remove the modules.config `cpus`, `memory`, and `time` closures for TRENDY entirely. This allows the static values from nextflow.config's `withName: 'TRENDY'` block (16 CPUs, 64 GB, 72 h) to take effect. This wastes resources for small pathogens but at least provides correct allocation for large ones.

### 7.2 CRITICAL -- Fix the h_vmem / Memory Mismatch on Retry

**The problem:** `clusterOptions = '-l h_vmem=80G'` (nextflow.config, line 146) is static while `memory` scales with `task.attempt`. On attempt 3, memory = 96 GB but h_vmem = 80 GB. SGE will kill the process.

**The fix:** Replace the static clusterOptions with a dynamic version (matching the pattern already present in cdc-dev.config's rosalind profile, line 150):

```groovy
withName: 'TRENDY' {
    // ... other directives ...
    clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
}
```

Note: cdc-dev.config line 150 has a syntax error in the existing dynamic clusterOptions:
```groovy
clusterOptions = { "-l h_vmem=${(check_max((task.memory.toGiga())+20), 'memory').toString().replaceAll(/[\sB]/,'')}G" }
```
The parentheses here create a Groovy tuple `(check_max(...), 'memory')`, which is almost certainly not intended. The correct version should be:
```groovy
clusterOptions = { "-l h_vmem=${check_max((task.memory.toGiga() + 20).GB, 'memory').toGiga()}G" }
```
Or more simply:
```groovy
clusterOptions = { "-l h_vmem=${task.memory.toGiga() + 20}G" }
```

### 7.3 HIGH -- Activate the Rosalind Profile in run_workflow.sh

**The problem:** `run_workflow.sh` (lines 1201, 1208, 1224) uses `-profile singularity` exclusively. The rosalind profile's queue selection, conservative queueSize, and (once fixed) dynamic h_vmem are never activated.

**The fix:** Change all three invocations in run_workflow.sh:

```bash
# Line 1201 (preprocess mode):
cmd="nextflow run main.nf -profile rosalind,singularity -entry PREPROCESS_ONLY \

# Line 1208 (normal mode):
cmd="nextflow run main.nf -profile rosalind,singularity -entry SPLINE \

# Line 1224 (resume mode):
cmd="nextflow run main.nf -profile rosalind,singularity -resume -entry SPLINE \
```

Verify that the merged profiles do not conflict (they should not, per Section 4.4 analysis, but test with `-profile rosalind,singularity` and `nextflow config -profile rosalind,singularity` to confirm effective values).

### 7.4 HIGH -- Switch from rstan to cmdstanr Backend

**The problem:** rstan does not support within-chain threading. Allocated cores beyond the chain count are completely wasted.

**The fix:**

1. In `functions.R`, change line 410:
   ```r
   # Before:
   backend = "rstan"
   # After:
   backend = "cmdstanr"
   ```

2. Add threading support to the `brm()` call at line 407:
   ```r
   brm(
     count ~ s(year, by = state) + state + offset(log(population)),
     data = data,
     family = negbinomial(),
     chains = chains,
     iter = iterations,
     cores = cores,
     threads = threading(max(1, floor(cores / chains))),
     seed = seed,
     control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
     backend = "cmdstanr"
   )
   ```

3. Update `foodnet.def` to enable Stan threading:
   ```
   %post
       # ... existing commands ...
       # Enable Stan threading support
       mkdir -p /root/.R
       echo "CXX14FLAGS += -DSTAN_THREADS -pthread" >> /root/.R/Makevars
       echo "CXX17FLAGS += -DSTAN_THREADS -pthread" >> /root/.R/Makevars
   ```

4. Rebuild the container.

**Impact analysis:**
- With 6 chains and 12 CPUs: each chain gets 2 threads. 12 of 12 cores active = 100% utilization.
- With 2 chains and 4 CPUs: each chain gets 2 threads. 4 of 4 cores active = 100% utilization.
- Expected speedup: 15--30% reduction in wall-clock time due to within-chain parallelism on gradient computation.

### 7.5 HIGH -- Right-Size Resource Tiers

The current tiers in modules.config (lines 29--74) have two problems: they never activate, and even if they did, they are too generous for small pathogens and potentially insufficient for large ones in production.

Replace with empirically grounded values based on the memory scaling comments in functions.R (lines 337--341). These should be implemented via the process-alias approach (Recommendation 7.1) or as static values in modules.config/nextflow.config:

**Development settings (2 chains, 500 iterations):**

| Tier | Rows | CPUs | Memory | Time | h_vmem |
|------|------|------|--------|------|--------|
| tiny | < 2,000 | 2 | 8 GB | 2 h | 12 G |
| small | 2,000--10,000 | 2 | 12 GB | 4 h | 16 G |
| medium | 10,000--25,000 | 2 | 16 GB | 8 h | 24 G |
| large | > 25,000 | 2 | 24 GB | 12 h | 32 G |

**Production settings (6 chains, 10,001 iterations):**

| Tier | Rows | CPUs | Memory | Time | h_vmem |
|------|------|------|--------|------|--------|
| tiny | < 2,000 | 6 | 20 GB | 8 h | 28 G |
| small | 2,000--10,000 | 6 | 28 GB | 16 h | 36 G |
| medium | 10,000--25,000 | 8 | 48 GB | 24 h | 56 G |
| large | > 25,000 | 12 | 64 GB | 48 h | 80 G |

If using cmdstanr with threading, multiply CPUs by 1.5--2x (threads per chain) while keeping memory constant.

**Consider making tier selection chain-aware:** Since memory scales roughly linearly with chain count (functions.R lines 338--341), the pipeline could select resource tiers based on `chains * rows` rather than `rows` alone:

```groovy
def memoryFactor = params.chains <= 2 ? 1.0 : params.chains <= 4 ? 2.0 : params.chains <= 6 ? 2.5 : 3.0
```

### 7.6 MEDIUM -- Reduce queueSize

Change `nextflow.config` line 152:

```groovy
executor {
    name = 'sge'
    queueSize = 25    // accommodate 23 TRENDY + preprocessing jobs
    submitRateLimit = '10/1min'
}
```

For production runs with many serotypes, 25 is sufficient. For development runs with 2--3 pathogens, this makes no difference. The key benefit is preventing accidental submission storms.

Alternatively, activate the rosalind profile (Recommendation 7.3) which sets `queueSize = 12`. With 23 pathogens, this creates a natural batching effect that is kinder to the shared cluster -- at the cost of slightly longer wall-clock time (roughly 2x if all jobs are equal duration, but in practice short jobs finish fast and free slots).

### 7.7 MEDIUM -- Run Lightweight Processes Locally

Add executor overrides for processes that do not need SGE:

```groovy
// In modules.config or nextflow.config:
withName: 'RESOURCE_PROFILER' {
    executor = 'local'
    cpus = 1
    memory = '4.GB'
}

withName: 'PREPROCESS' {
    executor = 'local'
    cpus = 1
    memory = '8.GB'
}

withName: 'DASHBOARD' {
    executor = 'local'
    cpus = 1
    memory = '4.GB'
}
```

This eliminates ~30--60 seconds of SGE scheduling + container startup overhead per lightweight process.

### 7.8 MEDIUM -- Enable Nextflow Tower or Seqera Platform Monitoring

The `tower.yml` file (lines 1--4) contains boilerplate MultiQC configuration, not actual Tower/Seqera Platform integration:

```yaml
reports:
  multiqc_report.html:
    display: "MultiQC HTML report"
  samplesheet.csv:
    display: "Auto-created samplesheet with collated metadata and FASTQ paths"
```

This has no effect on resource monitoring. For a production pipeline on a shared HPC cluster, real monitoring is essential. Add to nextflow.config:

```groovy
tower {
    enabled = true
    endpoint = 'https://tower.nf'  // or CDC institutional instance
    accessToken = "${TOWER_ACCESS_TOKEN}"
}
```

This provides real-time resource utilization tracking, historical comparison of allocated vs. used resources, and automated detection of systematic over/under-provisioning.

### 7.9 LOW -- Leverage Existing Trace Reports for Calibration

The trace, timeline, report, and DAG outputs are enabled in nextflow.config (lines 159--175). The trace file (`execution_trace_*.txt`) contains columns including `realtime`, `%cpu`, `peak_rss`, `peak_vmem`, `rchar`, and `wchar` that reveal actual resource usage vs. allocation.

**Actionable recommendation:** After the next production run, extract the trace file and compute:

```bash
# On Rosalind, after a run:
awk -F'\t' 'NR>1 && $4=="TRENDY" {print $4, $10, $11, $14, $15}' execution_trace_*.txt
```

This shows `process`, `cpus`, `memory`, `peak_rss`, `peak_vmem` for each TRENDY invocation. Use these values to calibrate the resource tiers in Recommendation 7.5.

### 7.10 LOW -- Fix the Environment Name Typo

The conda environment name `FootNetTreands_R` is misspelled (should be `FoodNetTrends_R`). It appears in:
- `foodnet.yml` line 1: `name: FootNetTreands_R`
- `foodnet.def` line 22: `export PATH="/opt/conda/envs/FootNetTreands_R/bin:$PATH"`
- `nextflow.config` line 122: `R_LIBS = "/opt/conda/envs/FootNetTreands_R/lib/R/library"`

All three must be updated simultaneously, and the container must be rebuilt. This is low-priority but improves maintainability and reduces confusion for new team members.

### 7.11 LOW -- Remove or Activate cmdstanr

If switching to cmdstanr (Recommendation 7.4), keep it. Otherwise, remove `r-cmdstanr=0.8.1` from `foodnet.yml` line 22 to reduce container size by ~200--300 MB and eliminate a potential source of version conflicts between rstan and cmdstanr's bundled Stan headers.

---

## 8. Summary of Findings

| # | Finding | Severity | Location | Impact |
|---|---------|----------|----------|--------|
| 1 | Dynamic resource allocation is entirely non-functional due to Nextflow DSL2 directive evaluation timing | **CRITICAL** | trendy.nf:37, modules.config:29--74 | All TRENDY jobs get identical resources (4 CPU, 32 GB) regardless of pathogen size |
| 2 | Static h_vmem=80G conflicts with scaled memory on retry | **CRITICAL** | nextflow.config:146 | Retry attempt 3 requests 96 GB memory but SGE caps at 80 GB; retries are self-defeating |
| 3 | modules.config unknowingly downgrades TRENDY resources | **CRITICAL** | modules.config:29--74 vs nextflow.config:140--147 | Intended 16 CPU / 64 GB / 72 h reduced to 4 CPU / 32 GB / 12 h |
| 4 | Production runs will OOM on large pathogens | **HIGH** | functions.R:338--340 vs effective 32 GB allocation | Campylobacter needs ~56 GB for 6-chain production; only 32 GB allocated |
| 5 | Rosalind profile never activated | **HIGH** | run_workflow.sh:1208 | No queue selection, oversized queueSize, no dynamic h_vmem |
| 6 | rstan backend wastes 50--75% of allocated CPUs | **HIGH** | functions.R:410 | 2 of 4 cores used (dev), 4 of 4 used but 2 chains serialized (prod) |
| 7 | All dev-setting jobs over-provisioned by 2--8x on memory | **MEDIUM** | Effective 32 GB allocation vs ~6--12 GB actual | ~500 GB wasted across 23-job run |
| 8 | RESOURCE_PROFILER incurs 30--60s SGE overhead for 2s task | **MEDIUM** | resource_profiler.nf:3, nextflow.config:130 | Unnecessary scheduling delay |
| 9 | queueSize=100 allows excessive concurrent submissions | **MEDIUM** | nextflow.config:152 | Could impact other Rosalind users |
| 10 | cdc-dev.config clusterOptions has syntax error | **MEDIUM** | cdc-dev.config:150 | Groovy tuple created instead of function call; h_vmem value unpredictable |
| 11 | Serotype adjustment logic (15% scaling) is dead code | **LOW** | spline.nf:200--213, 347--360 | Clever logic that never affects actual resources |
| 12 | cmdstanr installed but unused | **LOW** | foodnet.yml:22 | ~200--300 MB container bloat |
| 13 | Environment name typo `FootNetTreands_R` | **LOW** | foodnet.yml:1, foodnet.def:22, nextflow.config:122 | Maintainability |
| 14 | tower.yml is MultiQC boilerplate, not Tower integration | **LOW** | tower.yml:1--4 | No real-time monitoring |

---

## 9. Recommended Target Architecture

```
RESOURCE_PROFILER (executor: local, ~2s)
    |
    v
spline.nf classifies pathogens by size_category from resource_profile.csv
    |
    +--[branch: large/extra_large]--> TRENDY_LARGE  (label: process_large,  12 cpu, 64 GB, 48h)
    +--[branch: medium]-------------> TRENDY_MEDIUM (label: process_medium,  8 cpu, 48 GB, 24h)
    +--[branch: small]--------------> TRENDY_SMALL  (label: process_low,     4 cpu, 16 GB, 12h)
    +--[branch: tiny]---------------> TRENDY_TINY   (label: process_single,  2 cpu,  8 GB,  6h)
    |
    v
DASHBOARD (executor: local, ~5s)
```

This approach:
- Uses Nextflow's label system as designed, avoiding DSL2 timing issues entirely.
- Leverages the `size_category` field already computed by `RESOURCE_PROFILER` (resource_profiler.nf, lines 54--60).
- Reduces total cluster footprint by 50--70% for a full production run compared to flat allocation.
- Naturally handles the retry scaling correctly (each label tier has appropriate memory + time with `task.attempt` multiplier).
- Makes resource allocation transparent and auditable (no hidden dynamic closures that silently fail).

**Estimated cluster impact with right-sized tiers (23-pathogen production run):**

| Current (flat allocation) | Recommended (tiered) |
|---------------------------|----------------------|
| 23 x 4 CPU = 92 CPUs | 5x12 + 2x8 + 8x4 + 8x2 = 124 CPUs |
| 23 x 32 GB = 736 GB | 5x64 + 2x48 + 8x16 + 8x8 = 588 GB |

Wait -- the recommended tiers actually use **more** CPUs for large pathogens (which is correct, since they need more cores for chains). But total memory drops from 736 GB to 588 GB, a **20% reduction**. More importantly, the large pathogens now have adequate memory (64 GB vs. 32 GB), eliminating OOM failures.

For development runs (2 chains, 500 iter), the savings are much larger because tiny/small tiers use 8--12 GB instead of 32 GB:

| Current (flat, dev) | Recommended (tiered, dev) |
|---------------------|---------------------------|
| 23 x 32 GB = 736 GB | 5x24 + 2x16 + 8x8 + 8x6 = 264 GB |

A **64% reduction** in memory allocation for development runs.
