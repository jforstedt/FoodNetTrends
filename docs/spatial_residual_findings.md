# Saved spatial error review

The corrected portable audit contains 162 completed BYM2 saved-fit reports,
covering nine pathogens, three development origins and six temporal/seasonal
packages. Manifest hashes, task/plan bindings, matrix identity, report settings,
state/year domains, monthly domains and aggregate reconciliation pass local
review. Private saved-fit and county-result bytes remain on the cluster and are
not independently reread here. This is execution completion, not model acceptance.

Reproduce the portable review with:

```bash
python3 scripts/review_spatial_residual_results.py /path/to/spatial_residual_audit_RUN.tar.gz --output output/spatial_residual_review_NEW_LOCAL
```

The reports show that removing shared state-level error reduces the overall
neighbor association across pathogens. Shigella retains substantial descriptive
spatial association and consecutive-month persistence across all six packages.
It is the clearest candidate for a bounded investigation of evolving local
patterns. That hypothesis is not proof of outbreaks, missing covariates or a
need for any particular new model term.

Cyclospora and Cryptosporidium show stronger dependence on the temporal/seasonal
package; broad medians would obscure those differences. Listeria, Vibrio and
Yersinia have comparatively weak typical within-state monthly neighbor association.
A small or negative index does not establish correct calibration or independent
errors, particularly with sparse counts. Lower residual correlation is not a
forecast ranking criterion: score, calibration, bias and tail behavior remain
separate evidence.

The audit does not compare these county residuals with matched IID controls.
Therefore it cannot establish how much spatial smoothing removed, or whether
additional smoothing would improve forecasts. The log1p residual is affected by
sparsity, population and nonlinear transformation. Overlapping origins, months
and model packages are correlated; median summaries are descriptive, with no
null distribution, p-values or posterior uncertainty.

## Disposition and next work

No incidence model, prior, pathogen eligibility rule or accepted state output is
changed. No repeat of the completed fits is justified by this audit. Preserve
both the failed factor-label audit and the corrected result in the execution
history; only the corrected result supports these findings.

Combine this evidence with the existing paired spatial forecast-score and
calibration comparisons when freezing the candidate rationale. Do not automatically
add a spatiotemporal interaction to all pathogens. A possible Shigella interaction
would be a new development hypothesis requiring explicit priors, simulation
checks, matched controls and a bounded comparison protocol before fitting.

The next product gate remains the [final validation plan](spatial_final_validation_plan.md):
resolve the later-period input/access ledger and intended-use acceptance criteria,
then freeze candidate/control comparisons. No independent eligible holdout has
been established. An exploratory release can disclose these limits; a claim of
validated production forecasting cannot bypass them. Numerical tables remain in
ignored local output, not in public documentation.
