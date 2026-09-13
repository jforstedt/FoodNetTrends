# Targeted surveillance-window corrections

`python3 scripts/launch_surveillance_refits.py` inspects saved settings in the original combined-state run and the finalized feature run. It schedules only analyses affected by a documented observation-window issue:

- Campylobacter series extending beyond 2023 are restricted through 2023, before CIDT-only surveillance stopped.
- STEC non-O157 series starting before 2000 start in 2000.
- Other affected pathogens extending into 2025 are restricted through 2024 because site-specific completeness after optional reporting began has not been established. Salmonella and STEC are exempt from this restriction. Cryptosporidium has already been corrected separately and is not refitted.

The correction changes eligible input years. The existing state negative-binomial spline formula, population offset, and prior specification remain in place. Data-dependent default prior scales can change when eligible observations change. Saved travel, diagnostic-category, state, baseline, and subgroup settings are preserved, along with the per-analysis classification rules. The launcher rejects incompatible baselines and recognized custom-catchment or travel-stratified sources rather than silently substituting assumptions. The two default source runs used the standard catchment and did not request travel-stratified extra fits.

Each independent fit receives 12 CPUs, six chains, 10,001 iterations, and the established SGE memory/time request. All selected fits are submitted as one array with no additional concurrency cap. Feature-source fits use `adapt_delta=0.999`; original combined-source fits use `0.99`. This is a sampler control, not a prior change. The scheduler determines when resources are available.

The source R files are copied and hashed before submission. Outputs go into a fresh timestamped directory; original fits are preserved. Each successful fit now receives an independent saved-checkpoint audit before collection. The collector checks actual output coverage, baseline values, saved settings, numerical tables and checkpoint-bound sampling evidence, including bulk/tail ESS, divergences, treedepth and chain energy. Missing or invalid evidence requires review. It generates one archive without the RDS checkpoints. A successful execution alone is not a statistical pass. Early-year catchment and partial-year exposure questions remain under review. The launcher does not automatically replace dashboards.

Use `--prepare-only` to build and inspect the plan without submitting. Repeat `--source /path/to/spline_results` to select alternate saved result directories, and use `--clean-file` or `--data-dir` only when those input locations differ. The plan's `manifest.json` contains the exact commands and input-setting provenance; `collection.log` and `review_summary.json` provide the final checks.

For completed runs created before checkpoint auditing was added, use the [standalone post-run audit](surveillance_postrun_audit.md). It also checks full-period Listeria reportability against saved counts without refitting.
