# Arbitration Review: FoodNetTrends Pipeline

**Reviewer:** Senior Biostatistician / Epidemiologist (Independent Third Reviewer)
**Date:** 2026-03-13
**Purpose:** Resolve discrepancies between Biostatistics Modeling Review (Reviewer A) and Epidemiological Review (Reviewer B), verify all claims against source code, identify missed issues, and produce a unified priority-ranked assessment.

**Files verified:**
- `bin/functions.R` (784 lines)
- `bin/trendy.R` (697 lines)
- `bin/preprocess.R` (423 lines)
- `modules/local/resource_profiler.nf` (155 lines)
- `modules/local/trendy.nf` (92 lines)
- `workflows/spline.nf` (477 lines)
- `run_workflow.sh` (~900 lines)
- `nextflow.config` (219 lines)
- `source/splinesmodel_16Mar2024_OrCatch.R` (505 lines, original reference)
- `source/Unspeciated_Shigella.R` (461 lines, original reference)

---

## Section 1: Review of Reviewer Agreement

Both reviewers agree on the following findings. Each is verified below against the actual code.

### 1.1 Agreed: Model specification is appropriate

Both reviewers agree the negative binomial GAM with state-specific splines, state fixed effects, and log-population offset is a sound modeling choice for overdispersed surveillance count data.

**Verification:** Confirmed at `functions.R` line 402:
```r
count ~ s(year, by = state) + state + offset(log(population))
```
The `negbinomial()` family is specified at line 404. This matches the original source (`source/splinesmodel_16Mar2024_OrCatch.R` lines 232-236). **Both reviewers are correct.**

### 1.2 Agreed: Catchment state definitions and join years are correct

Both reviewers confirm the 10 FoodNet states and their start years at `functions.R` lines 71-73 are accurate.

**Verification:** The default config at lines 71-73 specifies:
- CA(1996), CO(2001), CT(1996), GA(1996), MD(1998), MN(1996), NM(2004), NY(1998), OR(1996), TN(2000)

Cross-referenced against the original source at `source/splinesmodel_16Mar2024_OrCatch.R` line 128. **Both reviewers are correct.**

### 1.3 Agreed: Cyclospora/Salmonella data duplication bug

Both reviewers identify the duplicate processing of Cyclospora (and potentially Salmonella) data through both `PATH_ANALYSIS` and the dedicated `CYCLOSPORA_ANALYSIS`/`SALMONELLA_ANALYSIS` functions, combined via `smartbind()` at `trendy.R` lines 476-477.

**Verification:** This is correct but requires nuance. Looking at the code flow:

1. `PATH_ANALYSIS` at `functions.R` line 185 processes `all_pathogens <- unique(mmwrdata$pathogen)`, which includes CYCLOSPORA and SALMONELLA.
2. Lines 192-193 define `parasitic_pathogens <- c("CRYPTOSPORIDIUM", "CYCLOSPORA")` and route them to the Parasitic census (lines 210-212).
3. When `"CIDT+" %in% cidt` is TRUE, `trendy.R` lines 468-477 additionally call `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS`, producing separate data frames.
4. `smartbind()` at lines 476-477 combines all three outputs.

**Critical detail both reviewers noted correctly:** `PATH_ANALYSIS` already handles CYCLOSPORA with the Parasitic census and SALMONELLA with the Bacterial census. The dedicated functions produce duplicate rows.

**However, there is an important mitigating factor neither reviewer fully explored:** The `CYCLOSPORA_ANALYSIS` function (lines 260-281) does NOT retain a `pathogen` column -- the `group_by(year, state) %>% summarise(count = n(), .groups = "drop")` at lines 263-264 drops it. Similarly, `SALMONELLA_ANALYSIS` (lines 296-316) drops the `pathogen` column through its `group_by(year, state)` at line 298. The `PATH_ANALYSIS` output retains a `pathogen` column because it uses `group_by(year, state, pathogen)` at line 197.

When `smartbind` combines them, the Cyclospora/Salmonella rows from the dedicated functions would have `pathogen = NA` (since `smartbind` fills missing columns with NA), while those from `PATH_ANALYSIS` would have the correct pathogen name. At `trendy.R` line 493, `subset(bact, pathogen == opts$pathogen)` would exclude the NA rows.

**But** if no specific `--pathogen` is provided (analyzing all pathogens), the code at line 528 does not filter. Then the `NA`-pathogen rows from dedicated functions would be extra rows in `bact` without a pathogen label. These would cause problems during the `split(bact, bact$pathogen)` at line 541 -- they would create a group with name `NA` that gets processed in the model-fitting loop, potentially fitting a spurious model.

**Revised severity:** MEDIUM for the standard Nextflow workflow (which always passes `--pathogen` per `trendy.nf` line 79). HIGH for standalone R script usage without `--pathogen` and CIDT+ in the filter, because the NA-pathogen data would produce a spurious model fit.

### 1.4 Agreed: Default MCMC parameters are inadequate for publication

Both reviewers flag the defaults (2 chains, 500 iterations) as insufficient. Reviewer A cites the "publication" profile in `run_workflow.sh` (6 chains, 10001 iterations). Reviewer B cites the `production` profile in `nextflow.config` (4 chains, 2000 iterations).

**Verification:** There is a discrepancy because these are different profiles:

- `nextflow.config` lines 102-107 define the `production` profile: **4 chains, 2000 iterations, adapt_delta=0.99, max_treedepth=15**. Reviewer B is correct about this.
- `run_workflow.sh` lines 820-824 define the `publication` flag: **6 chains, 10001 iterations, adapt_delta=0.99, max_treedepth=15**. Reviewer A is correct about this.

**These are two different configuration paths.** The `production` Nextflow profile and the `publication` bash flag are not the same thing. Reviewer B correctly identifies that the `production` Nextflow profile still falls short of the original source parameters (6 chains, 5001 iterations, adapt_delta=0.999, max_treedepth=19). The `publication` bash flag is closer but still uses adapt_delta=0.99 vs. the original's 0.999 and max_treedepth=15 vs. 19. **Both reviewers are partially correct; neither noted that these are separate configuration mechanisms.**

### 1.5 Agreed: HDI fallback silently produces equal-tailed intervals

Both reviewers flag the fallback HDI function at `functions.R` lines 52-58 as problematic.

**Verification:** Confirmed. The fallback at lines 53-58 computes `quantile(x, probs = alpha/2, ...)` and `quantile(x, probs = 1 - alpha/2, ...)`, which are equal-tailed intervals, not HDIs. The warning at line 59 goes to the console only. Output columns labeled `_hdi` would contain equal-tailed intervals. **Both reviewers are correct.**

### 1.6 Agreed: Travel label logic bug

Both reviewers identify the unreachable code branch at `trendy.R` lines 271-277.

**Verification:** Confirmed. Line 271: `if (("YES" %in% travel) || ("UNKNOWN" %in% travel))` -- the `||` operator means if EITHER "YES" or "UNKNOWN" is present, the condition is TRUE and `travelLabel <- "All Cases"`. Line 273: `else if (!("YES" %in% travel) & ("UNKNOWN" %in% travel))` -- this requires UNKNOWN present but YES absent. But if UNKNOWN is present, line 271 already catches it. So the "Domestically-Acquired (UNK Travel Included)" label is unreachable.

Reviewer B correctly notes the original source (`source/splinesmodel_16Mar2024_OrCatch.R` line 223) uses `&` (AND), not `||` (OR): `if(("YES" %in% travel) & ("UNKNOWN" %in% travel))`. The pipeline introduced this bug by changing `&` to `||`. **Both reviewers are correct; Reviewer B provides the more precise diagnosis.**

### 1.7 Agreed: No programmatic convergence diagnostics

Both reviewers flag that the pipeline does not programmatically check R-hat, ESS, or divergent transitions after model fitting.

**Verification:** Confirmed. After `brm()` at `functions.R` line 394, the model is returned without any diagnostic checks. The summary is saved to a text file at `trendy.R` lines 589-592 via `sink()/print(summary(proposed))/sink()`, but there is no automated parsing of convergence metrics. **Both reviewers are correct.**

### 1.8 Agreed: 2004 vertical line lacks annotation

Both reviewers note the hardcoded `geom_vline(aes(xintercept = 2004), ...)` at `functions.R` lines 602 and 635 without legend or explanation.

**Verification:** Confirmed. No annotation text or legend entry exists for either plot function. **Both reviewers are correct.**

### 1.9 Agreed: SAFE_WRITE append behavior risk

Both reviewers flag the append-on-existing behavior of `SAFE_WRITE` at `functions.R` lines 156-158.

**Verification:** Confirmed. If the file exists, data is appended without headers (`col.names = FALSE`). Cross-run contamination is possible if output directories are not cleaned. **Both reviewers are correct.**

### 1.10 Agreed: Dead code in PLOT_PCTCHange_TREND

Both reviewers identify `PLOT_PCTCHange_TREND` at `functions.R` lines 747-770 as referencing undefined variables `pathogen` and `outDir`.

**Verification:** Confirmed. The function signature at line 747 is `PLOT_PCTCHange_TREND <- function(hp30)` -- only one parameter. But line 754 uses `pathogen` and line 766 uses `outDir`, neither of which are parameters or globally defined at that scope. Additionally, line 752 uses `type="dashed"` instead of the correct `linetype="dashed"` (a ggplot2 error). This function is never called in `trendy.R`. **Both reviewers are correct.**

---

## Section 2: Review of Discrepancies

### 2.1 Discrepancy: Severity of Cyclospora/Salmonella duplication

- **Reviewer A:** Rates it as HIGH severity, stating it would "inflate case counts and produce biased incidence rate estimates."
- **Reviewer B:** Rates it as CRITICAL severity.

**Arbitration:** As analyzed in Section 1.3 above, the standard Nextflow workflow always passes `--pathogen` (see `trendy.nf` line 79), which means the dedicated analysis functions produce rows without a `pathogen` column that would be filtered out at `trendy.R` line 493. The actual duplication risk is **MEDIUM for the standard Nextflow workflow** and **HIGH for standalone R script usage without --pathogen**. Neither reviewer is fully correct -- Reviewer A is closer to the actual severity in the standard deployment context. However, the code is confusing and should be cleaned up regardless.

### 2.2 Discrepancy: epred_draws vs. add_linpred_draws significance

- **Reviewer A:** Notes `epred_draws()` returns response-scale expected values, calls the misleading function name/comments a MEDIUM issue, but considers the statistical method itself correct.
- **Reviewer B:** Rates the methodological change as HIGH severity, arguing results will differ from published analyses and that the uncertainty propagation differs.

**Arbitration:** Reviewer B's claim about `epred_draws()` vs. `exp(add_linpred_draws(transform=FALSE))` needs careful examination.

For a negative binomial GLM with log link:
- `add_linpred_draws(transform=FALSE)` gives the log-scale linear predictor for each posterior draw. Exponentiating gives `exp(X*beta)` = the conditional mean mu.
- `epred_draws()` gives the expected value of the response distribution, which for NB with log link is also mu = `exp(X*beta)`.

Reviewer B states: "the uncertainty propagation differs because `epred_draws()` integrates over all posterior uncertainty (including the shape parameter), while the original approach only transforms the linear predictor." This is **incorrect**. Both methods draw from the same posterior. For `epred_draws()`, the expected value of NB(mu, phi) is simply mu, regardless of the shape parameter phi. The shape parameter does not enter the expected value calculation. Both methods produce E[Y|theta] = exp(X*beta) for each posterior draw theta. The difference is negligible for the mean.

The key difference in the original source's catchment aggregation is: the original exponentiates each state's linear predictor independently and then sums (source lines 258-261), while the new pipeline gets response-scale values from `epred_draws` and then sums in the `CATCHMENT` function. These are algebraically identical: sum(exp(linpred_i)) = sum(epred_i).

**Verdict:** Reviewer A is correct that the statistical method is equivalent. Reviewer B overstates the impact. The results should be numerically very close (any differences would be due to floating point precision). **Reviewer A is correct; Reviewer B's HIGH rating is overstated.** The naming/documentation issue is real (MEDIUM).

### 2.3 Discrepancy: HDI computation scale difference

- **Reviewer A:** Notes the fallback issue (MEDIUM) but does not discuss the log-scale vs. response-scale HDI difference.
- **Reviewer B:** Identifies a HIGH-priority difference between computing HDI on response-scale (pipeline) vs. log-scale (source).

**Arbitration:** Reviewer B correctly identifies a real methodological difference. The original source at `source/splinesmodel_16Mar2024_OrCatch.R` lines 299-309 computes:
```r
splits <- split(catchments %>% mutate(.value = log(.value)) %>% select(.value), catchments$yearn)
t <- lapply(splits, function(x) HDInterval::hdi(x) %>% exp() %>% as.data.frame())
```
This takes the log of the response-scale values, computes HDI on the log scale, then exponentiates back. This produces asymmetric intervals that respect the log-normal-like shape of count distributions.

The new pipeline at `functions.R` lines 512-513 computes HDI directly on response-scale `.epred` values. For right-skewed distributions (common for count data), the HDI on the response scale will differ from the back-transformed log-scale HDI. The log-scale HDI tends to produce narrower, more symmetric intervals on the original scale.

