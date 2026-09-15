# Integrating diagnostic observations with incidence

Research review, 14 September 2026. This memo proposes research designs; it does
not change the accepted state model, case eligibility, or fitted results. It
uses public sources and the repository's documented variable audit. Private
case counts and review results are excluded.

## Recommendation

Diagnostic information can be integrated now for **prediction of reported
infections**, provided it is modelled as an outcome jointly with counts rather
than inserted as a known future case-derived covariate. Estimating the underlying
community infection rate is a separate, more demanding objective. Laboratory
testing volumes, assay histories and population care-seeking information are the
most directly useful additions for that objective.

The earlier caution about circularity should not be interpreted as a prohibition
on all integration. It identifies a particular mistake: using future observed
CIDT shares to predict the same future case totals, then calling the result a
forecast or a causal correction. A coherent joint distribution avoids that
mistake but does not, by itself, identify undiagnosed infections.

Daniel's paper explicitly proposes time-spline interactions with diagnostic
method and geography, alongside spatial and intra-annual extensions. Its
proposal is compatible with a method-stratified count model. It is not evidence
that the available CX+/CIDT+ recode measures independent testing intensity. See
the paper's future-improvement discussion and the repository's
[dictionary review](foodnet_dictionary_review.md).

## What the external evidence establishes

