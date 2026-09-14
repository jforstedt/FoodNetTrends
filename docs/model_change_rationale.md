# Model-change rationale register

## Decision standard

Every scientific model change needs a problem statement and mechanism before
selection. A higher score alone is not a biological explanation. Begin with shared
rules; justify pathogen-specific exceptions through surveillance eligibility,
data support, biological knowledge, or repeatable predictive evidence. Identify
explanations proposed after reviewing results as hypotheses. Do not convert a
numerical repair into evidence for changing the scientific model.

For each experiment record the reference model and exact changed component,
pathogen and time/geographic scope, motivating problem, proposed mechanism,
evidence and source, assumptions, frozen comparison plan, validation dates,
predictive score/coverage/bias/interval width, numerical diagnostics, uncertainty,
interaction candidates, and decision. Record unsuccessful results too. Archive
private numerical evidence with the run; keep this public register free of
unpublished case counts and internal diagnostic tables.

Allowed decisions: accepted within specified scope; exploratory candidate;
unsupported in this comparison; deferred for combination testing; blocked by
input evidence; superseded with explanation. “Unsupported alone” does not mean
“discarded.” Reuse of evaluation years must be disclosed. Do not characterize
repeated development comparisons as independent final validation.

## Current entries

| Change | Problem and rationale | Scope and evidence needed | Current decision / interaction question |
|---|---|---|---|
| Surveillance eligibility and population alignment | Cases and population must describe the same surveillance period and catchment. Ineligible periods must not silently become observed zeros. | Apply pathogen-specific documented surveillance rules; retain source citations and coverage assumptions. See protocol and coverage reviews. | A data-validity requirement, not a model-performance optimization. Preserve accepted state-model specification unless a documented correction requires an explicitly reviewed change. |
| County spatial effects | Nearby counties may share unmeasured exposure or reporting patterns; partial pooling may stabilize sparse estimates. This is a hypothesis, not proof of a spatial mechanism. | Compare spatial and IID county effects with common likelihood, data, priors where comparable, and evaluation windows. Audit graph and disconnected regions. | Exploratory extension alongside the state model. Test interaction with temporal structure and seasonality; do not imply replacement of Daniel's state model. |
| Monthly seasonality | Annual aggregation cannot represent within-year recurring patterns. | Requires defensible event dates and monthly eligibility. Compare seasonal and reference structures using common inputs; avoid causal attribution from a seasonal fit alone. | Retain as a combined-model candidate. Assess whether seasonal effects change spatial or diagnostic-classification associations. |
| AR1 versus RW1 temporal structure | Different persistence and extrapolation assumptions may address temporal instability. Neither structure is automatically biologically correct. | Same pathogen inputs, origins, horizon and seasonal structure; assess bias and uncertainty, not only average scores. | Pathogen-specific results remain provisional within their tested scope. Document any selected exception in the private decision ledger; revisit in predeclared combinations. |
| Smooth/spline temporal structure | Gradual nonlinear change may not be represented by a linear trend or the current temporal reference. | Check smoothness priors, boundary extrapolation, sparse periods and predictive performance. | Retained for combination testing. Prior standalone results are not a universal rejection. |
| Conditional diagnostic-classification trends | The recorded CX+/CIDT+ mix can vary across time and sites. Describing this mix may reveal reporting heterogeneity. | Target is CIDT label conditional on eligible CX+/CIDT+ records. CX+ is not culture-only. No everyone-tested denominator or confirmed adoption date is available. | Exploratory description, not an incidence correction. Incorporation into incidence needs a justified observation model and protection against circular use of case-derived predictors. |
| Site-specific classification slopes | A common time slope may miss site heterogeneity in recorded classification. | Compare common slope versus partially pooled site deviations with identical denominators, priors and holdout periods. Classification or reporting differences are hypotheses, not established biological differences. | No general rollout. Keep all six pathogens available for predeclared interaction testing; see pathogen entries below. |
| CPO recomputation | Positive CPO failure indicators question the numerical reliability of leave-one-out diagnostics. | Recompute only flagged observed rows, preserving original model, priors, posterior and files. Report remaining flags and invalid values. | Numerical diagnostic repair only. Does not cure predictive bias or establish scientific acceptance. |

