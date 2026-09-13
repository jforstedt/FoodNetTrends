# Retrospective county forecast check

Run on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_county_forecast.py
```

This submits four concurrent training-only fits: spatial baseline, IID baseline, spatial county-time extension and IID county-time extension. Each requests eight CPUs with `h_rss=32768M`, `mem_free=32768M`, `h_vmem=64G` and a twelve-hour limit. There is no additional array concurrency cap or automatic retry loop. A held collection job writes one archive. Existing `foodnet-inla-fixed.sif` is reused; there is no container build. These new fits are necessary because the saved full-period fits already used the years being predicted.

## Fixed experiment

All models train on the audited Salmonella data for 2004–2016 and predict 2017, 2018 and 2019 from the single 2016 origin. No 2017 outcomes are used to update the 2018 prediction, and no 2017–2018 outcomes update 2019. The fitting input replaces all 1,458 held-out responses with NA; the 6,318 earlier responses remain. Original observations are retained separately for scoring. Training-only county case totals define sparse-count strata (0, 1–5, 6–20, 21–100, 101+).

The four specifications keep the original county SD bound at 1. Priors and hyperparameters are not initialized from full-data estimates. The two temporal variants add the same county RW1 component tested in the preceding experiment. Population offsets, the fixed graph, state effects and pathogen selections remain as documented for the county pilot. This does not extend validation to another pathogen, change Daniel's model or publish county dashboard estimates.

Future census populations are treated as known, and the fixed 2004–2019 latent time domain/scaling is retained for every candidate. The test therefore conditions on known denominators and geography; it is not a test of forecasting population or future surveillance coverage. The historical full panel is validated for integrity, but later outcomes do not enter the fit likelihood.

This is **retrospective**, not an untouched validation set: these years already informed the earlier model investigation and the choice of candidates. It is one forecast origin with three horizons, not rolling-origin validation or geographic holdout. The distinction between future prediction and same-data leave-one-out comparisons follows the [loo leave-future-out guidance](https://mc-stan.org/loo/articles/loo2-lfo.html).

## Predictive checks and sparse-count review

Each fitted model generates 4,000 joint posterior samples, in batches, retaining the established `skew.corr=FALSE` approximation. Predictors are exponentiated to expected counts, and negative-binomial draws use the jointly sampled size parameter. An explicit log-link setting is supplied for missing-response predictions. Original sensitivity fits retain their default predictor settings.

Reports include:

- Internal county/year observations, expected counts, 50% and 95% predictive count intervals, log predictive densities, zero probabilities, zero Brier scores and randomized PIT values.
- Pooled total/zero predictive checks by year, state, state/year, county, population band and training-case band, aggregated from joint draws. County groups have only three forecast years and should not be overinterpreted.
- Log scores, absolute errors, interval coverage/width and zero Brier scores for the same groups. Higher log score is better; lower Brier score/error is better. Coverage must be considered together with width; discrete count intervals can be conservative.
- Paired candidate-minus-reference log-score sums and Brier changes, including temporal versus baseline and spatial versus IID comparisons. The standard error is explicitly naive under dependence and is not a formal significance test.
- Training split, hyperparameters, formulas, checksums and error logs.

The log score is calculated as the log of the posterior average probability of the observed count using a stable log-sum-exp calculation. Sums of these **marginal cell scores are not a joint three-year sequence score**. Relative Monte Carlo standard errors for the estimated cell predictive densities flag estimates dominated by too few posterior samples. Very uncertain scores should not be treated as decisive differences.

The sparse-count review asks whether zero probabilities and intervals work for counties that were sparse during training. It does not infer a zero-inflation mechanism, establish reporting completeness, or automatically select a new model. PIT plots and subgroup rankings are descriptive, with dependence and multiple comparisons in mind.

## Preservation and validation

All outputs go into new directories; the audited panel is mounted read-only and checked for changes. New fit RDS objects are checkpointed before scoring and remain on HPC. Archives contain internal aggregate reports, not source datasets or fit objects. Failures are archived and reported as incomplete; no winner or dashboard update is automatic.

Tests run all four specifications in actual INLA on synthetic data with later responses masked. Altering those later outcomes leaves the training input and sparse-count groups identical. Tests verify the missing-response log link, predictive score calculation, bounded probabilities/PIT, interval order and aggregation. Collector tests check matching splits/truth, score differences, failure reporting and exclusion of private fits. A regression run checks the existing full-data sensitivity variants after the optional prediction-link argument was added.
