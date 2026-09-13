# Parallel county forecast validation batch

Run `module load singularity && python3 scripts/launch_county_forecast_validation.py` on Rosalind. The existing `foodnet-inla-fixed.sif` is reused. No container build or state-model refit is performed.

The launcher fingerprints audited panels, reconciliation evidence, code and container, then submits six scheduler jobs:

1. Horizon-invariance tests on synthetic spatial/IID models, with and without county time effects.
2. A small scalar negative-binomial posterior reference, comparing Gaussian joint samples with independent numerical quadrature.
3. An array of 80 calibration-screen fits: sparse/dense × spatial/IID × 20 independent datasets, each with 2,000 predictive draws.
4. A held prerequisite-check job. It verifies complete, unchanged artifacts and screen results, rather than treating scheduler completion as success.
5. An array of 54 exploratory county fits, held until the prerequisite check. Every worker checks the gate before fitting. Nine pathogens × three eligible forecast origins × spatial/IID county-time models are compared with an analytic training-only historical-rate reference.
6. A held collector that reports all tasks, including blocked and failed tasks, and writes one internal archive. Checkpoints remain on HPC.

There is no extra concurrency cap. Screens request two CPUs and 4 GB RSS; real fits request eight CPUs and 32 GB RSS, with the established SGE virtual-memory limits. Resource requests follow scheduler semantics, not a promise of physical memory per job. Actual local synthetic examples passed; full real-data runtime is not established.

Forecast temporal scaling and centering now depend only on the training period. Future coefficients follow unconstrained random-walk continuations. This changes the county forecast prior relative to the earlier full-domain setup; it does not change Daniel's state spline or rewrite earlier fits.

The 80-fit calibration batch is a gross-error screen, not certification of nominal coverage. The scalar quadrature reference tests a limited conditional model, not the full county joint posterior. Passing these gates permits **exploratory comparisons only**. Full uncertainty assessment remains a review task, and no model winner or dashboard promotion occurs automatically.

These are conditional hindcasts using realized future populations and historical outcomes previously used during model development. Cryptosporidium stops in 2017. The protocol fixes origins, targets and candidates before this batch; overlapping origins and spatial dependence prohibit naive independent-cell significance tests.

The launcher prints each job ID immediately and records it in submission.json. After all six IDs appear, the jobs continue independently of the terminal. If submission is interrupted, preserve that directory and its ledger rather than launching a duplicate whole batch. `--prepare-only` produces an explicitly unverified plan; such a plan cannot execute real-data fits.

Sources for the numerical changes: [INLA RW1 definition](https://inla.r-inla-download.org/r-inla.org/doc/latent/rw1.pdf), [IGMRF scaling](https://www.inla.r-inla-download.org/r-inla.org/doc/vignettes/scale-model.html), and [joint posterior sampling](https://www.r-inla.org/learnmore/docs/reference/posterior.sample.html). See the protocol and calibration documents for the fixed experiment and limitations.
