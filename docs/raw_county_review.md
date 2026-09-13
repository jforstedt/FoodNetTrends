# Raw-to-clean county reconciliation

Run on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_raw_county_review.py
```

One four-slot job reads the original MMWR SAS, existing clean CSV, original preprocessing pathogen mapping and audited panel. It performs no preprocessing or fitting, writes a separate report directory, and prints one archive path. Source inputs are mounted read-only. Missing required inputs or changed clean-data checksums stop the job.

The review uses exactly the raw pathogen aliases recorded as Salmonella in the original preprocessing report, within 2004–2019. It also inventories all raw pathogen labels in that period so labels missing from the historical mapping remain visible; it does not invent new fuzzy matches. Unmapped raw labels are not silently included in the Salmonella comparison.

Reports include raw-versus-clean counts by state, FIPS, year, travel, diagnosis and site; a second comparison after hypothesized default removal rules; state/year removal categories and geographic validity; and the 15 flagged counties' raw geographic label histories. Hypotheses are `UNKNOWN` county, `OUT OF STATE` county and `COEX` before 2023. They are disjoint, in that priority order. County labels are exported separately because legitimate spelling corrections can change labels while leaving FIPS unchanged.

The collector searches the source project's execution traces for PREPROCESS tasks and copies small surviving command/output/error/exit files and staged data rules. It records whether collected files are symlinks, their resolved paths and current hashes: staged symlinks may now reference changed files. Current repository rules and preprocessing code are explicitly labeled current. Missing task evidence is recorded rather than replaced by assumed historical provenance.

`RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH` means the tested exclusions reproduce the cleaned aggregate keys. It does not prove which rules the historical run used or certify surveillance completeness. `RAW_CLEAN_REVIEW_REQUIRED` means unexplained differences remain; diagnostics are still archived. A `FAIL` status indicates an execution or input-validation error. Raw file checksums establish the input read by this job, not identity to an unavailable historical raw checksum.

The archive contains internal aggregate counts and provenance only—no individual records, full input datasets or model fits. State-level unknown-county records are never redistributed to counties. Four threads are used for CSV reading; SAS import and aggregation do not automatically gain fourfold speedup.

Validation includes a full synthetic SAS-to-CSV comparison with 122,024 retained records, three excluded records and 7,776 panel cells; it verifies exact reconciliation. Unit checks cover disjoint exclusion hypotheses and deliberate unexplained differences. Launcher checks cover read-only inputs, four-slot allocation, provenance collection and shell syntax. Real-data results remain pending the cluster job.
