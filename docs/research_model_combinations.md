# Research recommendation: the next county-model combinations

Research review, 14 September 2026. This is a proposal for development, not a
claim that a new model has been fitted or validated. It combines the published
paper, current model code, and qualitative findings in the candidate decision
and saved-residual records. Private numerical results are not reproduced.

## Recommendation

The most justified new combination is **the retained pathogen-specific temporal
model + partially pooled state-specific seasonality + evolving county deviations**.
Test the parts together and separately. The existing factorial tested a common
seasonal cycle and static county effects; it did not test this combination.
Do not repeat the completed RW1/AR1/spline × seasonality × static-space factorial.

There is no evidence for one universal best combination. Preserve Daniel's
accepted state analysis, and treat this as a separately evaluated monthly county
forecast product. The aim is better calibrated county and aggregate predictions,
not simply smoother maps or smaller residual correlation.

## What the paper and code actually support

The published model has separate site-specific penalized thin-plate trends,
negative-binomial counts and population offsets. Its county-year comparison
refers to catchment-entry groups, not a full modern county-month interaction
model. Its comparisons were in-sample; near-term extrapolation validation is
explicit future work. It proposes INLA, spatial relationships, diagnostic-method
interactions, intra-annual variation and pathogen-specific priors/distributions.
Those are motivations, not tested specifications for the present extension.
The full paper was read from the cached PMC XML/text after the browser endpoint
returned a challenge. [Weller et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC13055632/)

The implemented monthly incidence model already has **state-specific** RW1 or AR1
trends (`replicate=state_id`), or state spline components. Its county effect is
static IID/BYM2; its optional twelve-month cyclic effect is common across states.
Consequently, neither adding another state trend nor calling a static BYM2 term
“dynamic spatial smoothing” would be a new hypothesis. See
[scripts/monthly_seasonal_model.R](../scripts/monthly_seasonal_model.R) and
[scripts/monthly_spatial_combination.R](../scripts/monthly_spatial_combination.R).

## Prioritized components

### 1. Allow seasonal shape to differ by state, with shrinkage

