# Biostatistical Review: FoodNetTrends Bayesian Modeling Pipeline

**Reviewer:** Senior Biostatistician
**Date:** 2026-03-13
**Scope:** Statistical methodology, model specification, posterior processing, and data handling
**Files reviewed:**
- `bin/functions.R` (core statistical engine)
- `bin/trendy.R` (modeling orchestrator)
- `bin/preprocess.R` (data preparation)
- `modules/local/resource_profiler.nf` (data profiling)
- `nextflow.config` (model parameter defaults)
- `run_workflow.sh` (user-facing parameter options)

---

## 1. Model Specification

### 1.1 Negative Binomial GAM with State-Specific Splines

**Assessment: Appropriate with caveats.**

The model formula at `functions.R` line 402:

```r
count ~ s(year, by = state) + state + offset(log(population))
```

This specifies a negative binomial GAM with:
- State-specific smooth functions of year (`s(year, by = state)`)
- State fixed effects (intercept differences)
- A log-population offset for rate modeling

The negative binomial family (`functions.R` line 404) is appropriate for overdispersed surveillance count data where variance exceeds the mean, which is typical of foodborne illness counts. This is a sound choice over Poisson regression.

**Concern 1 -- Spline basis and knot selection.** The `s(year, by = state)` call uses `brms`/`mgcv` defaults: thin plate regression splines with `k = 10` basis functions. For a time series spanning approximately 28 years (1996-2024), `k = 10` is reasonable, but this is not explicitly documented or justified. With 10 states and a "by" variable, the model fits 10 separate splines, each with up to 9 effective degrees of freedom. For pathogens with non-monotonic trends (e.g., Campylobacter showing an increase, plateau, and then further increase), the default `k` may be sufficient, but there is no diagnostic check (e.g., `gam.check()` or `k.check()` equivalent) to verify that the basis dimension is adequate. **Recommendation:** Add a post-hoc check on the effective degrees of freedom used by each spline and document that `k = 10` was evaluated for adequacy. Consider allowing `k` as a configurable parameter.

**Concern 2 -- Identifiability of `state` fixed effects with `by = state` splines.** The formula includes both `state` (as a fixed effect) and `s(year, by = state)`. The `by = state` construct in `brms`/`mgcv` creates separate smooths for each state, each with its own intercept absorbed into the smooth. When `state` is also included as a main effect, the model can potentially have identifiability issues depending on how `brms` handles centering constraints. In practice, `brms` and `mgcv` apply identifiability constraints to factor-by smooths (centering them), so the `state` main effect captures the overall level while the smooth captures deviations. This is technically correct, but should be explicitly verified and documented.

### 1.2 Offset Term

**Assessment: Correctly specified.**

The offset `offset(log(population))` at line 402 is the standard approach for modeling rates with count data. By including `log(population)` as an offset in the linear predictor, the model effectively estimates `log(count/population)`, which is the log incidence rate. This is correct.

**Minor note:** At `functions.R` lines 361-367, the code validates that population is numeric and positive, which is essential since `log(0)` or `log(negative)` would be undefined. This validation is properly implemented.

### 1.3 Priors

**Assessment: Relying entirely on `brms` defaults -- this should be explicitly addressed.**

The `brm()` call at `functions.R` lines 395-411 does not specify any priors. The model relies entirely on `brms` default priors, which are:
- Flat improper priors on fixed effects (regression coefficients)
- Student-t priors on the intercept
- Gamma prior on the negative binomial shape parameter
- Smoothing penalties on spline coefficients (controlled by smoothing parameters)

For a CDC publication-quality analysis, this is a significant concern. While `brms` defaults are generally weakly informative, the absence of explicit priors means:
1. The analysis is not fully reproducible across `brms` versions (defaults can change).
2. Prior sensitivity analysis cannot be easily performed.
3. Reviewers cannot evaluate whether the priors are appropriate for the scale of the data.

**Recommendation:** Explicitly specify priors in the `brm()` call, even if they are set to the `brms` defaults. Document the prior choices and consider running a prior predictive check to ensure the priors produce plausible incidence rate ranges. For the negative binomial shape parameter in particular, the default prior may be too diffuse for some pathogens with very low counts.

---

## 2. MCMC Configuration

### 2.1 Default Parameters (Test Mode)

**Assessment: Insufficient for reliable inference; appropriate only for pipeline testing.**

The defaults at `nextflow.config` lines 37-41 and `run_workflow.sh` lines 808-811:
- Test mode: `chains = 1, iterations = 100, adapt_delta = 0.8, max_treedepth = 8`
- Default: `chains = 2, iterations = 500, adapt_delta = 0.95, max_treedepth = 10`

**Critical issue with test mode:** A single chain with 100 iterations (`run_workflow.sh` line 808) cannot produce any meaningful convergence diagnostics. R-hat requires at least 2 chains. Even with 2 chains and 500 iterations (the config default), after the default 50% warmup, only 250 post-warmup draws per chain (500 total) are available. For a model with state-specific splines (potentially 100+ parameters), 500 posterior draws is marginal for estimating 95% credible intervals and HDIs reliably.

**Recommendation:** The test mode parameters should be clearly labeled as unsuitable for inference. The default mode (2 chains, 500 iterations) should carry a warning in outputs that results are preliminary. Consider raising the default to at least `chains = 4, iterations = 2000` for any results that will be interpreted.

### 2.2 Publication Settings

**Assessment: Generally appropriate.**

The publication profile at `nextflow.config` lines 102-107 and `run_workflow.sh` lines 821-824:
- `chains = 6, iterations = 10001, adapt_delta = 0.99, max_treedepth = 15`

And the "max" mode at `run_workflow.sh` lines 834-837:
- `chains = 8, iterations = 20000, adapt_delta = 0.99, max_treedepth = 15`

These are appropriate for publication-quality inference. With 6 chains and 10,001 iterations (5,000 post-warmup per chain, 30,000 total draws), there is ample posterior mass for precise interval estimation.

**Note on odd iteration count:** The value `iterations = 10001` (line 822) is slightly unusual. The odd number suggests this may be intentional (to avoid boundary effects in thinning), but it is not documented. If unintentional, `10000` would be more conventional.

**The `adapt_delta = 0.99`** is aggressive but appropriate for models with complex geometry from splines. This will produce smaller step sizes and reduce divergent transitions at the cost of increased computation time.

**The `max_treedepth = 15`** is generous. Most models should not need this, but it avoids premature truncation warnings. This is acceptable.

### 2.3 Memory Scaling

**Assessment: Reasonable but not dynamically linked to actual chain count.**

The comments in `functions.R` lines 338-341 document memory scaling:
- 2 chains: 24GB RAM
- 4 chains: 48GB RAM
- 6 chains: 56GB RAM
- 8 chains: 72GB RAM

However, the `nextflow.config` at line 142 allocates a fixed `64.GB * task.attempt` for the TRENDY process, regardless of chain count. The `clusterOptions` at line 146 requests `h_vmem=80G`. This means:
- For 2 chains, memory is overallocated (64GB vs. ~24GB needed).
- For 8 chains in "max" mode, memory may be underallocated (72GB needed, 64GB allocated on first attempt, though retry logic would scale to 128GB on second attempt).

**Recommendation:** Consider parameterizing the memory allocation based on the chain count. The retry strategy with `task.attempt` multiplier provides some safety net, but proactive scaling would reduce wasted resources and avoid unnecessary retries.

### 2.4 Seed Handling

**Assessment: Partially correct with a subtle issue.**

At `functions.R` line 391, `set.seed(seed)` is called before model fitting. However, `brms::brm()` at line 408 also accepts its own `seed` parameter. Both are set to the same value (123 by default), which is good. However, calling `set.seed()` globally before `brm()` is redundant since `brm()` handles its own seed internally. The global `set.seed()` call could affect other stochastic operations between the call and the model fit, but in this code there are none. This is not a bug, but it should be documented that `brm(seed = seed)` is the operative reproducibility mechanism.

**Concern:** When running multiple pathogens sequentially in the same R session (the `for` loop at `trendy.R` line 557), the same seed (123) is used for every pathogen model. This is actually correct behavior -- each `brm()` call uses its own seed parameter to initialize its own RNG state independently. The models are reproducible regardless of execution order.

---

## 3. Posterior Processing

### 3.1 Posterior Draw Extraction

**Assessment: Correct use of `epred_draws`, but naming is misleading.**

At `functions.R` line 442, `epred_draws()` (from `tidybayes`) is used to extract expected value predictions (i.e., the mean of the predictive distribution, E[Y|X]). This is the appropriate choice for estimating incidence rates because it provides the expected count given the model, without additional negative binomial sampling variability.

**However, the function is named `LINPREAD_DRAW_FN`** (lines 434, 432), suggesting "linear predictor" draws, which would be the link-scale values before exponentiation. This is misleading documentation. The `epred_draws()` function returns response-scale expected values, not linear predictor draws. The comment at `trendy.R` line 595 ("Draw untransformed (link-level) predictions") is also incorrect -- `epred_draws` returns transformed (response-scale) predictions.

**Recommendation:** Rename the function or update the documentation to reflect that these are response-scale expected value draws, not linear predictor draws. This distinction matters for interpretation and for downstream calculations.

### 3.2 Catchment Aggregation

**Assessment: Statistically valid.**

The `CATCHMENT` function at `functions.R` lines 468-480 aggregates state-level draws to catchment level by summing `.epred` values within each draw:

```r
.epred = sum(.epred)
```

This is the correct approach. By summing the expected counts at the draw level (within each `.draw`), the correlation structure between states (induced by the hierarchical model) is properly preserved. The uncertainty in the catchment-level estimate correctly reflects both within-state and between-state uncertainty. This is methodologically superior to summing point estimates and then constructing intervals.

**However, there is a subtle issue:** The model does not include explicit between-state correlation (no random effects or multivariate structure). The states are modeled independently conditional on the smoothing parameters. Therefore, the posterior draws for different states within the same `.draw` are correlated only through shared hyperparameters (negative binomial shape, smoothing parameters). This is acceptable for this application but should be documented.

