#!/bin/bash
#
# monitor_pipeline.sh - Real-time progress monitor for FoodNetTrends pipeline
#
# Usage:
#   ./monitor_pipeline.sh output/20260313_160520
#   ./monitor_pipeline.sh -i 10 output/20260313_160520   # 10s refresh
#   ./monitor_pipeline.sh -1 output/20260313_160520       # single snapshot, no loop
#
# Parses Nextflow's execution trace file to show per-pathogen status
# with a terminal dashboard. Works over SSH and in tmux.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
REFRESH_INTERVAL=5
ONE_SHOT=false
OUTPUT_DIR=""

# ---------------------------------------------------------------------------
# Color and cursor support (guarded for non-interactive terminals)
# ---------------------------------------------------------------------------
setup_terminal() {
    if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
        BOLD=$(tput bold 2>/dev/null || true)
        DIM=$(tput dim 2>/dev/null || true)
        RESET=$(tput sgr0 2>/dev/null || true)
        GREEN=$(tput setaf 2 2>/dev/null || true)
        RED=$(tput setaf 1 2>/dev/null || true)
        YELLOW=$(tput setaf 3 2>/dev/null || true)
        CYAN=$(tput setaf 6 2>/dev/null || true)
        WHITE=$(tput setaf 7 2>/dev/null || true)
        CAN_CLEAR=true
    else
        BOLD="" DIM="" RESET="" GREEN="" RED="" YELLOW="" CYAN="" WHITE=""
        CAN_CLEAR=false
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS] <output_directory>

Monitor FoodNetTrends pipeline progress by reading Nextflow trace files.

Options:
  -i SECONDS   Refresh interval (default: 5)
  -1           Single snapshot, then exit (no refresh loop)
  -h           Show this help message

Examples:
  $(basename "$0") output/20260313_160520
  $(basename "$0") -i 10 output/20260313_160520
  $(basename "$0") -1 output/20260313_160520
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        -i)
            shift
            if [ $# -eq 0 ] || ! [[ "$1" =~ ^[0-9]+$ ]]; then
                echo "Error: -i requires a numeric argument" >&2
                exit 1
            fi
            REFRESH_INTERVAL="$1"
            ;;
        -1)
            ONE_SHOT=true
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage
            ;;
        *)
            OUTPUT_DIR="$1"
            ;;
    esac
    shift
done

if [ -z "$OUTPUT_DIR" ]; then
    echo "Error: output directory required" >&2
    echo "Usage: $(basename "$0") [-i SECONDS] [-1] <output_directory>" >&2
    exit 1
fi

if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: directory not found: $OUTPUT_DIR" >&2
    exit 1
fi

setup_terminal

# ---------------------------------------------------------------------------
# Locate trace file
# ---------------------------------------------------------------------------
find_trace_file() {
    local trace_dir="${OUTPUT_DIR}/pipeline_info"
    local trace_file=""

    if [ -d "$trace_dir" ]; then
        # Find the most recent execution_trace file
        trace_file=$(ls -t "${trace_dir}"/execution_trace_*.txt 2>/dev/null | head -1)
    fi

    # Fallback: check for trace.txt in the output dir itself
    if [ -z "$trace_file" ] && [ -f "${OUTPUT_DIR}/trace.txt" ]; then
        trace_file="${OUTPUT_DIR}/trace.txt"
    fi

    echo "$trace_file"
}

# ---------------------------------------------------------------------------
# Extract project ID from directory name
# ---------------------------------------------------------------------------
extract_project_id() {
    basename "$OUTPUT_DIR"
}

