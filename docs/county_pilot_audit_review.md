# Review of the completed Salmonella pilot input audit

Reviewed archive: `county_pilot_audit_20260912_205807_702050.tar.gz`.
SHA256: `45a6bb743cff377841d5e60c83b16140f88e4d059303055c7f3fc8550c8c00fc`.
The job reported INPUT_AUDIT_PASS and process exit 0. Independent local checks
of the archived tables support that input-audit result.

## Verified from the archive

- All 122,024 selected Salmonella records in 2004–2019 reconcile to direct county
  matches. None was excluded by the selected travel/diagnosis/county filters.
- All 160 state/year reconciliation rows have equal selected and directly matched
  counts. No geographic exception tuples are reported.
- There are exactly 7,776 unique county/year population keys (486 counties × 16
  years). Every population is positive and has audit status `ok`. The population
  range is 636–1,668,412; no population row is duplicated or missing in the panel.
- The graph contains 486 nodes and 1,210 distinct undirected edges, with no self
  edges, unknown nodes, or isolated counties. Independently recomputed node degrees
  match the archived graph report.
- The R audit/matching script snapshots match the reviewed repository sources.
  The geographic inputs and provenance also match, allowing for CSV line endings.
- Diagnosis inventory contains CX+ and CIDT+ only for this Salmonella window.
  Travel NO, UNKNOWN, and YES are retained. This is an all-travel pilot with no
  diagnostic-method adjustment, not a domestically acquired or CIDT-counterfactual
  analysis.

## Spatial components matter

Independent traversal of the graph found these components:

| Component footprint | Counties |
|---|---:|
| California | 3 |
| Colorado | 7 |
| Connecticut | 8 |
| Georgia and Tennessee together | 254 |
| Maryland | 24 |
| Minnesota | 87 |
| New Mexico | 33 |
| New York, first group | 17 |
| New York, second group | 17 |
| Oregon | 36 |

Thus ten components does not mean ten independent state graphs. A future BYM2 fit
must use the actual adjacency and component-specific constraints/scaling, retaining
GA–TN cross-state edges and the disconnected NY groups. State temporal effects are
a separate part of the proposed model and must not replace graph components.

## Decision and limits

No input-audit defect requiring a rerun was found. These inputs can advance to
prior-predictive checks and implementation of the explicitly exploratory pilot
model described in [the specification](county_pilot_specification.md).

This review validates consistency of the archived audit tables and their source
code, not the underlying surveillance data independently. The archive deliberately
omits the exact county count panel; its contents must be revalidated on HPC when
loaded for fitting. The audit relies on the existing cleaned data, supplied
population series, documented historical footprint, and fixed candidate Census
adjacency. It does not independently prove every boundary is unchanged throughout
2004–2019, verify source population vintage choices, or establish statistical
model adequacy. No real-data INLA model has yet been fitted or approved for the
dashboard.