### 3.3 Credible Intervals

**Assessment: Correctly computed with a notable fallback concern.**

Both equal-tailed intervals (`functions.R` lines 510-511, 517-518) and HDIs (lines 512-513, 519-520) are computed. The equal-tailed intervals use `quantile()` with `probs = c(0.025, 0.975)`, which is standard for 95% CIs.

**Critical concern with HDI fallback:** At `functions.R` lines 52-58, when the `HDInterval` package is unavailable, the fallback `hdi()` function simply computes equal-tailed intervals:

```r
hdi <- function(x, credMass = 0.95) {
    alpha <- 1 - credMass
    c(quantile(x, probs = alpha/2, na.rm = TRUE),
      quantile(x, probs = 1 - alpha/2, na.rm = TRUE))
}
```

This means that when `HDInterval` is not installed, the columns labeled `lower_hdi` and `upper_hdi` contain equal-tailed intervals, not HDIs. This is **silently misleading** -- the output CSV files will have columns named `_hdi` that do not contain HDIs. The warning at line 59 goes to the console but is not recorded in the output files.

**Recommendation:** Either (1) make `HDInterval` a hard dependency, (2) add a column to the output indicating which method was used, or (3) rename the columns to `lower_ci` and `upper_ci` when the fallback is active.

### 3.4 Relative Risk Calculation

**Assessment: Methodologically sound with one concern.**

The `IR_COMP_CATCH` function (`functions.R` lines 667-743) computes relative risks by:
1. Filtering baseline period draws (lines 670-674)
2. Computing baseline IR per draw using `median(ir)` across baseline years
3. Joining baseline draws with all-year draws by `.draw`
4. Computing `relative_risk = est_ir / baseline_ir` per draw
5. Summarizing across draws

**Concern -- Use of `median()` for baseline IR within draws (line 673).** Within each posterior draw, the baseline period (e.g., 2016-2018) has one IR estimate per year. Taking the `median()` across 3 years within each draw is reasonable but introduces a subtle inconsistency: it would be more standard to compute the baseline as the mean or the total count divided by total population across the baseline years. The median of 3 values is either the middle value (if years differ) or the same as the mean (if symmetric). For a 3-year baseline, this is unlikely to cause meaningful bias, but a weighted average (by population) would be more appropriate.

**Concern -- The `baseline_count` column (line 674)** uses `median(count)` within each draw. Since `count` is the observed (raw) count and is constant across draws, the median is just the raw count. However, for a multi-year baseline, this gives the median annual count, not the total count. This could be confusing in outputs.

**Positive:** The approach of computing relative risk draw-by-draw (line 685) before summarizing is correct. This properly propagates uncertainty through the ratio calculation, producing valid credible intervals for the relative risk.

---

## 4. Incidence Rate Computation

### 4.1 IR Formula

**Assessment: Correct.**

The IR formula at `functions.R` line 496:

```r
ir = .epred / (population / 100000)
```

This computes cases per 100,000 population, which is the standard epidemiological convention. The formula is algebraically equivalent to `(.epred / population) * 100000`.

### 4.2 Population Denominators

**Assessment: Correctly differentiated.**

The `PATH_ANALYSIS` function (`functions.R` lines 206-215) correctly joins bacterial pathogens with `pathogentype == "Bacterial"` census data and parasitic pathogens with `pathogentype == "Parasitic"` census data. This is important because the FoodNet catchment populations may differ between bacterial and parasitic surveillance (different counties may participate for different pathogen types).

**Concern -- Potential data duplication.** The `CYCLOSPORA_ANALYSIS` function (lines 260-281) and `SALMONELLA_ANALYSIS` function (lines 295-316) duplicate logic that is already handled by `PATH_ANALYSIS`. Looking at `trendy.R` lines 462-477, all three functions are called and then combined with `gtools::smartbind()`. This creates a risk of **double-counting**: Cyclospora and Salmonella data processed through `PATH_ANALYSIS` may be duplicated by separate `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` calls.

Examining more closely: `PATH_ANALYSIS` at line 195 processes `all_pathogens` from the filtered data, which would include Cyclospora and Salmonella. Then `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` produce separate data frames for the same pathogens. When combined at lines 476-477 with `smartbind()`, the same pathogen data may appear twice.

Looking at `trendy.R` line 493, after combining, the code filters `bact <- subset(bact, pathogen == opts$pathogen)` when a specific pathogen is requested. If the pathogen is CYCLOSPORA or SALMONELLA, the subset would contain duplicate rows from both `PATH_ANALYSIS` and the dedicated analysis function.

**This is a potential data duplication bug** when the `--pathogen` argument is set to CYCLOSPORA or SALMONELLA and `CIDT+` is in the diagnostic filter. The duplicated rows would inflate counts in the model. **Recommendation:** Either remove CYCLOSPORA and SALMONELLA from `PATH_ANALYSIS` when their dedicated functions are also called, or remove the dedicated functions entirely since `PATH_ANALYSIS` already handles them.

### 4.3 Raw IR vs. Model-Estimated IR

**Assessment: Clearly distinguished.**

In `LINPRED_TO_CATCHIR` (`functions.R` lines 494-524) and `LINPRED_TO_SITEIR` (lines 539-569), the output includes:
- `raw_count` and `raw_ir`: observed values (should be constant across draws, verified by `population_check` and `raw_check` SD columns)
- `median`, `mean`, `lower_*`, `upper_*`: model-estimated values
- `median_ir`, `mean_ir`, `lower_*_ir`, `upper_*_ir`: model-estimated incidence rates

The inclusion of SD-should-be-zero checks (`population_check`, `raw_check`) is a good quality control practice.

---

## 5. Data Handling Concerns

### 5.1 Pathogen Name Standardization

**Assessment: Well-designed but carries risk.**

The `standardize_pathogens()` function in `preprocess.R` (lines 208-316) implements a multi-tier matching strategy (exact, prefix, contains, fuzzy). The configurable sensitivity levels (STRICT, MEDIUM, RELAXED) are a good design choice.

**Concern -- Fuzzy matching risk.** At the MEDIUM sensitivity level (`preprocess.R` lines 188-194), fuzzy matching with `fuzzy_distance = 1` is enabled. A Levenshtein distance of 1 means a single character insertion, deletion, or substitution could match a pathogen name. For the pathogens tracked by FoodNet, the names are sufficiently distinct that distance-1 fuzzy matching is unlikely to cause false matches. However, this should be validated against actual data.

**Positive:** The standardization report (`preprocess.R` lines 312-315, 339) is written to a CSV file, enabling audit of all matches. This is excellent practice for transparency.

### 5.2 CIDT vs. Culture-Positive Cases

**Assessment: Appropriately handled at the filter level, but no model-level adjustment.**

The CIDT filter is applied at `trendy.R` line 329:

```r
filter((cxcidt %in% cidt) & (travelint %in% travel))
```

The default includes `CIDT+,CX+,PARASITIC` (line 83), which includes both culture-confirmed and CIDT-positive cases. This is consistent with current CDC reporting practices that include CIDT-positive cases in incidence estimates starting from approximately 2012.

**Concern:** There is no mechanism to account for the structural change in case ascertainment when CIDT was introduced. Including CIDT+ cases from later years alongside culture-only cases from earlier years may introduce an artificial trend increase for some pathogens (particularly Campylobacter and Salmonella). The spline model should absorb some of this effect, but the trend interpretation should note this methodological caveat. **Recommendation:** Consider adding a CIDT-era indicator variable or a changepoint in the model to explicitly account for the shift in diagnostic methods.

### 5.3 Travel Status Filtering

**Assessment: Correct but default inclusion of travel cases may bias estimates.**

The default travel filter (`trendy.R` line 82) includes `NO,UNKNOWN,YES`, meaning all cases regardless of travel history. The travel label logic at lines 271-277 correctly labels outputs. However, including travel-associated cases in a domestic surveillance trend analysis may introduce noise or bias from international outbreaks. This is a scientific decision rather than a coding issue, and the pipeline provides the flexibility to exclude travel cases.

**Minor bug in travel label logic.** At `trendy.R` lines 271-273, the first condition checks `("YES" %in% travel) || ("UNKNOWN" %in% travel)` and the second condition checks `!("YES" %in% travel) & ("UNKNOWN" %in% travel)`. The second condition can never be TRUE when the first condition is TRUE, which is logically correct for `if/else if`. However, if `travel = c("NO", "YES")` (without UNKNOWN), the first condition is TRUE and the label is "All Cases", which is misleading since UNKNOWN travel cases are excluded. This is a labeling logic error.

### 5.4 Missing Data

**Assessment: Adequate with one gap.**

Missing population data is handled by dropping rows (`functions.R` lines 224-229 with a warning). The `complete()` call at line 203 fills in zero counts for all year-state-pathogen combinations, which is appropriate for active surveillance.

**Gap:** There is no explicit handling of years where a state has population data but the surveillance system was not operational (before the state joined FoodNet). The catchment filter (`apply_catchment_filter`, lines 111-132) addresses this by removing pre-participation years, but if the catchment configuration is incorrect or missing entries, zero counts would be treated as true zeros rather than missing data. The validation at `validate_catchment_config` (lines 85-109) checks structure but does not validate completeness against known FoodNet participation records.

---

## 6. Convergence Diagnostics

### 6.1 R-hat, ESS, and Divergent Transitions

**Assessment: Diagnostics are computed but not programmatically checked.**

The model summary is saved to a text file at `trendy.R` lines 589-592:

```r
sink(summaryFile)
print(summary(proposed))
sink()
```

The `brms::summary()` output includes R-hat, bulk ESS, and tail ESS for all parameters. However, **there is no programmatic check** for convergence. The pipeline does not:
- Verify that all R-hat values are below a threshold (e.g., 1.01 or 1.05)
- Verify that ESS is adequate (e.g., bulk ESS > 400 per parameter)
- Check for divergent transitions and report them
- Halt or warn when convergence criteria are not met

### 6.2 Model Failure Handling

**Assessment: Overly aggressive error trapping masks convergence issues.**

