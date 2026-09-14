# Independent adversarial review of the combination work

Reviewed source commit: `f49e37c`. Review date: 2026-09-14.

## Scope and disposition

This review inspected the monthly temporal-family by seasonality launcher, its
reuse and collection gates, the new spline combination implementation, their
immediate model/data/scoring dependencies, tests and rationale documents. It did
not inspect new cluster results or certify surveillance coverage. No production
model or existing result was modified during the review.

No observed defect requires interrupting the running model fits. One medium
priority collection safeguard should be fixed before trusting newly generated
review tables. The spline candidate remains an engineering candidate. The subsequent data-free
prior/extrapolation review is recorded in `monthly_combination_prior_audit.md`;
a frozen real-data protocol remains required.

## Finding: collection continues after a global integrity failure

**Severity: medium.** At the reviewed commit,
`scripts/launch_monthly_factorial.py:199` catches a failed global verification and
records an issue, but continues. The reference branch at line 204 rechecks original
source files, while reading copied reports in the new run directory; it does not
recheck those copied files locally. Line 217 therefore can construct numerical
contrasts using a copied report whose plan-bound hash has failed.

A synthetic reproduction changed a copied score after binding its hash. The
collector correctly returned nonzero and reported the altered artifact, but also
emitted a contrast computed from that altered score. This is not silent success,
and no actual corruption was observed. The risk is that a downstream consumer
reads the CSV without enforcing the summary and plan gates.

Resolution implemented locally: retain failure diagnostics and the archive, but
suppress comparison tables after any global integrity failure; verify each copied
reference again before reading it; remove stale derived tables on recollection. Review tooling must reject
integrity issues, validate the archive manifest and source plan bindings, and
never treat CSV presence as evidence of a valid comparison. Preserve the running
snapshot; this hardening does not warrant refitting valid model checkpoints.

## Remaining spline engineering boundary

The internally constructed nonlinear basis passes training-only construction,
rank, phase-orthogonality and variance-normalization checks. However, the supplied
`basis` interface at `scripts/monthly_spline_combination.R:29` checks dimensions,
finite values and a version label rather than rechecking these properties at the reviewed commit. A
finite rescaling of a supplied nonlinear matrix can retain that label while
changing the effective prior. This is a hardening requirement before accepting
externally prepared bases in a real-data launcher, not evidence that the current
constructor produces an invalid basis.

Follow-up implemented locally: consumption now verifies training orthogonality,
rank, slope convention and normalization, with rescaling and slope-tampering
regression checks. Binding the complete prepared object (including prediction
rows) to its generation inputs and source remains a real-data launcher requirement.
Checks must not tune the basis using held-out outcomes. The phase projection can
alter extrapolation and must be examined in prior predictions rather than assumed
to provide a natural trend/seasonality decomposition.

## Scientific and comparison checks

- All pathogens receive the same factorial arms. The documented interpretation
  compares specified model/prior packages; it does not claim RW1 and AR1 have
  equivalent functional priors.
- Outcome masking happens before model fitting. Future realized exposure and
  previously examined evaluation years are expressly disclosed. No independent
  final-validation or prospective population-forecast claim is supported.
- Reused task identities, source hashes, temporal/seasonal settings and draw
  counts are checked. Canonical held-out county/month truth must match across
  arms. Training rows and exposures should remain bound to the existing source
  chain; equality of held-out counts alone would not establish that equivalence
  for arbitrary future reuse sources.
- Score contrasts require all four arms per site/year/stream. Equal-site summaries
  require the full site set. The interaction is an arithmetic predictive-score
  contrast, not a biological interaction or independent hypothesis test.
- Overlapping forecast origins and posterior streams must not be treated as
  independent generalization replicates. Calibration, bias, interval width and
  Monte Carlo stability remain necessary companions to score differences.
- The code fits into new output directories and refuses existing checkpoint
  paths. No call was found that replaces Daniel's state model or accepted outputs.
- Methods with weak individual results remain candidates for combinations. A
  pathogen-specific disposition needs the rationale, empirical evidence and
  limitations recorded separately; a score improvement is not a biological
  explanation.

## Verification performed

The original nine tests in `tests/test_monthly_factorial.py` passed. After the
collector hardening, all ten tests passed, including corruption rejection with
global verification enabled and bypassed and stale-table removal. The non-fitting R
checks in `tests/test_monthly_spline_combination.R` passed, including held-out
outcome poisoning and training-basis invariance. The collector corruption scenario
above was independently reproduced with temporary synthetic files. Full INLA
fits, new cluster outcomes and prior-predictive simulations were outside this
review's execution scope and are not implied by these test results.