# ---------------------------------------------------------------------------
# Parse the trace file into structured per-process data
#
# Nextflow trace files are TSV with columns that vary by version, but
# typically include: task_id, hash, native_id, name, status, exit,
# submit, start, complete, duration, realtime, %cpu, peak_rss, ...
#
# We look for process names containing pathogen identifiers and extract
# status, duration, and peak memory.
# ---------------------------------------------------------------------------
parse_trace() {
    local trace_file="$1"

    if [ ! -f "$trace_file" ]; then
        return
    fi

    # Read header to find column indices (0-based)
    local header
    header=$(head -1 "$trace_file")

    # Determine separator (tab or whitespace)
    local sep=$'\t'

    # Map column names to indices
    local name_col=-1 status_col=-1 duration_col=-1 realtime_col=-1 peak_rss_col=-1
    local i=0
    local IFS_save="$IFS"
    IFS="$sep"
    for col in $header; do
        # Strip leading/trailing whitespace
        col=$(echo "$col" | tr -d '[:space:]')
        case "$col" in
            name)      name_col=$i ;;
            status)    status_col=$i ;;
            duration)  duration_col=$i ;;
            realtime)  realtime_col=$i ;;
            peak_rss)  peak_rss_col=$i ;;
        esac
        i=$((i + 1))
    done
    IFS="$IFS_save"

    if [ "$name_col" -eq -1 ] || [ "$status_col" -eq -1 ]; then
        return
    fi

    # Parse each data row (skip header)
    tail -n +2 "$trace_file" | while IFS="$sep" read -r line_raw; do
        # Split line into array
        local IFS_inner="$IFS"
        IFS="$sep"
        local -a fields=($line_raw)
        IFS="$IFS_inner"

        local name="${fields[$name_col]:-}"
        local status="${fields[$status_col]:-}"
        local duration="${fields[$realtime_col]:-${fields[$duration_col]:-}}"
        local peak_mem="${fields[$peak_rss_col]:-}"

        # Strip surrounding whitespace
        name=$(echo "$name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        status=$(echo "$status" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        duration=$(echo "$duration" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        peak_mem=$(echo "$peak_mem" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

        # Output structured line: name|status|duration|peak_mem
        if [ -n "$name" ]; then
            echo "${name}|${status}|${duration}|${peak_mem}"
        fi
    done
}

# ---------------------------------------------------------------------------
# Map Nextflow status to display status
# ---------------------------------------------------------------------------
format_status() {
    local status="$1"
    case "$status" in
        COMPLETED)  echo "${GREEN}DONE${RESET}" ;;
        CACHED)     echo "${GREEN}CACHED${RESET}" ;;
        RUNNING)    echo "${CYAN}RUNNING${RESET}" ;;
        SUBMITTED)  echo "${YELLOW}QUEUED${RESET}" ;;
        FAILED)     echo "${RED}FAILED${RESET}" ;;
        ABORTED)    echo "${RED}ABORTED${RESET}" ;;
        *)          echo "${DIM}${status:-UNKNOWN}${RESET}" ;;
    esac
}

# Plain status for width calculation (no ANSI)
format_status_plain() {
    local status="$1"
    case "$status" in
        COMPLETED)  echo "DONE" ;;
        CACHED)     echo "CACHED" ;;
        RUNNING)    echo "RUNNING" ;;
        SUBMITTED)  echo "QUEUED" ;;
        FAILED)     echo "FAILED" ;;
        ABORTED)    echo "ABORTED" ;;
        *)          echo "${status:-UNKNOWN}" ;;
    esac
}

# Status indicator symbol
status_symbol() {
    local status="$1"
    case "$status" in
        COMPLETED|CACHED) echo "${GREEN}+${RESET}" ;;
        RUNNING)          echo "${CYAN}*${RESET}" ;;
        SUBMITTED)        echo "${DIM}o${RESET}" ;;
        FAILED|ABORTED)   echo "${RED}x${RESET}" ;;
        *)                echo "${DIM}-${RESET}" ;;
    esac
}

# ---------------------------------------------------------------------------
# Extract pathogen name from Nextflow process name
# e.g. "SPLINE:TRENDY (CAMPYLOBACTER~combined)" -> "CAMPYLOBACTER"
#      "SPLINE:PREPROCESS (1)"                   -> "PREPROCESS"
#      "SPLINE:DASHBOARD (1)"                    -> "DASHBOARD"
# ---------------------------------------------------------------------------
extract_pathogen() {
    local name="$1"
    local pathogen

    # Try to extract from parenthesized pathogen~grouping
    if echo "$name" | grep -qE '\([A-Z]+~'; then
        pathogen=$(echo "$name" | sed -E 's/.*\(([A-Z]+)~.*/\1/')
        echo "$pathogen"
        return
    fi

    # Try to extract process step name (e.g., PREPROCESS, DASHBOARD, RESOURCE_PROFILER)
    if echo "$name" | grep -qE '(PREPROCESS|DASHBOARD|RESOURCE_PROFILER|MERGE)'; then
        pathogen=$(echo "$name" | sed -E 's/.*:([ ]*)?([A-Z_]+)[ ]*.*/\2/')
        echo "$pathogen"
        return
    fi

    # Fallback: use the full name
    echo "$name"
}

