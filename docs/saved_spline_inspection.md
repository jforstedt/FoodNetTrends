# Read-only inspection before revisiting spline combinations

The recovered Campylobacter 2011 spatial spline emitted aborted approximation
corrections and implausible predictions. Inspect its saved object alongside the
matched IID spline before diagnosing the cause. Execution completion and a passed
synthetic gate do not resolve this real-fit numerical problem.

`launch_saved_spline_inspection.py` submits one two-core job that reads both
checkpoints concurrently using the existing fixed INLA container. It extracts
hyperparameter/fixed-effect summaries, ranges of random and predictor summaries,
optimizer structure, configuration theta values and existing CPO flags. Native
predictor scales are retained; no posterior mean count is inferred by exponentiating
a mean log predictor. CPO flags may include prediction-only rows and must not be
interpreted automatically as training failures.

The job performs no fitting or posterior sampling. It verifies source task outputs,
pins current checkpoint/input/script hashes and the submitted plan, then rechecks
inputs after inspection. Older checkpoints still lack original completion-time
byte certification. Originals are untouched, RDS files stay on the cluster, and one
internal archive contains reports, original logs and a report checksum manifest.

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_saved_spline_inspection.py
```

Default source: `next_phase_recovery_20260913_163836_142708`. A two-hour limit and
32GB RSS/64GB virtual-memory request allow loading both checkpoints; that limit is
not an expected runtime. The launcher prints the job, log and archive paths.

Local tests exercise saved-object immutability, variant mismatch rejection,
nonfinite summary reporting, unverified/changed-plan blocking, and Python 3.6
syntax. They do not diagnose the unavailable real cluster checkpoints.

Spline plus seasonality remains a planned controlled comparison under the
[combination protocol](extension_combination_protocol.md). First resolve or isolate
the numerical failure and pass appropriate checks for the revised candidate.
Adding seasonality must not be used to conceal unresolved approximation errors.
No new smoothing prior or model combination is selected by this inspection.
