#!/usr/bin/env bash
# One report: contract tests, synthetic end-to-end features, real-data membership.
set -euo pipefail
cd "$(dirname "$0")/.."
project_id=${1:?Usage: bash scripts/validate_features.sh PROJECT_ID}
[[ "$project_id" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Invalid project ID' >&2; exit 1; }
[[ -d "output/$project_id" ]] || { echo 'Completed output directory not found' >&2; exit 1; }
command -v singularity >/dev/null
command -v python3 >/dev/null
report="foodnet_feature_validation_${project_id}_$(date +%Y%m%d_%H%M%S).txt"
set -o noclobber
: > "$report"
set +o noclobber
validation_tmp=$(mktemp -d "$PWD/.feature-validation.XXXXXX")
trap 'status=$?; rm -rf -- "$validation_tmp"; if (( status != 0 )); then echo "Validation failed; details saved: $PWD/$report" >&2; fi' EXIT
export TMPDIR="$validation_tmp"
export FOODNET_RSCRIPT='singularity exec --bind /scicomp foodnet.sif Rscript'
(
  set -e
  echo 'Feature acceptance checks: synthetic model draws, not new scientific fits.'
  git log -1 --format='%h %s'
  singularity exec --bind /scicomp foodnet.sif Rscript tests/test_analysis.R
  singularity exec --bind /scicomp foodnet.sif Rscript tests/test_parasite_coverage.R
  python3 tests/test_feature_matrix.py
  singularity exec --bind /scicomp foodnet.sif Rscript scripts/validate_feature_inputs.R "output/$project_id"
  echo 'ALL ACCEPTANCE CHECKS PASSED'
) >> "$report" 2>&1
echo "Report saved: $PWD/$report"
