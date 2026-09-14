# Diagnostic-method workstream: bounded next steps

Reviewed 14 September 2026. This is a readiness assessment and specification,
not a fitted adjustment or approval of new forecasts. Existing state, county and
monthly results remain unchanged. Supporting case-derived summaries stay in local
review output; this document contains no private counts or laboratory identifiers.

## What is ready now

The completed extension and definition audits already contain raw category counts,
pathogen/state/year test-code tables, same-record category/result crosswalks and
laboratory-name completeness summaries. Reuse those archives; do not repeat the
broad cluster audit to obtain the same information.

The existing `cxcidt` field supports descriptive classification trends. The more
detailed `culturestatus` field distinguishes source labels that the three-category
field combines. The archived crosswalk is internally consistent with that
combination, but consistency does not establish its upstream derivation or the
clinical meaning of every code. In particular, culture-classified cases cannot be
assumed never to have received CIDT testing.

Proceed concurrently with these internal descriptive products:

1. Tabulate literal category shares among recorded cases by pathogen/state/year,
   separately for raw and eligible modeling universes. Existing raw tables are
   ready; an eligible version must use the same case and coverage contract as the
   model and reconcile exactly to its eligible totals.
2. Display clinical versus public-health field completeness and literal result
   distributions over time. Keep blank, missing, unknown and not-tested separate.
   Do not turn missing historical fields into negative results or no testing.
3. Display `cxcidt` versus `culturestatus` crosswalks and flag disagreements if a
   later extract changes the observed mapping. Describe these as source labels,
   not a newly validated positive/negative recode.
4. Review clinical PCR/culture/antigen recording together, retaining
   pathogen-dependent toxin/organism codes. A field-wide universal binary recode
   is not supported by the available public schemas.

Suitable visuals are category-share trajectories and recording-completeness
heatmaps. Their denominators are recorded cases with explicit missingness groups,
not all tested people. Raw audit views must say that eligibility filtering has not
been applied. Do not publish private aggregate tables in the repository or public
dashboard as a side effect of this review.

## A useful association experiment, after a narrow contract check

A conditional classification model can ask: **among eligible recorded infections,
how does the probability of the existing CIDT+ classification vary by site and
time?** It cannot ask how much true infection incidence changed because of testing.

For bacterial records with exactly one applicable category, a binomial category
count model conditional on the observed CX+ plus CIDT+ total is a possible first
specification. Retain PARASITIC separately; do not force it into a bacterial test
contrast. The target is the recorded classification, so CX+ is not renamed
"culture-only." Sparse or unavailable site/time categories must remain visible.

Before fitting, freeze eligibility, the category definition, its denominator,
training-only transformations, and a prespecified validation scheme. Reconcile
category counts to the accepted eligible case panel and document any upstream
classification-definition changes. Do not use held-out observed diagnostic shares
as covariates for forecasting the same held-out case counts: these are partly
constructed from the outcome and would leak future information. If classification
shares are forecast, that is its own target and requires its own evaluation.

This association experiment is **specified, not implemented or submitted** by this
review. It can proceed independently of temporal forecast selection once those
narrow inputs are checked. It is not required to finish the first exploratory
county/monthly release.

## What still blocks a stronger testing adjustment

- The extract-specific derivations and conflict precedence for `cxcidt` and
  `culturestatus` are unverified. Public variable lists define several supporting
  fields but do not certify the transformation generating this extract.
- Testing volume, adoption histories and sensitivities are not established by
  positive case records. Population exposure is an incidence denominator, not a
  number-tested denominator. An informative external ascertainment model could
  sometimes replace a testing-volume input, but it would need explicit evidence
  and sensitivity analysis; these inputs are currently absent.
- Laboratory names have only case/whitespace normalization, not a validated stable
  identity crosswalk. First populated test dates are not adoption dates.
- Repeated identifier-like fields do not establish specimen/person linkage. No
  automated deduplication or dual-testing denominator is justified by this audit.
- Test-field availability and pathogen-specific vocabularies vary historically;
  complete ascertainment cannot be inferred from a field becoming populated.

Therefore no testing-adjusted true-incidence forecast, causal correction, or
laboratory-specific adoption effect is ready for promotion. This blocks those
specific claims, not the descriptive outputs above or the separate monthly model
workstream.

## Evidence and checks

Definitions and source links are recorded in [the public dictionary review](foodnet_dictionary_review.md).
Audit semantics are recorded in [diagnostic audit readiness](extension_diagnostics_readiness.md).
The local review verified all eight definition-task output hashes and derived
literal-code and field-completeness summaries directly from the saved crosswalk
and code tables, without fitting, changing inputs, or exporting identifiers.

## Implemented descriptive interface

The optional diagnostic section of [the offline monthly review](monthly_review_dashboard.md) now presents the saved raw classification trends, supporting-field recording summaries, literal codes and cxcidt/culturestatus crosswalks. It uses independently controlled raw-universe filters and a hash-bound definition archive. Denominator and crosswalk reconciliation are checked before rendering. This completes the initial raw descriptive interface; eligible case-category aggregation and any classification association fit remain separate work.
