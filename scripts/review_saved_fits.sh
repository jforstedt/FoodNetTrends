#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project=${1:?Supply the feature project ID}
[[ "$project" =~ ^[A-Za-z0-9_-]+$ ]] || exit 1
command -v singularity >/dev/null || module load singularity
review="output/$project/saved_fit_review_$(date +%Y%m%d_%H%M%S)_$$"
status=0
singularity exec --bind /scicomp foodnet.sif Rscript scripts/review_saved_fits.R "output/$project" "$review" || status=$?
if [[ -d "$review" ]]; then
  tar -czf "$review.tar.gz" -C "$(dirname "$review")" "$(basename "$review")"
  echo "Review report: $PWD/$review/review.txt"
  echo "Report and plots: $PWD/$review.tar.gz"
fi
exit "$status"
