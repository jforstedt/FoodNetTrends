# Conditional diagnostic-classification trends

This exploratory batch describes the probability that an eligible case is labelled
CIDT+, conditional on its classification being CX+ or CIDT+. It does not estimate
infection incidence, test positivity among everyone tested, or a causal testing
adjustment. CX+ must not be interpreted as culture-only: combined positive records
can belong to that category. Daniel's accepted state model is unchanged.

## Frozen comparison

The six pathogens are Salmonella, Campylobacter, Shigella, STEC, Vibrio and Yersinia.
Their audited 2012–2019 support has positive classification denominators for all
80 site/year cells per pathogen. Listeria has too few CIDT-labelled records for this
comparison; the two parasites do not have the required CX+/CIDT+ contrast.
2012 marks the first observed CIDT labels for these six in this dataset, not a
verified adoption date. Coverage remains EXPLORATORY_ASSUMED_CONTINUOUS.

Each pathogen has four fits, for 24 independent tasks:

- Shared linear time trend, trained through 2016, scored during 2017–2019.
- Shared trend plus partially pooled site slope deviations, with the same split.
- Each of those two models fitted through 2019 for historical description only.

All years have already been examined during development. The held-out comparison
is exploratory rather than independent final validation. Its observed category
denominator is conditioned on; this is not a prospective forecast of case counts.
No description-fit score will serve as held-out evidence.

Both models use binomial CIDT counts out of CX+ plus CIDT+ counts, IID site
intercepts and IID site/year latent effects to allow extra-binomial variation.
Time is (year − 2012)/4. The intercept prior is Normal(logit(0.1), 1.5²), and the
common slope prior is Normal(0, 1²). PC precision priors set P(SD > 1.5) = 0.01
for site intercepts and P(SD > 1) = 0.01 for cell effects and optional site slopes.
These are explicit regularizing assumptions, not empirically established truths.
No automatic model selection or incidence adjustment follows this batch.

## Outputs and interpretation

Four independent posterior sampling streams of 500 draws yield site/year
probability intervals, predictive count intervals, annual aggregates from joint
draws, and stream-specific and pooled log predictive scores. Relative Monte Carlo
standard errors accompany density estimates. Retain stream instability and
coverage as review criteria rather than declaring a winner from one total score.
The 2017–2019 rows compare the same outcomes and denominators between candidates;
in-sample rows are explicitly labelled. Annual intervals aggregate joint draws,
not marginal interval endpoints.

Saved fits and draws remain on the cluster. The portable archive contains aggregate
reports, numerical warnings, source snapshots, settings and hashes. No dashboard
integration or accepted-model replacement occurs automatically. Review predictive
coverage, annual bias, stream agreement, site heterogeneity and prior sensitivity
before considering any subsequent use. This analysis alone cannot establish how
much observed incidence changed because testing changed.

## Execution

Run `python3 scripts/launch_classification_trends.py` on Rosalind with Singularity
loaded and the completed eligible diagnostics directory available. The launcher
uses the existing foodnet-inla-fixed.sif and pinned INLA 26.08.07. It submits one
24-task array, four cores per task, with no concurrency cap, followed by a collector.
Each task requests 12 hours, h_rss/mem_free 8192M and h_vmem 16G; scheduler memory
semantics remain those of the cluster. It does not rebuild a container or refit
existing incidence models.

Inputs, source and task identity are hash-bound before and after execution.
Collection rejects missing, altered or inconsistent reports, preserves partial
results on failure and never marks these exploratory models accepted. A
`--prepare-only` plan is intentionally unverified and cannot execute workers.

## Local verification

`python3 -m unittest discover -s tests -p test_classification_trends.py` checks the
24-task plan, Python 3.6 syntax, refusal of unverified execution, altered outcomes,
invalid score diagnostics and partial collection. `Rscript
tests/test_classification_trends.R --fit` exercises both candidate models with
synthetic data under the pinned INLA version. The masking check perturbs held-out
outcomes while requiring every model-used data column to remain identical.
These implementation checks do not establish scientific adequacy on FoodNet data.