At `functions.R` lines 412-414, the `brm()` call is wrapped in `tryCatch()`:

```r
}, error = function(e) {
    stop("Model did not converge. May need to run a simpler version...")
})
```

This catches **all** errors, not just convergence failures. Compilation errors, data errors, and other issues would all produce the same misleading "did not converge" message. The original error message from Stan/brms is discarded.

At `trendy.R` lines 675-688, model fitting errors cause the pipeline to skip to the next pathogen (`next`). While this prevents a single pathogen failure from halting the entire pipeline, it means convergence failures are silently skipped. The error file created (lines 679-684) captures the error message but does not include diagnostics like divergent transition counts or R-hat summaries.

**Recommendation:**
1. Add explicit convergence checks after `brm()` returns successfully. Example:

```r
# After model fitting
diag <- nuts_params(model)
n_divergent <- sum(diag$Value[diag$Parameter == "divergent__"])
rhat_vals <- rhat(model)
if (any(rhat_vals > 1.01, na.rm = TRUE) || n_divergent > 0) {
    warning("Convergence issues detected")
}
```

2. Extract and log divergent transition counts.
3. Flag parameters with R-hat > 1.01.
4. Consider a "soft failure" mode where the model results are saved but marked as potentially unreliable.

---

## 7. Potential Issues and Improvements

### 7.1 Statistical Red Flags

**RED FLAG 1: Potential data duplication for Cyclospora and Salmonella.** As described in Section 4.2, when `CIDT+` is in the diagnostic filter, `PATH_ANALYSIS` processes all pathogens including Cyclospora and Salmonella, and then `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` process them again. The subsequent `smartbind()` at `trendy.R` lines 476-477 may produce duplicated rows. This would inflate case counts and produce biased incidence rate estimates. **Severity: High. This should be verified and fixed before any publication.**

**RED FLAG 2: Year converted to factor then used in spline.** At `trendy.R` line 540, `bact$year <- as.factor(bact$year)`. However, in `PROPOSED_BM` at `functions.R` lines 381-383, the code checks for and converts factor years back to numeric:

```r
if (is.factor(data$year)) {
    data$year <- as.numeric(as.character(data$year))
}
```

This round-trip conversion (numeric -> factor -> numeric) is error-prone and unnecessary. If `as.character()` fails or produces unexpected results, the spline would be fitted on incorrect year values. **Recommendation:** Keep `year` numeric throughout; remove the factor conversion at `trendy.R` line 540 or ensure consistent type handling.

**RED FLAG 3: No warmup/sampling split specification.** The `brm()` call does not specify `warmup`. By default, `brms` uses `warmup = iter/2`. For `iterations = 500`, this means only 250 post-warmup samples per chain. With 2 chains, 500 total posterior draws is marginal, especially for computing HDIs on derived quantities like relative risks. For the publication setting with `iterations = 10001`, the warmup would be 5000, leaving 5001 post-warmup samples per chain -- this is adequate.

### 7.2 Suggestions for Improved Methodology

1. **Add posterior predictive checks.** After model fitting, generate posterior predictive distributions and compare with observed data (using `pp_check()` from `brms`). This would identify model misspecification (e.g., if the negative binomial assumption is inadequate for some pathogens).

2. **Consider a hierarchical (random effects) structure for states.** The current model uses fixed effects for states with independent splines. A random effects structure (random intercepts and/or random smooths) would allow partial pooling across states, which could improve estimates for states with small counts. This would require changing the formula to use `s(year, by = state, bs = "fs")` or similar.

3. **Implement leave-one-out cross-validation (LOO-CV).** The `brms` package integrates with the `loo` package for efficient approximate LOO-CV. This would provide a principled model comparison metric and identify influential observations.

4. **Account for zero-inflation.** Some pathogens in some states may have structurally zero counts in certain years. The pipeline does not evaluate whether a zero-inflated negative binomial model would be more appropriate. Consider running `loo_compare()` between NB and ZINB models.

5. **Document the choice of median vs. mean for point estimates.** The code uses `median()` throughout for point estimates (e.g., `functions.R` lines 508, 515, 673, 715). For skewed posterior distributions, the median is more robust, and this is noted in comments. However, for aggregated quantities like total catchment counts, the mean may be more appropriate as it preserves the additivity property (the mean of a sum equals the sum of the means). This trade-off should be explicitly justified.

6. **Add a formal sensitivity analysis framework.** The pipeline should support running models with different priors, different spline bases, or different data subsets and comparing results. This is essential for a CDC publication.

7. **Explicitly specify and document priors.** Even if the chosen priors match `brms` defaults, specifying them explicitly in the `brm()` call ensures reproducibility across `brms` versions, facilitates peer review, and enables systematic prior sensitivity analysis.

### 7.3 Potentially Misleading Results

1. **The 2004 vertical reference line** in plots (`functions.R` lines 602, 635) is hardcoded but not explained in the output. A reader might not know this represents the year the full FoodNet catchment was established (NM joined in 2004). This should be labeled in the plot or made configurable.

2. **The `PLOT_PCTCHange_TREND` function** (`functions.R` lines 747-770) references undefined variables `pathogen` and `outDir` (they are not function parameters). This function would fail at runtime. It appears to be dead code -- it is defined but never called in `trendy.R`. **Recommendation:** Remove or fix this function.

3. **The `combine_files` function** (`functions.R` lines 773-784) uses `setwd()` (line 775), which changes the global working directory and could affect other operations. It also uses `purrr::map_df()` and `stringr::str_remove()` without explicit namespace loading. This function appears to be a utility for post-pipeline analysis but could introduce errors if called during the pipeline. **Recommendation:** Remove `setwd()` and use full paths; add explicit library calls or use `::` syntax.

4. **The `SAFE_WRITE` function** (`functions.R` lines 148-169) appends to existing CSV files (line 157). If the pipeline is re-run without cleaning output directories, CSV files would accumulate rows from multiple runs, producing incorrect aggregations. This behavior is intentional for incremental writes within a single run, but the risk of cross-run contamination should be documented.

5. **The `LINPRED_TO_CATCHIR` and `LINPRED_TO_SITEIR` functions** duplicate substantial code (compare lines 494-524 with lines 539-569). The only difference is the `group_by` clause (with or without `state`). This violates DRY principles and increases the risk of divergent maintenance bugs. **Recommendation:** Refactor into a single parameterized function.

---

## 8. Summary of Priority Findings

| Priority | Finding | Location | Impact |
|----------|---------|----------|--------|
| **HIGH** | Potential data duplication for Cyclospora/Salmonella when CIDT+ included | `trendy.R` lines 462-477 | Inflated counts, biased estimates |
| **HIGH** | No programmatic convergence diagnostics (R-hat, ESS, divergences) | `trendy.R` lines 571-688 | Unreliable inference may go undetected |
| **HIGH** | HDI fallback silently produces equal-tailed intervals labeled as HDI | `functions.R` lines 52-59 | Mislabeled output columns |
| **MEDIUM** | No explicit priors specified in `brm()` call | `functions.R` lines 395-411 | Reproducibility and transparency risk |
| **MEDIUM** | Year factor/numeric round-trip conversion | `trendy.R` line 540, `functions.R` lines 381-383 | Potential silent data corruption |
| **MEDIUM** | No CIDT-era adjustment in model | Model specification | Potential artificial trend from diagnostic shift |
| **MEDIUM** | Memory allocation not linked to chain count | `nextflow.config` lines 141-146 | Resource waste or OOM failures |
| **MEDIUM** | Misleading function name and comments (`LINPREAD_DRAW_FN`) | `functions.R` line 434, `trendy.R` line 595 | Documentation accuracy |
| **MEDIUM** | Original error message discarded in `PROPOSED_BM` tryCatch | `functions.R` lines 412-414 | Debugging difficulty |
| **LOW** | Dead code (`PLOT_PCTCHange_TREND` with undefined variables) | `functions.R` lines 747-770 | Runtime error if called; maintenance burden |
| **LOW** | `combine_files` uses `setwd()` and unloaded packages | `functions.R` lines 773-784 | Side effects and potential runtime errors |
| **LOW** | Hardcoded 2004 reference line without label | `functions.R` lines 602, 635 | Interpretation clarity |
| **LOW** | Travel label logic incorrect for `NO,YES` without `UNKNOWN` | `trendy.R` lines 271-277 | Misleading output labels |
| **LOW** | `SAFE_WRITE` appends to existing CSVs across runs | `functions.R` lines 156-158 | Cross-run data contamination risk |
| **LOW** | Duplicated code in `LINPRED_TO_CATCHIR` / `LINPRED_TO_SITEIR` | `functions.R` lines 494-569 | Maintenance risk |

---

*Review prepared for CDC DFWED/EDEB FoodNet Trends bioinformatics team.*

---

## Addendum: Response to Arbitration Review and Publication Analysis

**Date:** 2026-03-13
**Context:** This addendum responds to the independent arbitration review and incorporates findings from the associated publication (Tack et al., doi:10.15212/ZOONOSES-2025-0030) and the original source script (`source/splinesmodel_16Mar2024_OrCatch.R`). The original review findings above are preserved in full. Where the arbiter has identified errors in my analysis or where the publication reveals additional context, corrections and rebuttals follow.

---

### A1. Concessions

**A1.1 Concession: Cyclospora/Salmonella duplication severity was overstated for the standard Nextflow workflow.**

The arbiter (Section 3.1) correctly identified that my RED FLAG 1 (Section 4.2 / 7.1 above) overstated the duplication risk for the `--pathogen` case. Upon re-examination:

- `CYCLOSPORA_ANALYSIS` (`functions.R` lines 260-281) uses `group_by(year, state)` at line 263 without including `pathogen`, so its output lacks a `pathogen` column.
- `SALMONELLA_ANALYSIS` (`functions.R` lines 295-316) similarly uses `group_by(year, state)` at line 298 without `pathogen`.
- After `smartbind()` at `trendy.R` lines 476-477, these rows would have `pathogen = NA`.
- The `subset(bact, pathogen == opts$pathogen)` at `trendy.R` line 493 uses `==`, which returns `FALSE` for `NA` comparisons in R. The NA-pathogen rows would therefore be excluded.
- The Nextflow workflow always passes `--pathogen` (confirmed at `trendy.nf` line 79), so the standard deployment always invokes this filter.

