# Synthetic R-INLA validation

The `feature/rinla-county` branch contains an isolated smoke test, a dedicated
container recipe and a single-job SGE launcher. No production backend, real county
fit, dashboard integration, or equivalence to Daniel's state spline is claimed.

## What runs

`scripts/inla_smoke.R REPORTDIR THREADS` generates 136 invented area/year records.
It reads no surveillance files. Its two fits check:

1. An intercept-only Poisson model with a log-population offset against the
   analytic Gamma rate posterior under a flat log-rate prior. The reported
   comparison is on the log-rate scale: posterior mean, SD and 95% bounds must
   each agree within 0.02.
2. A negative-binomial model with BYM2 spatial effects and an RW1 time effect.
   Its graph has two disconnected eight-node chains and one isolated node.
   Summary checks require finite, ordered intervals, positive fitted means,
   finite WAIC and zero reported CPO calculation failures.

The second fit uses explicit **test priors**: normal log-size centered on log(12),
PC priors for spatial/time precision and spatial mixing, and a weak normal
intercept prior. These choices are not approved FoodNet priors. An RW1 or RW2
smoother is not automatically equivalent to Daniel's thin-plate spline, and a
successful fit does not establish approximation accuracy or scientific adequacy.

The script records the generated data, graph, formulas, fit summaries, fits,
package/session details, and PASS/FAIL status. Existing reports cannot be
silently overwritten. The launcher snapshots the script and archives diagnostics
on either success or failure. It does not retry fits automatically.

The underlying specifications are documented by R-INLA:
[negative-binomial likelihood](https://inla.r-inla-download.org/r-inla.org/doc/likelihood/nbinomial.pdf),
[BYM2 including disconnected components and isolated nodes](https://inla.r-inla-download.org/r-inla.org/doc/latent/bym2.pdf),
[container execution and thread limits](https://inla.r-inla-download.org/r-inla.org/doc/vignettes/Apptainer.pdf).

## Execution evidence — 12 September 2026

An actual local run with INLA **26.08.07** and an isolated R **4.5.3** environment
passed. It used two INLA threads and one BLAS thread.

| Check | Observed result |
|---|---:|
| Maximum absolute analytic log-rate summary error | 0.0001371 |
| Spatial fitted mean counts | 11.21–40.17 |
| CPO calculation failures | 0 |
| Spatial WAIC | 980.5803 |
| Elapsed time for the tiny synthetic test | 6.41 seconds |

The elapsed time is not a FoodNet runtime estimate. WAIC here is a recorded
calculation, not evidence that this model is preferable to another model. Local
execution emitted system-bus and NUMA `mbind` messages in the restricted host;
both fits completed and all checks passed. This does not establish that the
cluster's container environment will behave identically.

The SIF recipe separately pins R **4.5.2** and the same INLA release. No
Singularity/Apptainer runtime is available in this workspace, so **the SIF has not
been built or executed here**. Its mandatory test must pass during build and in
the finished read-only image. See [container instructions](inla_container.md).

Additional local checks passed: deterministic fixture and graph tests; refusal
to overwrite prior reports; missing-INLA failure/status capture; offline launcher
preparation; command quoting; mocked SGE submission and archive/failure handling;
and builder failure/overwrite/publication tests. These harness tests use stubs and
do not substitute for SGE or Singularity execution.

## Cluster execution

After building the dedicated image, submit the synthetic test with:

```bash
python3 scripts/launch_inla_smoke.py
```

It requests one two-slot job, a 30-minute limit, and 8 GB memory resources (SGE
may apply memory requests per slot). It prints one log path and one report
archive path. `--container PATH` selects an existing dedicated image, and
`--prepare-only` creates the plan without requiring cluster tools or an image.
No raw data files or existing fitted results are required.

Coverage research continues independently: [current findings](county_coverage_research.md).
Real-data county work still needs an explicit geographic/population scope,
verified coverage, and statistical model validation.

## Build-host success and compute-node permission failure

The user built the image on `docker3`; both build and finished-image checks passed.
The first SGE test (job 17817972) failed with permission denied executing
`INLA/bin/linux/64bit/inla.mkl.run`. Inspection of the installed official package
showed owner-only execute permissions (0744), which the root build masked.
The recipe now normalizes INLA package permissions and the smoke check explicitly
rejects missing group/other execute bits. A local-image repair avoids reinstalling
dependencies; see [repair instructions](inla_container.md#repair-an-image-built-before-the-executable-permission-fix).
Ordinary-user SGE execution is still pending after that repair.
