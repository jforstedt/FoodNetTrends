# publishDir Bug Analysis for TRENDY Process

## Problem Statement

TSV and PNG files from the TRENDY process end up in `output/spline_results/` instead of
`output/{projID}/spline_results/`. CSV files go to the correct location. Subsequent runs
overwrite previous results because the projID is missing from the path.

## Root Cause: Three Competing publishDir Definitions

There are **three** `publishDir` directives that apply to the TRENDY process, coming from
different configuration sources. Nextflow DSL2 **merges** (accumulates) publishDir
directives from the process script and from config selectors -- it does NOT use
last-one-wins for publishDir specifically. The result is that each output file may be
published by **multiple** publishDir rules simultaneously.

### publishDir #1 -- Process-level (trendy.nf line 7)

```groovy
publishDir "${params.outdir}/${projID}/spline_results", mode: 'copy'
```

- Uses the **input val `projID`** (a process input variable), not `params.projID`.
- This is the correct publishDir -- it resolves to e.g. `output/dashboard_test/spline_results`.
- It applies to **all** output files (no pattern filter).

### publishDir #2 -- Default process block (modules.config lines 15-19)

```groovy
publishDir = [
    path: { "${params.outdir}/${task.process.tokenize(':')[-1].tokenize('_')[0].toLowerCase()}" },
    mode: params.publish_dir_mode,
    saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
]
```

- For process `SPLINE:TRENDY`, `task.process.tokenize(':')[-1]` = `TRENDY`,
  then `.tokenize('_')[0]` = `TRENDY`, then `.toLowerCase()` = `trendy`.
- This resolves to: **`output/trendy`**
- The `saveAs` closure returns `null` only for `versions.yml`; everything else passes through.
- This applies to **all** output files (no pattern filter).

### publishDir #3 -- withName 'TRENDY' block (modules.config lines 21-25)

```groovy
withName: 'TRENDY' {
    publishDir = [
        path: { "${params.outdir}/${params.projID}/spline_results" },
        mode: params.publish_dir_mode,
        saveAs: { filename -> filename.equals('versions.yml') ? null : filename }
    ]
}
```

- Uses `params.projID`, resolving to e.g. `output/dashboard_test/spline_results`.
- This is the intended correct path.
- It applies to **all** output files (no pattern filter).

## How Nextflow Resolves Multiple publishDir Directives

In Nextflow DSL2, the **config-level** publishDir (from `withName` selectors in config files)
**overrides** the process-level publishDir declared in the `.nf` script file. This is the
standard config-over-script precedence rule.

However, multiple config-level `publishDir` directives applied through **different selector
mechanisms** interact in a specific way:

1. The **default process block** (modules.config lines 15-19) sets publishDir for ALL processes.
2. The **withName: 'TRENDY' block** (modules.config lines 21-25) sets publishDir specifically
   for TRENDY.

**Critical Nextflow behavior**: When a `withName` selector assigns `publishDir = [...]`
(a single map), it **replaces** the default process-level publishDir from the same config
scope. So within `modules.config`, the withName block's publishDir should override the
default block's publishDir.

BUT there is **also** a publishDir in the process script itself (`trendy.nf` line 7).
In Nextflow DSL2:
- Config-defined publishDir (`withName` in modules.config) takes **precedence over**
  process-script-defined publishDir (`trendy.nf` line 7).
- When config sets `publishDir = [single map]`, it replaces the script-level publishDir
  entirely.

So the **expected** effective publishDir should be only #3 (the withName block from
modules.config). This would publish everything to `output/{projID}/spline_results/`.

## The Actual Bug: `nextflow.config` Has a Second `process` Block

The file `nextflow.config` (lines 129-148) contains its own `process` block with a
`withName: 'TRENDY'` selector:

```groovy
process {
    executor = 'sge'
    penv = 'smp'
    // ...
    withName: 'TRENDY' {
        cpus = { check_max(16 * task.attempt, 'cpus') }
        memory = { check_max(64.GB * task.attempt, 'memory') }
        time = { check_max(72.h * task.attempt, 'time') }
        errorStrategy = { task.exitStatus in [143,137,104,134,139] ? 'retry' : 'finish' }
        maxRetries = 3
        clusterOptions = '-l h_vmem=80G'
    }
}
```

