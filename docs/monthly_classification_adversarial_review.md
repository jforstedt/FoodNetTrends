# Adversarial review of the monthly classification comparison

Scope: the RW1/AR1 conditional-classification matrix, its scorer, prior-only
checks and launcher. This review concerns implementation and scientific design;
it does not assess cluster results or accept a pathogen-specific model. The
matrix has 48 site/month fits and 96 county/month fits. The spline extension
remains a separate unresolved gate.

## Findings and verified closure

1. **Bind the spatial adapter into prior-check provenance.** Both the fitted BYM2
   formula and the prior-only graph calculation depend on
   `scripts/monthly_spatial_combination.R`. Its hash must be required by the prior
   manifest validator, alongside the model, prior-check script and geography.
   A launch-time snapshot alone does not establish that the helper matches the
   implementation used for calibration.
2. **Check calibration hashes against the actual snapshots.** After copying the
   scripts and graph, compare their hashes with the copied prior manifest's
   source hashes. Checking source paths before copying leaves an avoidable window
   for a changed file to become a newly bound but uncalibrated snapshot.

Both findings are closed in the launcher: the spatial adapter is now a required
prior-manifest source, and each copied model/graph source must match the copied
manifest after snapshot creation. The fourteen-test Python launcher suite passed
on independent rerun, including prior source/report alteration and a mutation
between prior verification and copying. These were provenance hardening findings;
they do not establish that any existing fit or scientific result was wrong. Final
prior-artifact generation remains a launch prerequisite enforced by the validator.

## Scientific and numerical assessment

The conditional target is coherent: CIDT-labelled records among eligible
CX+/CIDT+ records. The documented restrictions correctly prevent interpreting
this as test positivity, testing volume, diagnostic adoption, infection incidence
or an ascertainment correction. Keeping diagnostic methods as future combination
candidates is consistent with this bounded comparison.

Held-out category outcomes are erased before fitting. Future classified-case
counts remain explicit conditioning denominators. The temporal index and RW1
constraint use calendar identities, and RW1 scaling uses the training grid;
seasonality uses a fixed twelve-month cycle. No future category outcome is needed
for these constructions. Calendar cutoffs and eligibility should remain frozen
when the results arrive.

Zero-denominator cells retain latent locations but contribute no binomial
likelihood or predictive score. Empty information groups receive missing scores,
not zero scores. The scorer uses a stable logit-based binomial log density and
checks posterior predictor identities. Annual predictions aggregate the same
joint predictive draws across months and counties, preserving posterior
cross-cell dependence. Mean marginal cell log scores are suitable for matched
within-resolution comparisons; they are not joint vector log scores and cannot
be directly ranked between site/month and county/month resolutions.

The RW1 precision bound and prior simulation use the same training-grid scaling.
The seasonal component uses the corresponding cyclic scale. AR1 prior simulation
uses its marginal standard deviation and the transformed correlation parameter.
The site and cell PC scale conventions and the county IID/BYM2 scale conventions
are explicit. The prior-only BYM2 calculation uses the pinned INLA mixing-prior
implementation instead of substituting an unrelated distribution. Prior
trajectory checks are structural checks, not evidence that these priors are
biologically established or optimally calibrated for every pathogen.

Site intercepts, optional static county effects and independent cell effects
have different roles. The latter model extra-binomial heterogeneity; they do not
learn a county-specific temporal trajectory. BYM2 borrows information over the
fixed graph but supplies no missing laboratory denominator. The disconnected
component treatment is explicit, and isolated counties are rejected by the
shared adapter.

## Local review evidence

The domain/masking/prior-scale test passed, including a held-out outcome
perturbation that leaves prepared model inputs identical. The scoring test passed
in the pinned local INLA environment, including empty scored groups, boundary
log densities, reproducibility, posterior row reordering and joint annual
aggregation. Runtime snapshot dependencies were inspected; the sourced density
helper's standalone CLI dependencies are not executed by this model runner.

This review also inspected source/output hashing, per-task identity validation,
nonzero-denominator scoring domains, independent site/year total reconciliation,
partial-failure collection and exclusion of internal panels/fits from portable
archives. Numerical completion remains distinct from predictive adequacy and
scientific acceptance.

## Interpretation limits to retain

The overlapping development origins have already been examined and are not
independent final validation. A component's weak standalone performance is not a
reason to discard it from combination testing. Component contrasts and
interactions should be reported without silently selecting new pathogen rules.
CPO is not an acceptance or accuracy-ranking gate. High Monte Carlo errors,
broad predictions and sensitivity to prior choices remain findings requiring
assessment after the batch, even when the numerical solver completes.
