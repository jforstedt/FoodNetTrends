# External covariates for FoodNet county forecasts

Research reviewed 14 September 2026. This is a proposed experimental design, not a
claim that an external predictor improves these fitted models. No private case
counts, county results, or fitted parameters are reproduced. Existing eligibility,
case definitions, and Daniel's state reference remain unchanged.

The local extension audit, public dictionary review, and next-phase protocol were
read first. They already distinguish laboratory practices from case-derived
classification shares, specimen dates from administrative dates, and missing
surveillance from zero infections. External inputs must preserve those distinctions.

## Recommended first bundle

Start with **temperature and rainfall anomalies**, keeping a cyclic seasonal term
and the existing temporal/spatial comparators. Prepare two broad age-composition
variables in parallel for the next modest bundle comparison. Weather can represent unusually hot or wet months that a repeated
calendar pattern cannot; demography can represent changing susceptibility and
population composition. This is a plausible complement to seasonality, not evidence
that weather alone will repair forecast bias.

In parallel, audit public FoodNet laboratory-practice aggregates and determine
whether linked laboratory testing/adoption records can be obtained. Those records
could address changing ascertainment more directly than environmental covariates,
but a fraction of laboratories using PCR is not a fraction of specimens tested by
PCR. Do not wait for restricted laboratory data to prepare public weather inputs.

For multi-year forecasts, future weather is unknown. A model given the subsequently
observed weather is an **explanatory conditional hindcast**, not a deployable forecast.
The practical forecast must integrate seasonal weather scenarios or use archived
weather forecasts available at the origin. At long horizons, weather may improve
historical attribution and interval calibration without improving point forecasts.

For one-to-three-month forecasts, a prespecified recent-weather lag or archived
seasonal forecast ensemble may add usable information, subject to actual release
latency. For the existing 36-month target, draw complete future weather paths from
a training-only seasonal/climate scenario model and propagate their uncertainty.
Do not substitute a deterministic forecast of specific rain or temperature events
three years ahead. Compare this operational version against the same incidence
model using seasonal climatology; separately label an observed-weather hindcast as
a best-information explanatory experiment, not a performance guarantee.

## Ranked data choices

Rankings below are project judgments about potential usefulness and integration
cost, not estimated performance gains.

| Priority and source | Coverage and access | Plausible use | Main limitation / cost |
|---|---|---|---|
| 1. NOAA nClimGrid temperature and precipitation | CONUS daily 1951–present; county averages in CSV; public HTTPS bulk access | Short-lag temperature anomaly, rainfall anomaly, or a narrowly specified heavy-rain measure, especially Salmonella and Campylobacter | Low/medium integration cost. County boundary crosswalk and revisions must be checked; current historical product is not an archived operational forecast vintage. |
| 1b. PRISM as an alternative/sensitivity source | CONUS monthly 1895–present, daily 1981–present; public grid downloads without a username/password | Same weather mechanisms; grid-to-county aggregation permits weighting sensitivity | Medium cost. Recent grids change repeatedly; do not include NOAA and PRISM copies of the same predictor in one small model. |
| 2. Census county age composition | Historical county population estimates and ACS products; public bulk files | Under-5 and age-65+ population proportions; hypothesis most directly relevant to age-dependent disease/diagnosis patterns | Low/medium cost if age fields already exist in reviewed census inputs. Use covariates alongside the validated population offset; do not replace exposure totals without reconciliation. |
| 2b. ACS poverty/crowding | All-county five-year estimates begin with 2005–2009, released in 2010; public bulk files; API currently requires a key | Later small sensitivity bundle for access to care, household transmission, and deprivation | Five-year period estimates overlap and are not annual observations. No all-county ACS series for the entire 2004-onward period; preserve margins of error. |
| 3. FoodNet laboratory practices | Public annual aggregate tool; laboratory questionnaires and richer analysis data require a request | Independently measured testing-practice changes; potentially interacts with trend or pathogen | High scientific priority, uncertain linkage cost. Public lab percentages are not test-volume denominators or causal detection probabilities. |
| 4. USDA livestock/agriculture | County agricultural census cycles 2002, 2007, 2012, 2017 and later; public tables/bulk; API key route | Cattle or poultry density, selected by pathogen; candidate weather-by-agriculture interaction | Medium cost. Suppression is not zero; census-year estimates become available later. Resident county need not be food-production/exposure county. |
| 5. USGS water-use context | Public county water-use releases, including self-supplied domestic supply | Static/slow-changing water-source context for a narrowly justified enteric pathway | Medium cost; withdrawals do not measure contamination, pathogen load, or individual exposure. |
| 5b. USGS land cover | Annual NLCD retrospective CONUS record begins 1985 | Developed, pasture/cropland, or water fraction as spatial context | Medium/high raster cost. Modern annual reconstruction first released in 2024; not available as such at 2015 forecast origins. |
| 6. NOAA sea-surface temperature | OISST daily global 0.25-degree grids from September 1981; public access | Vibrio-specific coastal/exposure-location experiment | High linkage cost. Residence county and nearby ocean temperature may poorly represent shellfish origin or travel exposure; species/pathway matter. |
| Review only initially: NORS outbreaks | Public outbreak data and BEAM tool; more detailed data may require request | Interpret extreme residuals and assess robustness to outbreak-associated periods | Voluntary, delayed, incomplete reporting; outbreaks overlap FoodNet outcomes. Contemporaneous final outbreak counts would leak target information. |
| Not first bundle: NHSN | Public reports plus controlled facility surveillance system | Separate healthcare-associated surveillance questions | Target/population mismatch; does not supply a ready county stool-testing denominator for FoodNet. |

