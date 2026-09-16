# Historical county crowding: acquired public ACS data

Verified 2026-09-15. No models fitted, active experiment bundle changed, or case records used. The public county estimates are available locally for a later pathogen-specific experiment; this is an acquisition and arithmetic audit, not evidence of predictive improvement.

## What was acquired

Downloaded the Census ACS five-year B25014 **Tenure by Occupants per Room** sequences, paired margins of error (MOEs), geography files and official sequence templates. All three releases cover the frozen 486-county roster. No API key or credentials were needed for these bulk downloads.

| ACS vintage | Survey period | Public release date | Matched December-end origin | County rows | Estimate cells | MOE cells |
|---|---|---|---|---:|---:|---:|
| 2010 | 2006–2010 | 2011-12-08 | 2011 | 486 | 6,318 | 6,318 |
| 2012 | 2008–2012 | 2013-12-17 | 2013 | 486 | 6,318 | 6,318 |
| 2015 | 2011–2015 | 2016-12-08 | 2016 | 486 | 6,318 | 6,318 |

Release dates are confirmed by the Census [2010 release notice](https://www.census.gov/programs-surveys/acs/news/data-releases/2010/release.html), [2012 release notice](https://www.census.gov/programs-surveys/acs/news/data-releases/2012/release.html), and [2015 release notice](https://www.census.gov/programs-surveys/acs/news/data-releases/2015/release.html).

The 60 sequence/geography downloads total 186,359,996 bytes. The resulting 1,458-row county extract is 296,131 bytes. Large geography files contain other public geographies; extraction uses county summary level `050`, component `00`, and exact state-plus-county FIPS, then restricts to our roster. Geography identifiers and all joins retain leading zeroes.

## Exact public endpoints

Base URL: `https://www2.census.gov/programs-surveys/acs/summary_file/{year}/data/5_year_seq_by_state/{StateName}/All_Geographies_Not_Tracts_Block_Groups/`.

| Vintage | Sequence | Example estimate/MOE archive | Corresponding geography |
|---|---:|---|---|
| 2010 | 95 | [20105ca0095000.zip](https://www2.census.gov/programs-surveys/acs/summary_file/2010/data/5_year_seq_by_state/California/All_Geographies_Not_Tracts_Block_Groups/20105ca0095000.zip) | [g20105ca.csv](https://www2.census.gov/programs-surveys/acs/summary_file/2010/data/5_year_seq_by_state/California/All_Geographies_Not_Tracts_Block_Groups/g20105ca.csv) |
| 2012 | 102 | [20125ca0102000.zip](https://www2.census.gov/programs-surveys/acs/summary_file/2012/data/5_year_seq_by_state/California/All_Geographies_Not_Tracts_Block_Groups/20125ca0102000.zip) | [g20125ca.csv](https://www2.census.gov/programs-surveys/acs/summary_file/2012/data/5_year_seq_by_state/California/All_Geographies_Not_Tracts_Block_Groups/g20125ca.csv) |
| 2015 | 103 | [20155ca0103000.zip](https://www2.census.gov/programs-surveys/acs/summary_file/2015/data/5_year_seq_by_state/California/All_Geographies_Not_Tracts_Block_Groups/20155ca0103000.zip) | [g20155ca.csv](https://www2.census.gov/programs-surveys/acs/summary_file/2015/data/5_year_seq_by_state/California/All_Geographies_Not_Tracts_Block_Groups/g20155ca.csv) |

All ten state directories were actually downloaded: California, Colorado, Connecticut, Georgia, Maryland, Minnesota, NewMexico, NewYork, Oregon, Tennessee. Every exact URL, download SHA256, byte count, retrieval timestamp and server Last-Modified header is recorded in the local `receipts.json`.

Official templates used to discover the sequence and 13 exact `B25014_###` columns:

- [2010 templates](https://www2.census.gov/programs-surveys/acs/summary_file/2010/data/2010_5yr_SummaryFileTemplates.zip)
- [2012 templates](https://www2.census.gov/programs-surveys/acs/summary_file/2012/data/2012_5yr_Summary_FileTemplates.zip)
- [2015 templates](https://www2.census.gov/programs-surveys/acs/summary_file/2015/data/2015_5yr_Summary_FileTemplates.zip)

Template matching deliberately excludes similarly named race-specific `B25014A`–`B25014I` tables. Each archive's `e` member contains estimates and its `m` member contains MOEs. Files were parsed as CSV with Latin-1-compatible decoding; public numeric values were checked after extraction.

## Meaning and validation

The extract retains all 13 estimate/MOE pairs. It also derives occupied housing units, crowded housing units, and crowded share. Crowded means **more than one occupant per room**, combining owner and renter cells 005, 006, 007, 011, 012 and 013; the denominator is occupied housing units (001). It is a housing-unit proportion, not the proportion of people experiencing crowding.

For every vintage: exactly 486 counties; unique county/estimate-kind keys; all 6,318 estimates and 6,318 MOEs finite and nonnegative; denominator positive; owner plus renter totals equal overall total; the five occupancy categories sum to each tenure total; crowded count lies between zero and total. All checks pass. This tests extraction consistency, not survey certainty or causal validity.

MOEs are retained rather than discarded or misrepresented as point-estimate precision. A sum/proportion MOE requires the applicable ACS derived-estimate procedure and covariance assumptions; this acquisition does not manufacture a confidence interval by adding MOEs. The [ACS summary-file technical documentation](https://www2.census.gov/acs2010_5yr/summaryfile/ACS_2006-2010_SF_Tech_Doc.pdf) describes estimate/MOE files. Review sampling uncertainty before fitting small-area effects.

## Forecast-vintage rules and next use

These releases were public by the **end** of the three origin years, but not before their December release dates. They must not be treated as available throughout 2011, 2013 or 2016. They are five-year period estimates, not yearly/monthly measurements, so do not interpolate them into a purported observed annual exposure history.

Present-day historical downloads are **not certified byte-for-byte snapshots of what was originally downloadable**: server Last-Modified dates can be later than release (including 2015 dates for older files), and no revision-history reconciliation was performed. Label a future comparison “historical release-year matched, current archived bytes,” unless corrections and archived vintages are separately audited. The already acquired 2019 vintage must not be used for these earlier origins.

A defensible first test is one prespecified crowding share as a fixed county context covariate, selecting the release available at the forecast origin and freezing it through the future horizon. Using that origin-available snapshot for earlier training outcomes is an explicitly static-context approximation, not reconstruction of historical crowding or a causal effect. Standardization and any collinearity screening use training data only. An eventual rolling-month forecast must select by actual release date.

Biological priority remains Shigella's person-to-person transmission context; county crowding does not directly measure contacts, childcare exposure, homelessness, sexual networks, or foodborne exposure. It is a candidate susceptibility/contact-context proxy for testing alongside existing temporal effects, not a universal replacement for weather or a reason to alter current pathogen models.

## Local evidence

Ignored local directory: `output/historical_crowding_20260915_LOCAL/`.

- `receipts.json`: all 60 public bulk source receipts.
- `table_mapping.json`: exact template column mappings and labels.
- `county_crowding_estimates.csv`: 1,458 county-vintage rows, 13 estimate/MOE pairs and derived share.
- `coverage_checks.json`: per-vintage coverage and arithmetic results.
- `manifest.json`: roster hash, derived artifact hashes, release dates and limitations.
- `acquire.py`, `verify.py`: reproducible local acquisition and extraction/audit scripts; no pipeline integration.

The source archives/geographies, templates and directory indexes remain local. No private count records or active experiment artifacts were read or changed.
