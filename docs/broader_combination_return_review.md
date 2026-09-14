# Return archive intake and scientific review queue

Use the local integrity gate before interpreting the combined cluster archive:

```bash
python3 scripts/review_broader_combinations.py /path/to/broader_combinations_RUN.tar.gz --output output/broader_combinations_review_RUN_LOCAL
```

It verifies the outer and all available nested manifests without extracting or executing archived code. It checks the fixed 324 spatial, six classification and 54 inspection task identities, completion records, portable frozen inputs, output bindings and matching outer/inner summaries. Missing branches produce an explicit partial intake; malformed or altered evidence fails before review files are created. Existing review directories cannot be overwritten.

This gate verifies delivered evidence, not statistical correctness. It cannot re-read private cluster inputs or authenticate a maliciously rewritten set of all provenance records. It does not independently recompute score tables, review calibration, certify data coverage or select models. Synthetic tests establish software behavior, not real-data evidence.

Review the branches independently as soon as valid results arrive:

1. Spatial: verify per-task settings and paired truth; independently recompute IID/BYM2 differences and temporal/seasonal interactions. Compare score changes with bias, coverage, widths, tails and stream variability, by pathogen, origin and horizon. Preserve weaker standalone components when combinations warrant further study. Repeated development origins do not establish untouched validation.
2. Classification preparation: reconcile monthly counts to annual support, category-specific missing dates and zero denominators. Record support before freezing the conditional-binomial priors and launching its temporal/seasonal/spatial combinations. This outcome is diagnostic mix among classified cases, not incidence or test positivity.
3. Saved spline inspection: inspect training versus forecast linear and nonlinear contributions across all pathogens. Decomposition of posterior mean log effects excludes other model components and is not a joint predictive interval. Diagnose extrapolation before proposing another spline specification.

Maintain a separate rationale for each proposed change, contrary evidence, remaining uncertainty and next action. Daniel's accepted state model and the active cluster snapshots remain unchanged by these local review steps.

Local validation: six synthetic tests cover a full nested bundle, duplicate task identities, independently rehashed output/snapshot changes, unsafe paths, duplicate JSON keys, missing branches and refusal to overwrite review output.
