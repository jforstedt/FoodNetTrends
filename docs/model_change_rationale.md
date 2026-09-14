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
