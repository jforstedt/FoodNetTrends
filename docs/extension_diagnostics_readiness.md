# Diagnostic-method extension: data readiness

This is a feasibility investigation, not a model change. No testing correction or diagnostic interaction has been fitted or approved by this audit.

## What the repository establishes

`bin/trendy.R` selects cases using the existing `cxcidt` classification. Production options include `CX+`, `CIDT+`, and `PARASITIC`. `scripts/reconcile_raw_county.R` confirms raw and clean grouping fields `pathogen`, `year`, `state`, and `siteid`. `bin/preprocess.R` preserves source fields while applying site rules and pathogen standardization. Raw and cleaned pathogen labels therefore cannot be assumed identical.

These fields permit an inventory of case classification across sites and years. They do not by themselves establish all tests performed on a specimen, laboratory adoption dates, numbers tested, sensitivity, or changes in ascertainment. The presence of both CX+ and CIDT+ classifications within a site/year is category co-occurrence, not evidence that the same cases received both tests. A first CIDT-positive record is not a validated adoption date. Census population provides an incidence denominator, not a testing denominator.

## Cluster audit

The pure base-R function `audit_extension_diagnostics(raw, clean=NULL)` accepts lowercased, unique field names and returns named data frames. It does not modify inputs, filter surveillance eligibility, fit a model, or export case identifiers.

| Table | Contents |
| --- | --- |
| `fields` | Presence and classes of confirmed fields, SAS variable/value labels, and name-based diagnostic/identifier candidates explicitly marked unverified. |
| `categories` | Exact `cxcidt` categories by source, pathogen, year, state, and site; NA and blanks are separate. |
| `missingness` | Record totals, NA, blank, and explicit UNKNOWN/UNK counts for those groups. |
| `overlap` | Exact production-category counts and within-group CX+/CIDT+ co-occurrence. |
| `identifier_candidates` | Candidate case/record ID completeness and duplication counts only; no values and no linkage. |
| `readiness` | Fixed interpretation limits and remaining evidence needs. |

Raw source categories, including numeric SAS codes, are not silently decoded. SAS label metadata is exported so mapping can be reviewed. Clean input may contain only the five confirmed grouping/classification columns; absence of an ID in that restricted clean input is not evidence that the complete cleaned file lacks an ID. Optional name-based candidates are discovery leads, not approved field mappings. Summaries retain all provided rows and must not be interpreted as eligible incidence counts. Missing site fields remain visibly absent rather than being replaced with state.

The output is internal review material. Site/pathogen/year counts belong in the aggregate audit archive, not in source control or a public dashboard. No local inspection of the underlying cluster SAS data is claimed by this document.

## What the result can decide

If classification coverage and overlap are adequate, we can assess the feasibility of an association model with diagnostic-category effects varying over time and geography. Category-specific counts must still use applicable pathogen surveillance windows and compatible population coverage. Such an association would not automatically identify changes in true incidence caused by changing diagnostic practices.

Additional evidence needed for stronger ascertainment adjustment includes a data dictionary defining `cxcidt` and any discovered testing fields; laboratory/site adoption histories; testing volume or testing-eligible population information; and, if dual-testing analyses are intended, verified specimen/case linkage plus separate performed-test results. These needs remain unresolved unless the audit or an external source explicitly supplies them.

## Local checks

`Rscript tests/test_extension_diagnostics.R` checks totals, absent fields, empty input, raw/clean separation, numeric labelled-category preservation, unknown/blank/NA separation, category co-occurrence, ID duplication summaries, and absence of identifier values in output. It performs no fitting or cluster submission.