FoodNet has a relevant external data source already: annual diagnostic laboratory
practice surveys, including detection and reflex-culture practices. Public
summaries cover laboratories serving the surveillance area, not just our case
records. Laboratory-practice collection for Cryptosporidium ended in 2018.
An unweighted fraction of laboratories using a method is not the fraction of
patients tested by it; catchment and testing-volume weights would improve its
usefulness. [CDC laboratory-practices guide](https://www.cdc.gov/foodnet/data/laboratory-practices.html)

There is a direct FoodNet precedent for integration. Healy and colleagues used
severe-outcome incidence plus CIDT, panel and confirmation proxies in a
cross-pathogen Bayesian counterfactual model. Their central assumption was that
severe outcomes were consistently captured despite diagnostic changes. Their
evaluation used internal random-fold validation, not a future-period forecast
test. This is a useful sensitivity-analysis design, not proof that the diagnostic
effect is identified in our data. [Healy et al., 2024](https://doi.org/10.1093/ije/dyad133)

The published correction removes Listeria from the second key message; do not
attribute a demonstrated CIDT-adjustment finding for Listeria to this study.
[Healy study correction](https://academic.oup.com/ije/article/doi/10.1093/ije/dyae101/7723679)

A previous Campylobacter adjustment estimated test-specific positive predictive
values using external performance and prevalence information. The authors
identified missing total-tested counts as a major limitation. Culture was their
reference standard for comparison with historical culture incidence, not an
infallible measure of all true infections. [2018 FoodNet CIDT-adjustment study](https://academic.oup.com/ije/article/47/5/1613/4944215)

A recent Salmonella analysis found differing severity patterns by diagnostic
method, with CIDT diagnoses more associated with milder illness. This makes
severity useful to investigate, while warning against assuming an invariant
severity mix or that culture-confirmed cases are an unaffected control. Reflex
culture can itself depend on CIDT detection. [CDC, 2026 Salmonella analysis](https://www.cdc.gov/mmwr/volumes/75/wr/mm7529a2.htm)

## Feasible model with current data

The following is a proposed statistical construction, not an already validated
FoodNet correction. For an eligible pathogen/location/month, let N be total
recorded eligible cases and K their recorded classification category. A joint
marked-count model can factor as:

```
N ~ negative_binomial(mu, dispersion)
(N_1,...,N_K) | N ~ multinomial(N, pi_1,...,pi_K)
log(mu) = log(population) + incidence trend + season + geography + a * z
log(pi_k/pi_reference) = method trend_k + geography_k + b_k * z
```

Here z is an optional shared latent process, with a fixed scale/sign convention
and shrinkage. It describes predictive co-movement, not proven assay adoption.
The a=0 arm is essential: if count and classification parameters are independent,
the factorization is simply two separate analyses and cannot improve count
predictions through classification information. The shared arm deliberately
introduces a testable borrowing assumption. Keeping separate incidence and method
trends avoids forcing changing diagnostic composition to equal changing disease
risk. Correlated method-specific intensity models are an alternative.

Forecast both N and its composition from the training period; integrate over
future z and pi rather than supplying observed future N or shares. Score total
counts and category counts, plus calibration, against the exact same eligible
support. This is materially different from the completed conditional experiment,
whose future denominator was observed.

Begin with site-month models, where diagnostic practices can plausibly be shared
and counts are less sparse. Compare one prespecified shared-process arm with its
unshared control and the frozen count reference. Cross these with seasonal versus
nonseasonal structure where the earlier count comparison supports both. Keep
spatial county variants for a subsequent or parallel prespecified arm only when
the observation model's geographic support is defensible. Do not make a large
unrestricted factorial of poorly identified shared trends.

Category definitions are a prerequisite, not a requirement for every conceivable
new data source: current CX+ is not synonymous with culture-only. Preserve valid
unknown/unclassified cases as explicit categories or model their missingness;
do not silently redefine incidence as only the two classified categories.
Separate parasite-specific definitions are required. If a coherent exhaustive
partition cannot be established from current coding, label the experiment as
prediction of the recorded classified subset and do not compare its total to
the full-incidence target.

## Why this does not identify true incidence

In a simple idealization, true infections I have mean population * lambda and
each is observed with probability q. Poisson thinning gives observed mean
population * lambda * q. Case counts identify the product, not lambda and q
separately. Diagnostic composition adds relative information among detected
cases, but no count of missed infections. Extra smoothers or priors can stabilize
estimation without supplying the missing identification. The distinction is a
mathematical property of this proposed observation model.

With tested-person or tested-specimen denominators T by assay, a second layer can
model positive results using sensitivity, specificity and prevalence among
those tested. Repeat specimens, panel co-detections, reflex tests and selection
for testing must be handled explicitly. That prevalence still differs from
community prevalence: illness, seeking care and specimen submission select who
gets tested. A population denominator is appropriate for reported incidence;
a tests denominator defines a different positivity outcome, not a substitute
population offset.

CDC's burden methods combine evidence about underreporting and underdiagnosis;
these are distinct from the routine trend estimand. Their existence supports
using an explicit observation model, but does not provide a ready-made monthly
county detection series. [CDC burden methods](https://www.cdc.gov/food-safety/php/data-research/burden-methods.html)

## Additional inputs ranked by usefulness

| Input | Immediate use | What must accompany it |
|---|---|---|
| Laboratory assay/panel/reflex history by pathogen and lab | Independent diagnostic-change predictor; comparable tested methods | Stable lab crosswalk, catchment/service changes, dates and annual uncertainty, patient/test-volume weights where possible |
| All tests, including negative results, by pathogen/lab/month | Test-positivity and ascertainment modelling | Unique patients or documented specimen counting, repeats/reflex links, assay performance, changing indications and laboratory coverage |
| Existing hospitalization, death, specimen type and demographic fields | Severity-stratified count forecasts; sensitivity anchor for diagnostic shifts | Historical completeness and definitions, discharge follow-up, age mix, evidence about changing admission/testing practices |
| Population care-seeking and specimen-submission survey evidence | Priors/sensitivity ranges for community ascertainment | Survey weights, sampling period, severity/age strata, transportability uncertainty |
| Versioned reporting/observation calendar and event timestamps | Correct exposure intervals and possible reporting-delay model | Actual data-availability timestamps or historical snapshots; collection date alone cannot reconstruct reporting vintages |

FoodNet's population surveys explicitly collect diarrheal illness and
health-seeking information. The reviewed CDC page lists 2018–2019 as the latest
survey, so its estimates should not be treated as an annual county time series.
[CDC population surveys](https://www.cdc.gov/foodnet/surveys/population.html)

Public laboratory summaries can support an ecological sensitivity analysis
without private lab identifiers. They should enter at their actual annual/site
resolution, with no invented monthly adoption precision. If linked laboratory
records become available later, refine the measurement layer without changing
the definition of the underlying forecast target.

## NHSN and practical next steps

NHSN primarily monitors healthcare-associated infections and healthcare process
measures. Its facility-based coverage and outcomes do not supply the missing
community enteric testing denominator. It is a separate surveillance system,
not another version of this MMWR case file. A specific linked healthcare study
could use it, but it is not the next data integration for this project.
[CDC NHSN overview](https://www.cdc.gov/nhsn/about-nhsn/index.html)

Proceed in parallel with: (1) simulation-based identifiability and forecast checks
for the marked-count design; (2) a bounded audit of existing severity/category
fields, reusing earlier inventories; (3) acquisition and documentation of public
FoodNet laboratory-practice summaries. No external messages are authorized or
sent by this memo. If restricted laboratory data are needed later, request the
minimal columns in the table rather than an unspecified complete dictionary.

Before a real-data fit, freeze category semantics, temporal support, forecast
availability rules, priors and paired controls. Use rolling-origin development
comparisons; the repeatedly inspected historical periods are not independent
validation. Report observed-incidence forecasts, classification forecasts and
counterfactual sensitivity estimates separately. Keep Daniel's accepted state
analysis as its own product throughout.
