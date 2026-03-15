# UX Review & Improvement Plan: run_workflow.sh Interactive CLI Script

**Reviewer:** Claude (UX analysis)
**Date:** 2026-03-14
**Script:** `run_workflow.sh` (~1,360 lines)
**Audience:** CDC bioinformaticians on an SGE HPC cluster

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Overall Flow Analysis](#2-overall-flow-analysis)
3. [Information Presentation](#3-information-presentation)
4. [Error Handling](#4-error-handling)
5. [Confirmation and Review](#5-confirmation-and-review)
6. [Progress Monitoring (Major Feature Proposal)](#6-progress-monitoring-feature-proposal)
7. [Preprocessing Reuse](#7-preprocessing-reuse)
8. [Pathogen and Serotype Selection](#8-pathogen-and-serotype-selection)
9. [Background Execution](#9-background-execution)
10. [Prioritized Recommendations](#10-prioritized-recommendations)

---

## 1. Executive Summary

The script is functional and demonstrates good UX instincts: color-coded output, sensible defaults, input validation loops, and a confirmation summary before launch. For a 1,360-line interactive CLI guiding users through ~12 decision points, it holds together reasonably well.

### Critical Gaps

**The most significant issue is the complete absence of progress monitoring.** Once Nextflow launches (often for 24-48 hours), users see only Nextflow's default output: `[42%] 3 of 7` tells you 3 pathogens are done, but NOT which ones. For a pipeline with 7+ pathogens running in parallel, this is a severe usability hole.

Other major issues:

- **Too many prompts for the common case** -- experienced users must answer 10+ questions even when defaults would suffice
- **Inconsistent code structure** -- mixed indentation and duplicated blocks make maintenance harder
- **Preprocessing reuse flow is confusing** when no files are detected
- **Resume mode collects parameters that get ignored** -- lines 1002-1195 ask for states, CIDT, travel even though resume should replay prior settings

---

## 2. Overall Flow Analysis

### Current Question Sequence (non-resume, non-preprocess)

1. Run mode (test/publication/max/custom/resume/preprocess)
2. Background execution? (y/n)
3. Output directory
4. Preprocessed data selection (auto-detect + choose)
5. Pathogen selection mode (all vs. specific)
6. [If specific] Which pathogens?
7. Serotype config file? (y/n, then path)
8. Catchment config file? (y/n, then path)
9. [If no preprocessed data] Matching sensitivity
10. [If custom mode] Chains, iterations, adapt_delta, max_treedepth (4 prompts)
11. [If STEC selected] STEC grouping
12. [If Salmonella selected] Salmonella grouping (potentially with serotype picker)
13. State selection
14. CIDT method selection
15. Travel status selection
16. Confirm and launch

**That is up to 16 interaction points.** For the most common case ("run all pathogens in test mode with defaults"), the user still answers 8-9 prompts.

### Issues with Current Flow

**A. Too much friction for quick/test runs.** Developers iterate on the pipeline by running test mode repeatedly. Each time, they answer the same 8-9 questions with the same defaults. A "quick run" shortcut would be valuable.

**B. Background execution asked too early.** It is asked as the second question (line 329), before the user has configured any parameters. At that point, the user does not yet know if they want background execution. This decision is operational (not scientific) and should be deferred.

**C. Resume mode collects ignored parameters.** Lines 1004-1195 prompt for state, CIDT, and travel selections even though resume mode should replay the prior run's settings (lines 919-937). This creates the false impression that the user is configuring the resumed run, when in fact those answers are discarded. The sections should be guarded with `if [[ "$flag" != "resume" ]]`.

### Recommendations for Flow Improvement

#### Quick-Run Fast Path (High Priority)

Detect test mode and offer a shortcut:

```bash
# Line ~310, after confirming run mode
if [[ "$flag" == "test" ]]; then
    echo ""
    echo -e "${GREEN}Test mode selected.${NC}"
    echo "Using defaults: all pathogens, no filters, no custom configs."
    echo ""
    read -p "Proceed with defaults (y) or customize (c)? [y]: " quick_choice
    quick_choice=${quick_choice:-y}

    if [[ "$quick_choice" =~ ^[Yy]$ ]]; then
        # Skip to confirmation, using defaults for all remaining options
        skip_to_summary=true
    fi
fi
```

This converts the common test-mode flow from 8-9 prompts to 2. The implementation wraps most questions in `if [[ "$skip_to_summary" != true ]]; then ... fi` blocks.

#### Reorder for Logical Flow

After implementing the fast path, reorganize the remaining flow:

```
1.  Run mode (test/publication/max/custom/resume/preprocess)
2.  [If test AND user wants quick run] Jump to confirmation
3.  Preprocessed data (auto-detect, offer choices if found)
4.  Pathogen selection (all vs. specific)
5.  [If applicable] Subgroup/serotype decisions
6.  Data filters (combine: states, CIDT, travel)
7.  [If custom mode] MCMC parameters (chains, iterations, adapt_delta, max_treedepth)
8.  Config files (serotype, catchment) -- offer to skip both if not needed
9.  [If no preprocessed] Matching sensitivity
10. Output directory
11. Background execution? (y/n)
12. Confirmation summary + launch
```

#### Combine Filter Prompts (Medium Priority)

States, CIDT, and travel are all optional data filters. They should be grouped:

```bash
# After pathogen selection, before MCMC parameters

echo ""
echo -e "${BLUE}======== Data Filters (Optional) ========${NC}"
echo "Include all data? (y) or filter by state, diagnostic method, travel status? (n)"
read -p "Include all? [y]: " filter_choice
filter_choice=${filter_choice:-y}

if [[ "$filter_choice" =~ ^[Nn]$ ]]; then
    # Show states, CIDT, travel prompts
else
    # Use defaults for all three
    selected_states=""
    selected_cidt=""
    selected_travel=""
fi
```

This gate collapses three prompts into one for users who do not need filtering.

---

## 3. Information Presentation

### What Works Well

- **Color coding is consistent:** blue for headers, green for confirmations, yellow for warnings, red for errors
- **Section headers create clear visual grouping** (`======== MCMC Parameters ========`)
- **Defaults shown in brackets** (`[2]`, `[n]`) follow standard CLI conventions
- **Preprocessed file listing includes metadata:** creation date, size, and presence of companion files
- **The `handle_pathogen_grouping` function uses `>&2` redirection** to keep stdout clean for return values (good practice)

### Issues and Recommendations

#### A. Banner Lacks Context (Low Priority)

Current:
```
=========================================
   FoodNet Trends Analysis Pipeline
=========================================
```

Better:
```
=========================================
   FoodNet Trends Analysis Pipeline v1.0
=========================================
   Working dir: /scicomp/.../current
   Data dir:    /scicomp/.../data/
   Nextflow:    24.10.4
```

Users on a shared HPC system need to confirm they are in the right place.

#### B. Run Mode Descriptions Are Vague (Medium Priority)

Current:
```
1) Test
2) Publication
3) Max
4) Custom
5) Resume previous run
6) Preprocessing only
```

Better:
```
1) Test         - Quick validation  (1 chain, 100 iter, ~30 min per pathogen)
2) Publication  - Full analysis     (6 chains, 10K iter, ~6 hours per pathogen)
3) Max          - Extended run      (8 chains, 20K iter, ~12 hours per pathogen)
4) Custom       - Set your own MCMC parameters
5) Resume       - Continue a previous interrupted run
6) Preprocess   - Clean and profile data only (no modeling)
```

This helps users choose the right mode without guessing.

#### C. MCMC Parameter Prompts Are Bare (Medium Priority)

Current: `Number of chains [2]:`

Better:
```
Number of chains [2]: (recommended 2-6; more chains = better convergence but slower)
```

This provides helpful context without requiring external documentation lookup.

#### D. Final Command Dump Is Overwhelming (Low Priority)

Lines 1334-1335 print the raw Nextflow command, which is useful for debugging but long. Show it collapsed:

```bash
echo -e "Command:"
echo -e "${YELLOW}nextflow run main.nf -profile singularity -entry SPLINE [...]${NC}"
echo -e "(Press 'd' to see full command, 'y' to proceed, 'n' to cancel)"
```

Then implement the interactive prompt to expand if needed.

#### E. Unicode Checkmarks May Not Render on All Terminals (Low Priority)

Lines 401, 407 use `✓` (UTF-8 checkmark). On minimal HPC terminals, this may render as `?` or garbled. Use ASCII instead:

```bash
# Instead of:
echo "    ✓ Preprocessing report available"

# Use:
echo "    [+] Preprocessing report available"
```

---

## 4. Error Handling

### What Works Well

- All yes/no and numeric inputs use `while true` validation loops
- Invalid pathogen names are caught with context-aware error messages
- File existence checked for config files with yellow warnings

### Issues and Bugs

#### A. Bug: Invalid `continue` on Line 708 (High Priority)

The pathogen validation block (lines 704-708) calls `continue` to re-prompt for input, but this is not inside a loop. This should be:

```bash
# Lines 674-722, currently has no loop wrapping the validation
# Need to add loop structure:

while true; do
    if [[ "$pathogen_mode" == "1" ]]; then
        # ... all existing logic from lines 536-722
    fi

    # Validate pathogens here
    if invalid; then
        echo "Error message"
        continue  # <-- NOW this is inside a loop
    else
        break
    fi
done
```

#### B. No Validation on State Number Input (Medium Priority)

When user enters state numbers (line 1041), non-numeric input is silently ignored. Add validation:

```bash
for num in $state_selection; do
    if ! [[ "$num" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Invalid selection: '$num' (expected a number from the list)${NC}"
        continue
    fi
    if [[ -n "${state_array[$num]}" ]]; then
        # ... existing code
    else
        echo -e "${YELLOW}Selection $num out of range (only ${#state_array[@]} states available)${NC}"
    fi
done
```

#### C. No Input Validation for CIDT/Travel Menu (Medium Priority)

The `case` statements on lines 1118 and 1179 have no default branch. Invalid selections silently result in empty variables. Add:

```bash
case $cidt_mode in
    1) selected_cidt="" ;;
    2) selected_cidt="CX+" ;;
    # ... other cases ...
    *)
        echo -e "${RED}Invalid selection: '$cidt_mode'. Using all methods (default).${NC}"
        selected_cidt=""
        ;;
esac
```

#### D. Custom Path Flow Falls Through on Error (Medium Priority)

Lines 446-453: When a user provides an invalid custom path, the script prints a warning but then continues in an inconsistent state. Better:

```bash
if [[ -d "$custom_path" ]]; then
    # ... validation logic ...
else
    echo -e "${RED}Error: Directory not found: $custom_path${NC}"
    echo -e "${YELLOW}Will run preprocessing step instead.${NC}"
    # Explicitly set state to match the fallback:
    use_preprocessed=false
    preprocessed_file=""
    # Then re-prompt: "Continue with preprocessing? (y/n)"
fi
```

#### E. No Trap for Ctrl+C (Low Priority)

Users who press Ctrl+C mid-interview get no cleanup message. Add near top of script:

```bash
trap 'echo -e "\n${RED}Cancelled.${NC}"; exit 1' INT
```

---

## 5. Confirmation and Review

### What Works Well

The summary block (lines 1280-1336) is well-structured and shows all key parameters. The "Proceed with analysis? (y/n)" confirmation is essential and correctly implemented.

### Recommendations

#### A. Add Estimated Runtime (Medium Priority)

Based on run mode and pathogen count, show a rough estimate:

```bash
# After displaying the run mode
case "$flag" in
    test)
        est_per_pathogen=0.5  # hours
        ;;
    publication)
        est_per_pathogen=6
        ;;
    max)
        est_per_pathogen=12
        ;;
esac

# Count pathogens
if [[ "$pathogens" == "AUTO_DISCOVER" ]]; then
    num_pathogens=7  # conservative estimate
else
    num_pathogens=$(echo "$pathogens" | tr ',' '\n' | wc -l)
fi

est_total=$(echo "$num_pathogens * $est_per_pathogen" | bc)
echo -e "Estimated runtime: ~${est_total} hours (${num_pathogens} pathogens × ${est_per_pathogen}h each)"
```

#### B. Show Full Output Path (Medium Priority)

The summary shows `Output directory: output` but the actual results go to `output/<timestamp>/spline_results/`. Show the resolved path:

```bash
echo -e "Output directory: ${GREEN}${outDir}/${timestamp}/${NC}"
echo -e "Results will be in: ${GREEN}${outDir}/${timestamp}/spline_results/${NC}"
```

#### C. Highlight Non-Default Choices (Low Priority)

When user customizes from defaults, visually distinguish:

```bash
# Instead of always using GREEN:
if [[ "$selected_states" != "" ]]; then
    echo -e "States: ${YELLOW}$selected_states (custom)${NC}"
else
    echo -e "States: ${GREEN}ALL states (default)${NC}"
fi
```

#### D. Add "Save Configuration" Option (Low Priority)

After summary, offer:

```bash
echo ""
read -p "Save this configuration for future runs? (y/n) [n]: " save_config
if [[ "$save_config" =~ ^[Yy]$ ]]; then
    config_file="foodnet_config_${timestamp}.params"
    cat > "$config_file" <<EOF
params {
    pathogen = "${pathogens}"
    chains = ${chains}
    iterations = ${iterations}
    # ... etc
}
EOF
    echo -e "${GREEN}Configuration saved to: $config_file${NC}"
    echo -e "Replay with: nextflow run main.nf -params-file $config_file"
fi
```

---

## 6. Progress Monitoring (Major Feature Proposal)

### The Problem

Once Nextflow launches, the user sees Nextflow's default progress line:

```
executor > sge (8)
[5a/c3e2f1] process > SPLINE:PREPROCESS       [100%] 1 of 1 +
[7b/d4f3a2] process > SPLINE:RESOURCE_PROFILER [100%] 1 of 1 +
[3c/e5g4b3] process > SPLINE:TRENDY            [ 42%] 3 of 7
```

This shows "3 of 7" complete, but NOT which pathogens. For a 24-48 hour run with 7+ pathogens, users need to know:
- Which pathogens are currently running?
- Which finished successfully?
- Which failed and why?
- How long has each been running?
- Estimated time remaining?

### Solution: Companion Monitoring Script

Create a **separate script** `monitor_pipeline.sh` (not embedded in `run_workflow.sh`) that displays per-pathogen progress in real time.

#### Why Separate?

1. Users running in background mode cannot interact with the launch script
2. Multiple terminals can monitor the same run independently
3. Monitor can be started/stopped/restarted without affecting the pipeline
4. Keeps `run_workflow.sh` focused on configuration

However, `run_workflow.sh` should print the monitor command after launching.

#### Data Sources

The monitor leverages three Nextflow artifacts:

1. **Execution trace file** (`output/<projID>/pipeline_info/execution_trace_*.txt`): A TSV file Nextflow writes in real-time. Contains task name, status, submit time, start time, duration, exit code, CPU usage, memory usage. The `tag` directive in the TRENDY process definition (trendy.nf line 2: `tag "$pathogen"`) populates the pathogen name in the trace.

2. **Nextflow log** (`.nextflow.log`): Contains process-level events. Can be parsed for task submission, start, and completion events.

3. **Output file detection**: The TRENDY process publishes files to `output/<projID>/spline_results/`. Presence of `<PATHOGEN>_*_IRCatch.csv` indicates completion; `<PATHOGEN>_error.txt` indicates failure.

#### Terminal Output Mockup

```
================================================================================
  FoodNet Trends Pipeline Monitor            Run ID: 20260314_093021
  Updated: 2026-03-14 11:45:23               Elapsed: 2h 15m
================================================================================

  PREPROCESSING                                                       DONE 0:03:12
  RESOURCE PROFILER                                                   DONE 0:00:45

  PATHOGEN MODELING (TRENDY)                                       4/7 DONE

  Pathogen          Status       Duration    CPU%    Memory    Exit
  ───────────────   ──────────   ─────────   ─────   ──────    ────
  CAMPYLOBACTER     DONE         1:23:45     1580%   42.3 GB   0
  CYCLOSPORA        DONE         0:18:22      890%   12.1 GB   0
  SALMONELLA        RUNNING      1:52:03     1600%   58.7 GB   -
  SHIGELLA          DONE         0:45:11     1420%   28.4 GB   0
  STEC (O157)       RUNNING      0:33:17     1590%   35.2 GB   -
  STEC (nonO157)    QUEUED           -         -       -       -
  VIBRIO            DONE         0:22:08     1100%   15.6 GB   0
  YERSINIA          QUEUED           -         -       -       -

  DASHBOARD                                                        WAITING

  Legend: DONE = success | RUNNING = executing | QUEUED = submitted to SGE
          WAITING = dependencies not met | FAILED = error occurred

  Hint: Check error logs with:
    tail -n 20 output/20260314_093021/spline_results/STEC_O157_error.txt

  Monitor controls: [r]efresh now, [q]uit monitor, [l]og level change

================================================================================
```

When a failure occurs, highlight it and provide remediation hint:

```
  STEC (O157)       FAILED       0:33:17     1590%   35.2 GB   137
                    ^ Exit code 137 = out-of-memory killed (OOM)
                      Suggestion: Increase memory allocation or reduce iterations
                      Error log: output/20260314_093021/spline_results/STEC_O157_error.txt
```

When all jobs complete:

```
================================================================================
  FoodNet Trends Pipeline Monitor            Run ID: 20260314_093021
  PIPELINE COMPLETE                          Total time: 4h 22m
================================================================================

  PATHOGEN MODELING RESULTS                                        7/7 DONE

  Pathogen          Status       Duration    Exit
  ───────────────   ──────────   ---------   ----
  CAMPYLOBACTER     DONE         1:23:45     0
  CYCLOSPORA        DONE         0:18:22     0
  SALMONELLA        DONE         3:45:11     0
  SHIGELLA          DONE         0:45:11     0
  STEC (O157)       DONE         1:33:17     0
  STEC (nonO157)    DONE         0:52:44     0
  VIBRIO            DONE         0:22:08     0
  YERSINIA          DONE         0:14:33     0

  DASHBOARD         DONE         0:02:15     0

  Results:   output/20260314_093021/spline_results/
  Dashboard: output/20260314_093021/dashboard/
  Report:    output/20260314_093021/pipeline_info/execution_report_*.html

  Next steps: Review results and dashboard for trends in your data.

================================================================================
```

#### Implementation Outline

```bash
#!/bin/bash
# monitor_pipeline.sh -- Monitor a running FoodNet Trends pipeline
#
# Usage:
#   ./monitor_pipeline.sh <project_id>
#   ./monitor_pipeline.sh <project_id> --once    (print once and exit)
#   ./monitor_pipeline.sh <project_id> --watch   (continuous, default)

PROJ_ID="${1:?Usage: monitor_pipeline.sh <project_id>}"
MODE="${2:---watch}"
OUTDIR="${3:-output}"
POLL_INTERVAL=15  # seconds between refreshes

TRACE_DIR="${OUTDIR}/${PROJ_ID}/pipeline_info"
RESULTS_DIR="${OUTDIR}/${PROJ_ID}/spline_results"

# Find the execution trace file (wait for it if pipeline just started)
wait_for_trace() {
    local trace_file
    trace_file=$(ls "${TRACE_DIR}"/execution_trace_*.txt 2>/dev/null | head -1)
    if [[ -z "$trace_file" ]]; then
        echo "Waiting for pipeline to start..."
        while [[ -z "$trace_file" ]]; do
            sleep 5
            trace_file=$(ls "${TRACE_DIR}"/execution_trace_*.txt 2>/dev/null | head -1)
        done
    fi
    echo "$trace_file"
}

# Parse trace file and render dashboard
# Trace columns (tab-separated):
#   task_id, hash, native_id, name, status, exit,
#   submit, start, complete, duration, realtime,
#   %cpu, peak_rss, peak_vmem, rchar, wchar, ...
#
# The "name" column contains e.g., "SPLINE:TRENDY (CAMPYLOBACTER)"
# The tag in parentheses is extracted via regex.
#
# Collect all rows by pathogen tag, track latest status, duration, exit code.

render_dashboard() {
    local trace_file="$1"
    local start_time end_time elapsed

    # Get start time from first event
    start_time=$(awk 'NR==2 {print $7}' "$trace_file" | cut -d'T' -f2 | cut -d'.' -f1)
    # Get current time for elapsed calculation
    end_time=$(date +%s)

    # Clear terminal and move cursor to top
    tput clear

    # Print header
    echo "================================================================================"
    echo "  FoodNet Trends Pipeline Monitor            Run ID: ${PROJ_ID}"
    echo "  Updated: $(date '+%Y-%m-%d %H:%M:%S')               Elapsed: TBD"
    echo "================================================================================"
    echo ""

    # Parse trace file with awk to extract per-process status
    # Group by process name and tag, show latest status for each
    awk -F'\t' -v result_dir="$RESULTS_DIR" '
    NR==1 {
        # Header row: find column indices
        for (i=1; i<=NF; i++) {
            if ($i == "name") name_col = i
            if ($i == "status") status_col = i
            if ($i == "exit") exit_col = i
            if ($i == "duration") duration_col = i
            if ($i == "%cpu") cpu_col = i
            if ($i == "peak_rss") mem_col = i
        }
        next
    }
    {
        # Extract process type and pathogen tag from name field
        name = $name_col
        match(name, /^([^(]+)\s*\(([^)]+)\)/, m)
        process = m[1]
        tag = m[2]

        # Store latest event for this tag
        # (later rows in trace file are more recent)
        status[tag] = $status_col
        exit_code[tag] = $exit_col
        duration[tag] = $duration_col
        cpu[tag] = $cpu_col
        mem[tag] = $mem_col
        process_type[tag] = process
    }
    END {
        # Print preprocessing section
        print "  PREPROCESSING"
        # ... render status based on status[""] or status["1"] ...

        print ""
        print "  PATHOGEN MODELING (TRENDY)"
        print ""
        print "  Pathogen          Status       Duration    CPU%    Memory    Exit"
        print "  ───────────────   ──────────   ─────────   ─────   ──────    ────"

        # List pathogens (hard-coded list or read from resource profile)
        pathogens = "CAMPYLOBACTER,CYCLOSPORA,SALMONELLA,SHIGELLA,STEC~O157,STEC~nonO157,VIBRIO,YERSINIA"
        n = split(pathogens, parray, ",")
        done_count = 0

        for (i=1; i<=n; i++) {
            p = parray[i]
            s = status[p] != "" ? status[p] : "QUEUED"
            dur = duration[p] != "" ? duration[p] : "-"
            cpu_pct = cpu[p] != "" ? cpu[p] : "-"
            mem_gb = mem[p] != "" ? mem[p] : "-"
            ec = exit_code[p] != "" ? exit_code[p] : "-"

            if (s == "COMPLETED") done_count++

            printf "  %-17s %-12s %-9s %7s %10s %4s\n", p, s, dur, cpu_pct, mem_gb, ec
        }

        print ""
        print "  DASHBOARD        " (status[""] == "COMPLETED" ? "DONE" : "WAITING")
        print ""
        print "  Done: " done_count " / " n
    }
    ' "$trace_file"

    echo ""
    echo "================================================================================"
    echo "  Monitor controls: [r]efresh, [q]uit  |  Logs: ${RESULTS_DIR}/"
    echo "================================================================================"
}

# Main loop
main() {
    local trace_file

    trace_file=$(wait_for_trace)

    if [[ "$MODE" == "--once" ]]; then
        render_dashboard "$trace_file"
        exit 0
    fi

    # Continuous watch mode
    while true; do
        render_dashboard "$trace_file"

        # Non-blocking read with timeout
        if read -t "$POLL_INTERVAL" -n 1 key 2>/dev/null; then
            case "$key" in
                q|Q)
                    echo -e "\nMonitor closed."
                    exit 0
                    ;;
                r|R)
                    continue  # Immediate refresh
                    ;;
            esac
        fi

        # Check if pipeline process is still running
        if ! pgrep -f "nextflow.*${PROJ_ID}" >/dev/null 2>&1; then
            # Pipeline exited, show final status and offer to stay
            render_dashboard "$trace_file"
            echo ""
            read -t 5 -p "Pipeline has completed. Monitor will exit in 5 seconds (q to quit now): " key
            if [[ "$key" =~ [qQ] ]]; then
                exit 0
            fi
            exit 0
        fi
    done
}

main
```

#### Key Implementation Details

**Trace file format.** The Nextflow execution trace is a tab-separated file with headers. Use `awk` to parse it. The key fields are:

- `name`: Process name with tag, e.g., `SPLINE:TRENDY (CAMPYLOBACTER)`
- `status`: One of SUBMITTED, RUNNING, COMPLETED, FAILED, ABORTED
- `exit`: Exit code (0 for success, non-zero for failure)
- `duration`: Wall-clock time spent running
- `%cpu`: CPU utilization percentage
- `peak_rss`: Peak memory usage

**Handling retries.** The TRENDY process has `maxRetries 3`. The trace file contains multiple entries for the same pathogen if retries occur. The monitor should show only the latest attempt but indicate retry history (e.g., "RUNNING (retry 2/3)").

**SGE compatibility.** Use only standard POSIX tools: `awk`, `tput`, `read`, `pgrep`, `date`. No ncurses, no web server, no special terminal capabilities. This works over SSH, in tmux, in screen sessions.

**Pathogen list discovery.** If the user ran with `--pathogen "CAMPYLOBACTER,CYCLOSPORA"`, that list is known. If `AUTO_DISCOVER` was used, read the `resource_profile.csv` file to get the list of pathogens that were found.

**Non-blocking keyboard input.** Use `read -t` with a timeout so the monitor continues to refresh even if the user is not typing.

#### Integration with run_workflow.sh

After launching the pipeline (lines 1350-1356), print the monitor command:

```bash
if [[ $background == true ]]; then
    echo -e "${GREEN}Process started in background.${NC}"
    echo ""
    echo -e "Monitor progress:    ${YELLOW}./monitor_pipeline.sh ${timestamp}${NC}"
    echo -e "View raw log:        ${YELLOW}tail -f foodnet_run_${timestamp}.log${NC}"
    echo -e "View Nextflow trace: ${YELLOW}tail -f ${outDir}/${timestamp}/pipeline_info/execution_trace_*.txt${NC}"
else
    echo ""
    echo -e "To monitor from another terminal:"
    echo -e "${YELLOW}./monitor_pipeline.sh ${timestamp}${NC}"
fi
```

### Alternative: Integrate Monitor Directly into run_workflow.sh

If a separate script is not preferred, the monitoring logic could be embedded as a function. However, this has downsides:

- Users cannot start the monitor after the fact (if they did not request it at launch time)
- Foreground Nextflow output and the monitor output would conflict on the same terminal
- The script would grow significantly in size

**Recommendation: Keep monitor as a separate script.** It is cleaner, more flexible, and follows the Unix philosophy of small, composable tools.

---

## 7. Preprocessing Reuse

### Current Behavior

The script searches `output/` for `clean_mmwr.csv` files and presents them as numbered options. This is good, but has rough edges.

### Issues

#### A. "No Files Found" Path Is Awkward (Low Priority)

Lines 457-503: When no preprocessed files exist, the script says "No preprocessed data found locally" and immediately asks "Do you want to specify a custom path? (y/n)". Most first-time users will not have a custom path. This adds friction. Better:

```bash
if [[ ${#preprocessed_files[@]} -gt 0 ]]; then
    # ... show list ...
else
    echo -e "${YELLOW}No existing preprocessed data found.${NC}"
    echo -e "${YELLOW}Raw data will be preprocessed from scratch.${NC}"
    echo ""
    use_preprocessed=false
    preprocessed_file=""
    # Skip the custom path question unless user explicitly requests it
fi
```

Only offer the custom path question if the user is in preprocess-only mode or if there is other evidence they might have external data.

#### B. Search Limited to `output/` (Low Priority)

If the user specified a different output directory in a previous run, those files will not be found. Consider searching the user-specified `$outDir`:

```bash
search_dirs=("output" "$outDir")
for dir in "${search_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
        while IFS= read -r -d '' file; do
            preprocessed_files+=("$file")
        done < <(find "$dir" -name "clean_mmwr.csv" -type f -print0 2>/dev/null)
    fi
done
```

#### C. File Listing Lacks Pathogen Context (Low Priority)

The listing shows path, date, and size, but not what pathogens it contains. If `resource_profile.csv` exists, extract and display:

```bash
for i in "${!preprocessed_files[@]}"; do
    file="${preprocessed_files[$i]}"
    file_date=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1)
    file_size=$(du -h "$file" 2>/dev/null | cut -f1)
    echo "$((i+1))) $file"
    echo "    Created: $file_date, Size: $file_size"

    # Show pathogens if available
    resource_profile="$(dirname "$file")/resource_profile.csv"
    if [[ -f "$resource_profile" ]]; then
        pathogens_in_file=$(awk -F',' 'NR>1 {print $1}' "$resource_profile" | tr '\n' ', ' | sed 's/,$//')
        echo "    Pathogens: $pathogens_in_file"
    fi

    echo ""
done
```

#### D. Unicode Checkmarks Not Cross-Platform (Low Priority)

Lines 401, 407 use UTF-8 checkmark character. On minimal terminals, use ASCII:

```bash
# Instead of:
echo "    ✓ Preprocessing report available"

# Use:
echo "    [+] Preprocessing report available"
```

---

## 8. Pathogen and Serotype Selection

### Pathogen Selection

The current two-step approach (all vs. specific) is reasonable. Recommendations:

#### A. Offer Numbered Checklist, Not Typed Names (Medium Priority)

Current (lines 656-668): Users type comma-separated pathogen names, error-prone:

```
Available pathogens:
- CAMPYLOBACTER
- CYCLOSPORA
...
Enter pathogens to analyze (comma-separated with NO spaces)
```

Better:

```
Available pathogens:
 1. CAMPYLOBACTER
 2. CYCLOSPORA
 3. SALMONELLA
 4. SHIGELLA
 5. STEC
 6. VIBRIO
 7. YERSINIA

Enter numbers separated by commas (e.g., 1,3,5) or 'all': [all]
```

This is consistent with the Salmonella serotype picker pattern already used and eliminates typos entirely.

#### B. Default Behavior for Typed Input Is Confusing (Low Priority)

Line 668: When user presses Enter without typing, the default is `CAMPYLOBACTER,CYCLOSPORA`. This is a test convenience that could confuse production users. Either:

- Default to "all" (consistent with the gating question "Run ALL pathogens")
- Or require explicit input with no default

```bash
read -p "Leave blank for ALL: " pathogens
if [[ -z "$pathogens" ]]; then
    pathogens="all"  # More intuitive
fi
```

### Serotype Picker (Salmonella)

The frequency-ranked serotype picker (lines 86-204) is genuinely good UX -- showing ranked serotypes with case counts lets users make informed decisions.

#### A. Show Percentages, Not Just Counts (Low Priority)

Current:
```
[1] Enteritidis                    (n=45023)
```

Better:
```
[1] Enteritidis                    45,023 cases (28.3%)
```

#### B. Validate Entered Numbers (Medium Priority)

If user enters "1,2,99" and serotype 99 does not exist, the code silently ignores it (line 187-188). Show a warning:

```bash
selected_count=0
for sel in "${selections[@]}"; do
    serotype_name=$(echo "$serotype_data" | sed -n "${sel}p" | cut -f2-)
    if [[ -n "$serotype_name" ]]; then
        # ... add to list ...
        ((selected_count++))
    else
        echo -e "${YELLOW}Skipping invalid selection: $sel${NC}"
    fi
done

if [[ $selected_count -eq 0 ]]; then
    echo -e "${RED}No valid selections. Using combined analysis.${NC}"
    grouping="SALMONELLA~combined"
fi
```

#### C. Allow Selection by Name, Not Just Number (Low Priority)

Power users may want to type "Enteritidis,Typhimurium". Detect whether input is numeric or text:

```bash
if [[ "$serotype_selection" =~ ^[0-9,\ ]+$ ]]; then
    # Numeric: process as numbers
elif [[ "$serotype_selection" =~ ^[A-Za-z,\ -]+$ ]]; then
    # Text: match against serotype names
    IFS=',' read -ra selections <<< "$serotype_selection"
    for sel in "${selections[@]}"; do
        sel=$(echo "$sel" | xargs)  # Trim whitespace
        # Find matching serotype in serotype_data
        # ...
    done
fi
```

#### D. Clarify Analyzed vs. Combined (Low Priority)

When user selects multiple serotypes, the behavior is not obvious. Add clarification:

```
Each selected serotype will be analyzed independently as a separate model.
```

### STEC Grouping

The STEC grouping menu (lines 41-64) is clear and well-designed. No significant issues.

---

## 9. Background Execution

### Current Behavior

Lines 329-342, 1272-1278: When `background=true`, the script wraps the command in `nohup ... &` and tells the user to check the log.

### Issues

#### A. Log File Location Is Scattered (Low Priority)

The log goes to the current directory (`foodnet_run_<timestamp>.log`), not the output directory. This separates logs from outputs. Move into output dir:

```bash
log_dir="${outDir}/${timestamp}"
mkdir -p "$log_dir"
bg_log="${log_dir}/foodnet_run.log"
bg_cmd="nohup $cmd > ${bg_log} 2>&1 &"
```

#### B. Background Question Comes Too Early (Medium Priority)

It is asked at line 329, before configuring scientific parameters. At that point, the user does not know if they want background execution. Move this to just before the confirmation step (line ~1338).

#### C. No PID Capture (Low Priority)

After launching in background, capture and display the PID so the user can monitor/kill it:

```bash
eval $bg_cmd
bg_pid=$!
echo -e "${GREEN}Pipeline running in background (PID: ${bg_pid})${NC}"
echo -e "Monitor: ${YELLOW}./monitor_pipeline.sh ${timestamp}${NC}"
echo -e "Kill:    ${YELLOW}kill ${bg_pid}${NC}"
```

#### D. No `disown` (Low Priority)

The `nohup` handles SIGHUP, but the process is still a child of the shell. Add `disown` to fully detach:

```bash
eval $bg_cmd
disown
```

---

## 10. Prioritized Recommendations

### Immediate/Critical (Do First)

| # | Issue | Effort | Impact | Priority |
|---|-------|--------|--------|----------|
| 1 | Create `monitor_pipeline.sh` companion script | Medium | **Critical** | Do now |
| 2 | Fix bug: `continue` outside loop (line 708) | Low | High | Do now |
| 3 | Add "quick run" fast path for test mode | Low | High | Do soon |
| 4 | Guard resume-mode parameter collection with `if [[ "$flag" != "resume" ]]` | Low | Medium | Do soon |

### High Priority (Do Next)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 5 | Add input validation for CIDT/travel menu selections | Low | Medium |
| 6 | Validate state number input | Low | Medium |
| 7 | Move background execution question to end of interview | Low | Medium |
| 8 | Print monitor command after pipeline launch | Low | Medium |
| 9 | Add estimated runtime to summary | Low | Medium |

### Medium Priority (Next Pass)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 10 | Combine states/CIDT/travel behind single gate question | Medium | Medium |
| 11 | Show full output path (with project ID) in summary | Low | Low-Medium |
| 12 | Enrich run mode menu with parameter hints | Low | Low-Medium |
| 13 | Replace Unicode checkmarks with ASCII | Low | Low |
| 14 | Extract and display pathogens from preprocessed files | Low | Low |

### Lower Priority (Nice to Have)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| 15 | Add Ctrl+C trap for clean exit | Low | Low |
| 16 | Numbered pathogen checklist (replace typed names) | Medium | Low |
| 17 | Add "save configuration" export option | Medium | Low |
| 18 | Simplify "no preprocessed data found" flow | Low | Low |
| 19 | Move background log into output directory | Low | Low |
| 20 | Add serotype percentage display | Low | Low |

---

## Appendix: Code Quality & Maintainability

### Structural Issues to Address During Cleanup

1. **Mixed indentation.** Some blocks use 4 spaces, some use 2 spaces, some are not indented at all. Standardize on 4-space indentation throughout.

2. **Duplicated code.** The custom path validation logic (lines 426-453 and 471-499) is nearly identical. Extract into a helper function:

```bash
validate_custom_preprocessed_path() {
    local custom_path="$1"

    if [[ -d "$custom_path" ]]; then
        local custom_clean="${custom_path}/clean_mmwr.csv"
        if [[ -f "$custom_clean" ]]; then
            use_preprocessed=true
            preprocessed_file="$custom_clean"
            return 0
        fi
    fi
    return 1
}
```

3. **Hard-coded data file name.** The MMWR file (`mmwr9624_May2025.sas7bdat`) is hard-coded on lines 1202, 1210, and 1227. Define once at the top:

```bash
MMWR_FILE="${dataDir}/mmwr9624_May2025.sas7bdat"
CENSUS_B_FILE="${dataDir}/cen9624.sas7bdat"
CENSUS_P_FILE="${dataDir}/cen9624_para.sas7bdat"
```

Then use `$MMWR_FILE` throughout.

4. **The `eval` on line 1351.** Using `eval` with a dynamically constructed string is a security risk (though mitigated by input validation). Consider building the command as a bash array:

```bash
declare -a cmd_array=(nextflow run main.nf -profile singularity -entry SPLINE)
cmd_array+=(--mmwrFile "$dataDir/mmwr9624_May2025.sas7bdat")
# ... add more arguments ...

if [[ $background == true ]]; then
    nohup "${cmd_array[@]}" > "$bg_log" 2>&1 &
else
    "${cmd_array[@]}"
fi
```

5. **Good patterns to preserve:**
   - The `handle_pathogen_grouping` function uses `>&2` redirection to keep stdout clean for the return value. This is correct and should be followed elsewhere.
   - Validation loops with `while true; do ... break; done` are consistent and readable.
   - The summary section (lines 1280-1336) is well-organized and a good model for presenting configuration.

---

## Summary

This script demonstrates solid foundational UX design for a complex multi-step pipeline configuration workflow. The main gap is the complete absence of progress monitoring once the pipeline launches -- a critical usability issue for 24-48 hour runs.

The recommended approach is to create a companion `monitor_pipeline.sh` script that displays per-pathogen progress in real time, leveraging Nextflow's execution trace file. This should be prioritized as the first improvement.

Secondary improvements to flow (quick-run fast path, combined filter prompts, guard resume mode) will significantly reduce friction for common use cases.

The code is maintainable but would benefit from standardized indentation, extraction of helper functions for duplicated logic, and elimination of hard-coded paths.

---

## Architect Review

**Reviewer:** Senior Nextflow DSL2 Bioinformatics Architect
**Date:** 2026-03-14
**Scope:** UX plan validation, progress monitoring technical assessment, Nextflow/SGE integration, local executor for lightweight processes

---

### 1. Cross-Plan Conflict Analysis

The UX plan modifies `run_workflow.sh` and proposes a new `monitor_pipeline.sh` script. The Profiler Plan also modifies `run_workflow.sh` (Change 9: add `--stan_backend` to the Nextflow command). These changes are in different sections:
- Profiler Plan Change 9 adds a parameter to the command construction (lines 1208-1236).
- UX plan changes are spread across the interview flow (lines 310-997) and post-launch output (lines 1350+).

No textual conflicts. Both can be applied independently. When implementing both, the `--stan_backend` parameter should appear in the confirmation summary alongside other MCMC parameters.

No other cross-plan conflicts. The UX plan does not touch R scripts, Nextflow process definitions, or config files.

### 2. Progress Monitoring Technical Assessment

The proposal for `monitor_pipeline.sh` is **technically sound** for Nextflow on SGE. Detailed assessment:

#### 2a. Trace File as Primary Data Source

The plan correctly identifies the Nextflow execution trace file as the primary data source. Key technical details:

- **Trace file writing behavior:** Nextflow writes to the trace file incrementally as events occur. Each task state change (SUBMITTED, RUNNING, COMPLETED, FAILED) appends a new row. The file is NOT locked for exclusive writes -- it can be read concurrently by the monitor script. This is safe because Nextflow uses append-only writes and the monitor uses read-only access.

- **Trace file format:** Tab-separated with a header row. The `name` column contains the process name with the `tag` value in parentheses, e.g., `SPLINE:TRENDY (CAMPYLOBACTER)`. The `tag "$pathogen"` directive in `trendy.nf` line 2 populates this. The plan's awk parser correctly extracts this via regex.

- **Trace file timing:** The trace file is created when the first task is submitted. The `wait_for_trace()` function handles the startup delay correctly. However, the trace file path includes a timestamp (`execution_trace_${trace_timestamp}.txt`), and the timestamp is set at pipeline startup (`nextflow.config` line 159). The monitor's `ls` approach to find the latest trace file is correct.

- **Multiple trace entries per task:** When TRENDY retries (maxRetries 3), the trace file contains multiple rows for the same pathogen. The plan notes this but the implementation outline does not fully handle it. The awk script should track the latest entry per tag (which it does by overwriting `status[tag]` on each row), but it should also track retry count. Suggestion: count the number of FAILED entries per tag before the final status.

#### 2b. SGE Compatibility

The proposal uses only POSIX tools (`awk`, `tput`, `read`, `pgrep`, `date`). This is correct for Rosalind (SGE cluster). Specific SGE considerations:

- **`pgrep -f "nextflow.*${PROJ_ID}"`:** This checks if the Nextflow process is still running. On SGE, the Nextflow driver process runs on the login node (not on a compute node), so `pgrep` on the login node is correct. However, if the user runs Nextflow inside a `screen` or `tmux` session on a different login node, `pgrep` will not find it. This is an acceptable limitation -- document it.

- **`tput clear`:** Requires a terminal. If the monitor is piped to a file or run in a non-interactive context, `tput` will fail. Add a guard: `if [ -t 1 ]; then tput clear; fi` (checks if stdout is a terminal).

- **No `watch` dependency:** Good -- `watch` is not universally available on HPC systems. The custom poll loop with `read -t` is the right approach.

#### 2c. Nextflow 25.x Features That Could Help

Several Nextflow 25.x features are relevant to progress monitoring:

1. **`workflow.onComplete` / `workflow.onError` hooks (25.01+):** These are now native Nextflow features (no Groovy library needed). They can write a final summary file or send a notification. The monitor could detect this file to show a "PIPELINE COMPLETE" message reliably, rather than relying on `pgrep` to detect process exit.

2. **Trace file format improvements (25.04+):** Nextflow 25.04 added the `trace.overwrite` config option. With `trace.overwrite = true`, the trace file is rewritten on each event rather than appended. This makes parsing simpler (no need to handle multiple entries per task) but loses history. For the monitor, the append behavior (current default) is actually better because it preserves retry history. Keep `trace.overwrite = false` (the default).

3. **Nextflow Tower / Seqera Platform integration:** If the team ever adopts Seqera Platform (formerly Nextflow Tower), the `tower.yml` file in the repo enables automatic monitoring via a web UI. This would make `monitor_pipeline.sh` redundant for users with Platform access. However, on an air-gapped HPC system like Rosalind, the CLI monitor is the right approach.

4. **`nextflow log` command (all versions):** `nextflow log <run_name>` can show per-task details including status, duration, and exit code. The monitor could use this instead of parsing the trace file directly. However, `nextflow log` requires the Nextflow process to be running or the `.nextflow/` directory to be accessible, and it is slower than reading the trace file directly. The trace file approach is better for real-time monitoring.

#### 2d. Implementation Recommendations

1. **Add `--json` output mode** for programmatic consumption: `./monitor_pipeline.sh <proj_id> --json` outputs a JSON object with per-pathogen status. This enables future integration with web dashboards or Slack notifications.

2. **Handle the DASHBOARD process:** The monitor mockup shows DASHBOARD as "WAITING" until all TRENDY jobs complete. The trace file will show DASHBOARD status separately. The monitor should recognize the `SPLINE:DASHBOARD` process name and display it in its own section.

3. **Detect pipeline failure vs. completion:** The monitor currently uses `pgrep` to detect if Nextflow is running. A more reliable approach: check for the Nextflow exit marker. When Nextflow completes, it writes the `execution_report_*.html` file. Check for this file's existence and recency rather than (or in addition to) `pgrep`.

4. **Consider `inotifywait` as an alternative to polling:** On Linux systems with `inotify-tools` installed, `inotifywait -m -e modify <trace_file>` can trigger refreshes only when the trace file is updated, rather than polling every 15 seconds. This is more efficient and more responsive. However, `inotify-tools` may not be installed on all HPC systems, so keep polling as the fallback.

### 3. Integration with Existing Pipeline

The monitor script is purely external -- it reads Nextflow artifacts without modifying them. This is the correct design. No changes to the pipeline itself are needed for the monitor to work.

The integration points in `run_workflow.sh` (printing the monitor command after launch) are well-placed. One addition: when running in foreground mode, offer to launch the monitor in a background subshell automatically:

```bash
if [[ $background == false ]]; then
    echo ""
    echo -e "Launching pipeline monitor in background..."
    ./monitor_pipeline.sh "${timestamp}" --watch &
    MONITOR_PID=$!
    # Run Nextflow in foreground
    eval $cmd
    # Kill monitor after Nextflow exits
    kill $MONITOR_PID 2>/dev/null
fi
```

This gives foreground users automatic monitoring without needing a second terminal.

### 4. UX Plan Bug and Flow Fixes

The plan correctly identifies several real bugs and flow issues:

- **Bug: `continue` outside loop (line 708):** Confirmed. This is a real bug that will produce a bash error in certain pathogen validation scenarios.
- **Resume mode collecting ignored parameters:** Confirmed. Lines 1004-1195 should be guarded with `if [[ "$flag" != "resume" ]]`.
- **Background execution asked too early:** Correct assessment. Moving it to just before confirmation is better UX.
- **Quick-run fast path:** Well-designed. The `skip_to_summary` flag approach is clean and maintainable.

### 5. Local Executor for Lightweight Pipeline Steps

**Question:** Can PREPROCESS, RESOURCE_PROFILER, and DASHBOARD run on the local executor instead of SGE?

#### 5a. How to Configure Per-Process Executor in Nextflow DSL2

Nextflow supports per-process executor override. In `nextflow.config` or `conf/modules.config`, add:

```groovy
process {
    withName: 'PREPROCESS' {
        executor = 'local'
    }
    withName: 'RESOURCE_PROFILER' {
        executor = 'local'
    }
    withName: 'DASHBOARD' {
        executor = 'local'
    }
}
```

This overrides the global `process.executor = 'sge'` (nextflow.config line 130) for these three processes only. TRENDY would still use SGE.

Alternatively, use a label-based approach. The processes already have labels (`process_medium` for PREPROCESS, `process_low` for RESOURCE_PROFILER and DASHBOARD). You could set:

```groovy
process {
    withLabel: 'process_low' {
        executor = 'local'
    }
}
```

But this is less explicit and would apply to any future process with the `process_low` label. The `withName` approach is safer and more explicit.

#### 5b. Would This Break Anything?

**Container considerations:** All three processes have `container 'foodnet.sif'`. When using the `local` executor with Singularity enabled, Nextflow will still run the process inside the container -- it just executes `singularity exec` on the login node rather than submitting a `qsub` job. This works correctly as long as:
- Singularity is available on the login node (it is -- `run_workflow.sh` loads the `singularity` module).
- The login node has sufficient resources for these lightweight tasks.

**Resource requirements:**
- PREPROCESS: labeled `process_medium` (6 CPUs, 36 GB, 8h in `base.config`). In practice, preprocessing a ~500K-row SAS file takes seconds to a few minutes and uses minimal memory (<2 GB). The label is over-provisioned. For local execution, override resources:
  ```groovy
  withName: 'PREPROCESS' {
      executor = 'local'
      cpus = 1
      memory = '4.GB'
  }
  ```
- RESOURCE_PROFILER: labeled `process_low` (2 CPUs, 12 GB, 4h). In practice, it reads a CSV and computes group-by summaries -- under 30 seconds, <1 GB memory. Override to `cpus = 1; memory = '2.GB'`.
- DASHBOARD: labeled `process_low`. Generates an HTML report from CSV files -- under 2 minutes, <1 GB. Override similarly.

**Login node etiquette:** Running these on the login node is acceptable because they are fast (seconds to minutes) and lightweight (<2 GB memory). HPC systems generally allow short, light tasks on login nodes. Heavy tasks (TRENDY) would still go to SGE. However, check with the CDC HPC team's acceptable use policy for login node computation. Some sites have strict no-compute policies on login nodes.

**`-resume` behavior:** Changing the executor does NOT invalidate the task cache. Nextflow does not include the executor type in the task hash. A task cached from an SGE run can be reused in a local run and vice versa. This is correct behavior -- the executor choice does not affect results.

**Bind mounts:** The Singularity `--bind /scicomp` option from `singularity.runOptions` applies regardless of executor. Local execution still uses Singularity with the same bind mounts. No issue.

#### 5c. Would This Speed Up Pipeline Execution?

**Yes, significantly for initial pipeline startup.** The current flow is:

1. Nextflow submits PREPROCESS to SGE -> queue wait (30s-5min) -> execute (~1 min)
2. Nextflow submits RESOURCE_PROFILER to SGE -> queue wait (30s-5min) -> execute (~30s)
3. Nextflow submits TRENDY jobs to SGE -> queue wait -> execute (hours)
4. After all TRENDY done: submit DASHBOARD to SGE -> queue wait -> execute (~1 min)

With local executor for steps 1, 2, and 4:

1. PREPROCESS runs locally -> no queue wait -> execute (~1 min)
2. RESOURCE_PROFILER runs locally -> no queue wait -> execute (~30s)
3. TRENDY jobs submitted to SGE -> queue wait -> execute (hours)
4. After all TRENDY done: DASHBOARD runs locally -> no queue wait -> execute (~1 min)

**Time saved:** 2-15 minutes of queue wait time for 3 jobs. This is most noticeable in the startup phase: users currently wait 1-10 minutes after launch before TRENDY jobs even begin. With local execution of PREPROCESS and RESOURCE_PROFILER, TRENDY jobs are submitted within ~2 minutes of pipeline start.

For the DASHBOARD at the end, saving 30s-5min of queue wait means results are available sooner after the long TRENDY phase completes.

**The speedup is modest in absolute terms** (minutes saved on a multi-hour pipeline) but **significant for perceived responsiveness** -- the pipeline "feels" like it starts immediately.

#### 5d. Recommended Implementation

Add the following to `conf/modules.config` (or `nextflow.config`):

```groovy
process {
    withName: 'PREPROCESS' {
        executor = 'local'
        cpus = 1
        memory = '4.GB'
        time = '30.min'
    }
    withName: 'RESOURCE_PROFILER' {
        executor = 'local'
        cpus = 1
        memory = '2.GB'
        time = '10.min'
    }
    withName: 'DASHBOARD' {
        executor = 'local'
        cpus = 1
        memory = '2.GB'
        time = '30.min'
    }
}
```

**Testing plan:**
1. Run the pipeline and verify PREPROCESS, RESOURCE_PROFILER, and DASHBOARD execute locally (check `.nextflow.log` for executor type).
2. Verify these processes still run inside the Singularity container (check `.command.sh` in the work directory for `singularity exec`).
3. Verify TRENDY still submits to SGE.
4. Time the startup phase (pipeline launch to first TRENDY submission) and compare to the SGE-only baseline.
5. Verify `-resume` works correctly after switching executors.

**Risk:** Low. The only risk is if the login node has resource constraints that prevent even lightweight R scripts from running. Add a `local` profile that can be toggled:

```groovy
profiles {
    local_lightweight {
        process {
            withName: 'PREPROCESS' { executor = 'local'; cpus = 1; memory = '4.GB' }
            withName: 'RESOURCE_PROFILER' { executor = 'local'; cpus = 1; memory = '2.GB' }
            withName: 'DASHBOARD' { executor = 'local'; cpus = 1; memory = '2.GB' }
        }
    }
}
```

Then activate with `-profile singularity,local_lightweight`. This makes it opt-in rather than forced.

### 6. Verdict

**APPROVE.** The UX plan is thorough and the progress monitoring proposal is technically sound for the Nextflow/SGE environment. The monitor script design leverages the correct Nextflow artifacts (trace file, output file detection) and uses only POSIX-compatible tools suitable for HPC. Key recommendations:

1. Handle trace file retry entries explicitly in the awk parser.
2. Guard `tput` calls for non-terminal environments.
3. Consider `workflow.onComplete` hook (Nextflow 25.x) as a reliable pipeline-exit signal.
4. Add local executor for PREPROCESS, RESOURCE_PROFILER, and DASHBOARD to eliminate unnecessary SGE queue waits (implement as opt-in profile for safety).
5. Add `_convergence_diagnostics.csv` to the monitor's known output files (coordinate with Model Plan Step 5).

### Unified Implementation Sequence (All Five Plans)

| Phase | Plan | Changes | Rebuild? | Results? |
|-------|------|---------|----------|----------|
| 1a | Model Plan Steps 4,3,1,7,8 | `functions.R` only | No | YES (1,3) |
| 1b | Model Plan Steps 2,5,9 | `trendy.R` only | No | NO |
| 1c | Model Plan Step 6 | `preprocess.R` only | No | YES (2023+) |
| **CHECKPOINT: Full regression test** |||||
| 2a | Profiler Plan Changes 1-3 | `nextflow.config`, `trendy.nf` | No | NO |
| 2b | Profiler Plan Change 4 | `modules.config`, `nextflow.config` | No | NO |
| **CHECKPOINT: Verify resource allocation** |||||
| 3 | Container Plan (all) | `foodnet.def`, `foodnet.yml`, `pixi.toml`, `pixi.lock`, `nextflow.config` env | YES | NO |
| **CHECKPOINT: Verify container, all packages load** |||||
| 4 | Profiler Plan Changes 5-9 | `nextflow.config`, `trendy.nf`, `trendy.R`, `functions.R`, `run_workflow.sh` | No | NO |
| **CHECKPOINT: Test rstan and cmdstanr backends** |||||
| 5a | UX Plan: Bug fixes, flow improvements | `run_workflow.sh` | No | NO |
| 5b | UX Plan: `monitor_pipeline.sh` | New file | No | NO |
| 5c | UX Plan: Local executor for lightweight processes | `conf/modules.config` | No | NO |
| 6 | Cleanup Plan Priority 1-3 | Remove orphans, fix schema, fix test config | No | NO |
| 7 | Cleanup Plan Priority 4-6 | Documentation, future nf-core features | No | NO |
