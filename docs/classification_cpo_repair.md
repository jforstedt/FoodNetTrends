# Targeted classification CPO recomputation

This is numerical diagnostic work, not a new scientific model. Select only saved
inspection tasks with positive failure indicators on observed responses from
classification_diagnostics_20260914_102549_452910. The reviewed archive selects
13 fits. Do not recompute unflagged fits or treat missing held-out CPO values as
failures. Selection is derived from verified diagnostics rather than performance.

Use INLA 26.08.07 `inla.cpo(force=FALSE, recompute.mode=TRUE)` to recompute flagged
CPO/PIT values through observation-removal fits. The installed implementation uses
the saved second thread count for each removal fit. Set that to one and run up to
four independent removals per task, with four allocated cores. Run all selected
fits concurrently, without a concurrency cap. This entails additional fitting for
the diagnostics; it does not refit or replace the original scientific posterior.

Reference: [INLA CPO documentation](https://www.r-inla.org/learnmore/docs/reference/cpo.html).
The implementation was also checked against the installed pinned function.

Require source fit, support, diagnostic report and task identity hashes. Check
saved likelihood, priors/specification, original responses, trial counts, row order
and held-out masking. Before/after rows retain failure magnitudes, CPO, PIT,
observed status and requested selection. Original files must be unchanged. In the
returned object only CPO diagnostic fields may differ; non-targeted rows must be
identical. Save the repaired object to a new cluster-only checkpoint and omit it
from the portable archive.

A completed computation is not necessarily a resolved diagnostic. Report remaining
positive failure indicators, nonfinite/nonpositive requested CPO values and
invalid PIT values separately. Do not accept a result merely because it completed.
Do not overwrite original warnings, model comparisons, dashboard data or accepted
state results. No further posterior sampling is included: the precision question
was already adequately investigated for the current exploratory comparison.

Even successful CPO repair cannot fix biased annual predictions, supply missing
surveillance information, establish causation or justify an incidence adjustment.
Use model_change_rationale.md to record later scientific changes and retained
combination candidates separately.

Launch on Rosalind with Singularity loaded using
`python3 scripts/launch_classification_cpo.py`. One array and a dependent collector
produce one archive, including partial failures and unresolved diagnostics.