Source details are linked below. Public access here means official documentation
provides a public route; a full download and completeness audit has not yet been
performed. Some individual endpoints were temporarily inaccessible during browsing.

## Weather evidence and vintage contract

A primary FoodNet study examined extreme heat/rainfall and Salmonella serovars over
2004–2014, using earlier local weather thresholds. Another Georgia study examined
rainfall together with antecedent conditions. These support prespecifying a small
weather hypothesis, but neither establishes an out-of-sample forecasting benefit
for our county model. [FoodNet Salmonella study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8449873/),
[Georgia rainfall study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6792369/).

A Southwest county study of Campylobacter explicitly examined precipitation,
prior drought and animal operations. It supports the possibility of conditional
benefits from combinations; it does not justify a broad search over arbitrary
weather-by-land-use interactions. [Primary Campylobacter study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11412572/).

NOAA provides daily county averages directly, avoiding national raster processing.
Preliminary fields may appear after two or three days, then change as observations
arrive. The named version was released in 2022. Thus a 2015 evaluation using its
current historical values must be labelled a reconstructed-data hindcast unless
an as-of source is separately established. [NOAA product documentation](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily).

PRISM offers public monthly and daily histories; its recent data undergo a rolling
six-month revision process. Use one pinned release per experiment and preserve
both observation date and retrieval/revision metadata. Direct FTP needs no login.
[PRISM data](https://prism.oregonstate.edu/data/),
[bulk-download instructions](https://prism.oregonstate.edu/downloads/).

Recommended initial weather transform: one temperature anomaly and one transformed
rainfall anomaly, using a fixed historical baseline ending before every origin;
standardize from training data only. Freeze monthly lag choices before scores are
viewed. Retain the cyclic seasonal component to distinguish average season from
weather deviations. Forecast-origin availability determines which lags are usable:
a three-month-ahead prediction cannot use the observed weather two months ahead.
Area-average versus population-weighted county weather is a prespecified sensitivity,
not an opportunity to select the most favorable result.

## Demography, land, and water

Census supplies historical county estimates by age and sex. Intercensal estimates
are revised using later censuses, so they are suitable for retrospective adjustment
but not automatically available as-of an earlier forecast. First inspect whether
the existing census files already contain the required age totals; request only
missing inputs. [County 2000–2010 age estimates](https://www.census.gov/data/datasets/time-series/demo/popest/intercensal-2000-2010-counties.html).

ACS five-year products cover all counties but start at 2005–2009. Census now states
that API requests require a key; downloadable summary files offer another route.
These are five-year period estimates, not a monthly causal exposure. Carry forward
only estimates released by the forecast origin; never interpolate toward an
unreleased later estimate. [ACS product/API documentation](https://www.census.gov/data/developers/data-sets/acs-5year.2009.html),
[historical release explanation](https://www.census.gov/content/dam/Census/library/publications/2009/acs/ACSstateLocal.pdf).

Agricultural census publications and Quick Stats provide county histories. Use
released cattle/poultry inventory per land area only for a declared mechanism;
retain suppression flags. USDA exposes downloadable bulk files and an API using
a key. Release date is distinct from census reference year.
[Historical agricultural census](https://www.nass.usda.gov/AgCensus/archive/),
[Quick Stats download options](https://www.nass.usda.gov/Quick_Stats/),
[API documentation](https://quickstats.nass.usda.gov/api).

USGS water-use records can describe public versus self-supplied domestic water
context. They do not identify contaminated water or establish a monthly exposure.
The 2015 report was published in 2017, illustrating why reference years cannot be
used as release years. [USGS domestic/public supply report](https://pubs.usgs.gov/publication/ofr20171131),
[water-use downloads](https://water.usgs.gov/watuse/data/).

Annual NLCD reconstructs land cover from 1985 but began publication in 2024. Use it
for explicitly retrospective environmental analyses, or locate genuinely available
legacy releases for historical operational tests. Direct download routes exist;
EarthExplorer and cloud routes have different access requirements, and the listed
AWS route is requester-pays. [USGS product history](https://www.usgs.gov/centers/eros/science/about-annual-nlcd),
[data access](https://www.usgs.gov/centers/eros/science/annual-nlcd-data-access).

Vibrio warrants a separate design. A primary study links SST with vibriosis using
exposure counties and distinguishes transmission/species patterns. That makes a
residence-county nearest-coast merge insufficient by itself. OISST v2.1 revised
2016-onward values and replaced v2 in 2020; retain version history.
[Primary SST/vibriosis study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9422303/),
[NOAA OISST](https://www.ncei.noaa.gov/products/optimum-interpolation-sst).

## Observation process, outbreaks, and travel

FoodNet independently surveys diagnostic laboratories; the public tool reports
laboratory practices with surveyed-laboratory denominators. Annual finalization
creates lag. Cryptosporidium laboratory-practice collection ended in 2018. This is
useful external context but does not supply the number of residents tested or a
stable laboratory-to-county exposure mapping. [Tool definitions](https://www.cdc.gov/foodnet/data/laboratory-practices.html),
[public tool](https://wwwn.cdc.gov/FoodNetFast/LabSurvey),
[laboratory survey history](https://www.cdc.gov/foodnet/surveys/laboratory.html).

The most informative additional restricted input would be pathogen/laboratory/month
numbers tested (including negatives), assay adoption dates, catchment linkage, and
ascertainment/revision dates. Public aggregate practice data may support a modest
sensitivity analysis first; do not claim independent testing adjustment is impossible
simply because the case extract lacks denominators. Public availability does not
prove that detailed linked records are obtainable.

Travel information already present in cases should preserve existing rules. The
future fraction of cases reporting travel is not known at origin and must not be
used as a forecast covariate. A travel-stratified target or separate imported-case
component is possible after date/category completeness checks. No suitable public
county-month traveler denominator covering this historical window was verified in
this review; national travel volume would be a coarse exploratory proxy only.

NORS is voluntary outbreak surveillance. Finalized public reports exclude some
incomplete records and do not represent all sporadic illness. Use outbreak labels
for interpretation or a genuinely lagged alert stream with historical timestamps;
never subtract or add public outbreak totals without linkage and deduplication.
[CDC NORS data limitations](https://www.cdc.gov/nors/data/).

NHSN primarily tracks healthcare-associated infections and facility processes. Its
population and definitions differ from FoodNet. It should not be pooled into the
same incidence outcome or treated as a universal testing denominator.
[CDC NHSN scope](https://www.cdc.gov/nhsn/about-nhsn/index.html).

## Small parallel comparison that can answer the question

After public-input preparation and validation, freeze a four-arm bundle comparison
for eligible pathogens: existing seasonal comparator; comparator plus weather;
comparator plus age composition; comparator plus both. Keep spatial structure fixed
within each matched block, then include the same four arms for the alternative
spatial structure where the current candidate ledger retains both. This tests
combined value directly without assuming standalone value predicts combination
value. A pathogen-specific limited interaction (for example rainfall-by-agriculture)
belongs in a later mechanistic block, not every pathogen's universal formula.

Use matched outcomes, exposure, origins and posterior scoring, and report calibration
as well as point accuracy. Already inspected origins remain exploratory. Distinguish
three evaluations in metadata: historical explanation with observed covariates;
forecast using only origin-available inputs/scenarios; and genuinely unexamined or
prospective validation. Integrate covariate uncertainty into forecast draws. A final
weather-conditioned fit cannot establish operational benefit by itself.

Preparation can run in parallel now for weather, census age availability, and
laboratory-practice accessibility. Each source needs a manifest with URL, source
version, retrieval time, observation/reference period, publication/as-of time,
geography vintage, units, missingness, transformation and future-value policy.
Before fits, require unique county-month joins, unchanged eligible totals, no
unknown counties mapped to zeros, training-only scaling, and an explicit release
check at every forecast origin. No case data need to be sent to a public provider
for these public downloads.