**Verdict: Reviewer B is correct that this is a meaningful methodological difference.** However, it is debatable which is more appropriate. Computing HDI directly on the response scale is arguably more principled (it finds the actual highest density region of the posterior predictive distribution). The log-transform-then-back-transform approach finds the HDI of a different distribution. **Severity: MEDIUM** -- it is a legitimate methodological choice, not a bug, but it should be documented and justified.

### 2.4 Discrepancy: Baseline IR aggregation (median vs. mean)

- **Reviewer A:** Notes the use of `median()` for baseline IR at `functions.R` line 673 as a concern, recommends a population-weighted average.
- **Reviewer B:** Rates this as a methodological divergence from published results (which use `mean`).

**Arbitration:** The original source at `source/splinesmodel_16Mar2024_OrCatch.R` lines 331-333 uses `mean`:
```r
summarise_at(.vars = c("count", "population", ".value"), .funs = list(mean=mean))
```
The new pipeline at `functions.R` lines 670-674 uses `median`:
```r
summarise(baseline_ir = median(ir), baseline_count = median(count))
```

But there is a deeper issue neither reviewer fully articulated: the original computes mean of raw `.value` (expected count), `count`, and `population` separately across baseline years within each draw, then derives IR from those means. The new pipeline first computes `ir = .epred / (population/100000)` for each year within each draw, then takes the `median` of those IRs. These are fundamentally different calculations:

- Original: baseline_value = mean(value_y1, value_y2, value_y3), baseline_pop = mean(pop_y1, pop_y2, pop_y3), then baseline_ir = baseline_value / (baseline_pop/100000). This is a population-weighted average rate -- the standard epidemiological method for computing a pooled rate over multiple years.
- Pipeline: baseline_ir = median(value_y1/(pop_y1/100000), value_y2/(pop_y2/100000), value_y3/(pop_y3/100000)). This gives equal weight to each year regardless of population size.

For a 3-year baseline with varying population sizes, the approaches produce materially different results, and the pipeline's approach is epidemiologically non-standard.

**Verdict: Both reviewers correctly identify the divergence. Reviewer A's recommendation of population-weighted average is the epidemiologically correct approach. This is a genuine methodological error in the pipeline.** Severity: HIGH.

### 2.5 Discrepancy: Production profile parameters

- **Reviewer A:** Cites the `publication` profile in `run_workflow.sh` (6 chains, 10001 iter) as "generally appropriate."
- **Reviewer B:** Cites the `production` profile in `nextflow.config` (4 chains, 2000 iter) as inadequate and recommends matching the original (6 chains, 5001 iter, adapt_delta=0.999).

**Arbitration:** Both reviewers are talking about different things (see Section 1.4). The `production` Nextflow profile IS inadequate (2000 iterations yields ~1000 post-warmup samples per chain, 4000 total). The `publication` bash flag is reasonable but still does not match the original's adapt_delta=0.999.

**Verdict:** Reviewer B is correct that the Nextflow `production` profile should be strengthened. There are actually THREE separate MCMC configuration mechanisms (nextflow.config defaults, nextflow.config `production` profile, run_workflow.sh flags) that are not clearly coordinated. The Nextflow `production` profile should be updated to at least match `run_workflow.sh`'s `publication` settings. Severity: MEDIUM.

---

## Section 3: Reviewer Errors

### 3.1 Reviewer A: Overstated data duplication risk for --pathogen case

Reviewer A states at Section 4.2: "If the pathogen is CYCLOSPORA or SALMONELLA, the subset would contain duplicate rows from both `PATH_ANALYSIS` and the dedicated analysis function." As analyzed in Section 1.3, the dedicated analysis functions drop the `pathogen` column during `group_by(year, state) %>% summarise(count = n())`, so the rows from dedicated functions would have `pathogen = NA` after `smartbind`. The `subset(bact, pathogen == opts$pathogen)` at line 493 would NOT match these NA rows. **Reviewer A overstates the duplication risk for the --pathogen case.**

### 3.2 Reviewer B: Incorrect epred_draws uncertainty claim

Reviewer B states: "the uncertainty propagation differs because `epred_draws()` integrates over all posterior uncertainty (including the shape parameter), while the original approach only transforms the linear predictor." As analyzed in Section 2.2, the expected value of the NB distribution is mu = exp(X*beta), which does not depend on the shape parameter. Both methods draw from the same posterior and compute the same quantity. **Reviewer B's statement about uncertainty propagation is technically incorrect.** Both methods propagate the same posterior uncertainty for the conditional mean.

### 3.3 Reviewer B: Production vs. publication profile conflation

Reviewer B's comparison table (Section 6.1) lists a "Production Profile" column with values from the Nextflow `production` profile (4 chains, 2000 iter). This is not the same as the `publication` mode in `run_workflow.sh` (6 chains, 10001 iter). While Reviewer B's values for the `production` profile are correct, the table may mislead readers into thinking the pipeline has only one production-grade configuration. The pipeline actually has multiple tiers that are not well coordinated.

### 3.4 Reviewer A: Overstated year factor/numeric round-trip risk

Reviewer A rates the year factor/numeric round-trip as a RED FLAG (MEDIUM severity), stating "If `as.character()` fails or produces unexpected results, the spline would be fitted on incorrect year values."

**Verification:** At `trendy.R` line 540, `bact$year <- as.factor(bact$year)`. Then at `functions.R` lines 381-383, `as.numeric(as.character(data$year))` converts back. This is a well-known R idiom; `as.character()` on a factor returns the level labels (the original year strings), and `as.numeric()` converts those strings to numbers. It will not fail or produce unexpected results unless the original year values were non-numeric, which is prevented by earlier processing. **This is not error-prone in practice; Reviewer A overstates the risk.** Severity: LOW (code smell, not a bug).

### 3.5 Reviewer A: Missed catchment filter pathogen_type concern

Reviewer A does not flag the `apply_catchment_filter(selectDf, catchment_config, "bacterial")` call at `functions.R` line 243, but Reviewer B does (Section 1.4). Reviewer B correctly notes that `PATH_ANALYSIS` processes parasitic pathogens (CYCLOSPORA, CRYPTOSPORIDIUM) but passes `"bacterial"` to the catchment filter.

**Verification:** At `functions.R` line 111, `apply_catchment_filter` with `pathogen_type = "bacterial"` filters the config: line 114 keeps rows where `catchment_config$pathogen_type %in% c("both", "bacterial")`. The default config has all states as `"both"` (line 75), so **all states pass through**. Reviewer B correctly identifies this as a latent bug that only triggers with custom configs. **Reviewer B is correct; Reviewer A missed this.**

---

## Section 4: Missed Issues

### 4.1 MISSED: IR_COMP_CATCH baseline computation is fundamentally different from the original (beyond median vs. mean)

Beyond the median vs. mean difference noted by both reviewers, the computational structure itself diverges:

- **Original** (`source/splinesmodel_16Mar2024_OrCatch.R` lines 331-334): Averages the raw `.value` (expected count), `count`, and `population` columns **separately** across baseline years within each draw via `summarise_at(.vars = c("count", "population", ".value"), .funs = list(mean=mean))`. Then derives IR from: `ref_value / (ref_pop / 100000)`.
- **Pipeline** (`functions.R` lines 670-674): First computes `ir = .epred/(population/100000)` for each year within each draw, then takes `median(ir)` across baseline years.

The original approach is equivalent to a population-weighted average rate across the baseline period. The pipeline approach treats each year's rate equally regardless of population denominators. For a 3-year baseline with population growth (typical for FoodNet states), these produce different results. This was partially flagged by both reviewers but the precise structural divergence was not fully articulated by either.

### 4.2 MISSED: The `ir` and `est_ir` columns in IR_COMP_CATCH are identical

At `functions.R` lines 683-684:
```r
ir = .epred/(population/100000),
est_ir = .epred/(population/100000),
```
These are exactly the same computation. The `ir` column is redundant. This is a minor code quality issue but suggests incomplete refactoring.

### 4.3 MISSED: No validation that pathogen exists in data before calling dedicated analysis functions

At `trendy.R` lines 468-473, the code calls `CYCLOSPORA_ANALYSIS(mmwrdata_filtered, census, catchment_config)` and `SALMONELLA_ANALYSIS(mmwrdata_filtered, census, catchment_config)` when `"CIDT+" %in% cidt`, regardless of whether the filtered data actually contains CYCLOSPORA or SALMONELLA. If `--pathogen CAMPYLOBACTER` is passed, `mmwrdata_filtered` would contain only CAMPYLOBACTER data. The dedicated functions would produce empty or all-zero data frames that get `smartbind`ed unnecessarily.

**Severity: LOW.** No incorrect results, but wasteful computation and confusing code flow.

### 4.4 MISSED: Environment variable path typo in nextflow.config

At `nextflow.config` line 122:
```
R_LIBS = "/opt/conda/envs/FootNetTreands_R/lib/R/library"
```
The environment name is misspelled: `FootNetTreands_R` (should presumably be `FoodNetTrends_R`). If the Singularity container was built with this typo in the path, it would work. But if someone rebuilds the container with the corrected spelling, R packages would not be found.

**Severity: LOW** (container-specific, not a statistical issue, but a maintenance hazard).

### 4.5 MISSED: combine_files uses str_remove without loading stringr

At `functions.R` line 780, `str_remove()` is called. The library loading block at lines 34-45 does not load `stringr`. While `trendy.R` line 259 loads `tidyverse` (which includes `stringr`), if `combine_files` were called independently, it would fail. Reviewer A noted the `setwd()` issue and unloaded packages but did not specifically identify the `str_remove` / `stringr` dependency gap.

### 4.6 MISSED: Potential division by zero in relative risk calculation

At `functions.R` line 685:
```r
relative_risk = est_ir / baseline_ir
```
If `baseline_ir` is zero for any draw (possible if the baseline period has very low counts and a posterior draw produces a zero expected count), this produces `Inf`. The subsequent `median()` and `hdi()` would then include infinite values. For most FoodNet pathogens this is unlikely, but for rare pathogens (e.g., Cyclospora in some states) or serotype-specific analyses, zero expected counts in the baseline are plausible.

**Severity: LOW-MEDIUM.** Worth adding a guard clause.

### 4.7 MISSED: brm() hardcodes backend = "rstan"

At `functions.R` line 410:
```r
backend = "rstan"
```
This hardcodes the Stan backend. If the container has `cmdstanr` but not `rstan`, or if a future environment upgrade removes `rstan`, this would fail. The original source does not specify a backend. This is a valid design choice but should be documented.

**Severity: LOW** (operational, not statistical).

### 4.8 MISSED: PLOT_PCTCHange_TREND has additional ggplot2 error beyond undefined variables

At `functions.R` line 752:
```r
geom_vline(aes(xintercept = 2004), type="dashed", color="red")
```
The parameter `type=` is not valid for `geom_vline` in modern ggplot2; it should be `linetype=`. Both reviewers noted the undefined variable issue but neither identified this additional ggplot2 syntax error.

### 4.9 MISSED: Original source has a latent bug in site-level incidence computation

In `source/splinesmodel_16Mar2024_OrCatch.R` line 250:
```r
d.prop.fdraws$pinc <- (d.prop.fdraws$.linpred) / (d.prop.fdraws$population/100000)
```
This divides the LOG-SCALE linear predictor by population/100000. Since `.linpred` is on the log scale (because `transform=FALSE`), this computes `log(mu) / (population/100000)`, which is NOT a meaningful incidence rate. However, this intermediate value is never directly reported -- the catchment-level computation correctly exponentiates before computing IR. The pipeline's use of `epred_draws` (response-scale) avoids this intermediate confusion and is actually **more correct** for any site-level IR reporting. This is relevant context for evaluating whether the pipeline's methodological changes are improvements or regressions.

### 4.10 MISSED: No handling of CRYPTOSPORIDIUM in dedicated analysis functions

The pipeline has `CYCLOSPORA_ANALYSIS` but no `CRYPTOSPORIDIUM_ANALYSIS`. CRYPTOSPORIDIUM is handled through `PATH_ANALYSIS` (which correctly routes it to the Parasitic census at lines 210-212). This is functionally correct. However, CRYPTOSPORIDIUM is missing from `ALL_PATHOGENS` in `run_workflow.sh` line 24 (as Reviewer B noted). Since `PATH_ANALYSIS` handles it with the correct Parasitic census, this is only a user-facing omission, not a statistical error.

---

## Section 5: Unified Priority-Ranked Findings

### CRITICAL

*None.* The Cyclospora/Salmonella duplication issue, which both reviewers flagged as HIGH or CRITICAL, is mitigated in the standard Nextflow workflow because the dedicated analysis functions drop the `pathogen` column, and the `subset` at line 493 filters by pathogen name. However, the code is confusing and should be refactored.

### HIGH

**H1. Baseline IR computation uses median of year-specific rates instead of population-weighted average**
- **Location:** `functions.R` lines 670-674
- **Description:** The pipeline computes `baseline_ir = median(ir)` where `ir = .epred/(population/100000)` per year within each draw. The original source computes baseline by averaging raw `.value`, `count`, and `population` separately across baseline years within each draw, then deriving IR. The pipeline's approach gives equal weight to each year; the original weights by population (person-time). For a 3-year baseline with materially different populations, this produces different relative risk and percent change estimates.
- **Impact:** Relative risk and percent change estimates will diverge from published MMWR results.
- **Fix:** Replace `summarise(baseline_ir = median(ir), baseline_count = median(count))` with: compute `baseline_value = mean(.epred)`, `baseline_pop = mean(population)`, `baseline_count = mean(count)`, then derive `baseline_ir = baseline_value / (baseline_pop / 100000)`.