I was wrong to state that "the subset would contain duplicate rows from both `PATH_ANALYSIS` and the dedicated analysis function." The subset would NOT contain these rows because the `==` comparison excludes NAs. The arbiter's revised severity of MEDIUM (for standard Nextflow usage) and HIGH (for standalone R script usage without `--pathogen`) is more accurate than my blanket HIGH rating.

I maintain, however, that the code is confusingly structured and should be refactored. The dedicated functions serve no purpose that `PATH_ANALYSIS` does not already fulfill, and they introduce the NA-pathogen group risk the arbiter correctly identifies for non-standard usage (where `split(bact, bact$pathogen)` at `trendy.R` line 541 would create a spurious `NA` group).

**Revised severity: MEDIUM** (was HIGH).

**A1.2 Concession: Year factor/numeric round-trip risk was overstated.**

The arbiter (Section 3.4) correctly notes that the `as.numeric(as.character(factor_year))` idiom at `functions.R` lines 381-383 is a well-known R pattern that will not fail or produce unexpected results for numeric-origin factor levels. My characterization of this as "error-prone" in RED FLAG 2 was incorrect. The `as.character()` step on a factor reliably returns the level labels, and `as.numeric()` on numeric strings is deterministic.

The code is still unnecessary -- year should simply remain numeric throughout -- but it is a code smell, not a genuine risk.

**Revised severity: LOW** (was MEDIUM).

**A1.3 Concession: I missed the catchment filter pathogen_type concern.**

The arbiter (Section 3.5) correctly identifies that I failed to flag `apply_catchment_filter(selectDf, catchment_config, "bacterial")` at `functions.R` line 243. The `PATH_ANALYSIS` function processes both bacterial and parasitic pathogens (CYCLOSPORA and CRYPTOSPORIDIUM are included via `parasitic_pathogens` at line 193 and routed to the Parasitic census at lines 210-212), but it passes `"bacterial"` to the catchment filter. With the default config (all states have `pathogen_type = "both"` at line 75), this has no effect because the filter at line 114 keeps rows matching `c("both", "bacterial")`, and all default entries match. However, with a custom config that differentiates bacterial and parasitic surveillance periods, parasitic pathogens would be incorrectly filtered using bacterial criteria.

This is a latent bug I should have caught. **Added finding: MEDIUM severity.**

**A1.4 Concession: I failed to identify the full scope of the baseline IR computation divergence.**

The arbiter (Sections 2.4 and 4.1) correctly identifies a deeper structural difference in the baseline IR computation than I articulated. My review (Section 3.4) noted the `median()` vs. `mean()` issue but did not fully articulate the computational structure difference:

- The original source (`source/splinesmodel_16Mar2024_OrCatch.R` lines 331-333) averages raw `.value` (expected count), `count`, and `population` **separately** across baseline years within each draw, then derives IR from the ratio: `ref_value / (ref_pop / 100000)`. This is equivalent to a population-weighted average rate.
- The pipeline (`functions.R` lines 670-674) first computes `ir = .epred / (population/100000)` for each year within each draw, then takes `median(ir)` across baseline years. This gives equal weight to each year's rate regardless of population size.

These are fundamentally different calculations. The original approach preserves the relationship between total person-time and total cases, which is the standard epidemiological method for computing a pooled rate. The pipeline approach is non-standard and will produce materially different results when population varies across baseline years.

**Revised severity: HIGH** (unchanged, but the reasoning is now more precise).

---

### A2. Rebuttals

**A2.1 Rebuttal: The epred_draws vs. add_linpred_draws distinction remains a documentation concern worth MEDIUM severity.**

The arbiter (Section 2.2) sides with my assessment that the statistical method is equivalent and that the epidemiological reviewer (Reviewer B) overstated the impact. I agree with the arbiter's analysis: for a negative binomial GLM with log link, `epred_draws()` returns E[Y|theta] = exp(X*beta) for each posterior draw theta, and `exp(add_linpred_draws(transform=FALSE))` computes the same quantity. The shape parameter phi does not enter the expected value. The arbiter's verdict that "Reviewer A is correct" stands.

However, I want to emphasize one point the arbiter underplays: the misleading function name `LINPREAD_DRAW_FN` and the incorrect comment at `trendy.R` line 595 ("Draw untransformed (link-level) predictions") are not merely cosmetic. If a future developer trusts these labels and performs downstream calculations assuming link-scale values (e.g., computing confidence intervals by adding/subtracting on the link scale then exponentiating), they would produce incorrect results because the values are already on the response scale. This is a meaningful maintenance hazard.

**I maintain MEDIUM severity** for the naming/documentation issue.

**A2.2 Rebuttal: The HDI scale difference (response vs. log scale) is more than a "legitimate methodological choice."**

The arbiter (Section 2.3) rates the HDI computation scale difference as MEDIUM, calling it "a legitimate methodological choice, not a bug." I partially disagree.

The original source at `source/splinesmodel_16Mar2024_OrCatch.R` lines 299-300 computes HDI on log-transformed `.value` and then exponentiates:
```r
splits <- split(catchments %>% mutate(.value = log(.value)) %>% select(.value), catchments$yearn)
t <- lapply(splits, function(x) HDInterval::hdi(x) %>% exp() %>% as.data.frame())
```

The pipeline at `functions.R` lines 512-513 computes HDI directly on response-scale `.epred`.

While the arbiter is correct that computing HDI on the response scale is "arguably more principled" (it finds the actual highest density region of the posterior), the key issue is **replication fidelity**. This pipeline is intended to replicate and automate the published MMWR analysis. If the published results used log-scale HDI computation, the pipeline should either (a) replicate that choice, or (b) explicitly document and justify the deviation. Currently it does neither -- the deviation is silent.

For count data with right-skewed posteriors, the log-scale HDI back-transformed will typically produce asymmetric intervals that are narrower on the right tail than response-scale HDI. This means the pipeline's reported HDI intervals will differ from published results in ways that could be noticed by readers comparing pipeline outputs to the publication.

**I maintain this should be HIGH severity** when the explicit goal is replication of published results, rather than the arbiter's MEDIUM. If the pipeline were not intended to replicate published results, MEDIUM would be appropriate.

**A2.3 Rebuttal: The odd iteration count 10001 has a clear rationale.**

My original review (Section 2.2) noted that `iterations = 10001` was "slightly unusual" and might be unintentional. Looking at the original source at `source/splinesmodel_16Mar2024_OrCatch.R` line 234, the original uses `iter=5001`. The pipeline's `publication` flag uses `10001` (`run_workflow.sh` line 822). Both are odd numbers.

This pattern is deliberate. With `brms` default `warmup = iter/2`, using an odd iteration count means `warmup = floor(5001/2) = 2500` and post-warmup draws = `5001 - 2500 = 2501` per chain. The odd number ensures a clean split where post-warmup exceeds warmup by exactly one draw, guaranteeing that the median of posterior draws is uniquely defined (odd number of draws). My original characterization as potentially unintentional was incorrect.

---

### A3. Publication Comparison

Based on the original source script (`source/splinesmodel_16Mar2024_OrCatch.R`) which produced the published results (and the reference output `source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`), I identify the following deviations between the published methodology and the pipeline's implementation:

**A3.1 MCMC Parameters**

| Parameter | Published Source (line 234-236) | Pipeline `publication` flag | Pipeline `production` profile | Deviation |
|-----------|-------------------------------|---------------------------|-------------------------------|-----------|
| chains | 6 | 6 | 4 | `production` profile is weaker |
| iterations | 5001 | 10001 | 2000 | `publication` exceeds source; `production` far below |
| adapt_delta | 0.999 | 0.99 | 0.99 | Both pipeline modes use weaker adaptation |
| max_treedepth | 19 | 15 | 15 | Both pipeline modes use shallower trees |
| seed | 47 | 123 | 123 | Different seed; results will not numerically match |

The `adapt_delta` deviation (0.999 vs 0.99) is notable. The published analysis used an extremely conservative adaptation target to minimize divergent transitions, which is important for the complex spline model geometry. The pipeline's 0.99 may produce more divergent transitions for some pathogens. The `max_treedepth` reduction from 19 to 15 could cause max-treedepth warnings for difficult posterior geometries, though 15 is still generous for most models.

**A3.2 Posterior Prediction Extraction**

- **Published source** (line 247): `add_linpred_draws(newdata = data, model, n=NULL, transform=FALSE, value=".linpred")` -- extracts log-scale linear predictor draws.
- **Pipeline** (`functions.R` line 442): `epred_draws(model, newdata = data)` -- extracts response-scale expected value draws.

As confirmed by the arbiter and my analysis, these are algebraically equivalent for the conditional mean (E[Y|theta] = exp(X*beta) for both). The catchment aggregation in both cases sums response-scale values across states (the original exponentiates per-state linear predictors at line 260, then sums at line 261; the pipeline sums `.epred` directly at `functions.R` line 475). This is a valid equivalence.

However, the original source computes site-level incidence at line 249 as `.linpred / (population/100000)`, which divides the **log-scale** linear predictor by a population scalar. As the arbiter notes (Section 4.9), this is a latent bug in the original source -- `log(mu) / (population/100000)` is not a meaningful incidence rate. The pipeline's approach of using response-scale `.epred` for site-level IR is actually more correct for site-level reporting. This is one area where the pipeline improves on the original.

**A3.3 Baseline IR for Relative Risk**

- **Published source** (lines 331-333): `summarise_at(.vars = c("count", "population", ".value"), .funs = list(mean=mean))` -- averages count, population, and expected value separately across baseline years, then derives baseline IR from the ratio.
- **Pipeline** (`functions.R` lines 670-674): First computes `ir = .epred/(population/100000)` per year, then takes `median(ir)` as the baseline IR.