## Pathogen-specific classification rationale

These are interpretations of the current exploratory shared-versus-site-slopes
comparison, not rules for incidence models. Detailed figures and archives remain
in local review artifacts under output/classification*_review_LOCAL.

| Pathogen | Interpretation and rationale for current disposition | What could change it? |
|---|---|---|
| STEC | Retain site slopes as an exploratory candidate because the held-out comparison suggests some benefit from site heterogeneity. This does not establish its biological cause or remove annual bias. | Stable performance under prior/temporal sensitivity and justified combined models. |
| Yersinia | Keep the common slope as the reference; extra site slopes were not supported in the tested standalone comparison. | A predeclared interaction that improves prediction without unstable uncertainty or unsupported causal interpretation. |
| Salmonella | Keep the common slope as reference; small score differences and remaining bias do not justify complexity. Resolve flagged CPO diagnostics separately. | Better-supported temporal or observation mechanisms and rigorous combination testing. |
| Campylobacter | No compelling standalone site-slope gain; retain the simpler reference while inspecting diagnostic reliability. | Reproducible benefit from combinations or independent validation. |
| Shigella | A small preference for the simpler reference is insufficient to establish that site heterogeneity is absent. | Robust combined-model evidence after diagnostic review. |
| Vibrio | Site slopes have not resolved predictive limitations; keep the common slope as reference. | A scientifically motivated combination that improves calibration and accuracy. |
| Listeria | The available CIDT-labelled support is too sparse for the current comparison. This is a data-support limitation, not proof the mechanism is irrelevant. | Additional reliable classification support or a separately justified pooling strategy. |
| Cryptosporidium and Cyclospora | The current CX+/CIDT+ contrast is not supported by their category coding. | A documented pathogen-appropriate diagnostic variable and denominator. Do not force bacterial coding onto parasites. |

## Next-phase combination protocol

Before fitting, specify a bounded set of biologically or operationally plausible
combinations. Include the simple reference, relevant component-only models and
combined models so an apparent interaction can be distinguished from a single
component's contribution. Use the same eligible records and comparable priors,
freeze evaluation windows, check leakage and disclose reused years. Run independent
comparisons concurrently. Evaluate predictive gain alongside calibration,
uncertainty, complexity and numerical stability. Do not expand the search merely
to obtain a preferred result, and do not discard an entire method from one
pathogen or one standalone result.

Sources for scope and definitions: classification_trends.md,
classification_saved_diagnostics.md, classification_cpo_repair.md,
monthly_validation_inventory.md and checkpoint_20260914.md. Biology-specific
claims require an explicit source before being promoted beyond hypotheses.

## Classification specification choices and limits

- The 2012–2019 recording window and 2016 training cutoff define a bounded
  development comparison; they are not adoption dates or independently selected
  validation periods. The original eligible audit supports the category domain.
- The binomial likelihood matches a conditional label count out of CX+ plus
  CIDT+ records. IID site/year effects allow more heterogeneity than the simple
  binomial likelihood alone. They can also yield broad intervals, so coverage
  must not be considered sufficient on its own.
- A common linear trend is a deliberately simple reference. Partially pooled
  site slope deviations test one additional form of heterogeneity. Pooling is
  intended to regularize sparse site estimates; whether that helps must be tested.
- The explicit Normal and PC priors in classification_trends.md impose
  regularization and finite variation. Their numerical scales are modeling
  assumptions, not pathogen-specific biological measurements. Prior sensitivity
  remains necessary before stronger adoption claims.
- More posterior draws reduce Monte Carlo uncertainty in score estimates; they
  do not change the fitted model, repair numerical approximation or make the
  same historical evaluation data independent.

