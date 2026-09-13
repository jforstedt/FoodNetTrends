# Cryptosporidium observation-window correction

FoodNet ended Cryptosporidium surveillance in 2018, so its last observed year
is 2017. This is distinct from Cyclospora and from the availability of parasite
population denominators. Sources: [CDC timeline](https://www.cdc.gov/foodnet/about/timeline.html)
and [About FoodNet](https://www.cdc.gov/foodnet/).

The state input preparation now caps Cryptosporidium case and surveillance years
at 2017, even when parasite_end_year is later. Earlier user-specified limits still
apply. Cases after that date are reported as exclusions. The existing baseline
availability check rejects a baseline extending beyond the observed window; no
replacement baseline is silently selected. Model formula, priors and sampling
settings are unchanged. Other pathogens retain their existing input behavior.

County audits now use 2004–2017 for Cryptosporidium, producing 6,804 county/year
cells for the 486-county cohort. The other county windows remain 2004–2019.
The validator rejects older Cryptosporidium panels extending past surveillance.
Raw reconciliation applies the same corrected window. The expected end year is
recorded in observation_scope.csv and the multi-pathogen audit summary.

Run `python3 scripts/launch_crypto_correction.py` on Rosalind to create fresh
outputs. It submits preparation/reconciliation, four parallel fits and one
collector. Existing containers are reused. Two full-period county models cover
2004–2017; two retrospective forecast checks train on 2004–2014 and score
2015–2017. This is a different validation period and must not be pooled with the
previous 2017–2019 scores. No model parameters are selected using held-out data.
All original outputs remain in place for provenance.

Preparation also scans the supplied state run directory (default the existing
combined production run) for Cryptosporidium IRCatch, IRSite and EstIRR CSVs.
The report records their hashes, year coverage and post-2017 rows. It reads
result tables, not saved Stan posterior internals. Missing matching files or
unrecognized year fields are explicit review outcomes. Use --state-run PATH
for a different existing run. No state model is rerun automatically: its valid
reference baseline must be selected explicitly before replacement.

The final archive includes corrected audit/reconciliation reports, state CSV
inspection, fit/forecast diagnostics and logs; it excludes RDS checkpoints.
Reports remain internal surveillance material. Completion alone does not certify
statistical fit or repair old dashboards, and no old Cryptosporidium output is
silently relabeled as corrected.

Validation includes cutoff/exclusion tests, unchanged Cyclospora behavior, stale
county-panel rejection, shared state-analysis regressions, and synthetic read-only
state-output inspection with scheduler-script syntax checks.