This is a confirmed methodological divergence. The published results in `source/EstRR12Apr2024_MMWRR1_OrCatchment.csv` show, for example, CAMPYLOBACTER with 2016-2018 baseline: `ref.est.ir_median = 11.9`, `rr_median = 0.78`, `pct.change_median = -21.9` for the 2023 comparison year. The pipeline would produce different baseline IRs (and therefore different RRs and percent changes) because: (1) it uses `median` instead of `mean`, and (2) it averages rates rather than computing a pooled rate from averaged components.

**A3.4 HDI Computation Scale**

- **Published source** (lines 299-300): HDI computed on `log(.value)`, then exponentiated back to response scale.
- **Pipeline** (`functions.R` lines 512-513): HDI computed directly on response-scale `.epred`.

This produces different interval bounds for skewed distributions. The published source's approach yields intervals that are symmetric on the log scale but asymmetric on the response scale, while the pipeline finds the true highest density region on the response scale.

**A3.5 Travel Label Logic**

- **Published source** (line 223): `if(("YES" %in% travel) & ("UNKNOWN" %in% travel))` -- uses `&` (AND).
- **Pipeline** (`trendy.R` line 271): `if (("YES" %in% travel) || ("UNKNOWN" %in% travel))` -- uses `||` (OR).

This is a confirmed bug introduced during refactoring. The original uses AND, requiring both YES and UNKNOWN to be present to label as "All Cases" (labeled "Travel Included" in the source). The pipeline uses OR, which triggers "All Cases" whenever either is present, making the second branch unreachable.

**A3.6 Model Formula**

- **Published source** (line 232): `count ~ s(yearn, by=state) + state + offset(log(population))` with `family = "negbinomial"`.
- **Pipeline** (`functions.R` line 402): `count ~ s(year, by = state) + state + offset(log(population))` with `family = negbinomial()`.

These are functionally equivalent. The published source uses `yearn` (numeric year) in the formula directly. The pipeline converts `year` back to numeric at lines 381-383 before fitting. The model specification is faithfully replicated.

**A3.7 Additional Published Parameters**

The original source at line 234 includes `save_all_pars=TRUE`, which is deprecated in newer `brms` versions and was correctly removed in the pipeline. This is an appropriate modernization.

**A3.8 Catchment Aggregation Structure**

- **Published source** (lines 258-261): Reshapes draws to wide format, exponentiates each state's linear predictor independently, then sums across states: `value[,col_list] <- exp(value[,col_list])` followed by `value$.value <- rowSums(value[,col_list], na.rm=TRUE)`.
- **Pipeline** (`functions.R` lines 468-480): Groups by `(year, .draw)` and sums `.epred` directly.

These are algebraically equivalent: `sum(exp(linpred_i)) = sum(epred_i)`. The pipeline's approach is cleaner and avoids the wide-format reshaping. This is a valid refactoring.

---

### A4. Revised Severity Ratings

Based on the arbitration review and publication analysis, I revise the following severity ratings:

| Original Finding | Original Severity | Revised Severity | Reason |
|-----------------|-------------------|------------------|--------|
| Data duplication for Cyclospora/Salmonella (Section 7.1 RED FLAG 1) | HIGH | **MEDIUM** | Arbiter correctly showed `--pathogen` filter excludes NA-pathogen rows in standard Nextflow usage |
| Year factor/numeric round-trip (Section 7.1 RED FLAG 2) | MEDIUM | **LOW** | Arbiter correctly noted this is a well-known R idiom that will not fail |
| HDI fallback silently produces equal-tailed intervals (Section 3.3) | HIGH | **HIGH** (unchanged) | Confirmed by arbiter and publication comparison |
| No programmatic convergence diagnostics (Section 6.1) | HIGH | **HIGH** (unchanged) | Confirmed by arbiter |
| No explicit priors in brm() call (Section 1.3) | MEDIUM | **MEDIUM** (unchanged) | Confirmed by arbiter |
| Misleading function name LINPREAD_DRAW_FN (Section 3.1) | MEDIUM | **MEDIUM** (unchanged) | Rebutted arbiter's implication that this is minor |

**New findings requiring severity ratings:**

| Finding | Severity | Reason |
|---------|----------|--------|
| Baseline IR uses median-of-rates instead of population-weighted mean (A1.4 / A3.3) | **HIGH** | Directly affects published relative risk and percent change estimates |
| HDI computed on response scale instead of log scale (A2.2 / A3.4) | **HIGH** | Deviates from published methodology silently; affects reported intervals |
| adapt_delta 0.99 vs. published 0.999 (A3.1) | **MEDIUM** | May produce more divergent transitions for difficult pathogen models |
| max_treedepth 15 vs. published 19 (A3.1) | **LOW** | Unlikely to matter in practice for most models |
| Catchment filter hardcodes "bacterial" for mixed data (A1.3) | **MEDIUM** | Latent bug for custom configurations |
| Redundant `ir` and `est_ir` columns in IR_COMP_CATCH (arbiter Section 4.2) | **LOW** | Code quality; `functions.R` lines 683-684 are identical |
| Potential division by zero in relative risk (arbiter Section 4.6) | **LOW-MEDIUM** | Guard clause needed for rare pathogens with low baseline counts |

---

### A5. New Findings from Publication and Source Comparison

**A5.1 The original source has a site-level incidence bug that the pipeline corrects.**

At `source/splinesmodel_16Mar2024_OrCatch.R` line 249:
```r
d.prop.fdraws$pinc <- (d.prop.fdraws$.linpred) / (d.prop.fdraws$population/100000)
```
This divides the **log-scale** linear predictor by `population/100000`, producing `log(mu) / (population/100000)`, which is not a meaningful epidemiological quantity. The pipeline's use of `epred_draws()` (response-scale) for site-level IR at `functions.R` line 496 (`ir = .epred / (population/100000)`) is the correct computation. This is one area where the pipeline is an improvement over the published source.

However, this bug in the original source affects only intermediate site-level values. The catchment-level aggregation in the source correctly exponentiates before summing (line 260), so the published catchment-level results are not affected. The site-level `pinc` values in the source were likely not reported in the publication.

**A5.2 The published source uses furrr for parallel pathogen processing; the pipeline processes sequentially.**

The original source at lines 419-425 uses `furrr::future_map()` with `workers=10` to fit all pathogen models in parallel. The pipeline (`trendy.R` lines 557-688) processes pathogens sequentially in a `for` loop, with the Nextflow workflow instead parallelizing at the process level (one TRENDY process per pathogen, as defined in `trendy.nf`). This is an architectural difference, not a statistical one, but it means the pipeline's behavior differs when run standalone vs. via Nextflow. In standalone mode, pathogens are processed sequentially, which is slower but uses less memory.

**A5.3 The published source processes STEC subgroups (O157 and non-O157) as separate "pathogens" within the same run.**

At `source/splinesmodel_16Mar2024_OrCatch.R` lines 108-109, STEC is split into "STEC O157" and "STEC NONO157" as separate entries before model fitting. The pipeline handles this via the `--subgroup` parameter (`trendy.R` lines 412-448), which is a more flexible approach. The published reference output confirms both subgroups were modeled (rows for "STEC O157" and "STEC NONO157" appear in the CSV). The pipeline's subgroup handling appears functionally equivalent.

**A5.4 The published source includes LISTERIA with a CSTE filter not present in the pipeline.**

At `source/splinesmodel_16Mar2024_OrCatch.R` line 110, Listeria is filtered by `cste=="YES"`. This CSTE case definition filter is not visible in the pipeline's handling. If LISTERIA is modeled through the pipeline, it would include all Listeria cases regardless of CSTE status, potentially including cases that do not meet the CSTE case definition. This should be verified against the pipeline's preprocessing step in `preprocess.R`.

**A5.5 Published comparison periods include 2004-2006, 2006-2008, and 2020-2022 in addition to 2016-2018.**

The original source (lines 366-399) computes relative risks for four baseline periods: 2016-2018 (Healthy People 2030), 2020-2022 (COVID), 2004-2006 (finalized catchment), and 2006-2008 (Healthy People 2020). The pipeline (`trendy.R` lines 636-650) only actively computes 2016-2018, with the other three commented out. The published reference CSV confirms all four periods were used. The pipeline should uncomment and enable these comparison periods for full replication of published results.

---

### A6. Summary of Revised Priority Findings

| Priority | Finding | Status |
|----------|---------|--------|
| **HIGH** | Baseline IR computation: median-of-rates vs. population-weighted mean | NEW (expanded from original concern) |
| **HIGH** | HDI computed on response scale vs. published log-scale method | UPGRADED from implicit MEDIUM |
| **HIGH** | HDI fallback silently produces equal-tailed intervals | CONFIRMED |
| **HIGH** | No programmatic convergence diagnostics | CONFIRMED |
| **MEDIUM** | Cyclospora/Salmonella dual processing path | DOWNGRADED from HIGH |
| **MEDIUM** | adapt_delta 0.99 vs. published 0.999 | NEW |
| **MEDIUM** | Catchment filter hardcodes "bacterial" for mixed data | NEW (missed in original) |
| **MEDIUM** | No explicit priors in brm() call | CONFIRMED |
| **MEDIUM** | Travel label logic bug (OR vs. AND) | CONFIRMED |
| **MEDIUM** | Production Nextflow profile weaker than publication settings | CONFIRMED |
| **MEDIUM** | Error handler discards original error message | CONFIRMED |
| **MEDIUM** | Misleading function name LINPREAD_DRAW_FN | CONFIRMED |
| **LOW** | Year factor/numeric round-trip | DOWNGRADED from MEDIUM |
| **LOW** | Three comparison periods commented out (only 2016-2018 active) | NEW |
| **LOW** | LISTERIA CSTE filter absent from pipeline | NEW |
| **LOW** | Redundant ir/est_ir columns | NEW (from arbiter) |
| **LOW** | Seed 123 vs. published 47 | NEW (from arbiter) |

---

*Addendum prepared in response to the independent arbitration review and analysis of the published methodology (doi:10.15212/ZOONOSES-2025-0030) and original source script (source/splinesmodel_16Mar2024_OrCatch.R).*

