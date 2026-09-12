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
| County-level R-INLA spatial/temporal models | No | Input reconnaissance partially complete; geographic reconciliation and surveillance coverage remain unresolved |
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
Cluster execution of this helper is pending. No additional sampling is needed.

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