# ---------------------------------------------------------------------------
# Render the dashboard
# ---------------------------------------------------------------------------
render_dashboard() {
    local trace_file="$1"
    local proj_id
    proj_id=$(extract_project_id)

    # Parse the trace
    local trace_data
    trace_data=$(parse_trace "$trace_file")

    # Aggregate per-pathogen: take the latest entry for each pathogen
    # (processes may appear multiple times if retried)
    declare -A pathogen_status
    declare -A pathogen_duration
    declare -A pathogen_memory
    declare -a pathogen_order=()
    declare -A pathogen_seen

    if [ -n "$trace_data" ]; then
        while IFS='|' read -r name status duration peak_mem; do
            local pathogen
            pathogen=$(extract_pathogen "$name")

            # Track insertion order
            if [ -z "${pathogen_seen[$pathogen]+x}" ]; then
                pathogen_order+=("$pathogen")
                pathogen_seen[$pathogen]=1
            fi

            # Overwrite with latest data for this pathogen
            pathogen_status[$pathogen]="$status"
            pathogen_duration[$pathogen]="$duration"
            pathogen_memory[$pathogen]="$peak_mem"
        done <<< "$trace_data"
    fi

    # Compute summary statistics
    local total=${#pathogen_order[@]}
    local completed=0
    local failed=0
    local running=0

    for p in "${pathogen_order[@]}"; do
        case "${pathogen_status[$p]}" in
            COMPLETED|CACHED) completed=$((completed + 1)) ;;
            FAILED|ABORTED)   failed=$((failed + 1)) ;;
            RUNNING)          running=$((running + 1)) ;;
        esac
    done

    # Calculate elapsed time from trace file modification
    local start_time=""
    local elapsed=""
    if [ -f "$trace_file" ]; then
        start_time=$(stat -c %Y "$trace_file" 2>/dev/null || stat -f %m "$trace_file" 2>/dev/null || echo "")
        if [ -n "$start_time" ]; then
            local now
            now=$(date +%s)
            local elapsed_secs=$((now - start_time))
            # Trace file mtime updates on every write, so use file creation
            # from the directory instead
        fi
    fi

    # Try to get start time from directory creation
    local dir_time
    dir_time=$(stat -c %W "$OUTPUT_DIR" 2>/dev/null || echo "0")
    if [ "$dir_time" = "0" ] || [ -z "$dir_time" ]; then
        dir_time=$(stat -c %Y "$OUTPUT_DIR" 2>/dev/null || echo "")
    fi
    if [ -n "$dir_time" ] && [ "$dir_time" != "0" ]; then
        local now
        now=$(date +%s)
        local elapsed_secs=$((now - dir_time))
        if [ $elapsed_secs -lt 0 ]; then elapsed_secs=0; fi
        local em=$((elapsed_secs / 60))
        local es=$((elapsed_secs % 60))
        elapsed="${em}m $(printf '%02d' $es)s"
        start_time=$(date -d "@$dir_time" '+%Y-%m-%d %H:%M' 2>/dev/null || date -r "$dir_time" '+%Y-%m-%d %H:%M' 2>/dev/null || echo "unknown")
    else
        elapsed="--"
        start_time="unknown"
    fi

    # --- Render ---
    local W=60  # dashboard width

    # Clear screen if interactive, otherwise just print
    if [ "$CAN_CLEAR" = true ]; then
        tput clear 2>/dev/null || true
        tput cup 0 0 2>/dev/null || true
    fi

    local border_top border_mid border_bot
    border_top=$(printf '%0.s=' $(seq 1 $W))
    border_mid=$(printf '%0.s=' $(seq 1 $W))
    border_bot=$(printf '%0.s=' $(seq 1 $W))

    # Header
    echo "${BOLD}+${border_top}+${RESET}"
    printf "${BOLD}|${RESET}  %-28s %s  %-22s ${BOLD}|${RESET}\n" \
        "FoodNetTrends Pipeline Monitor" "|" "Project: ${proj_id:0:16}"
    printf "${BOLD}|${RESET}  %-28s %s  %-22s ${BOLD}|${RESET}\n" \
        "Started: ${start_time}" "|" "Elapsed: ${elapsed}"
    echo "${BOLD}+${border_mid}+${RESET}"

    # Column headers
    printf "${BOLD}|${RESET}  ${BOLD}%-18s %-10s %-12s %-14s${RESET}  ${BOLD}|${RESET}\n" \
        "Pathogen" "Status" "Runtime" "Peak Mem"

    # Separator
    printf "${BOLD}|${RESET}  %s  ${BOLD}|${RESET}\n" \
        "$(printf '%0.s-' $(seq 1 $((W - 4))))"

    if [ ${#pathogen_order[@]} -eq 0 ]; then
        printf "${BOLD}|${RESET}  ${DIM}%-$((W-4))s${RESET}  ${BOLD}|${RESET}\n" \
            "Waiting for pipeline to start..."
    else
        for p in "${pathogen_order[@]}"; do
            local st="${pathogen_status[$p]:-SUBMITTED}"
            local dur="${pathogen_duration[$p]:---}"
            local mem="${pathogen_memory[$p]:---}"
            local sym
            sym=$(status_symbol "$st")
            local st_display
            st_display=$(format_status "$st")

            # Trim duration/memory display
            [ "$dur" = "-" ] && dur="--"
            [ "$mem" = "-" ] || [ "$mem" = "0" ] && mem="--"

            printf "${BOLD}|${RESET}  %s %-17s %-18s %-12s %-14s ${BOLD}|${RESET}\n" \
                "$sym" "$p" "$st_display" "$dur" "$mem"
        done
    fi

    # Footer
    echo "${BOLD}+${border_mid}+${RESET}"

    local refresh_note
    if [ "$ONE_SHOT" = true ]; then
        refresh_note="snapshot"
    else
        refresh_note="@ ${REFRESH_INTERVAL}s refresh"
    fi

    printf "${BOLD}|${RESET}  Progress: %d/%d complete  |  %d failed  |  %s  ${BOLD}|${RESET}\n" \
        "$completed" "$total" "$failed" "$refresh_note"
    echo "${BOLD}+${border_bot}+${RESET}"

    # Check if all done
    if [ "$total" -gt 0 ] && [ $((completed + failed)) -ge "$total" ]; then
        echo ""
        if [ "$failed" -gt 0 ]; then
            echo "${RED}${BOLD}Pipeline finished with ${failed} failure(s).${RESET}"
        else
            echo "${GREEN}${BOLD}Pipeline completed successfully.${RESET}"
        fi
        return 1  # Signal to stop refreshing
    fi

    return 0
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
main() {
    local trace_file
    trace_file=$(find_trace_file)

    if [ -z "$trace_file" ]; then
        echo "Waiting for trace file in ${OUTPUT_DIR}/pipeline_info/ ..."
        while [ -z "$trace_file" ]; do
            sleep "$REFRESH_INTERVAL"
            trace_file=$(find_trace_file)
        done
        echo "Found trace file: $trace_file"
    fi

    # Trap Ctrl+C for clean exit
    trap 'printf "\n%s\n" "Monitor stopped."; exit 0' INT TERM

    if [ "$ONE_SHOT" = true ]; then
        render_dashboard "$trace_file"
        exit 0
    fi

    while true; do
        # Re-check trace file in case a new one appeared (pipeline restart)
        trace_file=$(find_trace_file)
        if [ -z "$trace_file" ]; then
            sleep "$REFRESH_INTERVAL"
            continue
        fi

        if ! render_dashboard "$trace_file"; then
            # Pipeline is done
            break
        fi

        sleep "$REFRESH_INTERVAL"
    done
}

main
