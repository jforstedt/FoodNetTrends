# Saved surveillance refit audit

Run from the repository on Rosalind after the surveillance array finishes:

```bash
module load singularity && python3 scripts/launch_surveillance_postrun_audit.py
```

The launcher selects the latest completed `surveillance_refits_TIMESTAMP` directory. Use `--source output/surveillance_refits_TIMESTAMP` to select an older run explicitly. Four independent checkpoint audits run concurrently by default; `--workers` accepts 1–8. This job reads existing fits, creates a new audit directory and archive, and neither fits models nor replaces dashboard results.

The audit checks:

- Saved brms/Stan model structure, declared catchment eligibility, populations, baseline settings and checkpoint hashes.
- Rank-normalized R-hat, bulk/tail effective sample sizes, divergences, treedepth hits and chain energy diagnostics.
- Estimate table schemas, intervals, state-year coverage and reconciliation with saved model counts and populations.
- Listeria CSTE-YES counts across the entire fitted period, using the current clean input and saved selection settings. Nonreportable rows excluded from the saved counts are reported without failing an otherwise correct fit.

The archive contains aggregate evidence and logs, not saved model checkpoints or individual case records. `AUDIT_CHECKS_PASS` means these implemented checks passed; it does not establish forecast calibration or resolve historical exposure assumptions. Older runs lack fitting-time hashes of case inputs, so matching current aggregate counts cannot establish individual-record identity.

Future surveillance launches also generate checkpoint validation evidence before collection. Fit completion and statistical acceptance remain separate: a successful fit with sampling flags requires review. Existing completed runs use the standalone audit above.

The September 13 seven-fit archive passed local CSV structural checks. Exported divergences were Shigella 3, Vibrio 6 and non-O157 STEC 2. Full checkpoint diagnostics require the cluster audit before deciding on targeted refits. Do not promote all seven solely because execution succeeded.

## Local validation

The focused regression pass included nine collector/launcher tests, two post-run audit tests, the Crypto launcher test, the actual model-flow harness, and the analysis, reportability, surveillance-boundary and saved-fit R tests. Python 3.6 syntax checks also passed. Saved rstan checkpoints cannot be inspected on this workstation because rstan/brms are unavailable here; their real diagnostics remain a cluster check.
