# Independent monthly spatial comparison review

The local reviewer validates the original portable spatial archive and optionally adds the successful Listeria numerical recovery. It does not overwrite original results or mark an incomplete comparison complete.

```bash
python3 scripts/review_monthly_spatial_results.py /path/to/broader_combinations_RUN.tar.gz --recovery /path/to/monthly_spatial_recovery_RUN.tar.gz --output output/spatial_review_RUN_LOCAL
```

Frozen task identities, copied source bindings, original task output hashes, paired truth, complete metric grids, sample counts, model settings and merged/per-task agreement are checked. Recovery is linked to the original plan, preserves task identity and posterior seeds, requires a previously failed task and intact completion records, and passes the same numerical gate. Portable evidence cannot independently reconstruct private raw inputs; their retained hashes establish identity rather than certify surveillance coverage.

The reviewer independently recomputes spatial-minus-IID score differences and verifies the original collector's values. Paired exports retain each pathogen, origin, state, horizon and posterior stream. Configuration summaries accompany scores with annual bias, coverage, interval width, absolute error and tail concentration. Plots label incomplete origin sets explicitly. Stream ranges describe Monte Carlo variation, not statistical confidence in generalization. Reported site-year coverage is descriptive coverage across these repeatedly used historical cases, not an external calibration guarantee.

Interpret gains with their magnitude, origin consistency and practical prediction tradeoffs. A positive average difference alone cannot select a model. Wider intervals can increase coverage; lower errors can coexist with poor calibration or unstable tails. Retain the tested temporal/seasonal/spatial combinations as evidence, including components that performed weakly alone. Successful numerical execution does not modify Daniel's accepted state model.

Classification support and saved-spline component review can proceed independently. Conditional diagnostic-mix models need zero-denominator masking, support and prior-predictive checks; they are not testing-intensity adjustments. Saved posterior mean component changes are descriptive decompositions, not predictive uncertainty intervals.

Local checks include eight synthetic unit tests and a complete review of the returned original-plus-recovery archives. Private findings and plots remain under output/ and are excluded from publication.
