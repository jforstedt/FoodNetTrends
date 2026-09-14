# Reviewing the monthly factorial batch

Run the local review after receiving the portable `monthly_factorial_*.tar.gz`
archive. This does not submit jobs, refit models, modify source reports, or
select a production model.

```bash
python3 scripts/review_monthly_factorial.py /path/to/monthly_factorial_RUN.tar.gz --output output/monthly_factorial_review_LOCAL
```

An extracted report directory is also accepted. The destination must be new.
Matplotlib is required for scientific PNG/PDF figures; `--no-plots` exports only
tables and Markdown. The report reader otherwise uses the Python standard
library. The CLI exits zero only for a complete, consistent exploratory report;
partial or blocked reviews return one and retain their explicit status.

## Verification and its limits

The reader never extracts archive files. It rejects traversal, absolute paths,
symlinks, hardlinks, special archive members, duplicate file names and duplicate
JSON keys. A one-GiB uncompressed size limit avoids unexpectedly large archives.
The manifest must bind every regular report file exactly once. Earlier plan
bindings are checked independently for snapshots carried inside the archive,
and available new-task outputs are also checked against their task records.
A newly generated manifest cannot make an altered plan-bound snapshot valid.
Merged metric rows must reproduce their portable per-task source reports, rather
than merely agreeing with contrasts generated from the same merged table.

A checksum manifest proves consistency, not authenticity. Cluster-only input
files and saved fits cannot be freshly checked from the portable archive.
The review checks the bound county-truth identities reported by reference/task
records, then independently checks matching observed site/year totals across
arms and streams and catchment totals against site sums. It states this limit
in the output instead of implying access to internal county predictions.

The expected 108-cell plan is verified against the frozen nine-pathogen,
three-origin, two-temporal-family, two-seasonality matrix. The 48 new/60 reused
allocation is checked by cell identity. Summary completion counts are recomputed
from task records; a count of 108 is never assumed to imply success. Completed
cells require complete site/year/stream grids, valid labels, finite scores,
valid predictive interval ordering, consistent observed counts, and exactly
four 2,000-draw streams plus their 8,000-draw pooled estimate.

Any collector issue or inconsistent paired truth suppresses numerical comparison
exports and figures. A partial run without integrity issues can show complete
four-arm blocks, clearly labelled partial; incomplete blocks cannot contribute
component contrasts. Published contrasts are independently recomputed from the
score table, and differing values or domains stop review.

## Exports and interpretation

`review.md` and `review_summary.json` give verification, completion counts and
limitations. `task_inventory.csv` preserves all complete and missing cells.
For interpretable blocks:

- `site_contrasts.csv` retains pathogen, origin, site, forecast year and stream.
- `equal_site_contrasts.csv` averages the ten sites equally within each block.
- `pooled_arm_scores.csv` preserves absolute equal-site scores for all four arms,
  with sampling-stream ranges and maximum cell-density relative MCSE.
- `pooled_component_review.csv` gives pooled component/interaction differences
  and the minimum/maximum across four sampling streams for each difference.
- `pooled_site_and_catchment_details.csv` gives observed and predicted annual
  counts, predictive intervals, coverage, bias, interval width and upper-tail
  diagnostics, using pooled stream zero only.
- `pooled_calibration.csv` retains each origin and horizon, with equal-site
  coverage, bias, width and tail contribution plus separate catchment summaries.
- Per-pathogen `*_contrasts.png/.pdf` and `*_calibration.png/.pdf` are standalone
  scientific figures suitable for a review document. Numerical output stays in
  the local destination; it is not written into source documentation.

Higher log score is better. The four component contrasts and the
AR1-with-seasonality minus AR1-without-seasonality minus RW1-with-seasonality
plus RW1-without-seasonality interaction follow the frozen factorial protocol.
Temporal effects compare the specified temporal model/prior packages, not just
one correlation property. The score interaction is not a biological interaction.

The four-stream range is Monte Carlo stability information, **not a confidence
interval**. Overlapping origins, sites, months and horizons are not independent
replicates. Coverage is a descriptive proportion of ten observed site totals,
not an independent validation estimate. Mean bias and interval widths can be
influenced by heavy tails; inspect the top-one-percent mean contribution too.
Relative site summaries are left undefined if any site's observed count is zero;
the positive-site count is included. Catchment intervals come from supplied joint
predictive draws, never from adding site interval endpoints.

No automatic winner, new pathogen-specific default or acceptance threshold is
introduced. Read the score contrasts with calibration and the rationale register.
A weak standalone component remains eligible for combination testing. Coverage
remains assumed continuous and the already examined development periods remain
exploratory; this review cannot create untouched final validation data.