## Activated combination comparison

The [monthly temporal × seasonality factorial](monthly_factorial.md) applies the
same complete comparison to all nine pathogens. It reuses completed controls,
adds only absent arms, and evaluates paired component and combination effects.
Previous pathogen-specific AR1/RW1 dispositions remain provisional references,
not a reason to omit a candidate. The state-only spline candidate stays separate
until its engineering and prior checks support a comparable matrix.

## Completed monthly factorial review

Reviewed 2026-09-14. The complete temporal-package × seasonality comparison
passed portable report consistency checks. Numerical evidence, paired plots and
limitations are retained locally in
`output/monthly_factorial_review_20260914_111339_LOCAL/scientific_review_LOCAL.md`.
This is exploratory historical evaluation, not independent final validation.
No production default or accepted state-model specification changes follow.

| Pathogen | Rationale for provisional disposition | Remaining question |
|---|---|---|
| Salmonella | Seasonal AR1 is a leading exploratory comparator: its score advantage accompanies less inflated uncertainty than RW1 in these evaluations. | Confirm practical calibration and prediction stability before adoption; retain component-only controls. |
| Cryptosporidium | Seasonal AR1 is a leading comparator; RW1's very broad upper tails weaken the interpretation of its high coverage. | Preserve the documented surveillance cutoff and examine rare-event density stability. |
| Shigella | Seasonal AR1 is a useful comparator, although its small seasonal score gain does not resolve annual bias. | Establish whether extra seasonal structure improves practical predictions beyond nonseasonal AR1. |
| Campylobacter | Seasonal RW1 remains important: AR1's nonseasonal advantage does not carry through consistently after adding seasonality, and seasonal AR1 undercovers annual outcomes. | Test other justified combinations without treating narrower intervals as automatically better. |
| STEC | Seasonal RW1 remains important because both scores and annual coverage expose weaknesses in seasonal AR1. | Investigate trend/extrapolation alternatives with identical eligibility and paired controls. |
| Cyclospora | Retain seasonal AR1 for combination research: adding seasonality changes the temporal comparison, supporting the decision not to discard a component solely on standalone performance. | Underprediction, missed intervals and unstable tails prevent acceptance. The score interaction does not establish a biological mechanism. |
| Listeria | Small differences do not justify a strong pathogen-specific rule. | Compare practical benefit against complexity and retain simpler controls. |
| Vibrio | Seasonal RW1 is an important comparator, but neither seasonal arm resolves calibration concerns. Extreme nonseasonal tails make broad coverage misleading. | Examine alternative extrapolation and uncertainty rather than selecting by coverage alone. |
| Yersinia | Keep the comparison unresolved: seasonal effects depend on temporal package and period, and calibration is incomplete. | Retain both components for justified combinations; do not generalize a weak standalone seasonal result. |

These interpretations describe the specified prior/model packages, not proven
pathogen biology. Four posterior streams assess simulation stability, not
generalization uncertainty. Some individual density estimates remain noisy even
when averaged score contrasts are stable. No CPO-based ranking is used.

## Activated spline combination experiment

`monthly_spline_factorial.md` freezes 54 new spline fits and reuse of the 108
completed temporal/seasonality controls. Its rationale is gradual nonlinear
state trends with explicit, proper extrapolation priors, tested with and without
seasonality for every pathogen. The wider prior forecast ranges are disclosed
and retained rather than tuned against the reviewed outcomes. This remains an
exploratory candidate; no pathogen-specific default or state-model replacement
is authorized by the protocol. Calibration, tail stability and paired component
effects must accompany any later recommendation.

## Completed spline combination review

Reviewed 2026-09-14. All planned cells passed the portable review; reused
control scores and calibration reproduce the preceding review. Detailed
numerical evidence and the completed pathogen worksheets remain local in
`output/monthly_spline_factorial_review_20260914_120120_LOCAL`.

