# Parallel county investigations

This batch follows the reviewed recovery run
`county_forecast_recovery_20260913_140522_657935`. It preserves accepted state
analyses and published dashboards. Every result remains exploratory until review.

## Work and dependencies

| Work | Tasks | CPUs per task | Purpose |
|---|---:|---:|---|
| Saved posterior sampling | 53 | 2 | Four independent 4,000-draw streams per existing fit; no refitting |
| Raw definition audit | 1 | 2 | Date consistency, laboratory-name support, raw test-code overlap and candidate identifiers |
| Cyclospora failure investigation | 2 | 1 and 8 | Repeat the failed 2011 spatial county-time specification with verbose logs at two thread counts |
| Training-only spline basis | 1 | 2 | Construct frozen bases using the existing FoodNet container |
| Spline numerical checks | 1 | 2 | Horizon invariance, held-out masking and an exact Gaussian reference |
| Spline pilot | 12 | 8 | Salmonella/Campylobacter, three forecast origins, spatial/IID variants |

Seven execution jobs/arrays and one final collector are submitted. The scheduler
can run independent tasks concurrently, without an array concurrency cap imposed
by the launcher. The spline gate waits for basis construction; all twelve spline
fits wait for the gate. Workers check successful prerequisite artifacts and hashes,
not just scheduler completion. The collector waits for all seven job IDs and
reports missing or failed tasks, including jobs terminated outside Python.

Sampling, spline and Cyclospora jobs request 24 hours, `h_rss=32768M`,
`mem_free=32768M`, and `h_vmem=64G`; remaining jobs request four hours,
`h_rss=16384M`, `mem_free=16384M`, and `h_vmem=32G`. These are scheduler requests,
whose per-slot enforcement is cluster-specific. BLAS threading is capped at one;
INLA receives the task's explicit thread allocation. No new container build is
needed: basis/raw work uses `foodnet.sif`, other R tasks use
`foodnet-inla-fixed.sif`.

## Interpretation

The [spline candidate](county_spline_candidate.md) uses a negative-binomial
likelihood and explicitly specified slope/spline priors. It is a temporal-model
comparison, not a reproduction of Daniel's state-model posterior. Training bases
exclude future observations. The pilot uses the same audited county footprints,
origins and three-year horizons as the RW1 comparison.

[Saved sampling](saved_forecast_sampling.md) estimates Monte Carlo stability,
including state/year score sums. Four streams do not provide four independent
forecast datasets. The collector also compares spline point log scores with RW1
predictive densities pooled across four equal-length streams (log-mean-exp per
cell, then summed). Spline predictions use 4,000 draws versus 16,000 pooled RW1
draws. Review Monte Carlo error, coverage, pathogen-specific failures and overlapping
origins before interpreting score differences. There is no automatic winner,
acceptance threshold or dashboard promotion in this exploratory batch.

The two Cyclospora fits investigate the prior segmentation failure. Completion
would establish execution at that thread count, not the cause of the crash or
adequate predictive performance. Neither substitutes automatically for the missing
forecast evaluation.

The definition audit reports aggregate date disagreement/delay counts, test-code
crosswalks and identifier completeness/duplication counts. It exports neither
laboratory names nor identifier values. Case/whitespace normalization treats unknown
labels as missing. Repeated identifiers are not automatically duplicate illnesses;
raw test codes require a data dictionary. These outputs do not establish laboratory
adoption dates, valid monthly exposure, structural zeros or causal testing effects.

## Running and reviewing

From the repository on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_next_phase_batch.py
```

Wait for all eight job IDs before disconnecting. A timestamped directory records
source snapshots, input fingerprints, shell logs and individual task statuses.
The collector writes `summary.json`, comparison tables and one `.tar.gz` archive.
Saved and newly fitted RDS checkpoints stay on the cluster. The archive contains
internal county results and raw-code aggregates; it must not be committed publicly.

`--prepare-only` creates a non-executable, unverified plan for local launcher tests.
A failed or partial submission is recorded in `submission.json`; inspect that ledger
before launching again to avoid duplicating successful submissions. The launcher
never silently refits a missing saved checkpoint.

## Non-array dispatch correction and targeted recovery

The first cluster batch completed all 53 sampling tasks. Five single-task jobs
produced no worker status, and all twelve spline tasks stopped at their prerequisite
checks before fitting. The original dispatch used `${SGE_TASK_ID:-1}` for every job.
SGE supplies the literal `undefined` for non-array jobs, so that expression does not
fall back to 1 and the shell exits before worker logging. This behavior is documented
in the [Grid Engine qsub manual](https://gridscheduler.sourceforge.net/htmlman/htmlman1/qsub.html).
The archive pattern is consistent with that fault; it does not itself record the
failed jobs' environment variables.

Single-task jobs now receive an explicit task name; only arrays inspect the task
index. An executed shell regression covers `undefined` and valid array indices.
Recovery uses the original scientific worker snapshots, verifies the 53 completed
sampling artifacts and inputs, copies their report directories, and submits only
the other 17 tasks. It retains the basis/gate dependencies and never retries the
sampling array. The original run remains intact. A submission claim prevents
accidental duplicate recovery; inspect its destination ledger after an interrupted
submission before attempting any further recovery.

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/recover_next_phase_batch.py
```

Wait for all **seven** recovery job IDs. The new directory and final archive use
`next_phase_recovery_...`; the report combines reused sampling and new task results.
Local tests verify dispatch, copied fingerprints, rejection of changed sampling
outputs, unchanged model commands and omission of sampling submissions. No model
formulas, priors or accepted state outputs are changed by this correction.
