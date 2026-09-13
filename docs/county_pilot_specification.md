# Salmonella county pilot: input audit and proposed model

Scope agreed for this pilot: Salmonella, 2004–2019, historical FoodNet catchment.
This is a separate exploratory county analysis, not a replacement for Daniel's
state spline. The current launcher prepares inputs and diagnostics only; it does
not fit the draft model below or publish dashboard results.

## Cases and population

Reuse `output/20260911_140750/preprocessed/clean_mmwr.csv`, preserving its existing
preprocessing. Select `pathogen=SALMONELLA` and years 2004–2019, retaining travel
NO/UNKNOWN/YES and diagnosis categories CIDT+/CX+/PARASITIC, with the existing
exclusions for county OUT OF STATE/UNKNOWN/99997. The unusual PARASITIC category
is retained in the filter to match the current all-category invocation; audit
results must establish whether any Salmonella records actually carry that label.
No serotype selection, extra deduplication, or travel adjustment is performed.

Use the existing bacterial SAS population file `cen9625.sas7bdat` for this pilot;
record its checksum and report every county/year population. No CT 2020+ candidate
or new population vintage is applied. The pilot spans 486 counties and 16 years
(7,776 possible county/year cells). Population completeness, positive values,
unique keys, and state agreement are mandatory. Census EntryYear alone does not
define eligibility.

Publicly supported footprint: all counties in CT, GA, MD, MN, NM, OR, TN; three CA
counties (Alameda, Contra Costa, San Francisco); seven historical CO counties;
34 NY counties listed in the 2009 report. This follows the stable historical
catchment, separately from the 2023 expansion. The county list is committed in
`analysis_configs/county_pilot/counties.csv` with explicit 2004–2019 dates.
[CDC historical coverage](https://www.cdc.gov/mmwr/volumes/73/wr/mm7326a1.htm),
[2009 county roster, Table 1](https://stacks.cdc.gov/view/cdc/152214/cdc_152214_DS1.pdf).

Every selected geographic tuple must have a direct FIPS population match within
this footprint. Name-only candidates, contradictory names/FIPS, unexpected sites,
and missing population rows trigger REVIEW_REQUIRED; none is silently repaired
or dropped. The audit reports state/year selected and directly matched totals.
Only when all case and population checks pass does it construct an internal panel,
including zero observations for covered county/years with no selected cases.
That is an explicit observation assumption within this restricted pilot scope,
not a rule applied to all historical FoodNet records.

## Candidate graph

Use the official [2010 Census adjacency table](https://www.census.gov/geographies/reference-files/time-series/geo/county-adjacency.2010.html).
Census did not release intermediate annual tables before 2023. Retain edges
between included counties, including cross-state edges and Census water-boundary
neighbors; remove self edges. This is not a land-only or road-connectivity graph.
Preserve isolated counties and disconnected components, reporting their membership.
A fixed 2010 graph across 2004–2019 is a pilot assumption; minor boundary changes
and alternate adjacency definitions remain sensitivity questions.

County labels are independently checked against the
[2019 Census gazetteer](https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2019_Gazetteer/2019_Gaz_counties_national.zip).
The 2010 source has a mislabeled header for FIPS 27111 (Otter Tail, labeled Todd)
and a blank county name for 27165; its Doña Ana labels also contain encoding
artifacts. The independent gazetteer supplies the county names. Source label
conflicts are preserved in `source_label_issues.csv`; graph FIPS edges are not
rewired from county-name guesses. The source FIPS graph is symmetric.
Source hashes and URLs are recorded in `provenance.json`.

Reproduce public geography: `python3 scripts/build_pilot_geography.py ADJACENCY_TXT GAZETTEER_ZIP NEW_OUTPUT_DIR`.
No public file downloads are required on compute nodes.

## Draft model for review after the input audit

For county c in state s and year t:

- Counts follow a negative-binomial distribution, mean mu and variance mu+mu²/k.
- log(mu) = log(population) + state intercept + county BYM2 effect + state RW1 time effect.
- Scale the spatial components; handle disconnected components and singletons.
  Center temporal effects within each state. Record all constraints in the fit.
- Initial exploratory prior proposal: state log-rate intercepts Normal(log(20/100000), 2²);
  spatial SD PC prior P(SD>1)=0.01; spatial mixing P(phi<0.5)=0.5;
  temporal SD PC prior P(SD>0.5)=0.01; log(k) Normal(log(12), 1²).
  These are starting proposals requiring prior-predictive checks, not approved
  production priors or inherited priors from Daniel's model.

This first model shares a temporal shape among counties within a state; it cannot
claim independently estimated county-specific trend shapes. County/time interaction
is a later model extension to assess, not a feature hidden in the first fit.
An RW1 is not Daniel's thin-plate spline. The county model also introduces spatial
pooling and county-level overdispersion, so matching state results is a diagnostic,
not a mathematical equivalence test.

Before fitting real data: review the audit, inspect graph components and source
label issues, run prior-predictive checks on the actual exposure range, and settle
the initial model and sensitivity specifications. Subsequent validation should
include predictive residuals/zero counts, CPO failures, temporal holdout prediction,
prior/graph sensitivity, and a matched-data state comparison. Compare predictive
performance against a nonspatial county model rather than treating finite INLA
output or low WAIC alone as validation.

Candidate outputs after validation: county incidence per 100,000 with intervals,
state aggregates computed from joint posterior draws weighted by population, and
2019-reference contrasts. Do not sum marginal credible interval endpoints or use
independent marginal draws to compute aggregate uncertainty. No county maps or
dashboard controls are implemented by this audit.

## Run the audit on Rosalind

`python3 scripts/launch_county_pilot_audit.py` submits one one-slot read-only job
using the existing **foodnet.sif**, because it already contains haven/readr for
input preparation. It needs no new container build and does not rerun preprocessing.
The command prints one log and one diagnostic archive. `--prepare-only` creates
an offline plan; `--clean-file` and `--census-file` override input locations.

Reports: case selection flow, suppressed geographic exceptions, state/year
reconciliation, population audit, graph nodes/components/edges, source checksums,
and INPUT_AUDIT_PASS/REVIEW_REQUIRED/FAIL. The exact-count panel is kept separately
on HPC as `county_panel_INTERNAL.rds` and is omitted from the archive. Reports are
for internal review, not certified public-release tables.

Execution update: [the implemented pilot and prior review](county_pilot_fit.md)
revises the draft state-intercept SD from 2 to 1 following prior-predictive checks
on the audited exposures. It adds a same-data IID county comparison. Both remain
exploratory, and no dashboard publication is performed.
