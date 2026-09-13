# Multi-pathogen county input audit

Run `python3 scripts/launch_county_pathogen_audit.py` on Rosalind with the
Singularity module loaded. It uses the existing `foodnet.sif`, submits one
four-slot input audit, and prints one report archive path. No container build,
model fitting, state-pipeline execution, or dashboard replacement occurs.

The next extension covers nine **combined** pathogens over 2004–2019. The fixed
historical pilot footprint is a candidate checked independently for every
pathogen. This does not extend the map to post-2019 Connecticut boundaries or
Colorado's later expansion. It does not assert that a positive census population
alone proves county surveillance completeness.

Cryptosporidium and Cyclospora use the parasite census; the remaining pathogens
use the bacterial census, matching `bin/functions.R` and `bin/input_validation.R`.
The selected period is within the existing parasite end-year limit. All cases use
the current combined travel and CIDT categories and county exclusions. Listeria
requires the cleaned CSTE field to exist and equal YES for every in-period record;
missing or ineligible values trigger review rather than silent refiltering.

The shared classification code produces subtype inventories using its existing
source priority and rules. Combined counts are not modified by these inventories.
Subtype eligibility is not certified, and subtype models are not launched.

For each pathogen the audit checks direct county FIPS/name/state agreement,
unique positive county/year populations, census entry years, full grid coverage,
case-total reconciliation, and graph components. A failure in one pathogen does
not prevent reports for the others. Exact zero-filled panels remain on the
cluster and are excluded from the archive. Reports contain internal aggregate
surveillance information and should be handled accordingly.

`summary.csv` distinguishes input status, rule/classification issues, pending raw
reconciliation and absent model validation. INPUT_AUDIT_PASS is not permission
to declare the model validated. Review the archive, resolve mismatches, and check
raw-to-clean reconciliation before fitting new pathogens. The planned model
comparison is the combined spatial/county-time candidate and its IID comparator,
with independent parallel jobs and per-pathogen predictive checks. No automatic
promotion to the county dashboard is implemented by this audit.

The original Salmonella audit retains its default behavior and four-argument CLI;
its reusable function now also accepts an explicit pathogen name.