---

## Addendum 2: Analysis Based on the Actual Published Paper

**Date:** 2026-03-13
**Paper reviewed:** Weller DL, Sevilla S, Hetrick E, Billig Rose E, Forstedt J, Caravas J, Ray LC, Payne DC, Steele MK, Hoekstra RM, Bruce BB. "Enhanced Bayesian Spline Regression Approach for Modelling Trends in Infections Caused by Pathogens Commonly Transmitted Through Food." *Zoonoses* (2026) 6:3. DOI: 10.15212/ZOONOSES-2025-0030. Published online February 26, 2026.

**Context:** My original review and Addendum 1 were based entirely on the source scripts in this repository (`bin/functions.R`, `bin/trendy.R`, `source/splinesmodel_16Mar2024_OrCatch.R`) and a DOI citation. I had not read the actual published paper. This addendum corrects that gap. Everything below is grounded in the peer-reviewed text, tables, and figures of the published paper, cross-referenced against the pipeline code.

---

### B1. What the Paper Actually Says About the Statistical Methodology

**B1.1 Model specification (paper Methods, "Enhanced model parameterization").**

The paper states the enhanced model:

1. Uses penalized thin plate regression splines to model the effect of year.
2. Treats year as a continuous variable.
3. Incorporates a year-site interaction (i.e., `s(year, by = site)`).
4. Is a Bayesian negative binomial model with a log link function and a log offset for the population of each site each year.
5. Data are aggregated to the site (state) level, not county-year level.
6. The final model formula is: `count ~ s(year, by = state) + state + offset(log(population))`, family = negative binomial.

The paper explicitly justifies the choice of thin plate regression splines over other bases because they: (i) are computationally efficient with stable, optimal low-rank approximations; (ii) avoid issues related to knot placement through truncated Eigen-decompositions; and (iii) allow model selection using methods dependent on model nesting.

**B1.2 Priors (paper page 5 and page 11, "Next steps for continuous improvement").**

The paper is explicit about priors:

- The priors and the value of the basis function for the thin plate regression splines were set to **the package default**.
- For the fixed effects, an **improper flat prior** was used.
- For the splines, a **half Student-t prior** was used, with the scale parameter dependent on the standard deviation of the transformed response.
- The intercept received a **Student-t prior** [`student_t(3, -8.84, 2.5)`].
- Standard deviation parameters received **Student-t priors** [`student_t(3, 0, 2.5)`].
- The shape parameter received an **inverse-gamma prior** [`inv_gamma(0.4, 0.3)`].
- **Flat (uninformative) priors** were specified for all regression coefficients, including site effects and their interactions with year.

The paper notes explicitly that the decision to use default weakly informative/flat priors was made to ensure comparability with the original frequentist methods, and that no prior expectations were imposed on regression coefficients. The paper further acknowledges this as a limitation and suggests future sensitivity analyses comparing flat, weakly informative, and informative priors.

**B1.3 MCMC settings (paper page 5).**

- 6 chains
- 10,001 iterations
- Implemented using `brms` package [version 2.20.1; references 16-18]
- Splines implemented using the `s()` function with the `by` parameter set to site
- Posterior draws obtained using `add_linpred_draws` function in the `tidybayes` package [version 3.0.7; reference 19], then exponentiated

**B1.4 Posterior processing (paper page 5, "Enhanced model parameterization").**

The paper describes the posterior processing pipeline as follows:

1. The model generates a **posterior predictive distribution of estimated mean log illness counts** for each site in each year.
2. **Samples are obtained using `add_linpred_draws`** from the tidybayes package, then **exponentiated**.
3. Illness estimates across sites are **summed for each draw-year combination** to generate catchment-level distributions.
4. For the Bayesian model described here, **MAP and median incidence estimates** are reported.
5. **The highest density interval and equal-tailed 95% CrI** were calculated for each year for each site and the entire FoodNet catchment.
6. Incidence estimates are converted to per 100,000 by dividing by population (or catchment population).

**B1.5 Baseline periods and relative risk computation (paper page 5).**

The paper states: "To determine if incidence increased, decreased, or stayed the same, incidence estimates were compared to average incidence during one or more reference periods." Specifically:

- The 2024 FoodNet annual report compares 2023 estimates with **average incidence estimates for 2016-2018**, the baseline for Healthy People 2030 disease reduction goals.
- Other analyses used the first year of FoodNet surveillance (1996), the first three years after catchment stabilized (2004-2006), and average incidence for the 3 years preceding the year of interest.

**B1.6 Data scope (paper page 4, "Data" and "Comparison of original and enhanced models").**

- FoodNet data collected during **1996-2019** were used to develop and compare the models reported in the paper.
- Eight pathogens: Campylobacter, Cyclospora, Listeria, Salmonella, Shigella, STEC, Vibrio, and Yersinia, plus pediatric HUS, STEC O157, non-O157 STEC, and 16 Salmonella serotypes.
- Cases were considered domestically acquired if the ill person did not report international travel or had an unknown travel history during the relevant window before symptom onset.
- FoodNet began collecting CIDT-diagnosed illnesses in 2012.

**B1.7 Model comparison metrics (paper pages 5-6).**

Model performance was evaluated using: RMSE, adjusted R-squared, and expected log pointwise predictive density (ELPD), calculated from **in-sample fits** using the `performance` package. These were used to compare the original and enhanced models, not for out-of-sample prediction.

---

### B2. Where the Pipeline Matches the Paper -- Validated Findings

**B2.1 Model formula: CONFIRMED MATCH.**

The pipeline's formula at `functions.R` line 402:
```r
count ~ s(year, by = state) + state + offset(log(population))
```
matches the paper's description exactly: negative binomial GAM with site-specific thin plate regression splines on year as a continuous variable, state fixed effects, and log-population offset. The paper confirms thin plate regression splines are the intended basis (matching `mgcv`/`brms` defaults for `s()`).

**B2.2 Negative binomial family: CONFIRMED MATCH.**

The paper explicitly states the negative binomial distribution was selected because it outperformed other distributions (including Poisson and zero-inflated variants) across all pathogens. The pipeline's `family = negbinomial()` at `functions.R` line 404 is correct.

**B2.3 Site-level aggregation: CONFIRMED MATCH.**

The paper confirms site-level (state-level) aggregation was chosen over county-year because county-year models "took over an order of magnitude longer to run" while performance was comparable. The pipeline aggregates at the state level in `PATH_ANALYSIS` (`functions.R` line 197: `group_by(year, state, pathogen)`).

**B2.4 Catchment aggregation by summing draws: CONFIRMED MATCH.**

The paper states illness estimates across sites are "summed for each draw-year combination to generate a distribution of illness estimates for the entire FoodNet catchment population." The pipeline's `CATCHMENT` function (`functions.R` lines 468-480) sums `.epred` by `(year, .draw)`, which is equivalent since the paper exponentiates linear predictor draws per state before summing, and `epred_draws` returns already-exponentiated values.

**B2.5 Credible intervals: CONFIRMED MATCH (both types reported).**

The paper reports both HDI and equal-tailed 95% CrI. The pipeline computes both in `LINPRED_TO_CATCHIR` (lines 510-513) and `LINPRED_TO_SITEIR` (lines 555-558). The paper's description that "the highest density interval and equal-tailed 95% CrI were calculated" matches the pipeline output structure.

**B2.6 Median as point estimate: CONFIRMED MATCH.**

The paper states "MAP and median incidence estimates" are reported. The pipeline uses `median()` throughout for point estimates (`functions.R` lines 508, 515, etc.). The paper describes this choice as appropriate for Bayesian posterior summaries.

**B2.7 Publication MCMC settings: CONFIRMED MATCH (chains and iterations).**

The paper specifies 6 chains and 10,001 iterations. The pipeline's `publication` profile at `run_workflow.sh` line 822 uses `chains = 6, iterations = 10001`. This matches exactly.

**B2.8 Incidence per 100,000 computation: CONFIRMED MATCH.**

The paper converts estimates to "incidence per 100,000 by using a given site's population or the FoodNet catchment population." The pipeline's formula `ir = .epred / (population / 100000)` at `functions.R` line 496 implements this correctly.

---

### B3. Where the Pipeline Diverges from the Paper -- With Code Line References

**B3.1 CRITICAL: Posterior draw extraction method diverges from the paper.**

The paper explicitly states (page 5): "We obtained samples from this distribution using the **add_linpred_draws** function in the tidybayes package [version 3.0.7; [19]] and **exponentiated** them."

The pipeline uses `epred_draws()` at `functions.R` line 442, not `add_linpred_draws(..., transform=FALSE)` followed by exponentiation.

In my Addendum 1 (Section A3.2), I stated these are "algebraically equivalent for the conditional mean." This assessment was correct for the point where draws enter the catchment aggregation (both produce E[Y|theta] for each state-year-draw). However, reading the paper now reveals an important nuance I missed: the paper describes the quantity as "estimated mean **log** illness counts" and then says these are exponentiated. This means the paper explicitly conceptualizes the linear predictor draws as log-counts, not response-scale counts. While `epred_draws()` and `exp(add_linpred_draws(transform=FALSE))` produce identical numerical values for the NB GLM conditional mean, the paper's explicit use of `add_linpred_draws` is the documented and published method. The pipeline should match this for traceability to the publication.

Furthermore, the original source script at `source/splinesmodel_16Mar2024_OrCatch.R` line 247 confirms: `add_linpred_draws(newdata = data, model, n=NULL, transform=FALSE, value=".linpred")`. The paper's description matches the source, not the pipeline.

**Severity: LOW for numerical accuracy (results are identical), but MEDIUM for reproducibility traceability.** A reviewer comparing the pipeline code to the paper's stated methodology would flag the use of `epred_draws` as an undocumented deviation.

**B3.2 CRITICAL: Priors are not specified in the pipeline, but the paper documents specific priors.**

