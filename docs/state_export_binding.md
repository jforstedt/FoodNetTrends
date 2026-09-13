# Saved state fit and export binding

New primary state exports and sampler-recovery exports create `PREFIX_fit_export_manifest.csv` immediately after calculating the posterior tables. The manifest records the saved posterior's SHA-256 and hashes of catchment, site, and baseline-comparison tables, analysis settings, population metadata, classification rules, and convergence summary.

The collector and accepted-dashboard preparation require that binding. Arithmetic checks alone cannot distinguish coherent tables from another sampler run with identical case counts and populations. A changed table or checkpoint now blocks acceptance even if all count/rate conversions and aggregate totals remain internally consistent.

This safeguard detects post-export mixing or changes; it is not a cryptographic signature against a party able to rewrite both the data and its manifest. The existing independent saved-fit, observation-grid, baseline, and sampler checks remain required.

Earlier accepted files are preserved. A missing manifest means their posterior-table binding is unverified under this new check, not that their estimates are known to be wrong. Do not create a manifest by merely hashing old tables. Recompute tables from the existing posterior into a new directory without sampling:

```bash
Rscript scripts/reexport_saved_state_tables.R SOURCE_RESULTS NEW_RESULTS ANALYSIS_PREFIX
```

Use the existing state-model container and retain the independent saved-fit proof and original job specification for downstream review. This command does not launch `brm`, Stan sampling, or a model update. It does not replace the original results or automatically adopt its outputs. The subsequent saved-fit and artifact review must still pass before a dashboard uses them.
