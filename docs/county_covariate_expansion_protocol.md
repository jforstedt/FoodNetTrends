# All-pathogen county covariate expansion

Prepared 16 September 2026 before the expansion fits. This is a parallel,
historical conditional experiment. It does not change Daniel's accepted state
model, certify surveillance completeness, or select production county forecasts.

## Question and fixed design

Does county weather, county age composition, or regional seasonality add useful
predictive information to the existing common-seasonal county model? Does an
addition help when another addition is present, even when it does not help alone?

For each pathogen, origin and temporal reference, fit the same 12 arms:

- State-specific calendar-month seasonal deviations: off/on.
- Weather: off/current month/equal-weight current and previous month.
- County population age composition: off/on; under-5 and 65+ shares enter together.

Every arm retains the common seasonal cycle, static county IID effect, negative
binomial observation model, state effects and state-replicated temporal process.
Holding the common seasonal term on defines an incremental comparison; it does
not establish that common seasonality is preferred for every pathogen. The
existing seasonal-off, spatial and spline comparisons remain separate evidence.
No selected prior comparison is silently overwritten by this expansion.

| Pathogen | Temporal reference | Training begins | Origins | Last usable year |
|---|---|---|---|---|
| Salmonella | AR1; reuse compatible pilot fits | 2004 | 2011, 2013, 2016 | 2019 |
| Campylobacter | RW1; reuse compatible pilot fits | 2004 | 2011, 2013, 2016 | 2019 |
| Cryptosporidium | AR1 | 2004 | 2011, 2013, 2014 | 2017 |
| Cyclospora | AR1 research reference | 2004 | 2011, 2013, 2016 | 2019 |
| Listeria | AR1; common-seasonal preference unresolved | 2004 | 2011, 2013, 2016 | 2019 |
| Shigella | AR1; retain previous nonseasonal comparisons | 2004 | 2011, 2013, 2016 | 2019 |
| STEC | RW1 | 2004 | 2011, 2013, 2016 | 2019 |
| Vibrio | RW1 research reference | 2004 | 2011, 2013, 2016 | 2019 |
| Yersinia | RW1 and AR1; unresolved temporal choice | 2004 | 2011, 2013, 2016 | 2019 |

Each origin evaluates the following three calendar years. The matrix contains
360 cells: 72 compatible completed pilot cells and 288 new cells. Yersinia's two
temporal references receive the full matched covariate block; no reference is
selected after viewing the new covariate results. Temporal choices follow the
[candidate decision record](county_candidate_decisions.md), not pathogen-specific
tuning of new weather results.

This design can assess age/weather/local-seasonality combinations. It cannot
answer whether weather substitutes for the common seasonal cycle, whether the
same covariates interact with BYM2 or spline trends, or whether fitted product
terms improve prediction. A combined arm is additive on the log-rate scale.
Do not describe its age-by-weather score difference-in-differences as a fitted
biological age-by-weather interaction coefficient. Those distinct hypotheses
remain available for a separately specified comparison if warranted.

## Eligibility and unchanged surveillance rules

Use the hash-bound, previously reconciled pathogen monthly panels and their annual
audit inputs. Require exact county/month keys, counts, positive exposure and annual
reconciliation. Do not construct additional zero cells from a new data source.
Preserve pathogen case definitions, travel and diagnostic inclusion, county
catchment exclusions, parasite-specific populations, and Listeria CSTE eligibility.
The recorded combined surveillance outcome is retained: this is not a CX-only
experiment and not an ascertainment-corrected infection outcome.

Specimen collection month remains the declared event time. The narrow, previously
reviewed Shigella specimen/source-month exception must be bound to its original
evidence; it is not permission to accept new date discrepancies. Any unassigned
date, changed counts, new disagreement or population mismatch blocks that pathogen.
Other independently valid pathogen preparations may continue. Cryptosporidium's
2017 boundary applies to both fitting and held-out outcomes and cannot be relaxed
to make its origins match the other pathogens.

Monthly coverage retains the explicit `EXPLORATORY_ASSUMED_CONTINUOUS` status.
Valid population and observed cases do not certify uninterrupted ascertainment.
Annual exposures retain calendar-day monthly allocation; age shares do not replace
the population offset. These are the same surveillance limitations documented in
the [monthly expansion](monthly_expansion.md) and
[analysis assumptions](monthly_analysis_assumptions.md).

## Weather, age and prior contract

Reuse the prepared county temperature and precipitation series and Census age
shares. Weather is county land weather: it is neither a measurement of individual
exposure nor marine/harvest conditions. For Vibrio and imported-food hypotheses in
particular, a null county-weather increment does not reject the biological pathway.
Age shares measure ecological population composition, not age-specific case risk.

Preserve the pilot's transformation and priors: temperature and log1p precipitation,
county/calendar-month training-only centering, pooled training scaling, and age
standardization on the public reference grid. The lagged window averages current
and previous-month transformed weather before centering/scaling. December 2003
supplies the real previous month for January 2004. These two fixed weather windows
are a reproducible initial sensitivity, not pathogen incubation distributions.
Do not optimize lags or nonlinearities on held-out outcomes during this batch.