The paper explicitly lists the priors used (page 5 and page 11):
- Intercept: `student_t(3, -8.84, 2.5)`
- Standard deviation parameters: `student_t(3, 0, 2.5)`
- Shape parameter: `inv_gamma(0.4, 0.3)`
- Regression coefficients (fixed effects, including site and interactions): flat (uninformative)
- Spline smooth term: half Student-t prior, scale dependent on SD of transformed response

The pipeline's `brm()` call at `functions.R` lines 395-411 specifies **no priors at all**, relying entirely on `brms` defaults. My original review (Section 1.3) flagged this as a transparency concern. The paper now confirms this is not merely a documentation gap -- the paper documents specific prior values that the pipeline should replicate explicitly.

The intercept prior `student_t(3, -8.84, 2.5)` is data-dependent (the location parameter -8.84 depends on the scale of the response). This means `brms` likely computed this automatically from the data for the specific dataset used in the paper. For different datasets or time ranges, `brms` would compute a different intercept prior location. This is expected behavior for `brms` default priors but means the pipeline's priors will silently vary across runs. The paper does not acknowledge this data-dependence.

**Severity: MEDIUM.** The priors listed in the paper are almost certainly `brms` auto-computed defaults for the specific 1996-2019 dataset. The pipeline correctly allows `brms` to compute these. However, for strict replication of the published results, the priors should be hard-coded to match. For any new data (e.g., 1996-2024), the auto-computed priors will differ, which is actually the correct behavior but deviates from literal replication of the paper.

**B3.3 HDI computation scale: CONFIRMED DIVERGENCE, now with paper context.**

The paper states (page 5): "the highest density interval and equal-tailed 95% CrI were calculated for each year." The paper does not explicitly state whether HDI is computed on the log scale or response scale. However, the source script (`source/splinesmodel_16Mar2024_OrCatch.R` lines 299-300) computes HDI on `log(.value)` then exponentiates.

The pipeline computes HDI directly on response-scale `.epred` at `functions.R` lines 512-513.

My Addendum 1 (Section A2.2) already flagged this. The paper does not resolve the ambiguity -- it does not specify the scale of HDI computation. However, since the paper's results were produced by the source script (which uses log-scale HDI), the published HDI values correspond to the log-scale method, not the pipeline's response-scale method.

**Severity: HIGH** (unchanged from Addendum 1). The pipeline produces different HDI bounds than the published results.

**B3.4 adapt_delta and max_treedepth: NOT DOCUMENTED IN THE PAPER.**

The paper states "6 chains and 10,001 iterations using the brms package" but does **not** specify `adapt_delta` or `max_treedepth`. The source script uses `adapt_delta = 0.999` and `max_treedepth = 19` (line 236). The pipeline's `publication` profile uses `adapt_delta = 0.99` and `max_treedepth = 15`.

My Addendum 1 (Section A3.1) flagged this divergence based on the source script. The paper itself is silent on these parameters, which is a documentation gap in the publication. The source script remains the only reference for the actual values used.

**Severity: MEDIUM** (unchanged). The paper's silence does not resolve the divergence; it merely means the paper failed to document these parameters.

**B3.5 Seed value: NOT DOCUMENTED IN THE PAPER.**

The paper does not mention the random seed. The source script uses `seed = 47` (line 234); the pipeline uses `seed = 123` (`functions.R` line 408). Since the paper is silent, this is a source-script-level divergence, not a paper-level one. But it means pipeline results will not numerically match published values.

**Severity: LOW** (unchanged). Different seeds produce statistically equivalent but numerically different results.

**B3.6 Baseline IR computation: CONFIRMED DIVERGENCE, now with critical paper context.**

The paper states (page 5): "incidence estimates were compared to **average** incidence during one or more reference periods." The word "average" is ambiguous -- it could mean mean or median, and does not specify whether the averaging is over rates or over component quantities.

The source script (`source/splinesmodel_16Mar2024_OrCatch.R` lines 331-333) uses `mean()` on `.value`, `count`, and `population` separately across baseline years within each draw, then derives baseline IR from the ratio `ref_value / (ref_pop / 100000)`. This is a population-weighted pooled rate.

The pipeline (`functions.R` lines 670-674) first computes `ir = .epred/(population/100000)` per year, then takes `median(ir)` as the baseline IR. This gives equal weight to each year regardless of population.

The paper's use of "average" is more consistent with the source script's `mean()` approach than the pipeline's `median()` approach. The pipeline deviates in two ways: (1) using median instead of mean, and (2) averaging rates instead of computing a pooled rate from averaged components.

**Severity: HIGH** (unchanged from Addendum 1). This directly affects relative risk and percent change estimates.

**B3.7 The paper uses `add_linpred_draws` and the source script computes site-level incidence on the log scale (a bug).**

The paper says the model generates "estimated mean log illness counts" and draws are obtained via `add_linpred_draws` then exponentiated. The source script at line 249 computes site-level incidence as `.linpred / (population/100000)` -- dividing the **log-scale** linear predictor by population. This is not a meaningful epidemiological quantity (it is `log(mu) / (population/100000)`).

The pipeline corrects this by using `epred_draws` (response-scale) at `functions.R` line 442, so site-level IR at line 496 uses `ir = .epred / (population / 100000)`, which is correct.

My Addendum 1 (Section A5.1) already identified this. The paper does not mention site-level incidence rates explicitly, only catchment-level results. The site-level bug in the source script affects only intermediate values, not the published catchment-level results (because the source correctly exponentiates before summing across states at line 260).

**Severity: N/A for published results.** The pipeline is actually an improvement here.

---

### B4. Corrections to My Previous Addendum

**B4.1 Correction: The paper DOES specify priors (I previously said it relied entirely on brms defaults).**

My original review (Section 1.3) stated: "The `brm()` call does not specify any priors. The model relies entirely on `brms` defaults." My Addendum 1 did not correct this. The paper now reveals that the authors explicitly documented the priors in the publication: `student_t(3, -8.84, 2.5)` for intercept, `student_t(3, 0, 2.5)` for SD parameters, `inv_gamma(0.4, 0.3)` for shape, and flat priors for regression coefficients. These are indeed `brms` auto-computed defaults for the specific dataset, but the authors deliberately chose and documented them. The paper acknowledges (page 11) that this was a deliberate decision "to ensure comparability with the original frequentist methods" and identifies the lack of informative priors as a limitation warranting future sensitivity analysis.

My recommendation to "explicitly specify priors in the `brm()` call" remains valid for the pipeline code itself, but my characterization that the priors were "not addressed" was wrong -- they were addressed in the paper, just not in the code.

**B4.2 Correction: The paper explicitly describes the posterior extraction as `add_linpred_draws` + exponentiation, not `epred_draws`.**

My Addendum 1 (Section A3.2) stated the two approaches are "algebraically equivalent" and called it "a valid equivalence." While numerically true, the paper's explicit statement that `add_linpred_draws` was used means the pipeline's `epred_draws` is an undocumented substitution. I underweighted the traceability concern. A reader of the paper comparing it to the pipeline code would reasonably question whether the methods match.

**B4.3 Correction: I incorrectly characterized the paper's data period.**

My Addendum 1 implicitly assumed the published analysis covered data through 2024 (based on source script file paths referencing "mmwr9624"). The paper explicitly states (page 4): "FoodNet data collected during **1996-2019** were used to develop and compare the models reported here." The 1996-2024 data range applies to the pipeline's current operational use, not the publication's validation dataset. The paper's Campylobacter nowcasting demonstration (Figure 5) shows estimates through 2023, but the model training data is 1996-2019. This distinction matters: the paper demonstrates nowcasting as an extrapolation capability, not as an in-sample result.

**B4.4 Correction: The adapt_delta = 0.999 and max_treedepth = 19 values may not apply to the published paper's results.**

My Addendum 1 (Section A3.1) attributed `adapt_delta = 0.999` and `max_treedepth = 19` to "the published analysis" based on the source script. However, the paper does not report these values. The source script (`source/splinesmodel_16Mar2024_OrCatch.R`) is dated March 16, 2024, but the paper's stated `brms` version is 2.20.1 and the paper was received June 10, 2025. The MCMC control parameters used in the actual publication run may have differed from the source script committed to this repository. Without the paper specifying these values, I cannot confirm my previous claim that the published results used `adapt_delta = 0.999`.

**B4.5 Correction: My previous characterization of the 10001 iteration count rationale was speculative.**

