# Targeted numerical recovery of two monthly spatial fits

Source: broader_combinations_20260914_130328_942214/spatial. Its verified inventory has 322 completed cells and two failed new cells: LISTERIA_2011_ar1_seasonal_bym2 and SHIGELLA_2011_ar1_seasonal_bym2. Listeria's INLA executable crashed. Shigella failed the existing numerical fit gate; its warning file was empty, so the portable evidence does not identify which fit-status condition failed.

Retry exactly these two tasks concurrently, with INLA fitting threads changed from 4:1 to 1:1. This is an execution-stability attempt, not a demonstrated cure. Retain the frozen model code, formula, priors, likelihood, graph, exposures, training cutoffs, posterior scoring seeds and numerical acceptance checks. Single-thread execution can change floating-point paths; successful retries still require scientific comparison. No numerical quality threshold is relaxed.

The wrapper records fit_ok and mode_status before the existing gate. A crash before return can still prevent this file from being written. The original wrapper saves accepted checkpoints only after its gate; recovery does not claim to repair or accept failed checkpoints.

The launcher reads and hashes the original snapshots and writes a new recovery directory. It submits two one-CPU tasks with the original 52 GB RSS / 68 GB virtual-memory requests and a 48-hour limit. The one-CPU setting is deliberate for this numerical retry. Its held collector validates paired truth and task output hashes, then produces a separate portable recovery archive. Private fit and truth files remain on the cluster. The original 322 completed cells and all original failed outputs remain unchanged. Review the new archive alongside the original bundle; do not present it alone as a complete 324-cell comparison.

Run `python3 scripts/recover_monthly_spatial.py` on the SGE host after loading singularity. Preparation runs detached and can take time verifying the frozen evidence. The launcher prints its preparation log, output directory and eventual archive path. Do not resubmit simply because no fit has appeared in the queue yet.

Six local tests cover exact recovery scope, command preservation, source immutability, changed evidence, existing-directory refusal, rejected R failures and the single-thread wrapper retaining numerical checks. These are software checks; the two real-data numerical retries still require cluster execution.