The Cryptosporidium origin of 2014 requires a newly generated, outcome-free 2014
transform; neither the 2013 nor 2016 transform is interchangeable with it. All
training transformations must use only months through their declared cutoff.
The public reference-grid weighting convention is retained for comparability;
future pathogen outcomes never enter its scaling.

All enabled standardized fixed covariates retain independent Normal(0, 0.25²)
priors. Regional seasonal deviations retain P(SD > 0.5) = 0.01. Preserve the
existing temporal, seasonal, county and negative-binomial priors. Coefficients
under different weather-window scaling are per-window SD effects, not directly
identical physical-unit effects. Outcome-free prior checks and representative
RW1/AR1 integration tests precede real fits.

## Reuse, parallel execution and diagnostics

Reuse pilot results only after verifying source-plan and output hashes, task
identity, target, input domain, formula/prior contract, covariate transforms,
software and scoring protocol. A matching pathogen/model label is insufficient.
Report reused cells separately from new fits. Never silently refit completed
pilot tasks or treat rescoring as a new independent experiment.

Run independent new model cells concurrently under SGE, without an artificial
three-task cap. Heavy preparation belongs in a visible scheduled job. Fit tasks
use the established four-core, 52 GB RSS/68 GB virtual-memory request and pinned
INLA runtime; actual scheduling and memory enforcement are cluster-specific.
Fit failures do not cancel unrelated tasks, and do not trigger automatic retries
or weakened numerical criteria. Collection waits for dependencies and records
partial failures explicitly. No container rebuild is required.

Retain four independently seeded 1,000-draw posterior streams, the established
sampling protocol, and internal saved fits and held-out truth. Check fit status,
finite predictions, failed numerical correction warnings, exact future-count
masking, one-time exposure multiplication, truth/key pairing and report hashes.
Inspect score stability across streams; stream variation measures Monte Carlo
variation, not independent epidemiological replication. Additional saved-fit
sampling may be warranted for unstable cells without rerunning the model.

Compare matched local-season, age and weather contrasts, including their
difference-in-differences, separately by pathogen, origin and geography. Examine
joint state/catchment predictive interval coverage, width, bias, tail behavior,
county scores and sparse-count performance together. A pooled score gain alone
does not establish adequate calibration or justify a pathogen-specific rule.
No automatic winner or dashboard promotion follows an execution pass.

All historical periods are development evidence. Held-out realized weather and
revised age estimates make these conditional predictions, not operational
forecasts. Overlapping origins and related counties are not independent trials.
Any eventual operational forecast requires origin-available inputs or explicit
future-covariate scenarios with uncertainty, plus a separately documented
evaluation/access history and acceptance criteria.

## Other public inputs: parallel preparation, not hidden model additions

The ready inputs for this batch are county weather and county age composition.
Independent laboratory survey access has been demonstrated for a sample series,
but a historical site/pathogen panel and publication-timing contract are not yet
model-ready. No case-derived diagnostic shares are supplied from the future.

Historical USDA livestock/manure, USGS water-supply context and ACS household
crowding are practical parallel preparation priorities. Each still requires
historical releases, suppression/missingness policy, geography and release-date
checks. NOAA marine temperature needs exposure/harvest linkage; EPA source-water
Cryptosporidium measurements need service-area and monitoring-coverage linkage;
produce trade needs a usable historical series and commodity/release definitions.
Food Environment Atlas fields require historical availability and proxy rationale.
None becomes an automatically enabled predictor merely because a sample download
worked. The parallel [public-context preparation](public_county_context_preparation.md)
records the completed livestock, water and crowding inventories and remaining gates.

Keep patient-level inputs, county outcomes, saved fits, diagnostic result archives
and private review tables out of public commits. Public design and reusable code
do not imply permission to publish model-derived surveillance outputs.

## Launch and validation

From the existing FoodNetTrends checkout on Rosalind:

```bash
git pull --ff-only personal feature/county-covariates-seasonality && module load singularity && python3 scripts/launch_covariate_expansion.py
```

The launcher snapshots only small code/protocol/receipt files and immediately
submits a visible preparation job. That job verifies existing inputs and runtime,
copies the 72 portable pilot reports, and builds the Cryptosporidium transform.
Seven pathogen input checks then run in parallel, followed by the 288-cell model
array and a held collector. No manual data bundle or new container is needed.
The final `county_covariate_expansion_*.tar.gz` includes partial failures and
complete matched contrasts; `_INTERNAL` artifacts remain on the cluster.

The earlier-cutoff transform recenters the already frozen 2016 public features.
Removing the 2014 training mean and scaling cancels the original affine transform;
weather is recentered within county/calendar-month and age globally. Tests verify
equivalence to direct raw-input 2014 preparation and invariance of training values
to changes in later raw covariates. This reuses source provenance rather than
requiring another large public-data transfer.

Local validation includes launcher corruption/dependency/partial-result tests,
public-feature rebase equivalence and leakage tests, pathogen/preflight R checks,
and an actual synthetic Cryptosporidium 2014 AR1/local-season/weather/age fit with
four 1,000-draw streams. The source fitting helpers match the hash-bound completed
pilot's versions. Real pathogen input and numerical gates still execute on HPC.