This block does **not** define a `publishDir`, but it IS a `withName: 'TRENDY'` selector.

**Config loading order** (from `nextflow.config`):
1. Line 78: `includeConfig 'conf/base.config'` -- loaded first
2. Line 79: `includeConfig 'conf/cdc-dev.config'` -- loaded second
3. Lines 129-148: inline `process` block in `nextflow.config` -- loaded third
4. Line 186: `includeConfig 'conf/modules.config'` -- loaded **last**

Since `modules.config` is loaded last, its `withName: 'TRENDY'` publishDir definition
should be the final authority. The `nextflow.config` inline `withName: 'TRENDY'` does not
set publishDir, so it should not interfere.

## The Real Culprit: Process-Script publishDir + Config publishDir Merging

Here is where the bug actually lives. Let me re-examine:

The process script (`trendy.nf` line 7) declares:
```groovy
publishDir "${params.outdir}/${projID}/spline_results", mode: 'copy'
```

And `modules.config` withName block declares:
```groovy
publishDir = [
    path: { "${params.outdir}/${params.projID}/spline_results" },
    ...
]
```

In Nextflow DSL2, config publishDir **replaces** the script publishDir when config uses
`publishDir = [...]` (assignment syntax). So the script-level publishDir should be ignored.

**However**, the default process block in `modules.config` (lines 15-19) also sets publishDir.
The question is whether the withName block's publishDir assignment replaces ONLY the default
block's publishDir, or if both apply.

In Nextflow's config resolution:
- **Within the same `process {}` block**, a `withName` selector's `publishDir` replaces the
  top-level `publishDir` for matching processes. They do NOT accumulate.
- The withName publishDir is the one that takes effect.

So the effective publishDir for TRENDY should be:
`${params.outdir}/${params.projID}/spline_results` (from the withName block in modules.config)

## Revised Analysis: The `projID` Variable Difference

Wait -- there is a subtle but critical difference between the two "correct" publishDir paths:

- **trendy.nf line 7**: `${params.outdir}/${projID}/spline_results` -- uses `projID` (the
  **input val**, a process input variable)
- **modules.config line 23**: `${params.outdir}/${params.projID}/spline_results` -- uses
  `params.projID` (the **global parameter**)

If config publishDir fully replaces the script publishDir, then only `params.projID` is used,
which should be fine since it's set to `dashboard_test` in the command line.

**But the user says TSV and PNG files go to `output/spline_results/`** -- note that the
`projID` segment is missing entirely, not just wrong. This means something is resolving
the path as `${params.outdir}/spline_results` with no projID in between.

This points to a scenario where:
- `projID` (the input val) is empty/null in some context, OR
- Some publishDir path evaluates with `params.projID` being empty

Looking at the log, `params.projID` = `dashboard_test` -- that's set and non-empty.

## The Most Likely Explanation

After careful analysis, the most likely root cause is that **the process-script publishDir
in `trendy.nf` line 7 is NOT being fully overridden by the config**, and it is the one
producing the bad path.

Here's why: The `trendy.nf` publishDir uses `${projID}` -- a reference to the process input
`val projID`. But publishDir closures in Nextflow are evaluated in a **config context**, not
in the process script context. When the process-script publishDir is a plain string (not a
closure), it gets evaluated at process definition time.

However, `publishDir "${params.outdir}/${projID}/spline_results"` uses GString interpolation.
At the time the process is being defined/configured, `projID` is **not yet available** (it's
a runtime input). In Nextflow DSL2:
- If the publishDir is a GString in the process script, `projID` may resolve to `null` at
  definition time, producing: `output/null/spline_results` or `output//spline_results`
  (which the filesystem may normalize to `output/spline_results`).

**This is the bug.** The process-script publishDir uses a runtime input variable (`projID`)
in a context where it's evaluated before the input is available, causing it to resolve to an
empty/null value.

