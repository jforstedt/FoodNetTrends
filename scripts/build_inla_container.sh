#!/usr/bin/env bash
# Build and test a separate INLA SIF; publish it only after both steps pass.
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output="$repo_dir/foodnet-inla.sif"
fakeroot=()
output_set=false
for arg in "$@"; do
    case "$arg" in
        --fakeroot) fakeroot=(--fakeroot) ;;
        -h|--help)
            echo "Usage: bash scripts/build_inla_container.sh [OUTPUT.sif] [--fakeroot]"
            echo "Set INLA_CONTAINER_RUNTIME to singularity or apptainer if needed."
            exit 0 ;;
        -*) echo "Unknown option: $arg" >&2; exit 2 ;;
        *)
            if "$output_set"; then echo "Only one output path is allowed" >&2; exit 2; fi
            output=$arg; output_set=true ;;
    esac
done
if [[ $(basename -- "$output") == foodnet.sif ]]; then
    echo "Refusing the production container name foodnet.sif; choose a separate INLA image." >&2
    exit 2
fi
if [[ -e "$output" || -L "$output" ]]; then
    echo "Output already exists: $output. Choose a new filename." >&2
    exit 2
fi
if [[ $(uname -m) != x86_64 ]]; then
    echo "This pinned INLA container currently supports Linux x86_64 only." >&2
    exit 2
fi
runtime=${INLA_CONTAINER_RUNTIME:-}
if [[ -z "$runtime" ]]; then
    if command -v singularity >/dev/null 2>&1; then runtime=singularity
    elif command -v apptainer >/dev/null 2>&1; then runtime=apptainer
    else echo "Load singularity/apptainer before building the INLA container." >&2; exit 127
    fi
fi
command -v "$runtime" >/dev/null 2>&1 || { echo "Runtime not found: $runtime" >&2; exit 127; }
mkdir -p -- "$(dirname -- "$output")"
output_dir=$(cd -- "$(dirname -- "$output")" && pwd)
output="$output_dir/$(basename -- "$output")"
stage=$(mktemp -d "$output_dir/.foodnet-inla-build.XXXXXXXX")
log=$(mktemp "$output_dir/foodnet-inla-build.XXXXXXXX.log")
trap 'rm -rf -- "$stage"' EXIT
echo "Build log: $log"
cd -- "$repo_dir"
{
    "$runtime" --version
    "$runtime" build "${fakeroot[@]}" "$stage/image.sif" containers/foodnet-inla.def
    # Repeat the synthetic fit in the finished, read-only SIF.
    "$runtime" test --cleanenv "$stage/image.sif"
    # A hard link creates the destination atomically and refuses an existing path.
    ln -- "$stage/image.sif" "$output"
    sha256sum -- "$output"
    echo "INLA CONTAINER COMPLETE: $output"
} 2>&1 | tee "$log"
