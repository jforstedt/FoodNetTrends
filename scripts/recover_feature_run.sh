#!/usr/bin/env bash
# Restore the login-node tools, then resume the saved session under nohup.
set -eo pipefail
worker=false
if [[ ${1:-} == --worker ]]; then worker=true; shift; fi
project=${1:?Usage: bash scripts/recover_feature_run.sh PROJECT_ID SESSION_UUID}
session=${2:?Supply the original Nextflow session UUID}
[[ $project =~ ^[A-Za-z0-9_-]+$ && $session =~ ^[0-9a-f-]{36}$ ]] || { echo 'Invalid project or session ID' >&2; exit 1; }
cd "$(dirname "$0")/.."
plan="$PWD/output/$project/validation_plan"
[[ -f "$plan/resume.sh" && -f "$plan/params.json" ]] || { echo 'Saved run plan missing' >&2; exit 1; }
if [[ $worker == true ]]; then
  # FD 9 inherits the recovery lock held by the parent.
  set +e
  bash "$plan/resume.sh" "$session"
  result=$?
  python3 scripts/collect_run_diagnostics.py "$project" --skip-accounting
  collection_result=$?
  echo "Nextflow exit status: $result; diagnostics collection exit status: $collection_result"
  exit "$result"
fi
# Initialize environment modules in a fresh non-interactive login shell if needed.
if ! type module >/dev/null 2>&1; then
  for init in /etc/profile.d/modules.sh /usr/share/Modules/init/bash /usr/share/lmod/lmod/init/bash; do
    if [[ -r $init ]]; then source "$init"; break; fi
  done
fi
for tool in nextflow singularity java; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    type module >/dev/null 2>&1 || { echo "Missing $tool and environment modules are unavailable" >&2; exit 1; }
    case "$tool" in
      nextflow) module load nextflow/24.10.4 ;;
      singularity) module load singularity/4.1.4 ;;
      java) module load java/17.0.6 ;;
    esac
  fi
done
for tool in nextflow singularity java python3 nohup setsid flock; do
  command -v "$tool" >/dev/null || { echo "Required command missing: $tool" >&2; exit 1; }
done
# Preserve the Nextflow version recorded by this run, even if the module default differs.
version=$(python3 - "$plan" "$session" <<'PY'
import pathlib,re,sys
plan=pathlib.Path(sys.argv[1]); session=sys.argv[2]
for log in sorted(plan.glob('nextflow.log*'), key=lambda p:p.stat().st_mtime, reverse=True):
    text=log.read_text(errors='replace')
    if 'Session UUID: '+session not in text: continue
    match=re.search(r'N E X T F L O W\s*~\s*version\s+(\d+\.\d+\.\d+)',text)
    if match:
        print(match.group(1));break
else:
    sys.exit('Cannot establish original session/version from saved logs; no jobs started')
PY
)
export NXF_VER="$version"
export NXF_ANSI_LOG=false
exec 9> "$plan/recovery.lock"
flock -n 9 || { echo 'A recovery launcher is already active for this project' >&2; exit 1; }
stamp=$(date +%Y%m%d_%H%M%S)
log="$plan/recovery_${stamp}.log"
echo "Checking Nextflow $NXF_VER before starting recovery..."
nextflow -version
singularity --version
nohup setsid bash "$PWD/scripts/recover_feature_run.sh" --worker "$project" "$session" > "$log" 2>&1 < /dev/null &
echo "Recovery launcher PID: $!"
echo "Progress and final report path: $log"
