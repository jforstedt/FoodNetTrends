# First real-data monthly comparison

Status: executable exploratory comparison, 2026-09-13. This runs the monthly reference and seasonal addition for Salmonella and Campylobacter. It does not replace Daniel's accepted state model, alter the raw data, publish a dashboard or claim a validated county forecast.

## Run

From the FoodNetTrends repository on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_monthly_comparison.py
```

The launcher verifies the completed monthly preparation and upstream audit hashes, snapshots source, and submits 12 independent SGE tasks: two pathogens × cutoffs 2011/2013/2016 × reference/seasonal. All may run concurrently, subject to the scheduler. Each requests four slots, h_rss/mem_free 53248M, h_vmem 68G and a 48-hour limit. These are requested limits, not a runtime estimate; site-specific SGE accounting controls their enforcement. A held collector requests one slot and runs after the array. Once the array and collector IDs are printed, no persistent terminal or Nextflow controller is needed.

`--prepare-only` writes an explicitly unverified plan without jobs. An unverified plan cannot execute. Workers refuse existing task directories and do not automatically retry; failures remain visible. If collection fails, existing successful fits stay on disk. Do not submit an entirely new batch simply to regenerate reports.

## Coverage and date contract

This comparison adopts **EXPLORATORY_ASSUMED_CONTINUOUS** coverage for the audited 486-county footprint during 2004–2019. The assumption is now an analysis choice, not a claim that the previously missing interruption ledger was obtained. The launcher writes all 3,840 pathogen/site/month assumptions to a hashed CSV. Source calendars stay UNVERIFIED; only the in-memory fitting copy receives the assumption label. No monthly coverage certificate is produced.

The public-program evidence and its limits are in [the coverage review](monthly_coverage_evidence.md). This conditional exploratory analysis advances under that stated assumption; it supersedes the earlier blanket hold on all real-data fitting, not the requirement for better evidence before stronger claims. Known gaps, if supplied later, require exclusion and reevaluation. Results cannot establish completeness of surveillance or testing ascertainment.

The event target is specimen collection month, under [the date convention](monthly_analysis_assumptions.md). The source-month discrepancy is documented in the private review and retained for a later affected-result sensitivity if consequential. No source fields or annual cases are changed. Readiness requires no missing, invalid-month or year-conflicting assignments and exact reconciliation to the original annual case counts. The full loader checks county/state/year membership, all 12 months, nonnegative integer counts and exposure against the audited panel.

## Frozen first comparison

Training starts January 2004 and ends December of each cutoff year. Every task forecasts the next 36 months, ending no later than December 2019. Scoring uses horizons 1–12, 13–24 and 25–36 months separately. These historical origins were previously explored, so this is not an untouched confirmatory test.

Both models contain state intercepts, static IID county effects and state-specific monthly RW1 trends. The seasonal version adds a shared, explicitly centered 12-month cyclic RW1. The shared component repeats annually and joins December to January. County-specific temporal deviations, spatial effects and spline terms are deliberately deferred to later matched comparisons. This first batch answers the incremental seasonal question within this specified model only.

The shared implementation is used by the synthetic tests and real-data runner. Trend scale and centering depend only on training months; all future outcomes are masked internally. The seasonal domain always contains 12 coefficients. Prior settings are frozen in `plan.json` and in the snapshotted runner:

| Parameter | Prior |
|---|---|
| State log rate per person-year | Normal(log(0.0002), 1) |
| County SD | PC: P(SD > 1) = 0.01 |
| Training-scaled trend SD | PC: P(SD > 0.5) = 0.01 |
| Scaled cyclic seasonal SD | PC: P(SD > 0.5) = 0.01 |
| Negative-binomial log size | Normal(log(20), 1) |

The rate center is 20 per 100,000 person-years, matching the existing county reference intercept convention rather than the 200-per-100,000 synthetic stress setting. It is not estimated from held-out outcomes. The prior audit gives a broad marginal annualized rate range and remains an exploratory plausibility check, not proof these priors are optimal. The monthly size prior is explicit and is not a reuse of a fitted annual shape parameter. Negative-binomial variance is `mu + mu^2/size`.

Monthly exposure is annual county population × calendar days / days in year, including leap years. Future realized population is used identically within pairs: this is a conditional retrospective experiment, not a real-time forecast using only historical population vintages. A constant-within-year population assumption remains explicit.

## Predictions and comparison

Each fit uses two disjoint seeded streams of 500 joint posterior samples. The primary log score is the Monte Carlo mixture negative-binomial score for each county-month. County scores are averaged within site/horizon; paired differences are then averaged equally over ten sites. Origins and pathogens remain separate. These are site summaries of county scores, not log densities of aggregated site counts.

Secondary reports include 50%/95% interval coverage, 95% interval score, absolute error and predictive quantiles. The two-stream log-score difference is exported as a Monte Carlo stability diagnostic, not treated as a precise confidence interval. Site/catchment monthly and annual distributions are computed by summing joint draws, not interval endpoints. No promotion threshold is invented after scoring; every result remains exploratory and requires numerical, calibration and stability review.

The collector produces paired site metrics and equal-site comparisons only for complete pairs; missing or invalid jobs remain in the summary and cause nonzero completion status. INLA failure/aborted-correction messages block successful classification. Those checks do not substitute for statistical review.

## Artifacts and validation

The launcher prints the array ID, collector ID, final log and one archive path. The archive includes county-month prediction summaries, site/catchment summaries, seasonal effects, hyperparameters, comparison metrics, source snapshots and hashes. It contains study aggregates and should not be committed to Git. Fit and draw RDS files remain on the cluster, bound by hashes but omitted from the portable archive.

Local checks cover unverified/altered-plan rejection, array dispatch, failure archives, pairing, Python 3.6 syntax, complete annual-to-monthly reconciliation, exposure rejection, real shared-model fitting on synthetic inputs, joint aggregation and the original synthetic seasonal recovery/horizon tests. Live private SAS/audit access and full-scale HPC resource use can only be verified on the cluster.
