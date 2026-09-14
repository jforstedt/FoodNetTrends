# Eligible diagnostic-category audit

First next-phase operation: reconcile literal diagnostic categories to the same frozen annual case universe used by the county/monthly comparisons. This is an input audit, not a model fit or incidence adjustment. The raw diagnostic dashboard remains a separate universe.

Nine independent SGE tasks reuse each pathogen's verified panel and clean-input provenance, with Cryptosporidium ending in 2017 and the other established domains ending in 2019. Existing travel, category and county exclusions are retained. Cleaned Listeria must satisfy the existing CSTE=YES rule. Every selected county-year count must match its audited panel exactly before any category output is declared complete.

Outputs per pathogen: literal CX+/CIDT+/PARASITIC state-year counts, reconciled eligible totals/populations, disjoint selection flow, and descriptive support for a possible classification model. The CX+ plus CIDT+ denominator counts eligible records in those classifications, not people tested. CIDT-classification share remains missing when that denominator is zero. PARASITIC counts remain separate and are never forced into a bacterial contrast. CX+ is not labelled culture-only.

All results are marked review-required and coverage-uncertified. Finite population or reconciled counts do not establish complete surveillance. No missing month is certified, no case is deduplicated, and no fields are recoded. The audit does not need to read specimen dates or revisit the resolved Shigella month decision because its target is annual category accounting.

After review, a separate conditional category-association model could describe classification probabilities by site and time. Before that fit, freeze the target, priors, eligible periods and evaluation scheme. These existing years are development data, not an untouched final test. Category shares cannot be used as observed future covariates for predicting the same future case totals. Stronger ascertainment-adjusted incidence still needs definitions and independent testing information.

## Execution

```bash
git pull --ff-only personal feature/rinla-next-phase && module load singularity && python3 scripts/launch_eligible_diagnostics.py
```

Nine audits run concurrently, two cores each, with no concurrency cap; a held collector verifies domains and output hashes and produces one archive, including partial failures. No container build or model rerun occurs. After array and collector IDs appear the terminal may disconnect. Existing source/input fingerprints are rechecked before and after execution. Private aggregate outputs stay off Git.

Later-period eligibility is a different workstream: the local inventory establishes that existing years are already used, while later years require geographic/exposure reconciliation and outcome-access review. This audit does not create or reveal a new purported holdout.
