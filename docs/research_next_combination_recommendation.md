# Research recommendation: next useful combinations

Research synthesis, 14 September 2026. Three parallel reviews investigated model
structure, diagnostic observation and external covariates; a fourth investigated
forecast mixtures. This is a recommendation for bounded development, not a claim
that a best model has been established. No model, prior, input rule or running job
was changed by this research.

## Recommendation

The strongest next architecture to investigate is a negative-binomial county
count model with population/person-time exposure, the existing state-specific
trend, partially pooled state-specific seasonality, restrained county borrowing,
and a small number of mechanistically motivated external predictors. Test a
dynamic local effect selectively rather than adding it everywhere. Keep the
observation/diagnostic process explicit when integrating diagnostic data.

This is a research hypothesis, inferred from the completed experiments and
literature. No source or completed run establishes that all these terms together
will outperform simpler controls. The current code already includes state-specific
temporal effects; the untested seasonal extension is heterogeneity around the
common seasonal cycle, not the addition of seasonality for the first time.

Daniel's paper explicitly proposes diagnostic-method/geography interactions,
spatial relationships, finer temporal resolution and pathogen-specific prior or
distribution refinements. It also identifies validation of extrapolation as future
work. These proposals support the research direction but do not specify the exact
INLA models we should adopt. [Weller et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC13055632/)

## Priorities and parallel work

| Priority | Concrete experiment | Why this adds information |
|---|---|---|
| 1: flexible local seasonality | Shared seasonal cycle versus shared cycle plus regularized state-specific departures | The completed factorial used a common seasonal pattern. Different local timing/amplitude could explain variation without an unrestricted county spline. |
| 1: external weather | Add a small temperature/precipitation anomaly block to the seasonal reference and its heterogeneous-season candidate | Tests information beyond a recurring calendar pattern, including whether climate and seasonality complement each other. |
| 2: evolving local effects | Cross seasonal heterogeneity on/off with no dynamic departure, independent local dynamics, and spatially correlated local dynamics | Static BYM2 cannot describe local deviations that change over time. Shigella is the strongest diagnostic motivation; Campylobacter and Salmonella provide contrasting development cases. |
| Parallel: diagnostic observation | Joint reported-count and method-category model, shared versus unshared latent process; acquire independent lab-practice evidence | Allows diagnostic information to contribute without using future case shares as known predictors. Does not claim true-incidence identification. |
| Parallel: predictive ensemble | Equal-weight mixture of matched seasonal AR1 and RW1 predictive distributions | Tests complementary extrapolation using existing fits where saved densities/draws permit; no new covariates required. |

For the structural pilot, use the same three pathogens and existing three origins
for a six-cell seasonal-heterogeneity × local-dynamics comparison: 54 total
candidate/control cells, with up to nine exact frozen controls reusable (45 new).
The independent-local dynamic control is necessary to distinguish added temporal
flexibility from additional spatial borrowing. Reuse
requires identical support, likelihood, priors, forecast target and sampling
contract; changing any of those removes the reuse assumption. Prior and simulation
checks must precede real-data submission. All ready independent cells should run
in parallel. This is a proposed matrix, not a submitted or implementation-ready
job count.

Weather needs a separate forecast-availability contract. Start with a small
matched 2×2 seasonal-heterogeneity × weather comparison for Salmonella and
Campylobacter, rather than adding dozens of correlated climate variables. Select
lags and nonlinear complexity from mechanisms and training data, not from the
already reviewed forecast errors. A climate-only gain or a positive interaction
is insufficient if the full model loses calibration or has unstable tails.

## Data worth adding

**County temperature and precipitation are the most practical public addition.**
NOAA nClimGrid provides county aggregates, reducing the work needed to join gridded
weather to the frozen county footprint. Historical archives and revised products
must be distinguished from data available at the original forecast date.
[NOAA nClimGrid-Daily](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily)

For a one-to-three-month forecast, use only weather observations available at
issuance plus a specified weather forecast/scenario. For a three-year forecast,
future observed weather is unavailable: use climatology or probabilistic scenarios,
or call the analysis weather-conditional retrospective prediction. A historical
weather association does not guarantee operational forecast improvement.

**FoodNet laboratory-practice surveys are the most relevant independent diagnostic
addition.** They record surveyed testing practices rather than only methods among
our detected cases. Their public summaries may support site/year analyses; a
fraction of laboratories is not a fraction of patients tested. Detailed assay
history, stable lab linkage and negative/all-test denominators would support a
stronger observation model. [CDC guide](https://www.cdc.gov/foodnet/data/laboratory-practices.html)

**Existing severity and demographic fields deserve a targeted audit before another
large download.** A FoodNet counterfactual study used severe outcomes and diagnostic
proxies under strong ascertainment assumptions. That is a concrete precedent, not
proof of identifiability or a forecasting validation. The observation memo records
the study and its correction. [Healy et al.](https://doi.org/10.1093/ije/dyad133)

**Demographic composition and agricultural/land-use context are secondary additions.**
They may explain persistent county heterogeneity, but static spatial effects may
already absorb much of that information. Use a small interpretable set, respect
historical publication dates, and keep population exposure separate from risk
covariates. ACS rolling five-year estimates are not independent annual measurements.
Detailed access, resolution and vintage constraints are in the external-data memo.

NHSN is not the first choice: its healthcare surveillance targets do not supply a
community enteric testing denominator. Outbreak and genomic records may be useful
for retrospective mechanisms, but labels finalized after an outbreak cannot be
used as if available at forecast issuance.

## Important correction to the previous framing

Diagnostic integration is not categorically unavailable without all-test counts.
A coherent joint model can predict reported counts and diagnostic categories with
current case data if the category partition is valid. What those data alone do
not identify is the number of undiagnosed community infections. With independent
parameters, fitting counts and categories jointly is merely two separate models;
a shared process introduces the explicit borrowing assumption to test. Future
category shares and counts must both be predicted, not supplied from the holdout.

Likewise, “best combination” need not mean one maximal formula. Forecast mixtures
can hedge differing temporal extrapolation assumptions. Published infectious-
disease ensemble results motivate testing this, without establishing a FoodNet
benefit. [Fox et al.](https://wwwnc.cdc.gov/eid/article/30/9/24-0026_article)

## What to avoid

Do not automatically stack RW1, AR1 and spline trends; their roles overlap and
can become poorly identified. Do not add a zero-inflation process solely because
counts contain many zeros. Do not learn highly flexible ensemble weights from
three overlapping origins, treat weather measured after issuance as known, or
interpret residual Moran indices as a model-selection test. Do not automatically
pool unrelated pathogens or impose bacterial diagnostic categories on parasites.

Keep reported-incidence prediction, method composition, retrospective trend
estimation and ascertainment scenarios as separate outputs. Maintain Daniel's
state analysis as the reference product. Development can proceed on reused
historical periods with honest labels; independent production validation still
requires the input/access and acceptance gates already documented.

## Supporting research

- [Model combinations](research_model_combinations.md)
- [Diagnostic observation integration](research_observation_integration.md)
- [External covariates](research_external_covariates.md)
- [Forecast ensembles](research_forecast_ensembles.md)
- [Current candidate decisions](county_candidate_decisions.md)
