# Extension status — 12 September 2026

The March Claude upgrade proposals are design notes, not implemented or validated
features. Their duration and performance estimates have not been established for
these FoodNet inputs. This status distinguishes the September feature-validation
run from that broader program.

| Work | Implemented | Evidence / remaining work |
|---|---|---|
| Selectable baseline and baseline incidence columns | Yes | Synthetic contracts, saved-data checks and 2019 real-data feature run; earlier combined run used 2016–2018 |
| STEC groups, Salmonella selections and categories, species selection | Yes | 14 real-data groups completed; classification definitions remain provisional for FoodNet review |
| Travel stratification | Yes | Separate domestic/travel code, outputs and synthetic tests; the 14-model run did not enable it |
| CIDT filtering | Yes | Included-case selection; not an adjusted counterfactual model |
| Proposed CIDT-adjusted stratification and counterfactual estimates | No | Requires a specified model, assumptions, implementation and validation |
| Nowcasting | No | Requires reporting-delay data assessment and backtesting before interpreting estimates |
| County-level R-INLA spatial/temporal models | Synthetic prototype only | Actual local INLA smoke fit passed; dedicated SIF and SGE execution pending; real county inputs/model remain unvalidated |
| County maps, spatial dashboard and county-to-state comparisons | No | Depend on validated geographic inputs and county model outputs |

## Current state-level validation

The 14 selected feature analyses completed. Six fits had divergences. Separate
refits at adapt_delta=0.999 have zero divergences and zero tree-depth hits, with
maximum rank Rhat 1.001608 and minimum bulk/tail ESS 3939/3224. The final
checkpoint recovery verified equal data (zero tolerance), identical priors and
identical Stan code. It did not repeat sampling.

Across these six, the largest catchment median incidence difference was 0.72%
and the largest catchment relative-risk point-estimate difference was 0.84%.
Salmonella OTHER SEROTYPES in 2003 changed from an interval entirely above 1 to
one including 1 (lower bound 1.000494 to 0.999413). State-level differences were
larger, including an approximately 23% relative change in an interval endpoint.
These are comparisons of sampler settings, not proof of equivalence to all
historical pipeline versions or a complete assessment of model adequacy.

The consolidation helper creates a separate final_dashboard directory containing
eight original fits and six validated refits, regenerates affected plots and
summaries, and writes a source manifest. Original outputs remain preserved.
Cluster finalization completed on 12 September in final_dashboard_20260912_173916_851341. The downloaded dashboard was checked: all 14 analyses were present, all six replacement comparison outputs matched, and the 2019 reference rows were correct. No additional sampling was needed.

## Spatial input reconnaissance already completed

Evidence: foodnet_input_audit_20260911_134449.txt, generated on the cluster from
raw input files. These observations precede pipeline filtering and are not a
validated spatial analysis dataset.

- County population rows and identifiers exist in the census files. The parasite
  file ends in 2024.
- Raw case FIPS is blank for all 2023–2025 records in that audit: 31,655, 25,970
  and 24,072 records respectively.
- Diagnostic exact state/year/county-name matches recover many recent bacterial
  records, but leave 3,614 / 2,435 / 2,355 without a unique positive-population
  match. Name matching is not yet an approved geographic conversion.
- Connecticut case geography and the county/planning-region population transition
  require consistent boundaries and denominators. A state total is not a county
  denominator or crosswalk. Missing matched populations already appear in
  2020–2022 in the raw audit.
- Historical county surveillance eligibility, boundary vintage and adjacency
  have not been validated. Census row presence alone cannot establish eligibility;
  an unobserved county-year must not automatically become a zero-case observation.

## Next spatial implementation work

1. Produce a reviewable county/year eligibility table and geographic resolution
   table on the cluster. Preserve original identifiers; record matching method,
   ambiguity and unmatched reason. Resolve Connecticut geography consistently
   for both cases and populations. Do not allocate cases by population shares
   without an explicitly justified method.
2. Validate a separate INLA container with a small synthetic example. The local
   inla_r45.def/run_inla.sh files came from an unrelated April support ticket;
   they are not evidence that FoodNet has a working INLA backend.
3. Implement and test a county model against synthetic known-truth examples, then
   compare county aggregates with state results. State splines and a proposed
   RW2/BYM2 model are different specifications, not an automatic backend swap.
4. Add pipeline routing, county outputs, maps and interpretation text only after
   the input and model checks pass.

