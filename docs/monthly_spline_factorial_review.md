# Local review of the monthly spline factorial

Run this after the portable archive has been downloaded, using a new output directory:

```bash
python3 scripts/review_monthly_spline_factorial.py /path/to/monthly_spline_factorial_RUN.tar.gz --output output/monthly_spline_review_RUN_LOCAL
```

This reads the archive without extracting it and fits no models. Python standard-library validation runs before any result export. Matplotlib is required for PNG/PDF figures; `--no-plots` permits table-only review. The existing 108-cell reviewer retains its default protocol.

The frozen matrix has 162 cells: nine pathogens, three origins each, three temporal families (RW1, AR1, spline), and seasonality present/absent. There are 54 new spline fits and 108 copied controls. Cryptosporidium uses origins 2011/2013/2014 with surveillance ending in 2017; other pathogens use 2011/2013/2016 and end in 2019. Validation checks all identities, allocation, settings, complete site/year/stream domains, 2,000 draws in each of four streams and 8,000 pooled draws.

Integrity checks cover the whole portable manifest, earlier plan bindings of scripts/prepared basis/copied controls, the basis recipe's file and source hashes, per-task output bindings, and equality of merged tables with their task reports. The basis serial-month domain and finite values are checked; its scientific construction is bound to the previously reviewed preparation recipe, not re-estimated here. Bound held-out truth hashes must agree among all six arms within a pathogen/origin, and visible observed totals must agree across arms, streams and site/catchment aggregation. Missing tasks remain explicit; a completed task with an incomplete metric grid is rejected.

The archive is a consistency record, not a signature proving authenticity. Internal fit objects and county truth are intentionally excluded from the portable report; their checks and original cluster-only input verification remain collector evidence. The local tool cannot re-read unavailable cluster files or independently reconstruct excluded county truth.

For each reference (RW1 and AR1), independently recomputed four-arm contrasts are:

- Spline minus reference without seasonality.
- Spline minus reference with seasonality.
- Seasonality within the reference family.
- Seasonality within spline.
- Difference between those seasonality effects (the predictive-score interaction).

All must match the published collector contrasts. Positive spline-minus-reference values favor spline on predictive log score only. Score interactions are not biological mechanisms. Incomplete four-arm blocks produce no contrast, even when some arms are available. `comparison_block_inventory.csv` makes those exclusions visible. Any collector integrity issue or paired-truth disagreement suppresses all numeric comparison/calibration exports and plots; malformed or altered artifacts fail before output creation.

Outputs include task/block inventories, site and equal-site contrasts, pooled component comparisons with four-stream ranges, absolute equal-site scores for all six arms, pooled calibration, and site/catchment detail retaining expected and predictive medians, expected upper tails, interval endpoints, top-1% contribution and probabilities above twice observed. Figures show spline against **both** references and calibration for all six arms. No model is automatically selected.

Four-stream ranges describe Monte Carlo variability, not confidence intervals. Site weighting is equal within each origin/horizon; evaluations overlap in time and are not independent replications. Joint catchment intervals come from the existing pooled predictive draws and are never formed by adding site interval endpoints. Relative bias/width are undefined where observed counts are zero; absolute versions remain available. Calibration is descriptive for ten sites, rather than a formal population coverage estimate. CPO is not used for ranking or acceptance.

Apply the [decision checklist](monthly_spline_decision_checklist.md) and [decision template](../analysis_configs/monthly_spline_decision_template.csv). Compare scores with annual bias, coverage, interval width and tail stability, document the pathogen-specific rationale, retain interactions worth later examination, and keep Daniel's accepted state model unchanged unless separately justified and validated.

Tests use synthetic reports with known score effects. They cover a full 162-cell archive, both reference contrasts, partial blocks, integrity failures, basis/recipe tampering, merged/source disagreement, missing output bindings, duplicate/missing metric cells, paired truth and copied-control alteration. The legacy 108-cell suite runs alongside these tests. Synthetic plots can check presentation, but do not count as scientific evidence about the real fits.
