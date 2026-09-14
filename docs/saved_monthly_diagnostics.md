# Saved monthly sampling and tail diagnostics

This follow-up reuses all twelve completed monthly comparison fits. It never calls a fitting function, reruns preprocessing, changes the coverage assumption or modifies saved inputs. It writes fresh diagnostics into a new output directory.

Run from FoodNetTrends on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_saved_monthly_diagnostics.py
```

The launcher verifies the original plan, successful task identities, and recorded checksums of each saved fit and relevant prediction reports. It snapshots its scripts and submits twelve independent array tasks with no concurrency cap. Each requests two slots, h_rss/mem_free 32768M, h_vmem 48G and a 24-hour limit. The limit is not a runtime estimate. Seeded INLA posterior sampling uses one thread for reproducibility; extra cores would not accelerate that step under this implementation. Parallelism is across the twelve fits.

The collector is held until the array ends. Once both IDs print, the jobs require no open terminal. A single archive contains completed diagnostics and explicit failed/missing statuses. Do not relaunch successful fits if a sampling task fails.

## Identity and numerical checks

The R worker verifies the saved model specification, seasonal/nonseasonal identity, likelihood and posterior configurations, training-only centering, held-out masking, positive exposure, and exact held-out row ordering against the original prediction CSV. Recorded fit hashes bind the checkpoint to its original run; this diagnostic does not attempt to reconstruct the original raw-data audit. Saved fit and prediction checksums must be unchanged after sampling.

Each task uses four fresh streams of 2,000 draws, totaling 8,000. Seeds are disjoint across streams, tasks, and the original comparison batch; predictive count simulation has separate seed blocks from INLA sampling. Sampling retains the original `skew.corr=FALSE` approximation. These are posterior samples from the saved INLA approximation, not new MCMC chains or independent datasets; R-hat is not an appropriate diagnostic here.

Stable density-moment accumulation avoids underflow. Each stream and the pooled sample report mean county log predictive density by site/year and the largest cell-level relative Monte Carlo error estimate in that group. That maximum is a diagnostic for problematic cells, not a standard error for the group score. Paired seasonal-minus-reference scores are reported for every stream and pooled sample. Across-stream variation measures sampling variation conditional on the existing approximation; it cannot diagnose all INLA approximation error or validate real-time forecast performance.

## Tail diagnostics

Joint draws are summed to site/year and catchment/year totals before summarizing. For each independent stream and the pooled sample, the report contains expected-count mean, median, 97.5th percentile and maximum, the fraction of the mean contributed by the largest 1% of expected-count draws, predictive intervals and the posterior predictive fraction exceeding twice the held-out observed total. The latter is a retrospective tail diagnostic, not a prospective threshold or a model-selection rule.

A large top-1% contribution indicates sensitivity of the mean to rare large draws. Compare it with stability of medians, intervals and scores across streams. A stable heavy tail may be a property of the model; more samples do not fix an unsuitable forecast distribution. An unstable tail requires numerical review before interpreting the mean. Four streams are a diagnostic, not a guarantee that extreme tails have converged.

The report also includes negative-binomial size summaries and mean latent log-predictor SD by site/year to help distinguish predictive count variation from expanding latent uncertainty. Original score and catchment summaries are copied for comparison. County-level density diagnostics are aggregate case-count results, not individual records.

Large aggregate draw matrices remain on the cluster as a checksummed RDS, excluded from the portable archive. The new archive retains the assumed-coverage limitation and does not promote any model or alter Daniel's accepted outputs.

Local tests cover stable density arithmetic, contribution of rare large draws, invalid/reordered saved rows, model identity mismatch, unchanged input hashes, actual resampling from a small synthetic saved fit, seed isolation, scheduler dispatch, changed-checkpoint rejection and partial-failure archives. Full-scale resource use remains a cluster check.