Before implementing the proposed CIDT adjustment or nowcasting, recover the
specific model definitions and assess their required inputs. Do not use an
expected direction of a real-data trend as a test that forces a desired result.

Plan sources: .local/plans/future_models/UNIFIED_PLAN_v2.md,
spatial_and_inla.md, county_level_modeling.md, VALIDATION_REPORT.md and
PUBLICATION_OUTPUTS.md. These are locally saved proposals. The validation report
itself also contains unverified claims; it is not an external scientific review.

## County preparation job

`python3 scripts/launch_county_preparation.py` submits one SGE job using the
existing FoodNet container. It reads only the geography/pathogen fields needed
from raw MMWR data and county population fields from the two census files.
Each invocation writes a separate `output/county_preparation_*` directory.

Outputs include a match summary, internal geographic candidate/Connecticut
exception tables, and bacterial/parasitic county-year coverage-review templates.
No individual case identifiers are written. Case counts below five are suppressed;
these internal diagnostic tables are not certified for public release.

Direct FIPS matches are checked against state and available unique county-name
matches. Blank FIPS may yield a unique state/year/normalized-name candidate;
malformed or conflicting populated FIPS are never replaced automatically.
Duplicate population keys, missing/nonpositive populations, and years before
census EntryYear are flagged. Census EntryYear is a diagnostic constraint, not
proof of full county surveillance eligibility. Connecticut 2020 onward is marked
for boundary reconciliation. Every row retains unverified coverage and
`model_ready=FALSE`; no county-year zero case rows or spatial fits are created.

Local validation: geographic edge-case tests and a synthetic SAS-to-report test
passed, including checksum verification that source inputs were unchanged.
Real-data execution and adjudication of the candidate tables remain pending.

## Crosswalk and Connecticut follow-up — 12 September

The completed county-preparation archive was analyzed locally, without another
HPC run. All 477 unique candidate state/county-name mappings have a single FIPS
across the audited years and agree with historical direct-FIPS records. The
crosswalk remains a geographic candidate table, not a surveillance eligibility
list. The reproducible builder is `scripts/build_county_crosswalk.py`.

Exception tuples partition into 195 Colorado expansion groups outside the
historical analysis scope, 144 parasite groups lacking a 2025 population year,
76 Connecticut groups needing historical-county populations, 27 early California
parasite coverage groups, and seven unresolved blank/unknown/out-of-state groups.
These are counts of geographic tuples, not case counts. No exclusion was applied.

Connecticut DPH publishes historical-county population estimates that offer a
possible way to retain the geographic units used in the cases:
https://portal.ct.gov/dph/resources-and-records/data-research/vital-statistics-and-population-data/population-statistics

Downloaded public sources:
- CTDPH_2022-2025_CountyASRH_w_Methods.7z (DPH link): 2022 county data, 2023/2024
  town data with historical county identifiers, 2025 county data, and a methodology
  PDF specifically describing the 2022 estimates.
- State_CtyCEPR_ASR6H_2020-2024.zip (DPH link): historical-county data for 2020/2021
  at vintage 2021, and planning-region data for later years.

`scripts/extract_ct_county_candidates.py` validates duplicate demographic keys,
nonnegative finite values, the eight historical counties, expected row counts,
and the disjoint ethnicity/race combinations in the 2023+ files. It extracts 48
candidate county/year totals without changing pipeline denominators. Package
SHA-256 checksums accompany the local artifact. The original full census files
were not downloaded or edited; only the user's aggregate audit and public DPH
packages were used.

| Year | DPH candidate county sum | Existing SAS CT sum | Difference |
|---|---:|---:|---:|
| 2020 | 3,600,260 | 3,579,918 | +20,342 |
| 2021 | 3,605,597 | 3,606,607 | -1,010 |
| 2022 | 3,626,205 | 3,617,925 | +8,280 |
| 2023 | 3,617,176 | 3,643,023 | -25,847 |
| 2024 | 3,675,069 | 3,675,069 | 0 |
| 2025 | 3,688,496 | 3,675,069 | +13,427 |

These sources mix vintages; the methodology PDF covers 2022, and later CSV files
must not be assumed to share its vintage. Equal county boundaries do not make
these population series equivalent. Selection of a consistent series and coverage
validation remain required before applying these candidates to county analysis.
In particular, the current bacterial SAS file has the same CT total for 2024 and
2025; that observation does not by itself establish its source or intent.

Internal review artifacts are held locally under `.local/county_review_20260912`
and are not committed as case-geography data to the repository.

