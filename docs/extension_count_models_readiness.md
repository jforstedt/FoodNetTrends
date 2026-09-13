# County spline, spatial and pathogen-specific count-model readiness

The read-only count audit uses the existing nine reconciled county panels and
revalidates their source checksums, observation windows, complete county-year
grid, populations, state totals and adjacency. Cryptosporidium uses the corrected
panel ending in 2017. These historical panel windows are deliberately retained;
this audit does not extend surveillance eligibility or rebuild counts.

State/year summaries report count sparsity, zero fractions, count quantiles and
population ranges. County-history summaries report the distribution of observed
history length, years with positive counts and total counts within states. Graph
summaries report components, isolated nodes and degree ranges. Outputs are
aggregate internal diagnostics; individual county trajectories are not exported.

These summaries inform which spline comparisons and prior-predictive tests are
worth designing. They do not select priors, certify independent county curves,
prove spatial benefit, or establish structural zeros. Count variance across
unequal populations and trends is not residual overdispersion. Model tuning must
use training-only data and an explicit target; reviewing these historical data
must remain documented in the evaluation-use registry.

No raw or posterior model fit is required for this audit. The next modeling step
remains a controlled spline/RW1 comparison and separately assessed spatial
sharing, with appropriate prior and predictive checks.
