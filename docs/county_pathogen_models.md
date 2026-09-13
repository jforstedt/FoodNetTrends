# Parallel county pathogen comparisons

Run `python3 scripts/launch_county_pathogen_models.py` after the nine-pathogen
input audit has passed. It submits eight reconciliation tasks, sixteen fit tasks
held until reconciliation finishes, and one collector held until all fits finish.
There is no concurrency cap or automatic retry. Each fit requests eight slots,
32 GB h_rss/mem_free and 64 GB h_vmem with a twelve-hour limit. The scheduler
controls allocation and memory accounting. Existing Salmonella results are retained.

Each pathogen's fit checks its own reconciliation status and verifies the recorded
raw, clean, mapping-report and panel checksums. An unrelated pathogen's failed
reconciliation does not prevent other fits. Reconciliation uses aliases from the
original preprocessing report and explicitly tests existing county/site exclusions
and Listeria CSTE eligibility. Unknown differences stop that pathogen. Agreement
with exclusion hypotheses does not establish historical preprocessing provenance
or external surveillance completeness.

Both models use county-specific RW1 time trends plus state trends. One has BYM2
county effects; the comparator has IID county effects. Formula, likelihood and
priors match the exploratory Salmonella comparison. This is a candidate transfer,
not an assertion that these priors or models suit every pathogen. Prior predictive
simulations, posterior zero checks, CPO, WAIC and county intervals are collected
separately for review. No forecast validation or automatic dashboard promotion is
performed in this batch. Rare pathogens may require a different specification.

The extension validates the 486-county, 2004–2019 panel and population/case audit,
without requiring Salmonella's case total. Absent aggregate state/year records
are interpreted as zero only when the complete panel's count is exactly zero;
nonzero discrepancies fail. Original pilot validation defaults remain unchanged.

The two existing images are reused: foodnet.sif for reconciliation and
foodnet-inla-fixed.sif for fits. No container build is required. Fit checkpoints
remain on HPC; the final archive contains aggregate diagnostic reports and logs,
not checkpoints or individual records. Reports are internal surveillance material.
A nonzero final status still produces an archive for diagnosing failures.
