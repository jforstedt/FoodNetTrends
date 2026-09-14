# Monthly diagnostic-classification combinations

These exploratory models estimate the probability of a literal CIDT+ label among records labelled CIDT+ or CX+. They condition on the classified-case denominator, including the observed denominator in forecast months. They are conditional hindcasts of diagnostic mix, not incidence forecasts, detection probabilities or an adjustment to Daniel's accepted incidence model.

## Frozen design and likelihood

Training starts January 2012. Development cutoffs are December 2015 and December 2016, followed by exactly 36 months. These overlapping, previously examined periods are not independent final validation. The shared temporal effect is RW1 or stationary AR1, crossed with common cyclic seasonality absent/present. Site models retain partially pooled site intercepts and independent site-month logit effects. County models retain those site intercepts and independent county-month logit effects, plus county IID or BYM2 intercepts. There are four site structures and eight county structures. The spline combinations remain planned behind their separate review gate.

`prepare_monthly_classification(data, cutoff, level)` accepts site or county monthly tables with literal `cidt_classified`, `cx_classified` and their sum `classification_denominator`. It validates all training counts, conditioning denominators, the complete monthly grid and county/state identity. Future successes and complementary category counts are masked before model design. Zero-denominator responses are also masked; their latent prediction locations remain. A zero denominator never means zero CIDT probability. Rows are deterministically sorted, `row_id` is the predictor index and `row_key` records unit/year/month identity.

The binomial likelihood uses explicit logit link and `Ntrials=classification_denominator`. The county graph is validated in both IID and BYM2 arms, retaining the identical footprint; only BYM2 uses adjacency in its prior. BYM2 uses scaled connected components, explicit constraints, no isolated counties and the same graph helper as the spatial incidence experiment. Neither spatial arm adds county-specific temporal trends.

## Prior choices, frozen before outcome fitting

All scales below are on the logit scale. They are explicit regularization assumptions rather than biological claims.

| Component | Frozen prior and interpretation |
|---|---|
| Overall intercept | Normal(logit(0.1), 1.5²), carried from the annual classification model |
| Site intercept SD | PC upper 1.5, tail probability .01 |
| Cell logit SD | PC upper 1, tail .01; keeps extra-binomial variation in every arm |
| County marginal SD | PC upper 1, tail .01 in IID and BYM2 arms |
| RW1 temporal scale | PC upper 1, tail .01 for geometric-mean training marginal SD; training-only mean-zero constraint |
| AR1 temporal scale | PC upper 1, tail .01 for stationary marginal SD |
| AR1 correlation | Normal(log(19), 1.5²) on log((1+rho)/(1-rho)); median rho .9, allowing weaker and negative persistence |
| Common seasonal scale | Cyclic RW1 with mean-zero constraint, PC upper 1, tail .01 for scaled marginal SD |
| BYM2 mixing | Pinned INLA `pc` prior with parameters (.5, .5), using the audited graph and component handling |

The PC SD priors are exponential with rate `-log(.01)/upper`. RW1 precision is rescaled using only the training time grid, so extending the forecast horizon cannot tighten its training prior. Future RW1 innovation variance remains nonzero. AR1 is stationary, with marginal rather than innovation precision. The shared scale bound 1 was checked on the logit link; the incidence model's log-rate bound was not copied. Seasonal scaling uses the constrained 12-month cyclic precision. The annual cell effect convention is retained as an explicit candidate at monthly resolution, not presumed equivalent to annual overdispersion.

The mixing prior needs a precise numerical qualification. The pinned INLA graph implementation constructs and normalizes a finite table on logit(phi). For this 486-county, ten-component graph, its actual numerical table has median phi approximately **0.2903** and probability phi below .5 approximately **0.6656**, despite nominal parameters (.5, .5). The direct returned logit-density table integrates to one. These figures were checked through the same `inla.pc.bym.phi(graph=..., return.as.table=TRUE)` route called by `inla.ffield.section`; they do not result from forgetting a Jacobian. The prior is retained unchanged and interpreted by its actual table. We do not claim that its realized median is .5, and we do not silently substitute a beta prior or retune it using outcomes.

## Prior-only calibration and checks

`check_monthly_classification_priors.R` uses no case outcomes. It simulates 5,000 latent trajectories for every structure and both cutoffs, using the exact pinned BYM2 numerical mixing distribution and graph-scaled marginal variances. It records training/forecast probability quantiles, boundary mass and adjacent-month logit changes. The check also validates RW1 training centering, cyclic centering, scaled graph variances and numerical mixing-prior normalization. It samples representative marginal county trajectories; it is not a check of joint spatial prior correlation or a forecast skill assessment.

Across the 48 structure/origin/period summaries, median prior classification probabilities are about .095–.104. The central 95% bounds span about .0029–.80; less than .09% of draws exceed probability .99. This is broad probability support around the inherited .1 baseline, with no forced boundary mass. These are prior simulation results, not fitted pathogen results. The broad probabilities and monthly cell regularization remain assumptions to assess through predictive checks and later prespecified sensitivity work.

The tracked `analysis_configs/monthly_classification_priors` artifact records all summaries and source/graph checksums. Its `PRIOR_CHECK_PASS` manifest means the documented implementation and prior-only structural checks passed. It does not mean scientific acceptance, surveillance coverage certification or that priors have been selected to maximize model rankings.

## Local verification and API

Source `monthly_spatial_combination.R` and `monthly_classification_model.R`. Call `fit_monthly_classification(data, cutoff, level, temporal, seasonal, spatial, nodes, edges, threads=4)`. Saved attributes `monthly_classification_data` and `monthly_classification_specification` support independent masking, row identity and likelihood checks. The score worker uses joint predictor draws with `plogis`, preserving cell dependence when aggregating annual predictive totals.

Pure-R checks cover reordered inputs, missing cells, literal denominator errors, invalid denominators, complete future masking (including poisoned future outcomes), zero-denominator masking and training-only prior scaling. All twelve structures passed actual pinned-INLA synthetic fitting and joint posterior sampling with zero optimizer mode status. These tests validate execution and the binomial interface, not accuracy on real pathogen data. The numerical gate remains `ok=TRUE`, `mode.status=0` and no aborted variational correction; completed execution alone is not model selection.