The current state-only spline specification is not supported as a general
replacement. Seasonal improvements within a spline arm do not establish an
advantage over both seasonal controls. Annual bias, missed intervals and
extrapolation behavior limit adoption. This finding applies to the tested
prior/model package, not all smoothing approaches or future combinations.

| Scope | Provisional disposition and rationale |
|---|---|
| Campylobacter | Keep seasonal RW1 as an important comparator; spline's nonseasonal gains do not offset weaker seasonal comparisons and annual coverage. |
| Cryptosporidium, Salmonella | Keep seasonal AR1 as a leading exploratory comparator; spline does not improve the full score/calibration tradeoff. |
| Cyclospora | Preserve the temporal-seasonal combination hypothesis, but this spline does not resolve annual underprediction or outperform seasonal AR1 consistently. |
| Listeria | No added spline complexity justified by the current comparison; score losses and annual overprediction argue for retaining simpler controls. |
| Shigella | Do not promote either spline arm. Severe overprediction appears in medians as well as means; inspect saved temporal contributions and training trajectories before proposing another extrapolation specification. Its cause is not established from portable reports. |
| STEC | Retain evidence of nonseasonal gains and a seasonal uncertainty tradeoff; mixed comparisons against seasonal RW1 and weaker coverage prevent a replacement recommendation. |
| Vibrio, Yersinia | No practical replacement preference established; retain unresolved calibration and component evidence rather than force a winner. |

No default or accepted state-model change follows. No blanket refit is needed.
Any targeted saved-fit diagnostic or new specification must preserve the
original outputs, distinguish simulation variability from model inadequacy,
and continue to disclose reuse of these development years.

### Predeclared broader combination follow-up

The next batch tests whether a static BYM2 county effect changes the temporal and seasonal tradeoffs across all nine pathogens, including spline combinations that did not improve standalone forecasts. It retains every paired IID control and records spatial, temporal, seasonal and three-way contrasts. Six separate monthly diagnostic-classification preparations establish compatible denominators before fitting classification combinations. Inspection of all saved spline fits investigates extrapolation without changing fitted models. See broader_combination_batch.md; none of these steps automatically changes the accepted state model or promotes a county model.

## Completed spatial structure review

The complete spatial comparison and numerical recoveries remain development
evidence. Static county smoothing has generally small or heterogeneous added
value; it does not supply a universal improvement or repair the tested spline's
extrapolation weaknesses. The strongest mean spatial contrast is concentrated
by historical period and geography. A geographically concentrated gain warrants
inspection of the existing errors, not a new state-specific fitting rule.

The state/origin/horizon review retains all configurations and paired controls,
examines score, bias, absolute error, coverage and width together, and records
sensitivity to omitting an existing block. Omission summaries are not refits or
independent holdouts. County residual structure requires saved county-level
predictions and cannot be recovered from state aggregates. Remaining residual
association alone does not authorize a dynamic spatial effect or demonstrate
its predictive benefit. See [the validation plan](spatial_final_validation_plan.md).

No accepted model or prior changes. Weak standalone components remain available
for scientifically specified combination experiments; diagnostic-classification
models remain a separate conditional outcome, not an incidence adjustment.

## Completed conditional-classification comparison

The separate binomial diagnostic-mix experiment favors the tested RW1 temporal
package over stationary AR1 on its development comparisons. Seasonality and
static county borrowing have mixed incremental contributions; favorable
interactions do not establish that the full candidate beats its better reference.
The result concerns recorded CIDT share conditional on CX-or-CIDT totals, not
incidence. It does not revise the pathogen-specific incidence comparator ledger.

Persistent share bias and missed predictive intervals prevent automatic
promotion even where scores improve. Saved trajectories can expose extrapolation
limitations but do not identify diagnostic adoption, ascertainment or reporting
mechanisms. Preserve weak components as candidates for justified combinations,
and distinguish implementation success from calibrated predictions. The
[portable result review](monthly_classification_results_review.md) records the
scope and the next scientific gates. No fitted model or prior changes follow.