## Consistent Connecticut series and coverage evidence

The Vintage 2025 Census town series now provides a validated candidate for all
48 historical Connecticut county/year totals in 2020–2025. Both DPH crosswalks
agree for all 169 towns; Census town identifiers/names/regions match and all six
state totals reconcile exactly. `scripts/reconcile_ct_vintage2025.py` implements
this check, with seven passing tests and a successful run on the public files.
The mixed-vintage candidate above is superseded for future denominator selection,
not applied to existing fits. See [coverage reconciliation](county_coverage_reconciliation.md)
for the updated totals, source links, reproducible command, and unresolved early
Connecticut/California coverage evidence. Real-data county eligibility and R-INLA
model validation remain incomplete.

## Parallel coverage research and INLA build

Public DPH/CDC sources now resolve Fairfield bacterial entry in 1997. California's
broader early parasite catchment is documented, but its full county/date history
remains incomplete; Oregon's July 1997 parasite start adds a partial-year condition.
See [research findings](county_coverage_research.md).

The separate INLA smoke prototype passed actual local executable, analytic offset,
and disconnected/isolated spatial graph checks. The dedicated container builder
and SGE launcher are implemented and tested with stubs, but the SIF itself still
requires a Singularity build/test. See [validation evidence](inla_smoke_validation.md).
All work is isolated on `feature/rinla-county`; no real county fits were run.

## First real-data county pilot preparation

The repaired INLA image passed both synthetic fits through SGE (job 17818089,
`inla_smoke_20260912_204019_204221`, exit 0). Installation and ordinary-user cluster
execution are verified; real-data statistical validation remains separate.

Prepared a Salmonella 2004–2019 historical-catchment audit and
[proposed model specification](county_pilot_specification.md). The public roster
contains 486 counties, checked against an independent Census gazetteer; candidate
adjacency preserves components, isolated counties, and cross-state edges. The
read-only launcher reuses the existing cleaned CSV and bacterial census file and
writes one report archive. It does not fit the draft model. Local synthetic audit
and launcher tests passed. Real-data audit execution and review remain pending.

The real Salmonella pilot audit completed successfully (job 17818284). Local
[archive review](county_pilot_audit_review.md) verified 122,024 reconciled cases,
7,776 complete positive population rows, and 1,210 candidate graph edges. The ten
components include a joined GA–TN component and two NY groups; there are no
isolated counties. No input-audit rerun is indicated. Prior-predictive checks,
real-data fitting, and statistical validation remain next.

## Exploratory county fit implementation

[The fit implementation and prior review](county_pilot_fit.md) now prepare spatial
BYM2 and IID county variants for concurrent execution on the reviewed panel. Both
include state intercepts and state-specific RW1 paths. Prior-predictive checks on
the audited exposures motivated revising the new pilot's intercept SD from 2 to 1;
that decision and remaining prior sensitivity are recorded explicitly. Actual
synthetic fits, joint-draw aggregation/reference checks, input-change rejection,
and launcher/collector tests passed locally. Real-data execution is pending.
The launcher uses the existing repaired image; no container rebuild is required.

Both exploratory county fits completed on HPC. The
[first fit review](county_pilot_fit_review.md) confirms consistent aggregation,
zero CPO computation failures, and lower spatial WAIC, but identifies a tendency
to underproduce zero-case county/years and material county-level sensitivity to
spatial pooling. State-level agreement does not resolve those issues. County
results remain outside the dashboard pending targeted county-history review,
sensitivity analysis, and predictive validation.

### Saved county diagnostic follow-up

The zero-count mismatch from the first county pilot now has a saved-fit diagnostic launcher: `scripts/launch_saved_county_diagnostics.py`. It uses the existing spatial/IID checkpoints and audited panel, produces grouped predictive checks and a paired pointwise comparison, and performs no refits. Local tests and the real-data diagnostic job passed. The [diagnostic review](saved_county_diagnostics_review.md) locates the largest zero-count gaps in small counties and Minnesota, with marked spatial/IID sensitivity in Grant County, Oregon. Targeted county-history review is next; no further fits have been launched. See [saved county diagnostics](saved_county_diagnostics.md). County dashboard integration remains pending statistical review.

A [county-history review job](county_history_review.md) now reconstructs the fitted county counts from the clean source and exports internal target/neighbor histories, category totals and plots. It performs no refits and cannot independently certify reporting completeness. Synthetic validation passed; the real-data history archive is pending.
