# Exploratory county fits: execution and interpretation

This implementation advances the reviewed Salmonella 2004–2019 county panel to
two exploratory fits. It does not change Daniel's model, existing results, or the
dashboard. The audited graph has ten components, including GA–TN together and two
NY groups; the spatial fit uses that graph rather than assuming one component per
state.

## Prior-predictive review and revised draft

Before preparing real fits, 1,000 prior-predictive draws for each variant were
simulated locally on the **actual 7,776 audited county/year populations** and the
486-node graph. This needed no county case counts: only the already reviewed
pooled total 122,024 was used to mark observed pooled incidence on the plots.

The original draft state-intercept SD of 2 on the log-rate scale implied very
large pooled rates after combining lognormal state priors. It was revised to **1**
for this exploratory pilot, with center log(20/100,000) unchanged. This change is
data-informed prior checking, not independent prior validation. Both models use
the same revised prior. It does not alter a prior in Daniel's state model.

| Model / intercept SD | Prior pooled incidence 2.5% | Median | 97.5% |
|---|---:|---:|---:|
| Spatial / original SD 2 | 16.37 | 81.17 | 617.41 |
| IID / original SD 2 | 17.01 | 81.12 | 554.75 |
| Spatial / revised SD 1 | 15.04 | 30.98 | 76.29 |
| IID / revised SD 1 | 15.13 | 31.27 | 77.20 |

Rates are per 100,000 and pool all populations/years. Observed pooled incidence is
16.04, near the lower end of the revised prior distribution. The revised prior
therefore still deserves sensitivity analysis; it has not been tuned to reproduce
the observed rate. No draws exceeded their county/year populations in the revised
local simulations. These are finite Monte Carlo results, not guarantees.

All other draft priors remain unchanged: spatial/county SD PC prior
P(SD>1)=0.01, temporal SD PC prior P(SD>0.5)=0.01, graph-dependent BYM2 mixing prior
P(phi<0.5)=0.5, and log NB size Normal(log(12),1). State intercepts have SD 1.
The prior sampler uses scaled intrinsic Gaussian effects and INLA's pinned,
graph-dependent mixing-prior implementation; it does not substitute a uniform
mixing distribution. Internal INLA helpers are version-sensitive, so the script
requires INLA 26.08.07. Prior checks run again on the cluster and are archived.

## Two models on identical data

Both have a log-population offset, state intercepts, and state-specific scaled RW1
time effects. RW1 paths are replicated by state and share a precision parameter;
each path is centered. The spatial variant adds a scaled BYM2 county effect with
component-aware constraints; the comparison variant uses independent Gaussian
county effects with the same total-SD PC prior.

County effects are constant over time in both variants. Thus county trends share
a temporal shape within a state. Neither model claims independent county-specific
trend shapes, diagnostic-method adjustment, national representativeness, or
equivalence to Daniel's thin-plate spline. This comparison tests a spatial-pooling
choice; a matched-data comparison with Daniel's model remains future work.

## Revalidation and outputs

At fit startup, recheck the audit PASS status, panel completeness, counts,
populations, state assignments, all state/year totals, graph identifiers/degrees,
and source input checksums. The reviewed production scope is enforced: 486
counties, years 2004–2019, and 122,024 cases. Invalid or changed inputs stop fitting.
The exact panel's checksum is recorded.

Each model retains an internal RDS checkpoint immediately after fitting and writes:

- Prior-predictive plot, numerical draw summaries, and review notes.
- Fixed/hyperparameter summaries, formula, session information, WAIC and CPO failures.
- County incidence and 2019-reference ratios with intervals, marked INTERNAL.
- State incidence and 2019-reference ratios from population-weighted **joint** draws.
- State trend PDF and posterior-predictive total/zero-fraction summaries.

Posterior aggregation uses 1,000 approximate joint draws with improved means and
**skew correction disabled**. This explicitly uses INLA's Gaussian conditional
latent approximation and avoids the optional `sn` package absent from the current
image. It is not exact posterior sampling; approximation sensitivity remains a
validation task. Quantiles of state rates/ratios are computed after aggregation,
never by summing marginal interval endpoints. The final model is not saved as a
production dashboard output.

An EXPLORATORY_FIT_COMPLETE status means the fit and reporting code completed.
Inspect CPO failures, predictive checks, prior/graph sensitivity, and temporal
holdout performance before interpreting results. WAIC alone is not a validation
criterion. No holdout refit is included in this initial two-model run.

## Run on Rosalind

```bash
python3 scripts/launch_county_pilot_fit.py
```

Defaults use `foodnet-inla-fixed.sif` and audit
`county_pilot_audit_20260912_205807_702050`. The launcher submits both models as a
two-task SGE array with no extra concurrency limit. Each requests four slots,
16 GB memory resources and four hours (site SGE memory semantics may apply per
slot). A held collector packages one archive after both tasks finish. There is
no container build, raw preprocessing, or automatic fit retry in the launcher.

The collector archives reports/logs/code and exposes partial failures. Exact-count
panels and fitted RDS checkpoints stay on HPC outside the archive. Reports contain
county estimates and are for internal scientific review, not certified public
release. `--prepare-only` writes an offline execution plan.

## Local validation

Both variants were actually fitted on synthetic data with the same INLA release.
Tests check input-change rejection, joint state aggregation, posterior count scale,
reference-year identity, saved checkpoints, concurrent job-array setup, failure
archives and exclusion of private checkpoints. The local R version is 4.5.3;
the cluster image uses R 4.5.2 and still must execute these real-data fits.
