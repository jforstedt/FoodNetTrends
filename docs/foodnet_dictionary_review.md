# Public FoodNet dictionary review

Reviewed 13 September 2026. This is a public-schema interpretation, not certification
of the transformations used to create `mmwr9625.sas7bdat`. No model or running job
was changed. The raw field inventory was reviewed locally; private values and
counts are not reproduced here.

## Sources and matched fields

The [2024 site-transmitted variable list](https://www.reginfo.gov/public/do/DownloadDocument?objectID=147566101)
defines the following fields. Field names are matched case-insensitively to the
extract inventory; definitions are paraphrased.

| Extract field | Public meaning | Implication for our review |
|---|---|---|
| `dtspec` | Specimen collection date | Candidate seasonal event date |
| `dtonset` | Symptoms began | A different seasonal target; listed from 2009 |
| `dtrcvd` | Laboratory received specimen for initial testing | Not public-health notification time |
| `dtentered` | Entry into site database | Administrative timing |
| `dtrptcomp` | Case-report form completion | Not necessarily final data availability |
| `labname` | Submitting laboratory name | Does not establish a stable identifier |
| `patid` | Infection identifier, varies by state | Do not assume a universal person key |
| `localid` | Medical record identifier | Do not assume one infection per value |

The [2016 list](https://www.reginfo.gov/public/do/DownloadDocument?objectID=82265601)
also distinguishes these five date meanings and lists onset from 2009, while the
other four dates are listed from 1996. Its PCR result vocabulary includes
pathogen-dependent categories. A field's availability year does not establish
complete ascertainment at every site or unchanged historical coding.

The [2020 list](https://www.reginfo.gov/public/do/DownloadDocument?objectID=135159201)
identifies `bioid` as culture identification, with Yes/No/Unknown/Not Tested
responses; its older name was `StecBioId`. It identifies `cultclinic` as clinical
laboratory culture results, with availability from 2011 for Campylobacter and
2018 for other pathogens. Antigen fields were previously named `EiaClinic` and
`EiaSphl`. These documented history differences require review before pooling
testing categories across years. The 2024 list also documents clinical and
public-health PCR and antigen fields and assay-name fields; permissible results
depend on pathogen. We have not constructed a universal positive/negative recode.

These documents are version-labelled schemas. Their publication years, historical
availability notes and the actual export generation date are distinct. They do
not prove that this extract uses every listed definition without modification.
The public PDF text was accessible; screenshot retrieval failed, so this review
avoids assigning ambiguous wrapped legal-value rows to individual pathogens.

## Decisions we can make now

1. Keep the running raw audit's date comparisons separate by event meaning.
   Negative or long intervals are review flags, not automatic exclusions.
2. Treat specimen-date seasonality as a candidate. Do not silently fill missing
   onset with specimen or administrative dates: that would change the target over
   time as completeness changes.
3. Compare the upcoming code crosswalk with the public definitions before deciding
   any recode. Preserve Unknown, Not Tested and missing as distinct review groups.
   Same-record overlap is not validated linkage between specimens.
4. Review testing completeness within pathogen/site/year. Do not interpret a
   newly populated field as a laboratory's adoption date, or an earlier empty
   field as absence of that testing method.
5. Retain existing case eligibility and classification. The repository consumes
   `cxcidt`; this review does not establish its upstream derivation.

## Remaining questions, narrowed

- **Extract derivations:** `cxcidt` and `culturestatus` were not found by exact-name
  searches in the reviewed 2024 site-transmitted list. Their generation rules,
  conflict precedence and historical recoding remain unverified. Absence from
  this list does not prove that they are undocumented elsewhere.
- **Other identifiers:** We have not established relationships among `personid`,
  `resultid`, `specid`, `slabsid` and `narms_genrecid`. No automated deduplication
  follows from completeness or repeated values.
- **Dates:** Does the extract replace incomplete dates, and how is `month` derived?
  The running audit can flag patterns but cannot prove imputation rules.
- **Observation:** Confirm pathogen/site/month surveillance intervals before
  creating a zero-filled monthly panel. Annual population and case presence alone
  do not establish a monthly observation calendar.
- **Testing intensity:** Case-associated negative test results are not a count of
  everyone tested. Total-testing denominators remain a separate input if that
  adjustment is pursued.

No immediate contact or new cluster run is required. On receipt of the running
batch, review its definition tables against this document, reconcile any proposed
monthly grouping back to eligible annual totals, and retain unresolved dimensions
as explicit limitations. Escalate only contradictions that prevent a specific
analysis, rather than requiring a complete new dictionary before all work proceeds.