**H2. No programmatic convergence diagnostics**
- **Location:** `trendy.R` lines 571-688, `functions.R` lines 394-416
- **Description:** After `brm()` completes, there is no automated check for R-hat > threshold, ESS below minimum, or divergent transitions. The model summary is saved to a text file but not parsed. Convergence failures produce results that are silently used downstream.
- **Impact:** Unreliable posterior estimates could propagate to published incidence rates and relative risk estimates without any warning.
- **Fix:** After model fitting, extract `rhat()`, `neff_ratio()`, and divergent transition counts. Emit warnings or create a diagnostics summary file. Consider halting if R-hat > 1.05 for any parameter.

**H3. HDI fallback silently produces equal-tailed intervals labeled as HDI**
- **Location:** `functions.R` lines 52-59
- **Description:** When the `HDInterval` package is unavailable, the fallback `hdi()` function computes equal-tailed quantile intervals. Output columns labeled `_hdi` would be misleading.
- **Impact:** Mislabeled statistical output. Equal-tailed and HDI intervals can differ substantially for skewed posteriors.
- **Fix:** Make `HDInterval` a hard dependency (it is already listed in `trendy.R` line 259's package loading). Alternatively, mark output columns as `_eti` when using the fallback.

**H4. Cyclospora/Salmonella dual processing path creates confusing code and potential bug in standalone usage**
- **Location:** `trendy.R` lines 462-477, `functions.R` lines 182-316
- **Description:** `PATH_ANALYSIS` already handles all pathogens including CYCLOSPORA and SALMONELLA with correct census data routing. The dedicated `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` functions are called additionally when `CIDT+` is in the filter, producing data frames that get `smartbind`ed. While the standard Nextflow workflow mitigates the duplication (dedicated functions lack a `pathogen` column, and line 493 filters by pathogen), the code is confusing and would produce a spurious NA-pathogen model group if run without `--pathogen`.
- **Impact:** Potential silent model fitting on orphaned data in non-standard usage; code maintenance burden; risk of future regressions.
- **Fix:** Remove the `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` calls from `trendy.R` lines 468-477. `PATH_ANALYSIS` already handles these correctly. Alternatively, exclude CYCLOSPORA and SALMONELLA from `PATH_ANALYSIS` when dedicated functions are used.

### MEDIUM

**M1. HDI computed on response scale instead of log scale (methodological divergence from published results)**
- **Location:** `functions.R` lines 512-513, 519-520, 703-704, 710-711
- **Description:** The original source computes HDI on log-transformed values and then exponentiates back. The pipeline computes HDI directly on the response scale. These produce different intervals for skewed distributions.
- **Impact:** Reported HDI bounds will differ from published MMWR results.
- **Fix:** If exact replication of published results is required, transform to log scale before HDI computation and back-transform. Document the choice either way.

**M2. No explicit priors in brm() call**
- **Location:** `functions.R` lines 395-411
- **Description:** The model relies entirely on `brms` default priors, which may change between package versions.
- **Impact:** Reproducibility risk across `brms` versions; lack of transparency for peer review.
- **Fix:** Explicitly specify priors matching the current `brms` defaults. Document the prior choices.

**M3. Production Nextflow profile is weaker than publication bash flag and original source parameters**
- **Location:** `nextflow.config` lines 102-107 vs. `run_workflow.sh` lines 820-824
- **Description:** The Nextflow `production` profile uses 4 chains/2000 iterations, while the bash `publication` flag uses 6 chains/10001 iterations. Neither matches the original source (6 chains/5001 iter/adapt_delta=0.999/max_treedepth=19). Users running via Nextflow with `-profile production` get weaker MCMC than those using `run_workflow.sh` with the `publication` flag.
- **Impact:** Inconsistent results depending on how the pipeline is invoked.
- **Fix:** Align the Nextflow `production` profile with the `publication` bash settings. Consider adding a `publication` Nextflow profile that matches the original source parameters exactly.

**M4. Travel label logic bug (unreachable branch)**
- **Location:** `trendy.R` lines 271-277
- **Description:** The `||` (OR) on line 271 should be `&` (AND) to match the original source logic. The current code labels any analysis including "UNKNOWN" travel as "All Cases", even when "YES" is excluded.
- **Impact:** Misleading output labels when running domestically-acquired analyses with unknown travel included.
- **Fix:** Change `||` to `&` on line 271: `if (("YES" %in% travel) & ("UNKNOWN" %in% travel))`.

**M5. Error message discards original error in PROPOSED_BM tryCatch**
- **Location:** `functions.R` lines 412-414
- **Description:** The `tryCatch` error handler at line 413 discards the original error message and substitutes a generic "Model did not converge" message. This obscures the actual cause of failures (compilation errors, data errors, Stan errors).
- **Impact:** Significant debugging difficulty.
- **Fix:** Include the original error message: `stop(paste("Model fitting failed:", e$message))`.

**M6. Catchment filter uses "bacterial" for mixed bacterial/parasitic data**
- **Location:** `functions.R` line 243
- **Description:** `PATH_ANALYSIS` passes `"bacterial"` to `apply_catchment_filter` even though it processes both bacterial and parasitic pathogens. With the default config (all states = "both"), this has no effect. But with custom configs that differentiate pathogen types, parasitic pathogens would be incorrectly filtered.
- **Impact:** Latent bug for custom configurations.
- **Fix:** Pass `"both"` or apply separate filters for bacterial and parasitic subsets within `PATH_ANALYSIS`.

**M7. No COVID-19 pandemic period adjustment or caveat**
- **Location:** Model specification (`functions.R` line 402)
- **Description:** The spline model has no mechanism to account for the 2020-2021 surveillance disruption. The model will smooth through the pandemic dip, potentially biasing post-pandemic trend estimates.
- **Impact:** Trend interpretation for 2022+ may be affected by the pandemic-era surveillance artifact.
- **Fix:** Consider adding a pandemic indicator variable, or document the limitation prominently in all outputs.

**M8. Memory allocation not linked to chain count**
- **Location:** `nextflow.config` lines 140-147
- **Description:** The TRENDY process allocates 64GB regardless of chain count. For 8-chain "max" mode (needing ~72GB), first attempt would be underallocated.
- **Impact:** Unnecessary job failures and retries, wasted cluster resources.
- **Fix:** Parameterize memory based on chain count or increase base allocation.

**M9. Misleading function name and comments for posterior draw extraction**
- **Location:** `functions.R` line 434 (`LINPREAD_DRAW_FN`), `trendy.R` line 595 ("Draw untransformed (link-level) predictions")
- **Description:** The function name suggests "linear predictor" draws and the comment says "link-level," but `epred_draws()` returns response-scale expected values, not link-scale linear predictor values.
- **Impact:** Could mislead developers into incorrect downstream calculations if they assume link-scale values.
- **Fix:** Rename to `EPRED_DRAW_FN` or `RESPONSE_DRAW_FN`. Update comment at `trendy.R` line 595 to "Draw response-scale expected value predictions."

### LOW

**L1. Dead code: PLOT_PCTCHange_TREND function** (`functions.R` lines 747-770) -- references undefined variables `pathogen` and `outDir`, uses invalid `type=` instead of `linetype=` in ggplot2, never called. Remove it.

**L2. combine_files uses setwd() and undeclared dependencies** (`functions.R` lines 773-784) -- uses `setwd()` which changes global working directory, calls `str_remove()` without `stringr` loaded, uses `map_df` without explicit `purrr` load. Refactor or remove.

**L3. Hardcoded 2004 reference line without annotation** (`functions.R` lines 602, 635) -- add a text annotation or legend entry explaining NM joined FoodNet in 2004.

**L4. SAFE_WRITE append behavior** (`functions.R` lines 156-158) -- document the cross-run contamination risk or add overwrite-on-first-write logic.

**L5. LISTERIA and CRYPTOSPORIDIUM missing from ALL_PATHOGENS** (`run_workflow.sh` line 24) -- add them or document their intentional exclusion.

**L6. Comparison periods commented out** (`trendy.R` lines 641-650) -- uncomment or make configurable via command-line parameters.

**L7. Duplicated code in LINPRED_TO_CATCHIR / LINPRED_TO_SITEIR** (`functions.R` lines 494-569) -- the only difference is the `group_by` clause. Refactor into a single parameterized function.

**L8. Year factor/numeric round-trip** (`trendy.R` line 540, `functions.R` lines 381-383) -- unnecessary conversion that adds confusion; keep year numeric throughout.

**L9. Seed difference from original** (pipeline: 123, original: 47) -- results will not exactly reproduce original outputs. Document the choice.

**L10. R_LIBS environment path typo** (`nextflow.config` line 122) -- `FootNetTreands_R` is likely misspelled. Verify against container.

**L11. Redundant `ir` and `est_ir` columns** (`functions.R` lines 683-684) -- identical computations; remove the duplicate.

**L12. Potential division by zero in relative risk** (`functions.R` line 685) -- add guard clause for draws where `baseline_ir` equals zero.

**L13. No validation before calling dedicated analysis functions** (`trendy.R` lines 468-473) -- `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` are called even when the filtered data does not contain those pathogens, resulting in wasteful empty-data-frame processing.

---

## Section 6: Overall Assessment

### Is this pipeline suitable for production use in CDC reporting?

**Not yet in its current state, but close.** The core statistical methodology is sound -- the negative binomial GAM with state-specific splines, Bayesian estimation, and draw-level uncertainty propagation are all appropriate and well-implemented. The pipeline architecture (Nextflow orchestration, configurable parameters, modular design) is a significant improvement over the monolithic original scripts. The use of `epred_draws` for posterior prediction is actually an improvement over the original source's approach for site-level incidence computation.

### What must be fixed before publication-quality results can be trusted?

1. **H1 (Baseline IR computation):** The median-of-rates approach for baseline IR diverges from the population-weighted mean used in published MMWR reports. This directly affects relative risk and percent change estimates, which are key outputs cited in publications. **Must fix.**

2. **H2 (Convergence diagnostics):** Without automated convergence checks, there is no safety net against publishing results from a model that did not converge. **Must fix for any results that will be reported or published.**

3. **H3 (HDI fallback):** Since `HDInterval` is already in the package list at `trendy.R` line 259, making it a hard dependency is trivial. **Must fix.**

4. **H4 (Dual processing paths):** The confusing dual processing of Cyclospora/Salmonella should be cleaned up to prevent future maintenance errors, even though it does not currently produce incorrect results in the standard Nextflow workflow. **Should fix before production.**

5. **M3 (Production profile alignment):** The Nextflow `production` profile should match or exceed the original source's MCMC parameters for any results destined for publication. **Must fix before publication.**

6. **M4 (Travel label bug):** Simple one-character fix (`||` to `&`). **Must fix.**

### What are acceptable limitations vs. genuine bugs?

**Acceptable limitations (scientific choices that should be documented):**
- Using `epred_draws` instead of `add_linpred_draws` + `exp()` -- mathematically equivalent for the conditional mean; actually more correct for site-level IR.
- Computing HDI on response scale vs. log scale -- both are defensible; document the choice and its implications for comparison with prior publications.
- Default MCMC parameters being screening-only -- acceptable if clearly labeled and if publication-grade profiles are properly configured.
- No COVID-19 adjustment -- acceptable if documented as a caveat in publications.
- Seed difference from original -- expected when refactoring; does not affect statistical validity.

**Genuine bugs requiring correction:**
- Travel label logic (`||` instead of `&`) -- bug introduced during refactoring.
- Baseline IR uses median of rates instead of population-weighted average -- methodological error relative to published methodology.
- HDI fallback silently mislabels output -- bug.
- Error handler discards original error message -- bug.
- Catchment filter hardcodes "bacterial" for mixed pathogen data -- latent bug for custom configs.

### Summary

The FoodNetTrends pipeline is a well-architected modernization of the original analysis scripts. The core Bayesian modeling and most of the data handling are correctly implemented. The issues identified are primarily: (1) a few methodological divergences from the original that should be intentional and documented rather than accidental, (2) missing guardrails (convergence diagnostics, HDI dependency), and (3) code quality issues (dead code, confusing dual processing paths). With the four HIGH-priority fixes applied and the critical MEDIUM-priority items addressed, this pipeline would be suitable for CDC publication-quality analyses.

---

*Arbitration review prepared as an independent third assessment of the FoodNetTrends Bayesian modeling pipeline for CDC DFWED/EDEB.*

---

## Addendum: Response to Reviewer Rebuttals and Publication Analysis

**Date:** 2026-03-13
**Context:** This addendum responds to the addenda appended by Reviewer A (Senior Biostatistician) and Reviewer B (Senior Epidemiologist) to their original reviews. Both reviewers have read the arbitration, re-examined the source code, and compared the pipeline against the published methodology (Tack et al., doi:10.15212/ZOONOSES-2025-0030). Direct access to the publication full text was unavailable during this review; the analysis below relies on the original source scripts (`source/splinesmodel_16Mar2024_OrCatch.R`, `source/Unspeciated_Shigella.R`) and the reference output (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) as proxies for the published methodology, consistent with Reviewer B's approach and supplemented by both reviewers' publication analyses.

---

### 1. Rebuttal Assessment

#### 1.1 Reviewer A Rebuttal A2.1: LINPREAD_DRAW_FN naming is a meaningful maintenance hazard (MEDIUM)

Reviewer A (Addendum A2.1) argues that the misleading function name `LINPREAD_DRAW_FN` and the incorrect comment at `trendy.R` line 595 ("Draw untransformed (link-level) predictions") are not merely cosmetic but a genuine maintenance hazard, because a future developer trusting these labels might perform link-scale arithmetic on values that are actually response-scale.

**Assessment: Reviewer A's rebuttal is persuasive.** My original arbitration (Section M9) already rated this MEDIUM. Reviewer A is not asking for an upgrade -- they are defending MEDIUM against a perceived implication that I considered it minor. I did not intend to downplay this; MEDIUM was and remains appropriate. The function returns `epred_draws()` output (response-scale expected values) but is named and documented as if it returns linear predictor draws. Any downstream code that subtracts, adds, or otherwise manipulates these values assuming log-scale semantics would produce incorrect results. **Verdict: MEDIUM confirmed. No change from original arbitration.**

#### 1.2 Reviewer A Rebuttal A2.2: HDI computation scale should be HIGH for replication purposes

Reviewer A (Addendum A2.2) argues that the HDI scale difference should be HIGH rather than my original MEDIUM, on the grounds that the pipeline's explicit goal is replication of published MMWR results, and the published results used log-scale HDI computation (confirmed at `source/splinesmodel_16Mar2024_OrCatch.R` lines 299-309).

Reviewer B (Rebuttal 2.1) makes a nearly identical argument, proposing MEDIUM-HIGH, emphasizing reproducibility against the reference output in `source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`.

**Assessment: Both reviewers raise a legitimate point that my original arbitration underweighted.** I originally argued that response-scale HDI is "arguably more principled." That assessment was technically correct but failed to account for the pipeline's primary use case: reproducing and extending published CDC surveillance results. When the goal is replication fidelity, deviating from the published interval computation method -- even to a more principled one -- is a problem if undocumented. The reference output (e.g., Campylobacter 2023 vs. 2016-2018: estimated IR 9.30 [8.83, 9.80]) was produced with the log-scale HDI method. The pipeline would produce different bounds.

**Verdict: I upgrade this from MEDIUM to HIGH when the pipeline is used for replication of published results.** If the pipeline were deployed as a new, independent analysis tool with its own documented methodology, MEDIUM would remain appropriate. Since its stated purpose is to automate the published MMWR analysis, HIGH is warranted. Both reviewers' rebuttals are accepted.

#### 1.3 Reviewer A Rebuttal A2.3: The odd iteration count 10001 is deliberate

Reviewer A (Addendum A2.3) explains that the odd iteration counts (5001 in the original source at line 234, 10001 in the pipeline's `publication` flag at `run_workflow.sh` line 822) are intentional. With `brms` default `warmup = iter/2`, using `iter=5001` produces `warmup=2500` and `2501` post-warmup draws per chain, ensuring the median is uniquely defined.

**Assessment: This is a plausible and well-reasoned explanation.** I did not flag this in my original arbitration, but Reviewer A's original review noted it as "slightly unusual." The rebuttal corrects this and provides a sound rationale. **Verdict: Accepted. This is a deliberate design choice, not a concern.**

#### 1.4 Reviewer B Rebuttal 2.1: HDI computation scale is methodologically significant

Addressed jointly with Reviewer A's rebuttal in Section 1.2 above. **Verdict: Accepted; upgraded to HIGH for replication use cases.**

#### 1.5 Reviewer B Rebuttal 2.2: Baseline IR computation is a genuine methodological error

Reviewer B (Rebuttal 2.2) reinforces my original finding (Arbitration Section 2.4 / H1) that the baseline IR computation is epidemiologically non-standard, noting specifically that using `median` over a 3-year baseline discards information from two of the three years. Reviewer B further endorses my verdict that this is "a genuine methodological error in the pipeline."

**Assessment: Reviewer B's rebuttal aligns with my original arbitration and adds a useful observation about information loss from the median.** The original source at `source/splinesmodel_16Mar2024_OrCatch.R` lines 331-333 uses `mean` across all three baseline years' raw `.value`, `count`, and `population` values per draw, preserving the full 3-year information. The pipeline's `median(ir)` at `functions.R` line 673 selects only the middle year's rate, effectively reducing the baseline to a single year's estimate. For a 3-year period, `median` of three values always equals the second-ranked value, discarding the other two entirely. This is a more damaging characterization than "non-standard" -- it is information-destructive.

**Verdict: HIGH confirmed. Both the median-vs-mean and the rate-vs-pooled-ratio issues remain genuine methodological errors. No change from original arbitration severity, but the reasoning is strengthened by Reviewer B's additional observation.**

#### 1.6 Reviewer B Rebuttal 2.3: COVID-19 pandemic period handling

Reviewer B (Rebuttal 2.3) argues that the COVID-19 concern deserves ongoing attention, noting that the original source computes IRR relative to 2020-2022 (line 375), and that the pipeline comments this out (`trendy.R` lines 641-642).

**Assessment: Reviewer B's point about the commented-out 2020-2022 comparison period is valid as a completeness concern (addressed separately under comparison periods below), but does not change the severity of the model specification issue.** Neither the original source nor the pipeline includes a pandemic indicator variable. Both use unmodified splines that smooth through the pandemic. Since the original published analysis also did this, the pipeline's omission is consistent with published methodology. The commented-out comparison periods are a separate, lower-severity issue. **Verdict: MEDIUM unchanged for model specification; the comparison period gap is addressed in the updated priority list.**

---

### 2. Concession Validation

#### 2.1 Reviewer A Concessions

**A1.1 (Cyclospora/Salmonella duplication severity downgraded to MEDIUM):** Appropriate. Reviewer A correctly concedes that the `--pathogen` filter at `trendy.R` line 493 excludes the NA-pathogen rows from dedicated analysis functions in the standard Nextflow workflow. The concession to MEDIUM is well-calibrated.

**A1.2 (Year factor/numeric round-trip downgraded to LOW):** Appropriate. The `as.numeric(as.character(factor))` idiom is standard R practice and will not fail for numeric-origin factor levels. Reviewer A correctly concedes this was overstated.

**A1.3 (Catchment filter pathogen_type concern -- missed in original):** Appropriate. Reviewer A correctly acknowledges this was a gap in their original review. The latent bug at `functions.R` line 243 (passing `"bacterial"` for mixed bacterial/parasitic data) is real and was correctly identified by Reviewer B.

**A1.4 (Baseline IR computation -- deeper structural divergence):** Appropriate. Reviewer A correctly concedes the full scope of the issue was not articulated in their original review. The revised reasoning is precise and accurate.

**Overall assessment of Reviewer A's concessions: All four are appropriate in scope and severity. Reviewer A neither conceded too much nor too little.**

#### 2.2 Reviewer B Concessions

**1.1 (epred_draws vs. add_linpred_draws downgraded from HIGH to MEDIUM):** Appropriate. Reviewer B correctly concedes the algebraic equivalence for the conditional mean and retracts the incorrect claim about uncertainty propagation through the shape parameter. The revised MEDIUM rating for the naming/documentation issue is well-calibrated.

**1.2 (Cyclospora/Salmonella duplication downgraded from CRITICAL to MEDIUM/HIGH):** Appropriate. Reviewer B correctly concedes the mitigation through the missing `pathogen` column and the `--pathogen` filter. The tiered severity (MEDIUM for Nextflow, HIGH for standalone) matches my original arbitration.

**1.3 (Production vs. publication profile distinction acknowledged):** Appropriate. Reviewer B correctly concedes that they conflated the Nextflow `production` profile with the bash `publication` flag and acknowledges the three-tier configuration structure.

**Overall assessment of Reviewer B's concessions: All three are appropriate. Reviewer B conceded the right things and did not overcorrect. The epred_draws concession in particular shows intellectual honesty -- Reviewer B withdrew a technically incorrect claim about uncertainty propagation rather than merely softening the language.**

---

### 3. Publication Analysis

Note: Direct access to the full publication text (doi:10.15212/ZOONOSES-2025-0030) was unavailable. This analysis uses the original source scripts and reference output as proxies, consistent with Reviewer B's approach, and is supplemented by both reviewers' independent publication analyses.

#### 3.1 Pipeline Implementation vs. Published Methodology

**Model specification:** The pipeline faithfully implements the published model formula. The negative binomial GAM with state-specific splines, state fixed effects, and log-population offset at `functions.R` line 402 matches `source/splinesmodel_16Mar2024_OrCatch.R` line 232-236. Both reviewers confirm this in their addenda (Reviewer A Section A3.6, Reviewer B Section 3.1). **No discrepancy.**

**Posterior prediction extraction:** The pipeline uses `epred_draws()` (response-scale) at `functions.R` line 442; the original uses `add_linpred_draws(transform=FALSE)` at source line 247. Both reviewers now agree these are algebraically equivalent for the conditional mean. The catchment aggregation (summing response-scale predictions across states) is equivalent in both approaches: the original exponentiates per-state linear predictors at source line 260 then sums at line 261; the pipeline sums `.epred` directly at `functions.R` line 475. **No statistical discrepancy; pipeline approach is cleaner.**

**Baseline IR computation:** This remains the most significant divergence. The original (source lines 331-333) computes `mean` of raw `.value`, `count`, and `population` separately across baseline years within each draw, then derives IR from the ratio. The pipeline (`functions.R` lines 670-674) computes year-specific IRs first, then takes `median`. The reference output confirms the original approach: for example, Campylobacter 2023 vs. 2016-2018 shows `ref.est.ir_median = 11.9` (line 27 of the CSV), which is derived from the population-weighted mean of 3-year baseline values. The pipeline would produce a different baseline IR. **Confirmed methodological divergence.**

**HDI computation:** The original (source lines 299-309) computes HDI on log-transformed `.value` and back-transforms. The pipeline (`functions.R` lines 512-513) computes HDI directly on response-scale `.epred`. The reference output's interval bounds (e.g., Campylobacter 2023: estimated IR 9.30 [8.83, 9.80]) were produced by the log-scale method. **Confirmed methodological divergence.**

**MCMC parameters:** The original uses 6 chains, 5001 iterations, adapt_delta=0.999, max_treedepth=19, seed=47 (source lines 234-236). The pipeline's `publication` bash flag uses 6 chains, 10001 iterations, adapt_delta=0.99, max_treedepth=15, seed=123 (`run_workflow.sh` lines 820-824). The Nextflow `production` profile uses 4 chains, 2000 iterations, adapt_delta=0.99, max_treedepth=15 (`nextflow.config` lines 102-107). Both pipeline configurations use weaker `adapt_delta` (0.99 vs. 0.999) and shallower `max_treedepth` (15 vs. 19). The `publication` flag uses more total post-warmup draws (6 chains x 5001 = 30,006 vs. original's 6 x 2501 = 15,006), which partially compensates for the weaker adaptation. **Partial divergence; the adapt_delta difference is the most consequential because 0.999 vs. 0.99 affects the sampler's ability to explore difficult posterior geometries for the spline model.**

**Comparison periods:** The original computes four baselines: 2016-2018, 2020-2022, 2004-2006, 2006-2008 (source lines 366-399). `Unspeciated_Shigella.R` adds 2010-2012 (line 403). The pipeline has only 2016-2018 active (`trendy.R` line 637); the other three are commented out (lines 641-650). The reference CSV confirms all four periods were used in published results. **Confirmed gap: only 1 of 4 published comparison periods is active.**

**Travel label logic:** The original uses `&` (AND) at source line 223. The pipeline uses `||` (OR) at `trendy.R` line 271. This is a confirmed refactoring bug. **Divergence.**

#### 3.2 Methodological Choices in the Paper Not Implemented by the Pipeline

1. **Automated serotype ranking (`mostcommonsero` function):** The original source at lines 162-172 dynamically identifies the top 10 most common Salmonella serotypes in the most recent year and models each separately. The pipeline requires manual specification via `--subgroup`. This is a significant loss of automation noted by Reviewer B (Section 3.2). The reference CSV confirms serotype-specific results (rows for ENTERITIDIS, TYPHIMURIUM, NEWPORT, JAVIANA, INFANTIS, I 4,[5],12:i:-, BRAENDERUP, MISSISSIPPI, SAINTPAUL, MUENCHEN).

2. **Parallel pathogen processing via `furrr`:** The original (source lines 419-425) uses `furrr::future_map()` with `workers=10` to fit all pathogens in parallel. The pipeline relies on Nextflow for parallelization. This is an architectural difference, not a statistical one, but it means standalone R usage processes pathogens sequentially.

3. **Cyclospora exclusion from the main bacterial path:** The original source at line 107 explicitly excludes Cyclospora from the main pathogen dataset: `filter(pathogen %in% pathogens & pathogen!="CYCLOSPORA")`. Cyclospora is then processed ONLY through the dedicated parasitic path (lines 137-157). The pipeline's `PATH_ANALYSIS` at `functions.R` line 185 processes ALL pathogens including Cyclospora, then also calls `CYCLOSPORA_ANALYSIS`. This is the root cause of the duplication issue. Reviewer B's new finding (Section 5.5) correctly identifies this divergence from the original source's design. **This is an important detail that neither my original arbitration nor Reviewer A's review identified -- Reviewer B's addendum adds genuine value here.**

4. **`save_all_pars=TRUE`:** The original (source line 234) saves all parameter draws. The pipeline omits this (deprecated in newer `brms` versions). Reviewer B (Section 5.7) correctly notes this may affect post-hoc diagnostics like LOO-CV.

#### 3.3 Pipeline Implementation Details That Go Beyond or Diverge from the Paper

1. **Configurable catchment definitions:** The pipeline's `read_catchment_config()` at `functions.R` lines 68-83 allows custom catchment configurations via CSV, while the original hardcodes the state filter at source line 128. This is a significant improvement for extensibility.

2. **Pathogen name standardization in preprocessing:** The pipeline's `preprocess.R` lines 123-316 include a sophisticated pathogen matching system with configurable sensitivity levels (STRICT, MEDIUM, RELAXED) and fuzzy matching via `stringdist`. The original source has no equivalent preprocessing step, relying on pre-cleaned data.

3. **Subgroup handling via command-line parameters:** The pipeline's `--subgroup` mechanism (`trendy.R` lines 412-448) is more flexible than the original's hardcoded STEC O157/NONO157 split (source lines 108-109), though it loses the automated serotype ranking.

4. **Listeria CSTE filter placement:** Both the original (source line 110) and pipeline (`preprocess.R` lines 390-399) apply the CSTE filter for Listeria. The pipeline applies it during preprocessing; the original applies it during data aggregation. Functionally equivalent, but the pipeline's approach permanently excludes non-CSTE Listeria from the cleaned CSV. Reviewer B (Section 3.2) correctly notes this distinction.

5. **Correct site-level incidence computation:** The pipeline's use of `epred_draws()` at `functions.R` line 442 produces correct response-scale values for site-level incidence computation (`.epred / (population/100000)` at line 496). The original source at line 249-250 computes `(.linpred) / (population/100000)`, dividing the LOG-scale linear predictor by population -- a meaningless intermediate quantity. As noted in my original arbitration (Section 4.9) and confirmed by both reviewers, this is one area where the pipeline genuinely improves on the original.

#### 3.4 Does the Paper Validate or Contradict Review Findings?

The reference output (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) provides empirical evidence for several review findings:

- **Baseline IR computation divergence (H1):** The reference output for Campylobacter 2023 vs. 2016-2018 reports `ref.est.ir_median = 11.9`, `rr_median = 0.78`, `pct.change_median = -21.9`. These values were produced by the population-weighted mean approach. The pipeline's median-of-rates approach would produce a different `baseline_ir` and therefore different IRR and percent change values. **Validates the finding.**

- **HDI bounds divergence:** The reference output's interval bounds (e.g., Campylobacter: pinc 9.30 [8.83, 9.80] for the 2016-2018 baseline) were produced by the log-scale HDI method. The pipeline's response-scale HDI would produce different bounds. **Validates the finding.**

- **Four comparison periods used in published results:** The reference CSV contains rows with `startyear` values of 2004, 2006, 2016, and 2020 for each pathogen. The pipeline's single active period (2016-2018) produces only a subset of these results. **Validates the finding that commented-out periods are a gap.**

- **MCMC parameters -- adapt_delta 0.999:** The original source uses 0.999 at line 234. The reference output includes results for Cyclospora, which has highly variable, low-count data (the 2004-2006 baseline shows Cyclospora with IRR = 39.16 [16.22, 104.73] -- extremely wide intervals). This suggests the conservative adapt_delta was important for pathogen models with difficult posterior geometries. **Supports Reviewer A's concern (A3.1) about the pipeline's weaker adapt_delta.**

---

### 4. New Findings from the Publication

#### 4.1 The original source's Cyclospora exclusion from the main path is a critical design detail

Reviewer B's addendum (Section 5.5) identifies that the original source at line 107 explicitly excludes Cyclospora from the main pathogen dataset (`pathogen!="CYCLOSPORA"`) before combining with the dedicated Cyclospora path via `smartbind` (line 209). The pipeline's `PATH_ANALYSIS` at `functions.R` line 185 does NOT exclude Cyclospora -- it processes `all_pathogens <- unique(mmwrdata$pathogen)`, which includes Cyclospora. This means the pipeline processes Cyclospora through BOTH `PATH_ANALYSIS` (with Parasitic census, correctly) AND `CYCLOSPORA_ANALYSIS` (also with Parasitic census), whereas the original processes it ONLY through the dedicated path.

This detail was not identified in my original arbitration. It clarifies the root cause of the duplication issue and provides the cleanest fix: either exclude Cyclospora from `PATH_ANALYSIS` (matching the original design) or remove the `CYCLOSPORA_ANALYSIS` call entirely (since `PATH_ANALYSIS` handles it correctly with the Parasitic census). My original fix recommendation (H4) was correct in direction but lacked this diagnostic precision. **Credit to Reviewer B for this finding.**

#### 4.2 The reference output reveals the published analysis includes Salmonella serotype-specific models

The reference CSV contains rows for individual Salmonella serotypes: ENTERITIDIS, TYPHIMURIUM, NEWPORT, JAVIANA, INFANTIS, I 4,[5],12:i:-, BRAENDERUP, MISSISSIPPI, SAINTPAUL, MUENCHEN. These were produced by the `mostcommonsero()` function at source lines 162-172, which dynamically identifies the top 10 serotypes. The pipeline cannot replicate this without manual specification of each serotype via `--subgroup`. This is a functional gap that none of the three reviews (including my original) explicitly flagged as a priority issue.

#### 4.3 The original source processes multiple travel/CIDT combinations in a single script run

The original source at lines 405-505 runs four complete analysis cycles with different travel/CIDT combinations:
1. Travel = NO, UNKNOWN, YES; CIDT = CIDT+, CX+, PARASITIC (line 406-407)
2. Travel = NO, UNKNOWN; CIDT = CIDT+, CX+, PARASITIC (line 434-435)
3. Travel = NO; CIDT = CIDT+, CX+, PARASITIC (line 458-459)
4. Travel = NO, UNKNOWN, YES; CIDT = CX+, PARASITIC (line 485-486)

The pipeline handles only one travel/CIDT combination per run, with the Nextflow workflow expected to orchestrate multiple runs. This is a valid architectural choice but means the pipeline requires external orchestration to replicate the full published analysis matrix. None of the three reviews flagged this explicitly.

#### 4.4 Equal-tailed intervals are also reported in the original source

The original source at `from_linpred_catchIR` (lines 287-296) computes BOTH equal-tailed intervals (via `quantile` at lines 289-291) AND HDI intervals (via `HDInterval::hdi` at lines 299-300). Both sets of bounds are included in the output. The pipeline's `LINPRED_TO_CATCHIR` at `functions.R` lines 494-523 also computes both. However, the pipeline computes BOTH on the response scale, while the original computes equal-tailed intervals on the response scale but HDI on the log scale. The original's `IR.comp` function (lines 329-361) reports only equal-tailed intervals for IRR and percent change, not HDI. The reference CSV confirms this: the `rr_LL`, `rr_UL`, `pct.change_LL`, and `pct.change_UL` columns use equal-tailed intervals (quantile-based), not HDI. This means the HDI scale difference primarily affects the incidence rate bounds (`hdi.LL`, `hdi.UL`), not the IRR bounds.

This nuance was not identified by any of the three reviews. It slightly reduces the practical impact of the HDI scale difference for IRR reporting, though it remains relevant for incidence rate reporting.

#### 4.5 The original source uses `bayestestR` for CI computation

The original source loads `library(bayestestR)` at line 48, but the only reference to it is a commented-out line at source line 344: `# ci_hdi <- bayestestR::ci(comb$, method = "HDI")`. This suggests the original authors considered using `bayestestR` for HDI computation on IRR/percent change but ultimately used equal-tailed quantile intervals instead. The pipeline does not load `bayestestR`. This is a minor observation but confirms that HDI was intentionally NOT used for IRR/percent change bounds in the published results -- only for incidence rate bounds.

---

### 5. Updated Unified Priority List

This list supersedes Section 5 of the original arbitration. It incorporates all rebuttal arguments, both reviewers' publication comparisons, and the findings above.

#### CRITICAL

*None.* No individual issue rises to CRITICAL severity in the standard Nextflow deployment. However, the cumulative effect of H1 + H2 + H3 means the pipeline currently cannot reliably reproduce the published results, which is arguably a CRITICAL-level concern for its stated purpose.

#### HIGH

**H1. Baseline IR computation uses median of year-specific rates instead of population-weighted mean of components** *(unchanged from original)*
- **Location:** `functions.R` lines 670-674
- **Root cause:** The pipeline computes `ir = .epred/(population/100000)` per year within each draw, then takes `median(ir)` as the baseline. The original source (lines 331-333) averages raw `.value`, `count`, and `population` separately across baseline years within each draw, then derives baseline IR from the ratio `mean(.value) / (mean(population)/100000)`.
- **Impact:** The pipeline's approach (1) gives equal weight to each year regardless of population, and (2) uses `median` over 3 values, which selects only the middle value and discards information from the other two years. The reference output (e.g., Campylobacter 2023 vs. 2016-2018: `ref.est.ir_median = 11.9`, `rr_median = 0.78`) was produced by the original approach. The pipeline would produce different IRR and percent change estimates.
- **Fix:** Replace `summarise(baseline_ir = median(ir), baseline_count = median(count))` with: compute `baseline_value = mean(.epred)`, `baseline_pop = mean(population)`, `baseline_count = mean(count)`, then derive `baseline_ir = baseline_value / (baseline_pop / 100000)`.
- **Reviewers' positions:** Both reviewers agree at HIGH. Reviewer B's addendum (Rebuttal 2.2) adds the observation about median-induced information loss. Both rebuttals accepted.

**H2. No programmatic convergence diagnostics** *(unchanged from original)*
- **Location:** `trendy.R` lines 571-688, `functions.R` lines 394-416
- **Impact:** Unreliable posterior estimates could propagate to published results without warning. The reference output includes Cyclospora estimates with extremely wide intervals (IRR 39.16 [16.22, 104.73] for 2004-2006 baseline), suggesting some pathogen models are pushing the sampler's limits.
- **Fix:** After `brm()`, extract `rhat()`, `neff_ratio()`, and divergent transition counts. Emit warnings or halt if diagnostics fail.
- **Reviewers' positions:** Both agree at HIGH. No rebuttals.

**H3. HDI computed on response scale instead of log scale (methodological divergence from published results)** *(upgraded from MEDIUM)*
- **Location:** `functions.R` lines 512-513, 519-520, 703-704, 710-711
- **Root cause:** The original source (lines 299-309) computes HDI on `log(.value)` then exponentiates. The pipeline computes HDI directly on response-scale `.epred`.
- **Impact:** Reported HDI bounds for incidence rates will differ from published values. Note: the IRR/percent change bounds in the reference output use equal-tailed intervals, not HDI (see New Finding 4.4), so the HDI divergence primarily affects incidence rate reporting rather than IRR reporting.
- **Fix:** Transform to log scale before HDI computation and back-transform, matching the original methodology. Or explicitly document and justify the deviation.
- **Upgrade rationale:** Both reviewers argued persuasively in their rebuttals (Reviewer A Section A2.2, Reviewer B Section 2.1) that replication fidelity requires matching the published interval computation method. I accept their arguments.

**H4. HDI fallback silently produces equal-tailed intervals labeled as HDI** *(unchanged from original)*
- **Location:** `functions.R` lines 52-59
- **Fix:** Make `HDInterval` a hard dependency. It is already listed in `trendy.R` line 259's package loading.
- **Reviewers' positions:** Both agree at HIGH. No rebuttals.

**H5. Cyclospora/Salmonella dual processing path** *(unchanged severity; improved diagnosis)*
- **Location:** `trendy.R` lines 462-477, `functions.R` lines 182-316
- **Root cause clarification:** Reviewer B's addendum (Section 5.5) identifies the precise divergence: the original source at line 107 explicitly excludes Cyclospora from the main pathogen dataset (`pathogen!="CYCLOSPORA"`), processing it only through the dedicated parasitic path. The pipeline's `PATH_ANALYSIS` includes Cyclospora (via `all_pathogens <- unique(mmwrdata$pathogen)` at line 185), then also calls `CYCLOSPORA_ANALYSIS`, creating the dual-processing issue.
- **Impact:** MEDIUM in standard Nextflow workflow (NA-pathogen rows filtered by `subset` at `trendy.R` line 493); HIGH in standalone usage without `--pathogen`.
- **Fix:** Either (a) exclude CYCLOSPORA from `PATH_ANALYSIS` to match the original design, or (b) remove the `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS` calls since `PATH_ANALYSIS` handles them correctly. Option (a) is more faithful to the original design; option (b) is simpler.

#### MEDIUM

**M1. adapt_delta 0.99 vs. published 0.999**
- **Location:** `run_workflow.sh` line 823, `nextflow.config` line 104
- **Both** the `publication` bash flag and the `production` Nextflow profile use 0.99. The original source uses 0.999 (line 234). The more conservative value reduces divergent transitions for difficult posterior geometries (e.g., Cyclospora with extreme count variability). Reviewer A's addendum (A3.1) correctly flags this.
- **Fix:** Update at least the `publication` flag to 0.999, and consider updating `production` as well.

**M2. Production Nextflow profile is weaker than publication settings and original source** *(unchanged from original)*
- **Location:** `nextflow.config` lines 102-107 vs. `run_workflow.sh` lines 820-824
- **Fix:** Align the Nextflow `production` profile with the `publication` bash settings. Consider adding a `publication` Nextflow profile.

**M3. Travel label logic bug (unreachable branch)** *(unchanged from original)*
- **Location:** `trendy.R` line 271
- **Fix:** Change `||` to `&` to match the original source at line 223.

**M4. No explicit priors in brm() call** *(unchanged from original)*
- **Location:** `functions.R` lines 395-411
- **Fix:** Explicitly specify priors matching the current `brms` defaults.

**M5. Catchment filter uses "bacterial" for mixed bacterial/parasitic data** *(unchanged from original)*
- **Location:** `functions.R` line 243
- **Fix:** Pass `"both"` or apply separate filters for bacterial vs. parasitic subsets.

**M6. Error message discards original error in PROPOSED_BM tryCatch** *(unchanged from original)*
- **Location:** `functions.R` lines 412-414
- **Fix:** Include the original error message: `stop(paste("Model fitting failed:", e$message))`.

**M7. Misleading function name and comments for posterior draw extraction** *(unchanged from original)*
- **Location:** `functions.R` line 434, `trendy.R` line 595
- **Fix:** Rename to `EPRED_DRAW_FN` or `RESPONSE_DRAW_FN`. Update comment.

**M8. Only 1 of 4 published comparison periods is active** *(upgraded from LOW)*
- **Location:** `trendy.R` lines 641-650
- **Root cause:** The original source computes IRR for four baseline periods (2016-2018, 2020-2022, 2004-2006, 2006-2008). The pipeline has only 2016-2018 active; the other three are commented out. The reference CSV confirms all four were used in published results.
- **Fix:** Uncomment lines 641-650 or make comparison periods configurable via command-line parameters.
- **Upgrade rationale:** Both reviewers flag this in their addenda. For replication of published results, this is not merely a convenience issue -- it is a functional gap. Upgraded from LOW to MEDIUM.

**M9. No COVID-19 pandemic period adjustment or caveat** *(unchanged from original)*
- **Location:** Model specification (`functions.R` line 402)
- **Note:** The original published analysis also lacks a pandemic indicator. This is a shared limitation, not a pipeline-specific divergence.

**M10. Memory allocation not linked to chain count** *(unchanged from original)*
- **Location:** `nextflow.config` lines 140-147

**M11. No automated Salmonella serotype ranking** *(new)*
- **Location:** Pipeline lacks equivalent of `mostcommonsero()` function (original source lines 162-172)
- **Impact:** The published analysis dynamically identifies and models the top 10 Salmonella serotypes. The pipeline requires manual specification via `--subgroup`, which is less reproducible and more error-prone.
- **Fix:** Implement a serotype ranking step in preprocessing or add a `--top-serotypes N` parameter.

#### LOW

**L1. Dead code: PLOT_PCTCHange_TREND function** (`functions.R` lines 747-770). Remove.

**L2. combine_files uses setwd() and undeclared dependencies** (`functions.R` lines 773-784). Refactor or remove.

**L3. Hardcoded 2004 reference line without annotation** (`functions.R` lines 602, 635). Add annotation.

**L4. SAFE_WRITE append behavior** (`functions.R` lines 156-158). Document or add overwrite-on-first-write logic. Reviewer B concedes this is operational (Addendum item 8).

**L5. LISTERIA and CRYPTOSPORIDIUM missing from ALL_PATHOGENS** (`run_workflow.sh` line 24). Add or document exclusion.

**L6. Duplicated code in LINPRED_TO_CATCHIR / LINPRED_TO_SITEIR** (`functions.R` lines 494-569). Refactor.

**L7. Year factor/numeric round-trip** (`trendy.R` line 540, `functions.R` lines 381-383). Unnecessary; keep year numeric. Both Reviewer A (A1.2) and the original arbitration agree this is LOW.

**L8. Seed difference from original** (pipeline: 123, original: 47). Document.

**L9. R_LIBS environment path typo** (`nextflow.config` line 122). Verify against container.

**L10. Redundant ir and est_ir columns** (`functions.R` lines 683-684). Remove duplicate.

**L11. Potential division by zero in relative risk** (`functions.R` line 685). Add guard clause.

**L12. No validation before calling dedicated analysis functions** (`trendy.R` lines 468-473). Add existence check.

**L13. save_all_pars omitted** (original source line 234). Document; may affect LOO-CV post-hoc analyses.

**L14. max_treedepth 15 vs. published 19** (both pipeline modes). Unlikely to matter for most models; document.

**L15. Listeria CSTE filter applied in preprocessing vs. aggregation** (`preprocess.R` lines 390-399 vs. source line 110). Functionally equivalent but pipeline approach permanently excludes non-CSTE cases from cleaned CSV.

---

### 6. Final Overall Assessment

#### Has the overall verdict changed?

The original arbitration concluded: "Not yet in its current state, but close." After reviewing both reviewers' rebuttals and comparing more closely against the reference output, I refine this verdict:

**The pipeline is not production-ready for replication of published MMWR results in its current form.** The three HIGH-severity methodological divergences (baseline IR computation, HDI scale, and comparison period gaps) mean that the pipeline's output would differ numerically from published values in ways that would be noticeable to readers comparing pipeline outputs against the publication. These are not edge cases -- they affect every pathogen's IRR and percent change estimates (H1), every pathogen's incidence rate intervals (H3), and the completeness of the comparison period matrix (M8).

**However, the pipeline is architecturally sound and close to production-ready.** The core model specification is faithfully implemented. The Nextflow orchestration, configurable parameters, and modular design represent genuine improvements over the monolithic original scripts. The use of `epred_draws` is an improvement that avoids the original source's site-level incidence bug. The preprocessing system is more robust and extensible.

#### What must be fixed before the pipeline can replace the original scripts?

1. **H1 (Baseline IR computation):** Replace median-of-rates with population-weighted mean-of-components. This is the single most impactful fix -- a roughly 10-line code change at `functions.R` lines 670-674 that would bring all IRR and percent change estimates in line with published values.

2. **H3 (HDI scale):** Compute HDI on log-transformed values and back-transform, matching the original methodology. This is a roughly 5-line change at each HDI computation site (`functions.R` lines 512-513, 519-520, 703-704, 710-711).

3. **H4 (HDI fallback):** Make `HDInterval` a hard dependency. One-line change.

4. **H5 (Dual processing):** Either exclude Cyclospora from `PATH_ANALYSIS` or remove the dedicated `CYCLOSPORA_ANALYSIS` call. Straightforward refactoring.

5. **M1 (adapt_delta):** Change 0.99 to 0.999 in the `publication` configuration.

6. **M3 (Travel label):** Change `||` to `&` at `trendy.R` line 271. One-character fix.

7. **M8 (Comparison periods):** Uncomment the three additional comparison periods.

These seven fixes -- totaling perhaps 30-40 lines of code changes -- would bring the pipeline into alignment with the published methodology and address all HIGH-severity findings.

#### What are genuine improvements over the original?

- Correct site-level incidence computation via `epred_draws` (avoids original's log-scale division bug at source line 250)
- Configurable catchment definitions (extensible beyond the 10 hardcoded states)
- Robust pathogen name standardization in preprocessing
- Nextflow-based parallelization and resource management
- Cleaner catchment aggregation code (direct `.epred` summation vs. wide-format reshape-and-exponentiate)
- Input validation and error handling throughout

#### Quality of the Review Process

Both reviewers performed thorough, professional reviews. Their addenda demonstrate intellectual honesty -- both conceded where they were wrong and provided new findings of value. Reviewer A's concessions on the duplication severity and year round-trip risk were appropriate. Reviewer B's concession on `epred_draws` equivalence was technically precise. Both reviewers' rebuttals on the HDI scale issue were persuasive and led to an upgrade in this addendum.

Reviewer B's new finding about Cyclospora exclusion from the main path in the original source (Section 5.5) adds diagnostic precision to the duplication issue that was lacking in all three initial reviews. Reviewer A's publication parameter comparison table (A3.1) is comprehensive and useful for implementers.

The three-round review process has produced a thorough, well-calibrated assessment of the pipeline. The remaining issues are well-defined and actionable.

---

*Addendum prepared as the final arbitration response incorporating both reviewers' rebuttals, publication methodology comparison via source scripts and reference output, and updated priority assessment.*

---

## Addendum 2: Final Arbitration Based on the Actual Published Paper

**Date:** 2026-03-13
**Paper reviewed:** Weller DL, Sevilla S, Hetrick E, Billig Rose E, Forstedt J, Caravas J, Ray LC, Payne DC, Steele MK, Hoekstra RM, Bruce BB. "Enhanced Bayesian Spline Regression Approach for Modelling Trends in Infections Caused by Pathogens Commonly Transmitted Through Food." *Zoonoses* (2026) 6:3. DOI: 10.15212/ZOONOSES-2025-0030. Published online February 26, 2026.

**Context:** My previous addendum (Section 3, "Publication Analysis") was based entirely on the source scripts (`source/splinesmodel_16Mar2024_OrCatch.R`, `source/Unspeciated_Shigella.R`) and reference CSV output as proxies for the published methodology. I had not read the actual paper. Both Reviewer A and Reviewer B have now appended Addendum 2 sections based on the full published paper. This final addendum corrects my previous analysis where the paper reveals it was wrong, adjudicates where the two reviewers agree and disagree in their paper-based analyses, and produces a definitive unified priority list that supersedes all previous lists.

---

### 1. Corrections to My Previous Addendum

#### 1.1 CORRECTION: The paper specifies 10,001 iterations, not 5,001

My previous addendum (Section 3.1, "MCMC parameters") stated the original source uses "6 chains, 5001 iterations" based on `source/splinesmodel_16Mar2024_OrCatch.R` line 234 (`iter=5001`). The paper explicitly states "6 chains and 10,001 iterations" (page 5). This means either: (a) the source scripts in the repository are an earlier version that does not match the final published analysis, or (b) the paper describes a different run configuration than what the repository scripts implement. The pipeline's `publication` flag at `run_workflow.sh` line 822 uses `iterations=10001`, which matches the paper, not the source script. My previous characterization of the `publication` flag as using "more total post-warmup draws" than the original was framed as an unexplained deviation -- it is now clear the pipeline's `publication` flag was correctly targeting the paper's specifications, while the source scripts in the repository represent an earlier configuration. This also means my previous analysis overstated the fidelity of the source scripts as proxies for the published methodology.

#### 1.2 CORRECTION: The paper documents specific priors -- my previous analysis was incomplete

My previous addendum (Section 3.1, "Model specification") stated "No discrepancy" for the model specification, treating the `brm()` call's lack of explicit priors as a non-issue because `brms` defaults were used. The paper (page 5 and page 11) explicitly documents the prior values: `student_t(3, -8.84, 2.5)` on the intercept, `student_t(3, 0, 2.5)` on SD parameters, `inv_gamma(0.4, 0.3)` on the shape parameter, and flat priors for regression coefficients. My previous assessment that "M4. No explicit priors in brm() call" was MEDIUM severity was directionally correct but missed the paper's explicit documentation of these values. The paper further explains (page 11) that these were a deliberate choice "to ensure comparability with the original frequentist methods" and identifies the use of flat/weakly informative priors as a limitation. The pipeline's reliance on `brms` auto-defaults will reproduce these priors only when the input data has similar characteristics to the 1996-2019 dataset used in the paper. For the intercept prior in particular, the location parameter (-8.84) is data-dependent, so different data ranges will produce different auto-computed priors -- which is actually the intended behavior for `brms` defaults but means strict numerical replication of the paper's results requires either the same input data or hard-coded priors.

#### 1.3 CORRECTION: The adapt_delta and max_treedepth values cannot be attributed to the paper

My previous addendum (Section 3.1) stated the original uses "adapt_delta=0.999, max_treedepth=19" based on the source script, and characterized the pipeline's 0.99/15 as a divergence from "published" values. The paper is silent on both parameters -- it specifies only chains and iterations. Given Correction 1.1 (the source scripts do not match the paper's iteration count), I can no longer assume the source script's `adapt_delta=0.999` and `max_treedepth=19` were used in the actual published analysis. These values may have been used, or they may have been different. The divergence remains a concern (the source script is the best available reference for the actual run), but I previously overstated the certainty of attribution to the publication.

#### 1.4 CORRECTION: The paper is a methods paper, not a surveillance report

My previous addendum (Section 3.1) extensively analyzed the pipeline's ability to reproduce the reference CSV output (comparison periods, IRR values, etc.) as though the paper itself published these specific surveillance results. Having read the paper, it is clear that the paper is a **methodological description and comparison** -- it demonstrates model improvements over the original approach using 1996-2019 data. The paper does not publish surveillance IRR tables. The reference CSV (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) represents operational MMWR outputs, not the paper's specific results. My previous framing of the comparison period gap (M8) as a failure to reproduce "published results" was overstated for the paper itself, though it remains valid for operational MMWR reporting purposes.

#### 1.5 CORRECTION: Salmonella serotype count is 16, not 10

My previous addendum (Section 3.2) stated the original source "dynamically identifies the top 10 most common Salmonella serotypes" based on the `mostcommonsero()` function. The paper's Figure 2 explicitly shows **16** Salmonella serotypes, selected based on frequency during 2016-2018 (not the most recent year). The source code's dynamic approach and the paper's final analysis used different N values and reference periods. This means the source scripts are less reliable proxies for the paper's analysis choices than I previously assumed.

#### 1.6 CORRECTION: The paper's COVID-19 discussion validates the spline approach

My previous addendum (Section 1.6, addressing Reviewer B's Rebuttal 2.3) stated that "neither the original source nor the pipeline includes a pandemic indicator variable" and maintained this as a shared MEDIUM-severity limitation. The paper explicitly addresses COVID-19 as a demonstration of the model's nowcasting capability (Figure 5 and accompanying text, pages 8 and 10). The paper interprets the spline's smooth extrapolation through the pandemic period as a feature -- estimating what incidence "would have been" absent the pandemic disruption -- rather than a limitation. The discrepancy between modeled and observed 2020-2021 incidence is attributed to "reduced foodborne illness exposure and reporting during the COVID-19 pandemic, rather than to poor predictive performance." My previous severity rating of MEDIUM for the absence of a pandemic indicator was based on a source-code-only analysis that missed the paper's explicit framing of this as intentional methodology.

#### 1.7 MINOR CORRECTION: The paper uses brms version 2.20.1

My previous addendum did not address package versions. The paper specifies `brms` version 2.20.1, `tidybayes` version 3.0.7, and R version 4.4.0. The pipeline does not pin any package versions. This is a new concern relevant to exact reproducibility that I should have flagged as a general infrastructure issue.

---

### 2. Reviewer Agreement and Disagreement on the Paper

#### 2.1 Areas of Agreement Between Reviewer A and Reviewer B

Both reviewers agree on the following after reading the paper, and I concur with all:

**2.1.1 Model formula is a confirmed match.** Both reviewers validate that the pipeline's `count ~ s(year, by = state) + state + offset(log(population))` with `family = negbinomial()` exactly matches the paper's description. No dispute.

**2.1.2 Site-level aggregation is confirmed correct.** Both reviewers note the paper explicitly evaluated and rejected county-level models on computational grounds, validating the pipeline's state-level approach. No dispute.

**2.1.3 Catchment aggregation logic matches.** Both reviewers confirm the paper's description of summing exponentiated draws across sites per draw-year matches the pipeline's `CATCHMENT` function. Reviewer A (B2.4) provides the more precise characterization: the paper exponentiates linear predictor draws per state before summing, and `epred_draws` returns already-exponentiated values, making the operations algebraically identical. No dispute.

**2.1.4 Default brms priors are intentional per the paper.** Both reviewers note the paper explicitly documents that brms default priors were used and explains this was a deliberate choice for frequentist comparability. Both correctly observe that the pipeline's omission of explicit priors in the `brm()` call reproduces this behavior. No dispute.

**2.1.5 Baseline IR computation remains a HIGH divergence.** Both reviewers maintain that the pipeline's `median(ir)` approach at `functions.R` lines 670-674 diverges from the paper's "average" terminology and the source code's `mean()` implementation. No dispute.

**2.1.6 HDI computation scale remains a divergence.** Both reviewers confirm the paper does not specify the scale of HDI computation, but the source code (which produced the paper's results) uses log-scale HDI. No dispute.

**2.1.7 The paper describes nowcasting as a key capability not formalized in the pipeline.** Both reviewers independently identify this as a gap. No dispute.

**2.1.8 CIDT is a known limitation acknowledged by the paper.** Both reviewers note the paper explicitly discusses CIDT as a complicating factor and proposes future CIDT-method-by-site-by-year interactions. No dispute.

#### 2.2 Areas of Disagreement and Adjudication

**2.2.1 Severity of the `epred_draws` vs. `add_linpred_draws` divergence.**

Reviewer A (B3.1) rates this as "LOW for numerical accuracy, MEDIUM for reproducibility traceability." Reviewer B does not assign a separate severity rating to this specific item in Addendum 2 but validates it as a match at the algebraic level (Section 2.4) while noting the pipeline's approach is "actually more correct" for site-level IR computation (implicitly LOW concern).

**Adjudication:** Reviewer A is correct to separate numerical accuracy from traceability. The paper explicitly names `add_linpred_draws` as the method used. A reader comparing the pipeline code to the paper would flag `epred_draws` as an undocumented substitution. However, the pipeline's use of `epred_draws` is arguably an improvement -- it avoids the original source's bug where log-scale linear predictors were divided by population for site-level IR (source line 249-250), as I identified in my previous addendum (Section 3.3 item 5). **Verdict: LOW for numerical impact, MEDIUM for traceability. The pipeline should document that `epred_draws` was chosen as a numerically equivalent but computationally cleaner alternative to `add_linpred_draws` + exponentiation, and note the improvement for site-level IR computation.**

**2.2.2 Severity of the prior specification gap.**

Reviewer A (B3.2) rates the lack of explicit priors in the pipeline code as "MEDIUM" because the paper's documented priors are brms auto-defaults that the pipeline correctly reproduces via the same mechanism. Reviewer B (Section 2.7) considers this "Fully validated" because the paper confirms brms defaults were used and the pipeline uses brms defaults.

**Adjudication:** Both are partially correct. Reviewer B is right that the pipeline's behavior matches the paper's intent (use brms defaults). Reviewer A is right that for strict replication of the paper's specific results, the data-dependent intercept prior (`student_t(3, -8.84, 2.5)`) would need to be hard-coded, because new data would produce a different auto-computed intercept location. However, using brms auto-defaults for new data is the correct methodological behavior -- the prior should adapt to the data scale. **Verdict: LOW for methodological correctness (the pipeline does the right thing), MEDIUM for strict numerical replication of the paper's specific 1996-2019 results. For operational use, the pipeline's approach is correct. The prior values should be logged in model output for audit purposes.**

**2.2.3 Colorado 2023 catchment expansion.**

Reviewer B (Addendum 2, Section 3.5) identifies this as a **Critical** issue: the pipeline unconditionally excludes COEX data (`preprocess.R` line 328), making it unable to correctly model 2023+ CO data. Reviewer A does not mention this in Addendum 2.

**Adjudication:** Reviewer B raises a genuine issue that neither Reviewer A nor I previously identified. The paper explicitly states the catchment "expanded again in 2023 to include the remainder of CO" (page 3). The pipeline's unconditional COEX exclusion would produce an incorrect Colorado catchment for 2023+ analyses. However, the severity depends on use case: for replicating the paper's 1996-2019 comparison study, this is not relevant (the paper's data predates 2023). For operational analyses including 2023+ data, it is HIGH. **Verdict: HIGH for operational use (not Critical, since the pipeline can still correctly analyze pre-2023 data, and the fix is a conditional filter). Credit to Reviewer B for identifying this -- it is a genuine new finding not captured in any previous round of review.**

**2.2.4 Cryptosporidium 2017 cutoff and Campylobacter 2023 non-culture cutoff.**

Reviewer B (Sections 3.6, 3.7) identifies that the paper documents data collection changes (Cryptosporidium stopped in 2017, non-culture-confirmed Campylobacter stopped in 2023) that the pipeline does not enforce. Reviewer A does not mention these.

**Adjudication:** These are valid findings from the paper. However, the pipeline processes whatever data is in the input file -- if FoodNet stopped collecting Cryptosporidium data in 2017, then post-2017 input files should not contain Cryptosporidium records. The pipeline's risk is limited to data entry errors or legacy data files that include stale records. **Verdict: LOW as a pipeline code issue (the data source is the first line of defense), MEDIUM as a documentation/validation issue (the pipeline should warn when modeling a pathogen for years beyond its data collection cutoff).**

**2.2.5 Model performance metrics.**

Reviewer B (Section 3.4) identifies that the paper reports RMSE, adjusted R-squared, and ELPD but the pipeline computes none of these, rating this HIGH. Reviewer A (B5.7) notes the performance benchmarks from the paper but does not assign a severity to the pipeline's omission.

**Adjudication:** The paper reports these metrics for the purpose of comparing the enhanced model to the original model. They are not required for operational surveillance outputs. However, they would be valuable for pipeline validation (confirming the pipeline's implementation matches the paper's model performance). **Verdict: MEDIUM. The pipeline should compute and optionally output these metrics for model validation purposes, but their absence does not affect the correctness of surveillance estimates.**

**2.2.6 COVID-19 pandemic period handling.**

Reviewer A does not substantively change their position on COVID-19. Reviewer B (Section 4.3) explicitly corrects their previous position, now stating: "The paper explicitly addresses this as a feature, not a limitation" and concedes that the recommendation to add a pandemic indicator variable "conflicts with this stated purpose of the model."

**Adjudication:** Reviewer B's correction is appropriate and well-reasoned. The paper frames the spline model's behavior during the pandemic as demonstrating nowcasting capability rather than as a deficiency. My previous MEDIUM rating for M9 ("No COVID-19 pandemic period adjustment or caveat") was based on source-code-only analysis. **Verdict: Downgrade from MEDIUM to LOW. The model's behavior during the pandemic period is by design. However, the pipeline should document that extrapolated estimates for years affected by the pandemic reflect model projections of pre-pandemic trends, not adjusted estimates. Users performing operational surveillance (as opposed to methodological comparison) should be aware of this interpretation.**

**2.2.7 Nowcasting as a formalized capability.**

Both reviewers independently identify this gap. Reviewer A (B5.4) notes the pipeline has no explicit nowcasting mode. Reviewer B (Section 3.9) provides more specific recommendations: add a `--training-end-year` parameter and flag nowcast estimates in the output.

**Adjudication:** Both are correct. Reviewer B's recommendation is more actionable. **Verdict: MEDIUM. The pipeline inherently supports nowcasting via spline extrapolation but does not distinguish interpolated from extrapolated estimates. A `--training-end-year` or `--nowcast-start-year` parameter would formalize this capability and allow appropriate uncertainty flagging.**

**2.2.8 The 2025 data optionality change.**

Reviewer B (Section 3.8) identifies that the paper states FoodNet made data collection optional for all pathogens except Salmonella and STEC in 2025. Reviewer A does not mention this.

**Adjudication:** This is forward-looking information relevant to pipeline longevity. The pipeline currently assumes all nine pathogens are actively surveilled at all 10 sites. From 2025 onward, some pathogens may have incomplete data from some sites, which could bias model estimates. **Verdict: LOW for current use, MEDIUM for future-proofing. The pipeline should document this limitation and consider adding a data completeness check that warns when a pathogen-site combination has missing years.**

---

### 3. DEFINITIVE Unified Priority List

This list is the final word. It supersedes all previous priority lists from all three reviewers and both addenda. Every item has been verified against the actual published paper, the source scripts, and the pipeline code. Items that were previously listed but found to be incorrect or inapplicable have been removed.

#### HIGH PRIORITY -- Must Fix Before Production Use

**H1. Baseline IR computation: median-of-rates instead of population-weighted mean-of-components.**
- Location: `functions.R` lines 670-674
- The pipeline computes year-specific incidence rates per draw, then takes `median(ir)` as the baseline IR. The paper says "average incidence" and the source code uses `mean()` on raw `.value`, `count`, and `population` separately across baseline years within each draw, then derives baseline IR from the ratio. The pipeline's approach (a) gives equal weight to each year regardless of population, and (b) uses `median` over 3 values, which for a 3-year baseline always selects the middle year's rate and discards the other two.
- Impact: Affects every IRR and percent change estimate -- the primary deliverables for Healthy People 2030 tracking.
- Fix: Replace `summarise(baseline_ir = median(ir), baseline_count = median(count))` with: compute `baseline_value = mean(.epred)`, `baseline_pop = mean(population)`, `baseline_count = mean(count)`, then derive `baseline_ir = baseline_value / (baseline_pop / 100000)`.
- Status: Confirmed across all three review rounds. Both reviewers and the arbiter agree at HIGH.

**H2. No programmatic convergence diagnostics (R-hat, ESS, divergent transitions).**
- Location: `trendy.R` lines 571-688, `functions.R` lines 394-416
- The paper does not describe convergence diagnostics either, but any Bayesian analysis published in a peer-reviewed journal is expected to have passed convergence checks. The pipeline has no mechanism to detect or report convergence failures.
- Impact: Unreliable posterior estimates could propagate to reported results without warning. The Cyclospora model (with extremely wide intervals) is a known challenging case.
- Fix: After `brm()` completes, extract `rhat()`, `neff_ratio()`, and divergent transition counts from the model object. Emit warnings or halt if diagnostics exceed standard thresholds (R-hat > 1.01, ESS < 400, divergent transitions > 0).
- Status: Confirmed across all three review rounds. Both reviewers agree at HIGH.

**H3. HDI computed on response scale instead of log scale.**
- Location: `functions.R` lines 512-513, 519-520, 703-704, 710-711
- The source code (which produced the paper's results) computes HDI on `log(.value)` then exponentiates. The pipeline computes HDI directly on response-scale `.epred`. The paper does not specify the scale, but the published HDI bounds derive from the log-scale method. Computing HDI on the log scale better captures the asymmetric nature of count/rate distributions.
- Impact: Reported HDI bounds for incidence rates differ from published values. Note: IRR/percent change bounds in the reference output use equal-tailed intervals (quantile-based), not HDI, so this divergence primarily affects incidence rate reporting.
- Fix: Transform to log scale before HDI computation and back-transform. Apply at all four HDI computation sites.
- Status: Confirmed across all three review rounds. Both reviewers argued for upgrade; accepted.

**H4. HDI fallback silently produces equal-tailed intervals labeled as HDI.**
- Location: `functions.R` lines 52-59
- If the `HDInterval` package is not installed, the fallback function uses quantile-based equal-tailed intervals but labels them as HDI. The paper reports HDI and equal-tailed CrI as distinct quantities.
- Fix: Make `HDInterval` a hard dependency. It is already loaded in `trendy.R` line 259.
- Status: Confirmed across all three review rounds. Both reviewers agree at HIGH.

**H5. Cyclospora dual-processing path.**
- Location: `trendy.R` lines 462-477, `functions.R` lines 182-316
- The original source explicitly excludes Cyclospora from the main pathogen dataset (source line 107: `pathogen!="CYCLOSPORA"`) and processes it only through the dedicated parasitic path. The pipeline's `PATH_ANALYSIS` includes Cyclospora (via `all_pathogens <- unique(mmwrdata$pathogen)` at line 185), then also calls `CYCLOSPORA_ANALYSIS`, creating duplicate processing.
- Impact: MEDIUM in standard Nextflow workflow (downstream `--pathogen` filter removes duplicates); HIGH in standalone R usage.
- Fix: Exclude CYCLOSPORA from `PATH_ANALYSIS` to match the original design.
- Status: Confirmed. Root cause clarified by Reviewer B in Addendum 1.

**H6. Colorado 2023 catchment expansion not handled.**
- Location: `preprocess.R` line 328
- The paper documents that CO expanded to the full state in 2023. The pipeline unconditionally excludes COEX data, making it unable to correctly model 2023+ CO data.
- Impact: Incorrect Colorado catchment for any analysis including 2023 or later data.
- Fix: Make COEX exclusion conditional on year (exclude for pre-2023 data, include for 2023+), or provide a configurable parameter.
- Status: New finding from Reviewer B Addendum 2. Verified against the paper (page 3).

#### MEDIUM PRIORITY -- Should Fix for Operational Quality

**M1. adapt_delta 0.99 vs. source script 0.999.**
- Location: `run_workflow.sh` line 823, `nextflow.config` line 104
- The paper is silent on this parameter. The source script uses 0.999. Both pipeline configurations use 0.99. The more conservative value reduces divergent transitions for difficult posterior geometries. Since the paper specifies 10,001 iterations but the source script specifies 5,001, the source script parameters may not exactly match the published run, but 0.999 remains the best available reference.
- Fix: Update at least the `publication` flag to 0.999.

**M2. Production Nextflow profile is weaker than publication settings.**
- Location: `nextflow.config` lines 102-107
- The `production` profile (4 chains, 2000 iterations) is substantially weaker than the paper's specifications (6 chains, 10,001 iterations). The `publication` bash flag is closer but still diverges in adapt_delta and max_treedepth.
- Fix: Create a `publication` Nextflow profile matching the paper's specifications. Rename current `production` to `screening` or `development`.

**M3. Travel label logic bug (unreachable branch).**
- Location: `trendy.R` line 271
- The `||` (OR) operator makes the second `else if` branch unreachable. The original source uses `&` (AND) at line 223.
- Fix: Change `||` to `&`.

**M4. Catchment filter uses "bacterial" for mixed bacterial/parasitic data.**
- Location: `functions.R` line 243
- `PATH_ANALYSIS()` passes `pathogen_type = "bacterial"` to `apply_catchment_filter()`, even though it also processes parasitic pathogens. Currently benign because the default config sets all states to `"both"`, but would cause data loss with custom configs specifying `"bacterial"` for some states.
- Fix: Pass `"both"` or apply separate filters for bacterial vs. parasitic subsets.

**M5. Error handler discards original error message.**
- Location: `functions.R` lines 412-414
- The `tryCatch` block replaces the specific `brms`/Stan error with a generic message, making debugging difficult.
- Fix: Include the original error: `stop(paste("Model fitting failed:", e$message))`.

**M6. Misleading function name LINPREAD_DRAW_FN.**
- Location: `functions.R` line 434, `trendy.R` line 595
- The function is named after `add_linpred_draws` (the source code's method) but actually uses `epred_draws`. The comment at line 430 says "Uses add_linpred_draws to get untransformed predictions" which is incorrect.
- Fix: Rename to `EPRED_DRAW_FN` or `RESPONSE_DRAW_FN`. Update the comment.

**M7. Only 1 of 4 operational comparison periods is active.**
- Location: `trendy.R` lines 641-650
- The operational MMWR outputs require IRR comparisons across four baseline periods (2016-2018, 2020-2022, 2004-2006, 2006-2008). Only 2016-2018 is active. Note: the paper itself does not publish IRR tables, so this is an operational gap rather than a paper-replication gap.
- Fix: Uncomment or make configurable via command-line parameters.

**M8. No automated Salmonella serotype selection.**
- Location: Pipeline lacks equivalent of `mostcommonsero()` function
- The paper modeled 16 serotypes based on frequency during 2016-2018. The source code dynamically selects the top N. The pipeline requires manual specification via `--subgroup`.
- Fix: Implement a serotype ranking step with configurable N and reference period.

**M9. No formalized nowcasting framework.**
- Location: No explicit nowcasting logic in `functions.R` or `trendy.R`
- The paper demonstrates nowcasting as a key capability. The pipeline does not distinguish interpolated from extrapolated estimates.
- Fix: Add a `--training-end-year` parameter. Flag output rows where the year exceeds the training window. Differentiate uncertainty characterization for extrapolated years.

**M10. No model performance metrics computed.**
- Location: `trendy.R` lines 590-593 (summary only)
- The paper reports RMSE, adjusted R-squared, and ELPD using the `performance` package. The pipeline saves model summary but no formal goodness-of-fit statistics.
- Fix: Add `performance` package integration to compute these metrics after model fitting. Output alongside model results for validation.

**M11. No package version pinning.**
- Location: Pipeline-wide
- The paper specifies brms 2.20.1, tidybayes 3.0.7, R 4.4.0. Different package versions could change default priors, spline implementations, or sampling behavior.
- Fix: Document target package versions. Optionally add a version check at pipeline startup.

**M12. Memory allocation not linked to chain count.**
- Location: `nextflow.config` lines 140-147
- Memory requests do not scale with the number of MCMC chains. Running 6 chains (publication settings) with memory allocated for 2 chains could cause OOM failures.
- Fix: Scale memory allocation proportionally to chain count.

#### LOW PRIORITY -- Minor Issues and Documentation

**L1. Dead code: `PLOT_PCTCHange_TREND` function.** `functions.R` lines 747-770 references undefined variables `pathogen` and `outDir`. Remove or fix.

**L2. `combine_files` uses `setwd()` and undeclared dependencies.** `functions.R` lines 773-784. Refactor or remove.

**L3. Hardcoded 2004 reference line without annotation.** `functions.R` lines 602, 635. Add legend or text annotation explaining this is when NM joined, completing the 10-state catchment.

**L4. SAFE_WRITE append behavior.** `functions.R` lines 156-158. Could produce duplicate data on re-runs. Document or add overwrite-on-first-write logic.

**L5. LISTERIA and CRYPTOSPORIDIUM missing from ALL_PATHOGENS.** `run_workflow.sh` line 24. Add or document their intentional exclusion.

**L6. Duplicated code in LINPRED_TO_CATCHIR / LINPRED_TO_SITEIR.** `functions.R` lines 494-569. Refactor shared logic.

**L7. Year factor/numeric round-trip.** `trendy.R` line 540, `functions.R` lines 381-383. Unnecessary conversion; keep year numeric throughout.

**L8. Seed difference from source (123 vs. 47).** `functions.R` line 408. Results will be statistically equivalent but numerically different. Document.

**L9. R_LIBS environment path.** `nextflow.config` line 122. Verify against container configuration.

**L10. Redundant `ir` and `est_ir` columns.** `functions.R` lines 683-684. These compute the same value. Remove duplicate.

**L11. Potential division by zero in relative risk.** `functions.R` line 685. If `baseline_ir` is zero for any draw, division by zero occurs. Add guard clause.

**L12. No validation before calling dedicated analysis functions.** `trendy.R` lines 468-473. Add existence check for expected data.

**L13. `save_all_pars` omitted.** The original source uses `save_all_pars=TRUE` (deprecated in newer brms). May affect post-hoc diagnostics like LOO-CV. Document.

**L14. max_treedepth 15 vs. source 19.** Both pipeline modes use 15. The paper is silent. Unlikely to matter for most models but could affect difficult posteriors like Cyclospora.

**L15. Listeria CSTE filter applied in preprocessing.** `preprocess.R` lines 390-399. Permanently excludes non-CSTE Listeria from cleaned CSV. Functionally equivalent to the source code's approach but less flexible.

**L16. COVID-19 pandemic period -- documentation only.** The paper validates the spline model's behavior during the pandemic as intentional (nowcasting capability). The pipeline should document that estimates for pandemic-affected years reflect model projections of pre-pandemic trends, not adjusted estimates. No code change needed; documentation only.

**L17. Cryptosporidium 2017 and Campylobacter 2023 data collection cutoffs not enforced.** The paper documents these changes. The pipeline should add warnings when modeling these pathogens for years beyond their data collection boundaries.

**L18. 2025 data optionality.** The paper notes FoodNet made data collection optional for all pathogens except Salmonella and STEC in 2025. The pipeline should document this as a known limitation for 2025+ analyses.

---

### 4. Final Overall Assessment

#### Is this pipeline suitable for production CDC reporting?

**Not yet, but the required fixes are well-defined and modest in scope.**

The pipeline faithfully implements the core methodology described in the published paper: the negative binomial GAM with site-specific penalized thin plate regression splines, state fixed effects, log-population offset, and Bayesian estimation via `brms`. The model formula, family specification, site-level aggregation, catchment aggregation logic, and default prior behavior all match the paper's description. The pipeline's use of `epred_draws` instead of `add_linpred_draws` + exponentiation is numerically equivalent and actually corrects a site-level IR computation bug in the original source scripts.

The six HIGH-priority items (H1-H6) represent the gap between the pipeline's current state and production readiness:

- **H1 (baseline IR computation)** is the most consequential fix. It is approximately a 10-line code change that would align all IRR and percent change estimates with the published methodology. Every surveillance output depends on this calculation.
- **H2 (convergence diagnostics)** is essential infrastructure for any operational Bayesian pipeline. Without it, the pipeline cannot detect when a model fails to converge, risking unreliable results in official reports.
- **H3 and H4 (HDI computation)** together represent approximately 10 lines of changes that would align reported credible intervals with the published methodology.
- **H5 (Cyclospora dual processing)** is a targeted refactoring to match the original source's design.
- **H6 (Colorado 2023 expansion)** is essential for any analysis including 2023+ data, which is now the operational reality.

The total code change for all six HIGH items is estimated at 40-60 lines. The MEDIUM items (M1-M12) add operational polish and would collectively require perhaps 100-150 additional lines. None of the issues represent fundamental architectural problems -- the pipeline's design is sound.

#### What is acceptable as-is?

- **Model specification.** The core statistical model is correctly implemented and matches the paper.
- **Catchment definitions and join years.** Correct for pre-2023 data.
- **Pathogen handling.** Nine FoodNet pathogens correctly recognized and routed to appropriate census denominators.
- **STEC O157/non-O157 split.** Correctly implemented.
- **CIDT filtering.** Correctly implemented and configurable.
- **Nextflow architecture.** Well-designed for parallelization and resource management.
- **Preprocessing system.** More robust than the original scripts, with configurable sensitivity levels and audit trails.
- **Configurable catchment and serotype configurations.** Genuine improvements over the hardcoded original.

#### What are genuine improvements over the original source scripts?

1. Correct site-level incidence computation via `epred_draws` (avoids the original's log-scale division error at source line 249-250).
2. Configurable catchment definitions, serotype recoding, and CIDT filtering.
3. Robust pathogen name standardization with fuzzy matching.
4. Nextflow-based parallelization and containerized execution.
5. Modular function design with input validation and error handling.
6. Cleaner catchment aggregation code without wide-format reshape operations.

#### Summary judgment

The pipeline is architecturally sound, methodologically faithful to the paper's core approach, and represents a meaningful improvement over the monolithic original scripts. The HIGH-priority items are well-understood, localized, and fixable with modest effort. Once H1-H6 are addressed, the pipeline would be suitable for production CDC reporting. The MEDIUM items should be addressed for operational completeness before the pipeline fully replaces the original scripts for MMWR annual report production.

The three-round review process, now informed by the actual published paper, has converged to a stable and comprehensive assessment. The reviewers' independent paper-based analyses were largely consistent with each other and with the source-code-based findings from earlier rounds. The paper resolved several ambiguities (priors, iteration count, COVID-19 framing, serotype count) and revealed one new issue (Colorado 2023 expansion) not identified in any previous round.

---

*Final addendum prepared after full review of Weller et al. (2026), Zoonoses 6:3, DOI 10.15212/ZOONOSES-2025-0030, cross-referenced against both reviewers' Addendum 2 analyses, all previous review rounds, and the pipeline source code.*
