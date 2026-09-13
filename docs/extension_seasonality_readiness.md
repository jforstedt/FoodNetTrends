# Seasonality and finer-time readiness

The current state analysis operates on `year`, `state` and `pathogen`. The repository's example MMWR schema contains those columns plus diagnostic, travel, serotype and geographic fields, but no event-date field. Searches of the preprocessing and model code did not establish an onset, specimen, diagnosis or reporting date contract. This establishes a gap in local evidence, not the absence of dates from the cluster SAS file.

`audit_extension_seasonality(raw, census_b=NULL, census_p=NULL)` inspects the raw cluster data without fitting models. It returns named aggregate data frames suitable for CSV export:

- `field_inventory`: field name, class, SAS format, label, nonmissing count and candidate-date flag. Candidates are discovered from names, labels, date classes and explicit SAS metadata; they are not automatically accepted epidemiologic event dates.
- `date_completeness`: missing, parsed and unparsed records by candidate, pathogen, site and recorded year, including agreement between parsed year and recorded year.
- `date_agreement`: paired available dates agreeing on calendar day or month. Different legitimate date meanings can disagree; disagreement is not automatically an error.
- `monthly_observed_records`: positive observed record counts by candidate date and month, with recorded year retained. Each date remains separate. These are not incidence estimates or an eligible deduplicated case series.
- `record_year_coverage`: observed record counts by pathogen, site and recorded year.
- `population_bacterial` and `population_parasitic`: annual population row inventories and invalid-value counts by state/year.
- `limitations`: explicit interpretive restrictions.

Dates are parsed only when an R Date/POSIX class, explicit SAS date/datetime format, or an unambiguous ISO calendar-date string supports the interpretation. Numeric fields with unknown units and ambiguous strings remain unparsed. No earliest or most complete date is silently chosen. POSIX dates are inventoried in UTC; local-day interpretation must be established before daily analyses. The site grouping uses `siteid`, then `state`, then `site` according to availability; its label must be interpreted against the source dictionary.

Before monthly modeling, we still need a data dictionary specifying the event-date definitions and historical changes, pathogen/site/month surveillance availability, partial-year coverage, and a justified population-exposure convention. Annual population coverage does not prove continuous monthly surveillance. Months without observed records are deliberately not filled with zeros. Reporting-lag or nowcasting models additionally need validated event/report-date pairs and an extraction or revision history; a single file does not establish historical reporting completeness.

These audits can identify whether seasonal curves are feasible and which records would need review. They do not establish a seasonal effect, choose a forecast model, or change Daniel's annual analysis. Any usable date should first be reconciled to annual eligible totals under the existing pathogen rules.

Local tests cover SAS day and datetime formats, R POSIX dates, valid/invalid ISO strings, ambiguous strings, unknown numeric units, missing dates, pair agreement, and the absence of invented monthly zeros. No raw rows, case identifiers or model objects are exported by this module.
