# Saved county forecast sampling checks

This read-only check revisits numerical sampling precision in completed county forecasts. It does not fit or change any model. Missing checkpoints are failures requiring an explicit recovery decision; reports alone cannot substitute for a posterior checkpoint.

For each eligible saved forecast, four independent seed streams each generate 4,000 joint INLA Gaussian posterior draws (`skew.corr=FALSE`). Predictive probabilities use the negative-binomial probability mass function analytically conditional on each draw. No additional predictive-count simulation is needed for log scores. Batches of 100 draws bound memory, and scaled density moments avoid underflow. Runtime depends on the latent dimension and INLA sampling overhead; the work is 16,000 posterior draws per existing fit, not another model optimization.

Before sampling, the script revalidates the audited panel and source checksums, compares the stored predictor data and population offsets with that panel, checks the requested spatial/IID model identity, training outcomes and withheld counts, and requires an exact match to the training-origin temporal specification. Fit and panel checksums must remain unchanged afterward.

`seed_state_year_scores.csv` contains the sum of marginal county log predictive densities for each state/year and seed. It is not the joint probability of a state total. `seed_cells_INTERNAL.csv` and `cell_stability_INTERNAL.csv` retain numerical scores by county/year without raw case records. The internal filename indicates these summaries stay in the returned private archive. Cell relative Monte Carlo errors and independent-seed score variation are descriptive numerical diagnostics; they are not estimates of epidemiological uncertainty or evidence of predictive validity.

Compare spatial and independent-county variants only for the same pathogen, training origin, horizon and eligible panel. Use the full-seed sums and propagate sampling variability from both variants. The seeds do not establish matched common random numbers across different models. State/year cells and overlapping forecast origins are statistically dependent, so no significance test across them is implied. Batch score differences use fewer draws and can have larger log-transform bias; they are debugging evidence, not substitutes for full-seed comparisons. Four seeds can reveal large instability but cannot certify negligible tail bias.

CLI: `Rscript scripts/audit_saved_forecast_sampling.R AUDIT FIT ORIGIN HORIZON OUT EXPECTED_MODEL`.

Successful completion writes `SAVED_FORECAST_SAMPLING_COMPLETE` to `status.txt`. This means the sampling audit finished, not that the forecast passed scientific review.
