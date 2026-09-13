# Targeted recovery and retrospective prediction checks

`python3 scripts/launch_county_pathogen_review.py` creates a new output directory
and submits two arrays plus one final collector. It reuses foodnet-inla-fixed.sif.
No new container build is required. Source fits and audit directories are bound
read-only, and no existing dashboard is replaced.

The recovery array contains one full-period Vibrio spatial retry and two saved-fit
Shigella CPO repairs. The retry keeps the same likelihood, formula, priors and data;
it uses one computational thread and verbose logs to investigate the segmentation
fault. This is a diagnostic change, not a confirmed fix or evidence about its cause.
Each recovery task requests one slot, 32 GB h_rss/mem_free, 64 GB h_vmem and 24 hours.
There is no automatic retry loop.

Shigella repair identifies failed/nonfinite/nonpositive CPO entries and calls
`INLA::inla.cpo(force=FALSE, mc.cores=1)`. This performs targeted leave-one-out
recomputations, not a replacement of the full-period posterior. The original
checkpoint is preserved; the repaired object is saved separately. Before/after
cell diagnostics, remaining failure counts and source hashes are reported.
Posterior summaries must remain identical. Any unresolved entries retain an
explicit review status. See the [INLA FAQ](https://sites.google.com/a/r-inla.org/www/faq)
and the pinned installed function for the repair behavior.

The prediction array contains sixteen training fits: spatial and IID county-time
models for each of the eight new pathogens. All tasks may run concurrently;
there is no three-job cap. Each requests eight slots and the same memory/time
limits. Training ends in 2016; 2017–2019 case counts are masked until scoring.
The known future populations and fixed graph/year domain are conditioned upon.
These are retrospective checks because earlier exploration used this period.
They are not prospective validation or nowcasts. Original full-period fits cannot
be reused for this test without exposing the training process to held-out counts.

The existing forecast machinery collects 4,000 joint posterior draws, cell log
scores, predictive intervals, zero probabilities, grouped count/zero predictions,
and Monte Carlo diagnostics. Those outputs support review of the earlier
zero-count mismatch. Passing execution does not resolve that mismatch by itself.
No automatic model selection or dashboard promotion occurs.

All tasks independently verify reconciliation checksums and audited scope.
Failures do not block unrelated tasks. The final archive includes reports and
logs even when some tasks fail; RDS checkpoints and individual case records are
excluded. Aggregate surveillance reports remain internal material.
