# County denominator and coverage reconciliation — 12 September 2026

Follow-up: [primary-source research](county_coverage_research.md) resolves Fairfield's
1997 bacterial entry and identifies an additional Oregon partial-year parasite
issue. The table below preserves the questions as they stood before that research.

This review prepares the county/R-INLA extension. It does not change Daniel's
state-level model, existing denominators, fitted results, or dashboard.

## Connecticut: a consistent candidate population series

The [Census Vintage 2025 town series](https://www.census.gov/data/datasets/time-series/demo/popest/2020s-total-cities-and-towns.html)
provides estimates for every year from 2020 through 2025. Its
[file layout](https://www2.census.gov/programs-surveys/popest/technical-documentation/file-layouts/2020-2025/SUB-EST2025.pdf)
defines summary level 061 as minor civil divisions and uses January 1, 2025 geography.
The [Connecticut DPH population page](https://portal.ct.gov/dph/resources-and-records/data-research/vital-statistics-and-population-data/population-statistics)
links a historical-county package whose 2023 and 2024 town files contain both
historical county and current planning-region identifiers.

The reproducible checker, `scripts/reconcile_ct_vintage2025.py`, confirmed on the
public files:

- Exactly 169 unique town mappings, identical in both DPH files.
- Town codes, names, and planning-region codes agree with Census Vintage 2025;
  historical and current town codes also agree.
- Exactly eight historical counties and 48 positive county/year populations.
- County sums equal the independently provided Census state total in all six years.

It aggregates the Census town totals; it does not use DPH demographic allocations
or interpolate populations between geographic units. The earlier mixed-vintage
DPH candidate table is retained for provenance but is superseded as the preferred
2020–2025 population candidate. This does not reconcile vintages before 2020 or
establish surveillance eligibility.

| Year | Vintage 2025 candidate CT total | Existing SAS CT total | Difference |
|---|---:|---:|---:|
| 2020 | 3,579,643 | 3,579,918 | -275 |
| 2021 | 3,607,765 | 3,606,607 | +1,158 |
| 2022 | 3,618,707 | 3,617,925 | +782 |
| 2023 | 3,641,369 | 3,643,023 | -1,654 |
| 2024 | 3,674,449 | 3,675,069 | -620 |
| 2025 | 3,688,496 | 3,675,069 | +13,427 |

Existing totals come from the user's aggregate census audit, not a new download of
restricted SAS inputs. All candidate rows retain `approved_for_use=FALSE` and
`coverage_verified=FALSE`. Adoption would change county-model denominators and
must be recorded explicitly, rather than presented as a model-equivalent repair.

### Reproduction

Download `sub-est2025_9.csv` from the linked Census page. Extract
`CTDPH_2023_CountyASRH.csv` and `CTDPH_2024_CountyASRH.csv` from the DPH historical
county package. Run this single line with the actual input paths and a new output directory:

```bash
python3 scripts/reconcile_ct_vintage2025.py sub-est2025_9.csv CTDPH_2023_CountyASRH.csv CTDPH_2024_CountyASRH.csv ct_vintage2025_review
```

Outputs include 48 population candidates, the 169-town crosswalk, and source SHA-256
hashes. Validation occurs before creating the output directory. Seven local tests
exercise missing/duplicate towns, changed or conflicting mappings, misnamed towns,
invalid populations, state-total disagreement, and candidate-only status. The
actual downloaded public files also passed the checker.

## Coverage evidence and unresolved decisions

Population availability and FIPS agreement do not establish surveillance coverage.
No county/year zero-case grid has been generated.

| Scope | Evidence | Treatment pending resolution |
|---|---|---|
| CT early bacterial years, especially Fairfield 1997 | The supplied inventory includes Fairfield in 1997. The 2009 FoodNet report's Table 1 lists Hartford/New Haven initially and the rest of CT in 1998. The contemporary 1997 MMWR describes three CT bacterial counties, even when describing 1996. | Preserve the conflict. Obtain the county/date coverage record used for this extract; do not move Fairfield's start year automatically. |
| CA parasites, 1997 | The 1997 annual report says that before June 1 the catchment comprised Alameda, Contra Costa, and San Francisco. The contemporary MMWR describes eight counties for parasite surveillance. | A full-year county population alone cannot resolve this partial-year expansion. Confirm the additional counties and case inclusion/exposure convention. |
| CA parasite exception tuples, 1997–2003 | The case audit contains Marin, San Mateo, Santa Clara, Solano, and Sonoma groups without matching population rows. The 1997 reports establish broader parasite coverage, but do not by themselves verify every county/year through 2003. | Keep these as historical coverage/denominator exceptions, not invalid FIPS. Obtain the subsequent county/date coverage history. |
| CT 2020 onward | Both historical counties and planning-region rows appear in the supplied population inventory. Historical-county populations can now be constructed consistently from town totals. | Use one geographic system in a future county input; never sum both systems. Candidate adoption remains explicit. |
| Colorado expansion and parasite 2025 | Audit exceptions include records outside historical Colorado scope and parasite records beyond the available population series. | Apply only the documented analysis scope; absence of a denominator is not proof that surveillance stopped. |

Primary coverage sources:

- [FoodNet 2009 report, Table 1](https://stacks.cdc.gov/view/cdc/152214/cdc_152214_DS1.pdf)
- [FoodNet 1997 final report, initial catchment population table and footnote](https://stacks.cdc.gov/view/cdc/152204/cdc_152204_DS1.pdf)
- [1997 surveillance MMWR](https://www.cdc.gov/mmwr/preview/mmwrhtml/00054940.htm)

This is an evidence review, not a completed county-by-year eligibility ledger.
The remaining missing input is the California parasite county/pathogen coverage
history, including start/end dates, plus partial-year case/exposure conventions
for California and Oregon. Connecticut's geographic entry sequence is now resolved
in the linked follow-up; pathogen-specific start dates remain separate.
Do not infer that history from case presence, census EntryYear, or a missing row.

## R-INLA status

The denominator candidate is ready for review; real-data county modeling remains
blocked by coverage validation and explicit denominator selection. Synthetic INLA
installation/model checks can proceed independently. No INLA fit or model
comparison has been performed by this reconciliation script.

Local artifacts: `.local/county_review_20260912/connecticut_v2025/`. They include
the candidate populations, town crosswalk, provenance, and a comparison with the
existing SAS state sums. Public downloads and internal audit artifacts are not
committed into the source repository.
