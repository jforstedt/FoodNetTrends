# Isolated Shigella optimizer restart

The remaining Shigella 2011 seasonal AR1 plus BYM2 fit returned `ok=TRUE` but `mode.status=2` in the single-thread recovery. It therefore remains ineligible. This status alone does not establish a biological explanation, identify a prior problem, or justify weakening the numerical gate.

The next run recreates only this frozen task with one fitting thread, saves its returned optimizer checkpoint internally, and performs exactly one `INLA::inla.rerun()` restart. The other 323 completed comparison cells are retained, including the verified Listeria recovery. Completed-cell review proceeds independently.

## Evidence for the numerical intervention

The implementation of `INLA::inla.rerun` in the pinned local INLA 26.08.07 package was inspected directly. Its non-plain default restarts at the previous hyperparameter and latent modes, reuses optimizer directions, selects the plain optimization strategy, and tightens numerical controls. With default controls it changes the stencil from 5 to 9, finite-difference step from 0.005 to 0.001, and tolerance from 0.005 to 0.00005; it sets step factor 1 and step tolerance 1e-10. These are numerical changes, not new likelihoods or priors. `inla.rerun` also disables the fixed-effect correlation-matrix reporting switch.

The wrapper preserves and checks formula, data, likelihood, fixed-effect priors, family priors, predictor controls and compute controls. It restores the monthly metadata attributes that `inla.rerun` does not preserve automatically. Numerical settings before and after the restart are written to the diagnostic report. Verbose INLA output is captured by the task log.

## Acceptance and outputs

The existing spatial gate remains unchanged: `ok=TRUE`, exactly `mode.status=0`, and no recorded aborted variational correction. Passing execution and integrity gates does not automatically promote the model or establish predictive improvement. The same held-out truth and scoring implementation are used after a successful restart.

Both optimizer objects use filenames ending `_INTERNAL.rds` and remain on the cluster; collectors exclude them from portable archives. The portable archive contains settings, numerical summaries, logs, integrity evidence and, only when all gates pass, predictive summaries. If restart fitting fails, the initial checkpoint still remains available internally for diagnosis. No repeated-until-success loop is used.

Run from the repository on the cluster after loading Singularity:

```bash
python3 scripts/recover_shigella_numerics.py
```

Preparation is detached and verifies the original comparison and completed Listeria recovery before submitting one 1-CPU job. The 48-hour request is a ceiling, not a runtime estimate. Its held collector writes one new archive. Nothing is submitted for Listeria or any previously successful task.

## Local verification

Four Python tests cover the target, unchanged gate, archive exclusion and one-job/collector submission. R tests cover failed-fit checkpointing, metadata retention and rejection of a changed likelihood. Real pinned-INLA synthetic Poisson and matching seasonal AR1 plus BYM2 fits and documented restarts passed with mode status zero and preserved metadata; these validate the interface, not the unresolved Shigella fit.