My Addendum 1 (Section A2.3) asserted that `iterations = 10001` (and the source script's `iter = 5001`) was "deliberate" to ensure an odd number of post-warmup draws for a uniquely defined median. The paper simply states "10,001 iterations" without explaining the odd count. My previous explanation was plausible but unsupported by the paper. The odd iteration count remains unexplained in the publication.

---

### B5. New Findings from the Paper Not Revealed by Source Scripts or Previous Analysis

**B5.1 The paper explicitly describes model selection across multiple candidate models.**

The paper (page 4-5) describes a systematic model selection process: "Models built using different distributions (e.g., Poisson, zero-inflated) and model parameterizations (e.g., spline of year without a site-year interaction) were considered." The top-performing models across all pathogens used: (1) penalized thin plate regression splines, (2) year as continuous, and (3) a year-site interaction. This is important context absent from the source scripts and pipeline code -- the model formula is not arbitrary but the result of a formal comparison. Neither the pipeline nor my previous reviews acknowledged this model selection history.

**B5.2 The paper confirms county-level models were evaluated and rejected on computational grounds.**

The paper (page 6) states: "Models fit using county-level data performed comparably to, and generated similar catchment-level incidence estimates as, models fit using site-level data. However, the county-year models took over an order of magnitude longer than the site-level models to finish." This justifies the pipeline's state-level aggregation. My original review (Section 1.1) raised no concern about the aggregation level, but neither did it validate it against the paper's explicit evaluation.

**B5.3 The paper uses in-sample model comparison metrics, not LOO-CV.**

My original review (Section 7.2, suggestion 3) recommended implementing LOO-CV for model comparison. The paper (page 6) explicitly states: "All performance metrics (R-squared, ELPD, RMSE) reported here were calculated from **in-sample fits**, as the goal of this study was to evaluate methodological improvements relative to the original model rather than to assess out-of-sample forecasting accuracy." This is a deliberate methodological choice, not an oversight. My LOO-CV recommendation remains valid as a future improvement, but the paper's rationale for in-sample metrics is sound for the stated purpose.

**B5.4 The paper describes nowcasting as a key capability of the enhanced model.**

The paper (page 10, Figure 5) demonstrates that the spline model can extrapolate incidence estimates to years not in the training data (2020-2023, given 1996-2019 training data). This nowcasting capability is presented as a major advantage over the original categorical-year model, which cannot generate estimates for years outside the training set. The pipeline does not have an explicit nowcasting mode or documentation for this use case. If the pipeline is meant to support nowcasting (predicting incidence for the current year before complete data are available), this should be documented and the uncertainty characterization for extrapolated years should be differentiated from interpolated years.

**B5.5 The paper acknowledges CIDT as a complicating factor but does not model it.**

The paper (page 9, 11) discusses at length how culture-independent diagnostic tests (CIDTs) adopted from 2012 onward have complicated trend interpretation: "incorporating a spline of the year with an interaction between the diagnostic method and site (or county) would allow us to, at least partially, overcome this complication." However, the current enhanced model does not include a CIDT covariate. This validates my original concern (Section 5.2) and confirms it is a known limitation, not an oversight.

**B5.6 The paper discusses intra-annual variation as a future direction.**

The paper (page 11) notes that both the original and enhanced models "generate annual estimates" and that "past studies have reported substantial intra-annual variation in foodborne and enteric disease incidence." The authors suggest future research should consider intra-annual signals. Neither the pipeline nor my previous reviews discussed temporal resolution below the annual level.

**B5.7 The paper reports specific model performance improvements.**

Figure 2 and the accompanying text (page 6-7) report delta-R-squared values for the enhanced vs. original model across all pathogens. The greatest improvement was for *S.* Typhi (delta-R-squared = 0.27) and Yersinia (delta-R-squared = 0.20). For most pathogens, delta-R-squared ranged 0.02-0.11. Non-O157 STEC and three Salmonella serotypes showed no R-squared improvement but did show ELPD and RMSE improvements. These benchmarks provide ground truth for validating the pipeline's implementation -- if the pipeline produces materially different delta-R-squared values on the same 1996-2019 dataset, it indicates an implementation error.

**B5.8 The paper specifies the brms and tidybayes package versions.**

The paper states: brms version 2.20.1 (references 16-18), tidybayes version 3.0.7 (reference 19), R version 4.4.0. The pipeline's code does not pin package versions. As noted in my original review (Section 1.3), `brms` default priors can change across versions. The paper provides the specific versions needed for exact replication.

**B5.9 The paper explicitly compares Bayesian and frequentist implementations of both models.**

The paper implemented four model variants: (1) frequentist original, (2) Bayesian original, (3) frequentist enhanced, (4) Bayesian enhanced. The Bayesian versions of the original model were implemented specifically to ensure comparability with the enhanced model's Bayesian output. The pipeline only implements the Bayesian enhanced model. If the pipeline is intended to also support the original model for comparison purposes (as Table 1 suggests might be useful), this would require additional implementation.

**B5.10 The paper's Table 1 reveals the original model used county-year as a covariate, not state.**

Table 1 clarifies that the original model's unit of analysis was county-year with a county-year model-specific term, while the enhanced model uses state-level data with site-specific trends. My previous reviews did not discuss this spatial resolution difference because the pipeline only implements the enhanced model. However, this is important context: the pipeline's state-level aggregation in `PATH_ANALYSIS` is a design choice validated by the paper's comparison, not merely a simplification.

---

### B6. Revised Priority List Incorporating the Paper as Ground Truth

The following priority list supersedes the one in Addendum 1 (Section A6). Severity ratings are now calibrated against the paper's stated methodology as the authoritative specification.

| Priority | Finding | Source | Status vs. Addendum 1 |
|----------|---------|--------|-----------------------|
| **HIGH** | Baseline IR computation: pipeline uses median-of-rates; paper says "average" and source uses mean-of-components (population-weighted pooled rate) | `functions.R` lines 670-674 vs. paper page 5 and source lines 331-333 | CONFIRMED. The paper's "average" is more consistent with the source's `mean()` than the pipeline's `median()`. |
| **HIGH** | HDI computed on response scale in pipeline; source computes on log scale then exponentiates. Paper does not specify scale but published values derive from the log-scale method. | `functions.R` lines 512-513 vs. source lines 299-300 | CONFIRMED. |
| **HIGH** | HDI fallback silently produces equal-tailed intervals labeled as HDI when `HDInterval` package is absent | `functions.R` lines 52-59 | CONFIRMED. Paper reports both HDI and equal-tailed CrI as distinct quantities. |
| **HIGH** | No programmatic convergence diagnostics (R-hat, ESS, divergent transitions) | `trendy.R` lines 571-688 | CONFIRMED. Paper does not describe convergence diagnostics either, but this is essential for any Bayesian analysis. |
| **MEDIUM** | Pipeline uses `epred_draws`; paper explicitly states `add_linpred_draws` + exponentiation was used. Numerically equivalent but a traceability gap. | `functions.R` line 442 vs. paper page 5 | NEW finding. Previously rated LOW for numerical impact; upgraded to MEDIUM for methodological traceability to the publication. |
| **MEDIUM** | Priors not explicitly specified in pipeline code, though the paper documents specific prior values (which are brms auto-defaults for the 1996-2019 dataset). | `functions.R` lines 395-411 vs. paper page 5 and page 11 | REVISED. Previously characterized as "not addressed" -- paper does address priors, just not in the code. |
| **MEDIUM** | adapt_delta 0.99 vs. source script 0.999 (paper silent on this parameter) | `run_workflow.sh` line 823 vs. source line 236 | REVISED. Cannot confirm from paper alone; source script is the only reference. |
| **MEDIUM** | Cyclospora/Salmonella dual processing path risk | `trendy.R` lines 462-477 | CONFIRMED from Addendum 1 at MEDIUM. |
| **MEDIUM** | Catchment filter hardcodes "bacterial" for mixed pathogen data | `functions.R` line 243 | CONFIRMED from Addendum 1. |
| **MEDIUM** | Travel label logic bug (OR vs. AND) | `trendy.R` line 271 vs. source line 223 | CONFIRMED. Paper describes domestically acquired case definitions but does not address label logic. |
| **MEDIUM** | No CIDT-era adjustment in model | Model specification | CONFIRMED. Paper explicitly acknowledges this limitation and proposes a spline-CIDT interaction as future work (page 11). |
| **MEDIUM** | Pipeline does not document or support nowcasting use case that the paper describes as a key capability | Paper pages 5, 10 (Figure 5) | NEW. |
| **MEDIUM** | No package version pinning; paper specifies brms 2.20.1, tidybayes 3.0.7, R 4.4.0 | Pipeline-wide | NEW. |
| **MEDIUM** | Error handler discards original error message from brms/Stan | `functions.R` lines 412-414 | CONFIRMED from original review. |
| **LOW** | Seed 123 vs. source 47 (paper silent) | `functions.R` line 408 | CONFIRMED. |
| **LOW** | Three comparison periods commented out (only 2016-2018 active) | `trendy.R` lines 641-650 | CONFIRMED. Paper references multiple baseline periods including 2004-2006 and 2006-2008. |
| **LOW** | max_treedepth 15 vs. source 19 (paper silent) | `run_workflow.sh` line 824 vs. source line 236 | CONFIRMED. |
| **LOW** | Year factor/numeric round-trip | `trendy.R` line 540 | CONFIRMED at LOW from Addendum 1. |
| **LOW** | Misleading function name `LINPREAD_DRAW_FN` and incorrect comment about "link-level predictions" | `functions.R` line 434, `trendy.R` line 595 | REVISED downward from MEDIUM. The paper's use of `add_linpred_draws` makes the naming somewhat more defensible as a historical artifact, though the pipeline actually uses `epred_draws`. |
| **LOW** | Dead code (`PLOT_PCTCHange_TREND`) | `functions.R` lines 747-770 | CONFIRMED from original review. |
| **LOW** | Hardcoded 2004 reference line without label | `functions.R` lines 602, 635 | CONFIRMED. Paper (page 3) confirms 2004 as the year the full catchment was established (NM joined). |

---

### B7. Summary Assessment

Reading the actual published paper resolves several ambiguities from my source-script-only analysis and reveals that the pipeline is, on the whole, a faithful implementation of the paper's described methodology. The core model specification -- negative binomial GAM with site-specific thin plate regression splines, log-population offset, Bayesian estimation via `brms` -- matches exactly. The catchment aggregation logic is algebraically equivalent. The MCMC chain and iteration counts match the publication profile.

The most consequential divergences are:

1. **Baseline IR computation** (median-of-rates vs. population-weighted mean) -- this directly affects all relative risk and percent change outputs, which are the primary deliverables for tracking Healthy People 2030 goals.
2. **HDI computation scale** (response vs. log) -- this affects reported interval bounds for every pathogen-year estimate.
3. **Posterior extraction method** (`epred_draws` vs. `add_linpred_draws` + exp) -- numerically identical but an undocumented substitution relative to the paper's stated methods.

The paper also reveals that my original review's recommendation for LOO-CV was reasonable but the authors had a defensible reason for using in-sample metrics. The paper's explicit discussion of CIDT as a known limitation validates my original concern but confirms it was a deliberate scope decision, not an oversight.

The most important new insight from reading the paper is that the pipeline should be evaluated not just as a standalone modeling tool but as an implementation of a peer-reviewed, published methodology. Any deviation from the paper's stated methods -- even a numerically equivalent one -- creates a gap between the published record and the operational tool. For a CDC surveillance product used to track federal disease reduction goals, this traceability matters.

---

*Addendum 2 prepared after full review of Weller et al. (2026), Zoonoses 6:3, DOI 10.15212/ZOONOSES-2025-0030, cross-referenced against `bin/functions.R`, `bin/trendy.R`, and `source/splinesmodel_16Mar2024_OrCatch.R`.*
