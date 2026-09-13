# Overnight divergence-only refits

```bash
module load singularity && python3 scripts/launch_surveillance_sampler_refits.py
```

The default source is the September 13 saved-model audit. `--audit PATH` selects another audit explicitly. The launcher selects only fits whose sole independent saved-model diagnostic issue is divergent transitions. Other failures stop preparation; passing models are retained. For the current audit this schedules Shigella, Vibrio and non-O157 STEC.

Each receives 12 CPU slots, six chains, 10,001 iterations, the saved warmup/thinning, seed 123, and up to 48 hours. There is no additional concurrency cap. BLAS/OpenMP/MKL receive explicit two-thread limits inside the container. The existing 52 GB RSS request and 68 GB virtual-memory request are preserved; scheduler enforcement determines actual limits.

Only `adapt_delta` changes, to 0.9999. Saved data, numeric priors and generated Stan code must match exactly. Tree depth remains 15. Smaller sampling steps can reduce divergences but do not guarantee a reliable fit; see [Stan's sampler guidance](https://mc-stan.org/rstanarm/reference/adapt_delta.html). Persistent divergences require investigation rather than unattended repeated tuning.

The original models and input snapshots are preserved. A sampling checkpoint is written before exports, and the run produces estimate comparisons plus independent checkpoint diagnostics automatically. A dependent SGE collection job produces one archive with aggregate outputs, comparisons and diagnostics, excluding RDS checkpoints. No dashboard replacement occurs overnight.

After the launcher prints both scheduler job IDs, jobs continue independently of the terminal. The job IDs and final archive location are recorded in the new output directory. If submission fails after the array is accepted, do not rerun the launcher blindly: the array ID is retained in `array_job_id.txt` and its collection script can be submitted separately.

This batch resolves the immediate sampling gate. It does not launch new county model families or claim forecast calibration; those next-phase experiments depend on the outstanding validation work.
