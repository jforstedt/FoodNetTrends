# Monthly analysis assumptions and remaining evidence

Status: proposed analysis contract, 2026-09-13. This document does not certify a calendar or enable a fit. It separates a defensible analysis convention from facts that the extract cannot establish.

## Event month

Use specimen collection month (`dtspec`) for the candidate seasonal target, retaining the recorded annual year and the existing case rules. CDC explicitly calculated monthly FoodNet incidence from specimen collection date in its [1998 surveillance report, printed page 190](https://www.cdc.gov/mmwr/PDF/wk/mm4809.pdf). This supports the choice of target; it does not validate the construction or imputation of this particular extract. Public variable definitions also distinguish specimen collection from onset and administrative dates; see [dictionary review](foodnet_dictionary_review.md).

Do not overwrite the separate source `month` field or substitute onset/report dates. Missing specimen dates or specimen-year conflicts remain unassigned and require review. For valid same-year disagreements, retain a comparison under both month definitions. `source_month_comparison.csv` contains state/year/month counts under specimen date and source month, and their signed difference (source minus specimen). It exports neither case identifiers nor exact dates or counties.

The comparison isolates the effect of choosing the month definition, not which original value is factually correct. A source-month alternative with missing/invalid months cannot serve as a complete replacement series. Document the paired count differences before fitting. A small count change does not alone prove negligible effects on forecasts, especially for sparse county cells; inspect affected forecasts or run a paired sensitivity if they drive a conclusion.

## Observation calendar

Proposed exploratory assumption: the audited historical catchment participates throughout January 2004–December 2019 for Salmonella and Campylobacter, subject to documented interruptions and eligibility exceptions. This is an assumption about surveillance operation, not complete detection of community infections or constant testing sensitivity.

Supporting evidence: the [CDC 2004–2011 analysis](https://wwwnc.cdc.gov/eid/article/22/7/15-0833_article) documents a stable catchment from 2004, and the [2019 report](https://www.cdc.gov/mmwr/volumes/69/wr/mm6917a1.htm) describes active surveillance for both pathogens in the same ten site jurisdictions. This establishes program context, not a verified county-month interruption ledger. See [coverage evidence](monthly_coverage_evidence.md) for additional historical sources and limitations.

Before this assumption becomes an executable calendar, record its evidence, interval, county mapping, known exceptions, reviewer and explicit assumption status. Do not relabel it as independently verified coverage. An applicable program/site operational statement or equivalent historical documentation can resolve the remaining continuity question; a separate document for every month is not inherently required. Case presence cannot resolve it. If continuity remains unresolved, retain missing modeled counts and limit work to inventories, descriptive displays and synthetic tests. No site contacts are sent by these scripts.

Known interruptions must exclude affected observations rather than convert absent reports to zero. Partial-month exposure requires actual covered days and compatible ascertainment; a month-level count alone cannot identify covered days. Any future exploratory analysis using an assumed calendar must remain labelled conditional on that assumption and must not be promoted as a coverage-certified result.

## Exposure and validation

For eligible full months, propose constant population within each county-year and person-years equal to annual population multiplied by days in month divided by days in year. This preserves annual exposure and accounts for leap years. It assumes no within-year migration pattern, not equal calendar-month lengths. Do not introduce interpolation from future population estimates into a forecast unknowingly; document the population vintage and whether forecasts are conditional on known exposure.

Apply identical count, exposure, calendar and eligibility rules to seasonal and nonseasonal candidates. Annual reconciliation must pass before fitting. Calendar certification, numerical checks and held-out predictive performance remain separate gates. No change is made to Daniel's accepted annual model, and no claim of improved forecasts follows from preparation alone.