Use a common cyclic curve plus regularized state deviations, instead of ten
unrelated seasonal fits. This allows timing and amplitude to vary while small
sites borrow information. Hierarchical smooths are an established way to share
information while allowing group-specific response shapes; transferring that
principle to this cyclic INLA component is our proposal, not a result from that
paper. [Pedersen et al.](https://peerj.com/articles/6876/)

This is comparatively small: ten twelve-month curves rather than a new
county-by-month field. It requires no new external data beyond the existing
eligible monthly panel. It is particularly sensible alongside the retained
seasonal Campylobacter and Salmonella controls. It may also explain apparent
spatially patterned errors without needing a dynamic county effect.

Constrain each state's seasonal deviation to have zero calendar-month mean,
and constrain deviations across states for each month so that the common cycle
is identifiable. Use a shared deviation-scale prior shrinking toward the common
cycle. Choose constraints and exposure weighting before evaluation. Do not allow
the seasonal cycle to vary independently every year in this first comparison.

### 2. Let local county deviations evolve, with an independent-local control

Shigella is the strongest project-specific candidate: its saved residuals retain
both geographic association and consecutive-month persistence. That is evidence
to test a hypothesis, not proof that neighboring transmission caused the pattern.
The same batch should include Campylobacter and Salmonella to check whether the
extension generalizes beyond the pathogen that motivated it.

Compare no evolving county term, temporally correlated but spatially independent
county deviations, and spatially correlated evolving deviations. The independent
local term is essential: otherwise an improvement could be due entirely to local
time flexibility, with no benefit from spatial borrowing.

A practical first formulation is an AR1 evolution for county departures with
IID versus scaled spatial innovations, holding the remaining formula fixed.
This is a proper-AR1 analogue of structured space-time interaction, not literally
Knorr-Held's intrinsic RW1 Type IV. Published areal forecasting work found benefits
from structured interactions in cancer data; that establishes feasibility, not
FoodNet superiority. It also documents the constraints and computational costs
of intrinsic interactions. [Orozco-Acosta et al.](https://onlinelibrary.wiley.com/doi/10.1002/bimj.202300096)

Keep static county effects in every matched arm, but separate them from dynamic
departures with a frozen identifiable parameterization. Center county innovations
within the existing state/graph components at each time so that they cannot simply
re-create state trends. Specify the stationary initial distribution, marginal vs
innovation variance, and any temporal centering on the training domain. Constraints
must not change when future prediction rows are appended. The current graph is
disconnected; a single global constraint is insufficient for intrinsic spatial
components. Use scaled components and interpretable shrinkage to zero interaction.
BYM2's scaling rationale applies to interpretable spatial variance, not automatic
model quality. [Riebler et al.](https://arxiv.org/abs/1601.01180)

Do not copy an online `knmodels` example untested: the official interface supports
several interaction/constraint conventions, and an interface documented today
must still be checked against our pinned INLA build. [INLA interaction reference](https://www.r-inla.org/learnmore/docs/reference/knmodels.html)

### 3. Preserve spline combinations, but assign different components different jobs

A spline can represent slow change while an AR1 represents short-lived departures;
they are not mathematically mutually exclusive. But adding both unrestricted
state trends can make their attribution unstable. Our completed alternatives do
not evaluate a separated slow-trend/short-term-residual decomposition.

Keep this as a later bounded candidate: a training-defined low-rank smooth trend,
a constrained short-memory deviation, seasonality, and the selected county
structure. The spline basis, extrapolation rule and priors must be explicit.
Do not add it to every arm now: existing spline comparisons did not establish a
general gain, and increasing temporal flexibility cannot guarantee future accuracy.
A mean-zero stationary AR1 pulls departures toward zero as the horizon grows;
that can help transient deviations but harm persistent growth. This implication
follows from the AR1 model, not from a FoodNet-specific causal mechanism.
[INLA AR1 definition](https://inla.r-inla-download.org/r-inla.org/doc/latent/ar1.pdf)

## A concrete parallel batch

The primary question is a four-cell factorial: state-specific seasonality off/on
crossed with evolving spatial county effects off/on (A, B, E, F below). Add two
independent-local controls (C, D) to distinguish spatial borrowing from simply
allowing every county its own changing trajectory.

For county i in state s at month t, a proposed count model is:

```text
Y_it ~ NegativeBinomial(mu_it, size_p)
log(mu_it) = log(person_years_it) + alpha_s + g_s(t) + b_i
             + c(month_t) + h_s(month_t) + d_it
```

Here g is the retained state temporal model, b the fixed-in-time county package,
c the common cyclic season, h a shrinkable state seasonal deviation (zero in
A/C/E), and d the evolving county departure (zero in A/B). For C/D, d evolves
with spatially independent innovations; for E/F it evolves with scaled spatial
innovations. An illustrative evolution is d_t = rho_d d_(t-1) + epsilon_t,
with the within-state constraints applied consistently to the process. This is
a model definition to implement and validate, not a ready-to-run INLA formula.
The exact covariance and initial distribution must reconcile those constraints
with the static b and state g components.

Freeze the following six arms within each pathogen/origin:

| Arm | Seasonal structure | Evolving county departure |
|---|---|---|
| A | Existing common cycle | None; exact saved control |
| B | Common cycle + pooled state deviations | None |
| C | Existing common cycle | Independent county AR1 |
| D | Common cycle + pooled state deviations | Independent county AR1 |
| E | Existing common cycle | Spatial county AR1 |
| F | Common cycle + pooled state deviations | Spatial county AR1 |

Use Shigella and Salmonella AR1 temporal controls and Campylobacter RW1, as in the
current decision record. Hold negative-binomial likelihood, exposure, existing
static spatial package, temporal priors, observation calendar, outputs and scores
fixed within each six-arm block. For isolating the new spatial term, C vs E and
D vs F must differ only in spatial innovations. A static BYM2 block is a reasonable
controlled starting point, not a promotion of BYM2 over IID.

Three pathogens × three already-used development origins × six arms gives
**54 comparisons, 45 new fits if all nine A controls match exactly**.
This is a proposed size, not a submitted run. Reuse only content-verified identical
controls; if constraints or baseline priors change, count the required new controls
honestly. Do not retune the arms after seeing one pathogen's results. All independent
fits can run together after synthetic and prior-predictive gates; there is no
scientific reason to serialize pathogens.

Before launching, test recovery under no local effect, only heterogeneous
seasonality, only independent local persistence, and genuine spatial persistence.
Test disconnected graphs, sparse counts, aggregate coverage, and invariance to
extra forecast rows. Calibrate effect-scale priors through rates and counts;
scaling an intrinsic model changes the meaning of its precision prior.
[INLA scaling guidance](https://www.inla.r-inla-download.org/r-inla.org/doc/vignettes/scale-model.html)

Select prior scales from scientific effect-size judgments, synthetic calibration,
and training-only information; never estimate them from the evaluated forecast
outcomes. Freeze numerical values and the complete prior manifest before launch.
Freeze practical improvement and non-inferiority margins before the batch. Report
monthly and annual calibration, count bias, proper scores and interval width;
aggregate joint predictive draws to common state targets. Failure to improve
calibration cannot be excused by better smoothness. Reused origins remain
exploratory; neither this batch nor another random seed creates a new holdout.

## What additional data can change the recommendation

A good external predictor may explain a seasonal or spatial residual and reduce
the need for a latent effect. But future predictor availability determines whether
it helps forecasting, historical explanation, or both. Coordinate with the separate
source audit before selecting a large covariate matrix.

- **Laboratory testing/adoption and negative-test denominators:** highest value for
  distinguishing observation changes from illness changes. Conditional CIDT share
  among detected cases is not an independent incidence covariate. Prefer distinct
  category-incidence outcomes or an explicitly identified observation model.
- **Age-specific cases plus matching county-age exposure:** supports compositional
  adjustment and partial pooling, rather than attributing demographic shifts to
  geographic risk. Without matching denominators, case age proportions alone are
  not age-specific incidence.
- **Weather anomalies and relevant environmental exposures:** plausible adjuncts
  to seasonality; compare anomalies conditional on the seasonal cycle so a predictor
  cannot win merely by rediscovering month. Actual future weather is unavailable at
  a genuine forecast origin unless forecast/scenario uncertainty is propagated.
- **Serotype/species and outbreak context:** can explain opposing subtrends hidden
  in totals, but sparse categories need pooling and unknown-category accounting.
  A Virginia Salmonella study found locality and serotype heterogeneity; it did
  not establish that adding these dimensions improves our county forecasts.
  [Yates et al.](https://doi.org/10.1016/j.jfp.2025.100548)

A shared cross-pathogen latent observation factor is not yet justified as a
“testing adjustment”: it could absorb common weather, healthcare seeking,
reporting, or true transmission. It requires external anchors and sign/scale
constraints. A simple ensemble of existing calibrated candidate forecasts is a
cheap complementary experiment; weight selection still needs a temporally honest
protocol and cannot repair common bias simply by averaging.

No model, accepted state output, pathogen rule, container or cluster job is
changed by this research memo.