Meanwhile, the config-level publishDir (modules.config withName block) uses `params.projID`
which IS available at config evaluation time, so it resolves correctly.

If both publishDir directives are active (merged rather than replaced), then:
- The config publishDir publishes files to `output/dashboard_test/spline_results/` (correct)
- The script publishDir publishes files to `output//spline_results/` or
  `output/null/spline_results` (incorrect)

Files end up in both locations, and the user sees the wrong-path copies.

## Why CSVs Appear Correct but TSVs/PNGs Don't

This could be explained if:
1. All files are actually published to BOTH locations, but the user only noticed the
   wrong-path copies for TSV/PNG files.
2. Or, the TRENDY process doesn't actually output TSV files in its declared outputs (looking
   at the output block: it declares `.csv`, `.png`, `.Rds`, `.txt` -- no `.tsv`). The TSV
   files might be produced by the R script but not captured as named outputs. If they're
   leftover in the work directory and a different publishing mechanism picks them up, that
   could explain the discrepancy.

Looking at the process outputs in `trendy.nf`:
- `*_brm.Rds` (emit: rds)
- `*_IRCatch.csv` (emit: csv)
- `*_IRSite.csv` (emit: irsite)
- `*.png` (emit: png)
- `*_EstIRRCatch_*.csv` (emit: irr)
- `*_summary.txt` (emit: summary)
- `*_error.txt` (emit: errors)

There are no TSV outputs declared. If TSV files are being published, they must be coming
from a different mechanism or the user may be referring to TXT files.

## Fix

### The Correct Fix: Remove the process-script publishDir from `trendy.nf`

The publishDir on **line 7 of `trendy.nf`** must be removed. The config-level publishDir in
`modules.config` (withName: 'TRENDY' block, line 21-25) is the correct and sole authority
for publishing.

**File**: `/mnt/c/Users/User/Downloads/FoodNetTrends-sb_updates/modules/local/trendy.nf`
**Line 7**: Delete this line:
```groovy
    publishDir "${params.outdir}/${projID}/spline_results", mode: 'copy'
```

### Why This Fixes the Problem

1. Removes the process-script publishDir that uses the runtime input `projID` (which may
   not resolve correctly at publishDir evaluation time).
2. Leaves only the config-level publishDir from `modules.config` withName block, which uses
   `params.projID` -- a global parameter that is always available and correctly set.
3. Eliminates the dual-publish scenario where files end up in two locations.

### Additional Recommendation: Verify the Default publishDir Doesn't Interfere

The default process publishDir in `modules.config` lines 15-19 resolves to `output/trendy/`
for the TRENDY process. Confirm that the withName block's publishDir properly overrides this
default. If files are also appearing in `output/trendy/`, then the default block is leaking
through.

To be extra safe, you could also add `pattern` filters or explicitly set the default publishDir
to not apply to TRENDY. But normally, Nextflow's withName selector takes precedence over the
default within the same `process {}` block, so this should not be needed.

### Summary of All publishDir Sources for TRENDY

| Source | File | Line(s) | Path | Status |
|--------|------|---------|------|--------|
| Process script | `modules/local/trendy.nf` | 7 | `${params.outdir}/${projID}/spline_results` | **BUG -- REMOVE THIS** |
| Default process | `conf/modules.config` | 15-19 | `output/trendy/` | Overridden by withName (OK) |
| withName: TRENDY | `conf/modules.config` | 21-25 | `${params.outdir}/${params.projID}/spline_results` | **CORRECT -- keep this** |
| withName: TRENDY | `nextflow.config` | 140-147 | (no publishDir set) | No impact |
| withLabel: process_large | `conf/base.config` | 62-66 | (no publishDir set) | No impact |

### Exact Change Required

In `/mnt/c/Users/User/Downloads/FoodNetTrends-sb_updates/modules/local/trendy.nf`, remove
line 7:

```diff
 process TRENDY {
     tag "$pathogen"
     label 'process_large'
     shell "/bin/bash"
     container 'foodnet.sif'

-    publishDir "${params.outdir}/${projID}/spline_results", mode: 'copy'
-
     input:
```

No other files need to be modified.
