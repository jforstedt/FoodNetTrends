# County candidate decision record

Consolidated 2026-09-14 after the completed temporal, seasonal, spline, spatial
and conditional-classification comparisons and corrected saved spatial-error
audit. This records development decisions; it is not a frozen final-validation
manifest or a production-model selection. Daniel's accepted state model remains
the accepted state analysis. County and diagnostic-classification targets remain
separate extensions.

## Incidence candidates

A reference below is a comparator to retain, not a claim of adequate calibration.
The IID county version remains the simpler spatial reference. Any BYM2 evaluation
must use its otherwise matched IID comparator. Do not infer an exact fit identity
from a family name: final execution must bind formula, priors, input domain,
seasonality, graph, software and fit/source hashes.

| Pathogen | Retain for the next decision | Rationale and unresolved limit |
|---|---|---|
| Salmonella | Seasonal AR1 with matched IID/BYM2 variants | Existing score and uncertainty tradeoffs favor this temporal comparator; the residual audit does not establish a general additional spatial benefit. Calibration remains an acceptance gate. |
| Cryptosporidium | Seasonal AR1 with matched IID/BYM2 variants | Seasonal/temporal structure reduces the weaknesses of RW1 in the development evidence. Keep the 2017 endpoint; later observations cannot be added to manufacture validation. |
| Campylobacter | Seasonal RW1 with matched IID/BYM2 variants | Seasonal comparisons and coverage prevent replacing RW1 on the basis of nonseasonal AR1 gains. Residual clustering alone does not select BYM2. |
| STEC | Seasonal RW1 with matched IID/BYM2 variants | Retain the score/coverage tradeoff against AR1 and spline; no general spline replacement is established. |
| Shigella | Seasonal and nonseasonal AR1 controls; no spatial promotion | Seasonal gains are small and static spatial borrowing has no compelling incremental advantage. Persistent geographic and temporal errors justify a bounded hypothesis, not automatic complexity. Do not promote the tested spline. |
| Listeria | Simpler AR1 reference; seasonality unresolved | Small gains and sparse counts do not justify a stronger pathogen-specific rule. Weak residual association is not proof of good calibration. |
| Cyclospora | Seasonal AR1 as a research control only | The temporal-seasonal interaction matters, but underprediction and uncertainty limitations prevent general forecasting acceptance. |
| Vibrio | Seasonal RW1 as a research control only | Existing calibration and extrapolation concerns remain. Weak typical state-centered spatial association does not resolve those concerns. |
| Yersinia | Retain the unresolved temporal/seasonal controls, including nonseasonal AR1 IID/BYM2 | The strongest observed spatial gain is localized in time and geography, with residual underprediction. Do not turn that pattern into a state-specific rule or a universal BYM2 recommendation. |

No pathogen is promoted to a new production county forecast by this record.
Unsupported individual components remain documented for scientifically motivated
combinations; the completed factorials already test the declared static spatial,
temporal and seasonal combinations. Repeating those cells is not the next step.

## Diagnostic-classification target

Retain RW1 as the better tested temporal control for conditional CIDT share,
with the completed seasonal/spatial interactions preserved. Persistent share bias
and undercoverage block use as an incidence adjustment. These predictions condition
on observed CX-or-CIDT totals; they do not estimate testing volume or ascertainment.
The classification preference for RW1 does not override incidence AR1 comparisons.

## What is complete, and what remains

Completed: the declared comparisons, numerical recoveries, portable integrity
reviews, spatial error concentration review, and corrected 162-fit residual audit.
No further blanket fitting or audit repeat is needed for these completed questions.

Before a new-period model batch:

1. Establish an eligible county/exposure domain and retain every existing pathogen
   cutoff. A metadata-only source audit may check keys, dates and denominator
   coverage, but cannot certify surveillance continuity from the presence of cases.
2. Record prior outcome access. The current periods are development data, and
   later annual/state outcomes have also been inspected. A later date is not an
   independent holdout by itself.
3. Specify intended use and practical acceptance margins for calibration, bias,
   interval width, scores and tail stability. These are unresolved decisions, not
   thresholds to choose after seeing new results.
4. Bind exact candidate/control identities and one evaluation protocol. Run the
   resulting independent comparisons together when the input and decision gates
   are satisfied. If no protected period exists, use an explicitly exploratory
   external-period assessment or prospective validation.

A new Shigella space-time interaction is optional development work, not a
prerequisite to accepting every other extension. Its hypothesis would be that
local deviations evolve over time beyond a static county effect and common
trend. Residual correlation cannot distinguish that hypothesis from reporting
heterogeneity, sparse-count effects or missing predictors. Before fitting, define
an identifiable constrained interaction, proper scale priors, a simulation check,
and matched AR1 controls. Do not choose interaction type or priors by repeatedly
chasing these same forecast errors.

An exploratory dashboard can display existing county results with explicit
status and scope while these gates remain unresolved. It must not present them
as independently validated replacements for the accepted state analysis.

## Evidence

- [Model-change rationale](model_change_rationale.md): component and pathogen decisions.
- [Spatial comparison review](monthly_spatial_results_review.md): paired scores and calibration.
- [Spatial error concentration](spatial_error_structure_review.md): geographic and origin sensitivity.
- [Corrected residual review](spatial_residual_findings.md): descriptive saved-fit diagnostics.
- [Classification review](monthly_classification_results_review.md): separate conditional outcome.
- [Evaluation inventory](monthly_validation_inventory.md) and [final-validation protocol](spatial_final_validation_plan.md): input/access constraints and acceptance gates.

Private numerical evidence remains in ignored local review outputs. No new fits,
cluster submissions, default changes or revised pathogen rules accompany this record.
