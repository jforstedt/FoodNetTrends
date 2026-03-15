# Implementation Plan: Model/Statistics Fixes for FoodNetTrends Pipeline

**Date:** 2026-03-14
**Scope:** All HIGH-priority model and statistics fixes from the definitive review, plus critical MEDIUM fixes that affect statistical output
**Source of truth:** Definitive HPC Review (Addendum 2, Section 3) -- the final unified priority list verified against the published paper, source scripts, and execution data

---

## Overview

Six HIGH-priority fixes and three MEDIUM-priority fixes that affect statistical correctness. Ordered so that each step builds on the previous without conflicts. Files modified:

- `bin/functions.R` (Steps 1, 2, 3, 4, 5, 7, 8)
- `bin/preprocess.R` (Step 6)
- `bin/trendy.R` (Steps 2, 5, 7, 9)

---

## Step 1: Fix Baseline IR Computation (H1)

**Priority:** HIGH -- affects every IRR and percent change estimate
**File:** `bin/functions.R`, lines 670-675

### What is wrong

The `IR_COMP_CATCH()` function computes the baseline incidence rate by first calculating per-year rates, then taking their median. With a 3-year baseline (2016-2018), `median()` of 3 values simply picks the middle value and discards the other two entirely. This is information-destructive and not a recognized epidemiological method.

The correct computation (used by the original source at `source/splinesmodel_16Mar2024_OrCatch.R` lines 329-334 and consistent with CDC/MMWR methodology) averages the raw components (`.epred`, `count`, `population`) across baseline years within each draw, then derives the baseline rate from the ratio `mean(.epred) / (mean(population) / 100000)`. This is a population-weighted mean rate equivalent to `sum(cases) / sum(person-years)`.

### Why objectively correct

1. The epidemiological definition of incidence rate for a combined period is total cases / total person-time. This equals `mean(count) / mean(population)` when the number of years is constant.
2. The paper (page 5) describes comparing to "average incidence estimates for 2016-2018." CDC MMWR reports use the same definition.
3. `median(ir)` with 3 values always selects one year's rate and discards the other two, losing information and ignoring population differences across years.
4. The statistical justification review independently confirmed this as "objectively incorrect."

### Old code (lines 670-675)

```r
  period_data <- catch %>%
    filter(year >= start_year & year <= end_year)%>% group_by(.draw)%>%
    mutate(ir=.epred/(population/100000))%>%
    summarise(baseline_ir=median(ir),
              baseline_count=median(count))
  colnames(period_data)<-c(".draw", "baseline_ir", "baseline_count")
```

### New code

```r
  period_data <- catch %>%
    filter(year >= start_year & year <= end_year) %>%
    group_by(.draw) %>%
    summarise(
      baseline_value = mean(.epred),
      baseline_pop = mean(population),
      baseline_count = mean(count)
    ) %>%
    mutate(baseline_ir = baseline_value / (baseline_pop / 100000))
  colnames(period_data) <- c(".draw", "baseline_value", "baseline_pop",
                              "baseline_count", "baseline_ir")
```

### Downstream effects

- All IRR and percent change estimates change. The `relative_risk` and `percent_change` columns in the `_EstIRRCatch_*.csv` output files will produce different values.
- The join at line 682 (`left_join(catch, period_data, by=c(".draw"))`) gains two new columns (`baseline_value`, `baseline_pop`). The subsequent `mutate` at lines 683-686 uses `baseline_ir` which is preserved, so no further changes needed to that join.
- Results will align more closely with the published reference output (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`).

### Changes results: YES

The baseline IR values change, which changes all IRR and percent change estimates. For pathogens where population varied across 2016-2018 (all of them, due to catchment growth), the new values will differ from the old. This is the correction -- the old values were wrong.

### Test strategy

1. **Unit test:** Create a synthetic dataset with 3 baseline years, known `.epred`, `count`, and `population` values per draw. Verify that the new code produces `baseline_ir = sum(.epred) / sum(population) * 100000` (equivalent to `mean(.epred) / (mean(population) / 100000)`).
2. **Regression test:** Run the pipeline with `--pathogen CAMPYLOBACTER` using publication settings. Compare the `_EstIRRCatch_2016_2018.csv` output against the reference CSV (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`). The `ref.est.ir_median` column should be closer to the reference values than the current pipeline output. (Exact match not expected due to seed and iteration differences.)
3. **Edge case:** Verify behavior when baseline period has only 1 year (mean of 1 value = that value) and when population is identical across all baseline years (weighted mean = unweighted mean).

---

## Step 2: Remove Cyclospora/Salmonella Dual Processing (H5)

**Priority:** HIGH -- creates duplicate rows that can corrupt model input
**Files:** `bin/trendy.R`, lines 467-480; `bin/functions.R`, lines 260-316

### What is wrong

`PATH_ANALYSIS()` (functions.R lines 182-246) processes ALL pathogens including Cyclospora and Salmonella, correctly routing parasitic pathogens to the Parasitic census. Then `trendy.R` lines 468-477 separately call `CYCLOSPORA_ANALYSIS()` and `SALMONELLA_ANALYSIS()`, combining results with `smartbind()`. This creates duplicate rows.

In the standard Nextflow workflow, the `--pathogen` filter at line 493 excludes the NA-pathogen duplicates (because the dedicated functions don't include a `pathogen` column). But in standalone R usage without `--pathogen`, the duplicates enter the model via `split(bact, bact$pathogen)` at line 541, creating a spurious `NA` group.

The original source explicitly excludes Cyclospora from the main path (source line 107: `pathogen!="CYCLOSPORA"`). The pipeline's `PATH_ANALYSIS` includes it. Since `PATH_ANALYSIS` already handles both bacterial and parasitic pathogens correctly with appropriate census data, the dedicated functions are redundant.

### Why objectively correct

1. Duplicate data inflates sample size and artificially narrows credible intervals -- a fundamental data integrity issue.
2. `PATH_ANALYSIS` already correctly routes parasitic pathogens (CYCLOSPORA, CRYPTOSPORIDIUM) to the Parasitic census data (lines 193, 210-212).
3. The dedicated functions serve no purpose that `PATH_ANALYSIS` does not already fulfill.
4. Removing them eliminates dead code and the risk of the NA-pathogen group in non-Nextflow usage.

### Changes to `bin/trendy.R`

Old code (lines 467-480):

```r
  # Process Cyclospora and Salmonella if CIDT+ is included
  if("CIDT+" %in% cidt) {
    report_progress("ANALYSIS", message="Processing Cyclospora data")
    cyloDF <- CYCLOSPORA_ANALYSIS(mmwrdata_filtered, census, catchment_config)%>%as.data.frame()

    report_progress("ANALYSIS", message="Processing Salmonella data")
    salDF <- SALMONELLA_ANALYSIS(mmwrdata_filtered, census, catchment_config)%>%as.data.frame()

    # Combine all pathogen data
    bact <- gtools::smartbind(pathDf, cyloDF) %>%
      gtools::smartbind(salDF)
  } else {
    bact <- pathDf
  }
```

New code:

```r
  # PATH_ANALYSIS already handles all pathogens including Cyclospora and
  # Salmonella with appropriate census denominators (bacterial vs. parasitic).
  # No separate processing is needed.
  bact <- pathDf
```

### Changes to `bin/functions.R`

No code removal needed immediately -- `CYCLOSPORA_ANALYSIS()` (lines 260-281) and `SALMONELLA_ANALYSIS()` (lines 295-316) become dead code. They can be removed in a follow-up cleanup step. Keeping them does not affect correctness since they are no longer called.

### Downstream effects

- Cyclospora and Salmonella are now processed exactly once through `PATH_ANALYSIS`.
- The `bact` data frame no longer contains NA-pathogen rows from the dedicated functions.
- No change in results when `--pathogen` is specified (standard Nextflow mode) because the NA-pathogen rows were already filtered out at line 493.
- In standalone mode without `--pathogen`, the `split()` at line 541 no longer creates a spurious `NA` group.

### Changes results: NO in standard Nextflow usage; YES in standalone usage without --pathogen

In the standard workflow, the `--pathogen` filter already excluded the duplicate rows. The fix prevents potential corruption in non-standard usage.

### Test strategy

1. **Smoke test:** Run `--pathogen CYCLOSPORA` and verify the output contains exactly the expected number of year-state rows (no duplicates). Count should equal `n_years * n_active_states` for the parasitic catchment.
2. **Verification:** Run `--pathogen SALMONELLA` and similarly check row counts.
3. **Standalone test:** Run trendy.R without `--pathogen` and verify `split(bact, bact$pathogen)` produces exactly 9 groups (one per pathogen), with no `NA` group.

---

## Step 3: Fix HDI Computation Scale (H3)

**Priority:** HIGH -- reported HDI bounds differ from published methodology
**File:** `bin/functions.R`, lines 512-513, 519-520, 557-558, 564-565, 703-704, 710-711, 713-714, 716-717

### What is wrong

The pipeline computes HDI directly on response-scale values (`.epred` or `ir`). The original source code (which produced the published paper's results) computes HDI on `log(.value)` then exponentiates back. HDI is NOT transformation-invariant (unlike equal-tailed intervals), so these produce different interval bounds.

### Why objectively correct

1. The source code at lines 299-300 explicitly uses `log(.value)` then `exp()`:
   ```r
   splits <- split(catchments %>% mutate(.value = log(.value)) %>% select(.value), catchments$yearn)
   t <- lapply(splits, function(x) HDInterval::hdi(x) %>% exp() %>% as.data.frame())
   ```
2. Computing HDI on the log scale better reflects the asymmetric nature of count/rate posterior distributions (approximately log-normal).
3. The statistical justification review classified this as "both defensible" but noted that for replication of published results, the log-scale approach should be used.
4. The published HDI bounds in the paper derive from this log-scale computation.

### Changes

There are 8 HDI computation sites across 3 functions. Each must be changed to compute on the log scale and back-transform.

#### In `LINPRED_TO_CATCHIR()` (lines 494-524)

Old (lines 512-513):
```r
      lower_hdi = round(hdi(.epred, credMass = 0.95)[1],6),
      upper_hdi = round(hdi(.epred, credMass = 0.95)[2],6),
```

New:
```r
      lower_hdi = round(exp(hdi(log(.epred), credMass = 0.95)[1]),6),
      upper_hdi = round(exp(hdi(log(.epred), credMass = 0.95)[2]),6),
```

Old (lines 519-520):
```r
      lower_hdi_ir = round(hdi(ir, credMass = 0.95)[1],6),
      upper_hdi_ir = round(hdi(ir, credMass = 0.95)[2],6))%>%
```

New:
```r
      lower_hdi_ir = round(exp(hdi(log(ir), credMass = 0.95)[1]),6),
      upper_hdi_ir = round(exp(hdi(log(ir), credMass = 0.95)[2]),6))%>%
```

#### In `LINPRED_TO_SITEIR()` (lines 539-569)

Old (lines 557-558):
```r
      lower_hdi = round(hdi(.epred, credMass = 0.95)[1],6),
      upper_hdi = round(hdi(.epred, credMass = 0.95)[2],6),
```

New:
```r
      lower_hdi = round(exp(hdi(log(.epred), credMass = 0.95)[1]),6),
      upper_hdi = round(exp(hdi(log(.epred), credMass = 0.95)[2]),6),
```

Old (lines 564-565):
```r
      lower_hdi_ir = round(hdi(ir, credMass = 0.95)[1],6),
      upper_hdi_ir = round(hdi(ir, credMass = 0.95)[2],6))%>%
```

New:
```r
      lower_hdi_ir = round(exp(hdi(log(ir), credMass = 0.95)[1]),6),
      upper_hdi_ir = round(exp(hdi(log(ir), credMass = 0.95)[2]),6))%>%
```

#### In `IR_COMP_CATCH()` (lines 667-743)

Old (lines 703-704):
```r
     lower_hdi = round(hdi(.epred, credMass = 0.95)[1],6),
     upper_hdi = round(hdi(.epred, credMass = 0.95)[2],6),
```

New:
```r
     lower_hdi = round(exp(hdi(log(.epred), credMass = 0.95)[1]),6),
     upper_hdi = round(exp(hdi(log(.epred), credMass = 0.95)[2]),6),
```

Old (lines 710-711):
```r
     lower_hdi_ir = round(hdi(ir, credMass = 0.95)[1],6),
     upper_hdi_ir = round(hdi(ir, credMass = 0.95)[2],6),
```

New:
```r
     lower_hdi_ir = round(exp(hdi(log(ir), credMass = 0.95)[1]),6),
     upper_hdi_ir = round(exp(hdi(log(ir), credMass = 0.95)[2]),6),
```

**Note on relative_risk and percent_change HDI (lines 713-714, 716-717):** The original source computes RR/percent change HDI bounds using equal-tailed intervals (quantile-based), not HDI. The current pipeline labels them as HDI. These should remain on the response scale since RR is inherently a ratio that can span zero and log-transform is undefined for negative percent changes. However, since these are derived quantities not directly comparable to the published source's equal-tailed bounds, the current approach (response-scale HDI) is acceptable. No change needed for lines 713-717.

### Edge case: zero or negative values

The `log()` transform requires positive values. For `.epred` (expected counts from a negative binomial model), all values should be strictly positive. For `ir` (derived from `.epred / (population/100000)`), the same holds. However, as a safety measure, the HDI computations should handle the edge case where any draw has `.epred = 0` (theoretically possible for very low-count pathogens). A guard clause should be added. After Step 3 changes, add this helper function near the top of `functions.R` (after line 60):

```r
# Compute HDI on log scale and back-transform for positive-valued draws
log_hdi <- function(x, credMass = 0.95) {
  x_pos <- x[x > 0]
  if (length(x_pos) < 2) {
    return(c(NA_real_, NA_real_))
  }
  exp(hdi(log(x_pos), credMass = credMass))
}
```

Then use `log_hdi(.epred)` instead of `exp(hdi(log(.epred), ...))` at all 8 sites. This is cleaner and handles the edge case.

### Downstream effects

- All `_hdi` and `_hdi_ir` columns in `_IRCatch.csv`, `_IRSite.csv`, and `_EstIRRCatch_*.csv` output files change.
- HDI bounds will be tighter on the right tail and wider on the left tail compared to response-scale HDI, because the log-normal-like posterior is more symmetric on the log scale.
- Plot ribbons (`PLOT_SITE_TRENDS`, `PLOT_OVERALL_TREND`) use `lower_hdi_ir` and `upper_hdi_ir` for the bands, so visual appearance of uncertainty bands changes.

### Changes results: YES

All HDI-labeled columns change. Equal-tailed intervals are unaffected (they are transformation-invariant).

### Test strategy

1. **Mathematical verification:** Generate 10,000 draws from a known log-normal distribution (e.g., `rlnorm(10000, 5, 0.3)`). Compute HDI on the log scale and back-transform. Verify it matches `HDInterval::hdi(log(draws))` piped through `exp()`. Compare to response-scale HDI to confirm they differ.
2. **Edge case:** Test with draws that include exactly 0 (should be handled by the guard clause).
3. **Regression:** Compare output HDI bounds to the reference CSV for a known pathogen to verify closer alignment with the published values.

---

## Step 4: Make HDInterval a Hard Dependency (H4)

**Priority:** HIGH -- fallback silently mislabels equal-tailed intervals as HDI
**File:** `bin/functions.R`, lines 47-60

### What is wrong

When `HDInterval` is not installed, the fallback function at lines 53-58 computes quantile-based equal-tailed intervals but labels them `lower_hdi` / `upper_hdi`. This is factually incorrect -- ETI and HDI are different statistical quantities. The paper reports both HDI and equal-tailed CrI as distinct measures.

### Why objectively correct

1. Mislabeling a statistical quantity is always wrong, regardless of the numerical similarity.
2. `HDInterval` is already listed in the package loading in `trendy.R` line 259 (`pkgs <- c(..., 'HDInterval', ...)`), so it is effectively already a required dependency.
3. The container environment (`foodnet.yml` line 21) includes `r-HDInterval=0.2.4`.

### Old code (lines 47-60)

```r
# Try to load HDInterval for hdi() function
hdi_available <- requireNamespace("HDInterval", quietly = TRUE)
if (hdi_available) {
  suppressPackageStartupMessages(library(HDInterval))
} else {
  # Define a fallback hdi function using quantiles
  hdi <- function(x, credMass = 0.95) {
    # Simple approximation using equal-tailed intervals
    alpha <- 1 - credMass
    c(quantile(x, probs = alpha/2, na.rm = TRUE),
      quantile(x, probs = 1 - alpha/2, na.rm = TRUE))
  }
  warning("HDInterval package not available. Using quantile-based approximation for HDI.")
}
```

### New code

```r
# HDInterval is required for proper HDI computation
# The fallback of using equal-tailed intervals labeled as HDI is scientifically
# incorrect -- they are different statistical quantities. HDI finds the narrowest
# interval containing the specified probability mass; ETI places equal probability
# in each tail. For skewed posteriors (common with count data), they differ.
if (!requireNamespace("HDInterval", quietly = TRUE)) {
  stop("Required package 'HDInterval' is not installed. ",
       "HDI computation requires this package. ",
       "Install with: install.packages('HDInterval')")
}
suppressPackageStartupMessages(library(HDInterval))
```

### Downstream effects

- If `HDInterval` is missing, the pipeline fails immediately with a clear error instead of silently producing mislabeled output.
- No change in results when `HDInterval` is installed (the standard case).

### Changes results: NO (when HDInterval is installed, which is always in the container)

### Test strategy

1. **Negative test:** In a test environment without `HDInterval`, verify the pipeline fails with the expected error message.
2. **Positive test:** In the normal container environment, verify `functions.R` sources without error.

---

## Step 5: Add Convergence Diagnostics (H2)

**Priority:** HIGH -- unreliable models can propagate to reported results without warning
**Files:** `bin/functions.R` (new function), `bin/trendy.R` (after model fitting)

### What is wrong

The pipeline does not programmatically check R-hat, effective sample size (ESS), or divergent transitions after model fitting. The `summary(proposed)` is saved to a text file (trendy.R lines 589-593), but no thresholds are checked and no warnings are emitted. A non-converged model would silently produce results.

### Why objectively correct

1. Stan development team recommends R-hat < 1.01, bulk-ESS > 400, tail-ESS > 400, zero divergent transitions.
2. Any published Bayesian analysis is expected to have passed convergence checks.
3. The pipeline runs 9 pathogens automatically -- manual inspection does not scale.
4. All three review rounds confirmed this as HIGH priority.

### New function in `bin/functions.R` (add after `PROPOSED_BM`, around line 417)

```r
################################################################################
# CHECK_CONVERGENCE - Programmatic convergence diagnostics for fitted brms model
#
# Called by: trendy.R after PROPOSED_BM completes successfully
# Purpose: Check R-hat, ESS, and divergent transitions against standard thresholds
#
# Inputs:
#   - model: Fitted brms model object from PROPOSED_BM
#   - pathogen_name: Name of pathogen for diagnostic file naming
#   - output_dir: Directory to write diagnostics file
#
# Output: List with convergence status and diagnostic details
#         Also writes a diagnostics CSV to output_dir
#
# Thresholds (per Stan development team recommendations):
#   - R-hat: warning > 1.01, error > 1.05
#   - Bulk ESS: warning < 400
#   - Tail ESS: warning < 400
#   - Divergent transitions: warning > 0
################################################################################
CHECK_CONVERGENCE <- function(model, pathogen_name, output_dir) {
  diagnostics <- list(
    pathogen = pathogen_name,
    converged = TRUE,
    warnings = character(0)
  )

  # Check R-hat values
  rhat_values <- brms::rhat(model)
  rhat_values <- rhat_values[!is.na(rhat_values)]
  max_rhat <- max(rhat_values)
  n_rhat_warn <- sum(rhat_values > 1.01)
  n_rhat_fail <- sum(rhat_values > 1.05)

  if (n_rhat_fail > 0) {
    diagnostics$converged <- FALSE
    diagnostics$warnings <- c(diagnostics$warnings,
      paste0("CONVERGENCE FAILURE: ", n_rhat_fail,
             " parameters with R-hat > 1.05 (max: ", round(max_rhat, 4), ")"))
  } else if (n_rhat_warn > 0) {
    diagnostics$warnings <- c(diagnostics$warnings,
      paste0("CONVERGENCE WARNING: ", n_rhat_warn,
             " parameters with R-hat > 1.01 (max: ", round(max_rhat, 4), ")"))
  }

  # Check effective sample sizes
  neff_values <- brms::neff_ratio(model)
  neff_values <- neff_values[!is.na(neff_values)]
  # neff_ratio returns ESS/total_draws, so multiply by total draws for absolute ESS
  total_draws <- nrow(as.matrix(model))
  min_neff_ratio <- min(neff_values)
  min_ess <- min_neff_ratio * total_draws
  n_low_ess <- sum(neff_values * total_draws < 400)

  if (n_low_ess > 0) {
    diagnostics$warnings <- c(diagnostics$warnings,
      paste0("ESS WARNING: ", n_low_ess,
             " parameters with ESS < 400 (min ESS: ", round(min_ess, 0), ")"))
  }

  # Check divergent transitions
  tryCatch({
    np <- brms::nuts_params(model)
    n_divergent <- sum(np$Value[np$Parameter == "divergent__"])
    if (n_divergent > 0) {
      diagnostics$warnings <- c(diagnostics$warnings,
        paste0("DIVERGENCE WARNING: ", n_divergent, " divergent transitions detected"))
    }
    diagnostics$n_divergent <- n_divergent
  }, error = function(e) {
    diagnostics$warnings <- c(diagnostics$warnings,
      paste0("Could not extract divergent transition info: ", e$message))
    diagnostics$n_divergent <- NA
  })

  # Store summary statistics
  diagnostics$max_rhat <- max_rhat
  diagnostics$n_rhat_above_1.01 <- n_rhat_warn
  diagnostics$min_ess <- min_ess
  diagnostics$n_low_ess <- n_low_ess

  # Write diagnostics file
  diag_df <- data.frame(
    pathogen = pathogen_name,
    max_rhat = round(max_rhat, 4),
    n_rhat_above_1.01 = n_rhat_warn,
    n_rhat_above_1.05 = n_rhat_fail,
    min_ess = round(min_ess, 0),
    n_params_low_ess = n_low_ess,
    n_divergent = diagnostics$n_divergent,
    converged = diagnostics$converged,
    warnings = paste(diagnostics$warnings, collapse = "; "),
    stringsAsFactors = FALSE
  )

  diag_file <- file.path(output_dir,
    paste0(pathogen_name, "_convergence_diagnostics.csv"))
  write.csv(diag_df, diag_file, row.names = FALSE)

  # Print warnings to console
  if (length(diagnostics$warnings) > 0) {
    for (w in diagnostics$warnings) {
      warning(paste0("[", pathogen_name, "] ", w))
    }
  }

  return(diagnostics)
}
```

### Changes to `bin/trendy.R` (after model summary, around line 593)

Insert after the model summary sink block (after line 593):

```r
    # Check convergence diagnostics
    report_progress("DIAGNOSTICS", message=paste("Checking convergence for", pathogen_name))
    convergence <- CHECK_CONVERGENCE(proposed, pathogen_name, outDir)
    if (!convergence$converged) {
      report_progress("WARNING", message=paste(
        "CONVERGENCE FAILURE for", pathogen_name,
        "- results may be unreliable. See diagnostics file."))
    } else if (length(convergence$warnings) > 0) {
      report_progress("WARNING", message=paste(
        "Convergence warnings for", pathogen_name,
        "- review diagnostics file."))
    } else {
      report_progress("DIAGNOSTICS", message=paste(
        "Convergence OK for", pathogen_name,
        "(max R-hat:", round(convergence$max_rhat, 4),
        ", min ESS:", round(convergence$min_ess, 0), ")"))
    }
```

### Downstream effects

- A new `{PATHOGEN}_convergence_diagnostics.csv` file is created alongside each model output.
- Console warnings are emitted for any convergence issues.
- The pipeline continues even when convergence fails (soft failure) -- this is intentional to avoid halting a 9-pathogen run over one difficult pathogen. The diagnostics file provides the audit trail.
- No change to statistical output values.

### Changes results: NO

This is purely an addition of quality control infrastructure.

### Test strategy

1. **Integration test:** Run the pipeline with test-mode settings (2 chains, 100 iterations) where convergence is expected to fail. Verify the diagnostics CSV is created and contains appropriate warnings (R-hat > 1.01 expected with 2 short chains).
2. **Positive test:** Run with publication settings. Verify the diagnostics CSV shows convergence (R-hat < 1.01, ESS > 400, 0 divergent transitions).
3. **File verification:** Check that the diagnostics CSV has the expected columns and format.

---

## Step 6: Fix Colorado 2023 Catchment Expansion (H6)

**Priority:** HIGH -- discards legitimate surveillance data for 2023+
**File:** `bin/preprocess.R`, line 328

### What is wrong

The pipeline unconditionally excludes all COEX (Colorado Extended) data:

```r
filter(siteid != "COEX")
```

Before 2023, this is correct -- COEX counties were not under active FoodNet surveillance. But in 2023, Colorado expanded to include the full state. The paper (page 3) states: "the catchment area remained constant but expanded again in 2023 to include the remainder of CO." Excluding COEX for 2023+ discards approximately 2.7 million people's worth of surveillance data, underestimating Colorado's cases and population.

### Why objectively correct

1. The paper documents the 2023 expansion explicitly.
2. MMWR 2024 FoodNet report confirms the catchment population increased from ~50.1M to ~53.6M with the CO expansion.
3. For 2023+ data, COEX represents legitimate, population-based active surveillance that should be included in incidence rate calculations.
4. Pre-2023 COEX data should still be excluded (not under active surveillance).

### Old code (line 328)

```r
mmwrdata <- mmwrdata %>%
  filter(siteid != "COEX")  # Exclude Colorado expanded catchment
```

### New code

```r
mmwrdata <- mmwrdata %>%
  filter(!(siteid == "COEX" & year < 2023))
  # Exclude Colorado expanded catchment for pre-2023 data only.
  # In 2023, FoodNet expanded to include the full state of Colorado,
  # so COEX data from 2023 onward represents legitimate surveillance data.
  # See: Weller et al. (2026) Zoonoses 6:3, page 3.
```

### Downstream effects

- For analyses including 2023+ data, Colorado will have a larger population denominator and potentially more cases.
- The incidence rate for Colorado in 2023+ may change (direction depends on whether the rate in COEX counties differs from the original 7-county catchment).
- The catchment-level aggregation will reflect a larger total population for 2023+.
- Census population files must include the expanded Colorado population for 2023+. If the census files already have COEX population data for 2023, this fix ensures it is used. If they do not, the census data needs updating independently.

### Changes results: YES (for analyses including 2023+ data)

Any analysis that processes 2023 or later data will now include COEX records that were previously excluded.

### Test strategy

1. **Data verification:** After preprocessing, count the number of Colorado records for 2022 vs. 2023. In 2022, only the original 7-county catchment should be present (no COEX). In 2023, both original and COEX records should be present.
2. **Population check:** Verify that the Colorado population in 2023 is larger than in 2022 (reflecting the expansion).
3. **Backward compatibility:** Verify that pre-2023 analyses produce identical results to the current pipeline (COEX is still excluded for those years).
4. **Edge case:** Verify that `siteid == "COEX"` records with `year == 2023` are retained, and `year == 2022` are excluded.

---

## Step 7: Fix Catchment Filter Pathogen Type (M4)

**Priority:** MEDIUM -- latent bug for custom configurations
**File:** `bin/functions.R`, line 243

### What is wrong

`PATH_ANALYSIS()` passes `pathogen_type = "bacterial"` to `apply_catchment_filter()`, but `PATH_ANALYSIS` also processes parasitic pathogens (CYCLOSPORA, CRYPTOSPORIDIUM). With the default config (all states set to `pathogen_type = "both"`), this is benign. But with a custom config that specifies different surveillance periods for bacterial vs. parasitic pathogens, the parasitic pathogens would be incorrectly filtered using bacterial criteria.

### Why objectively correct

1. `PATH_ANALYSIS` routes parasitic pathogens to the Parasitic census data (lines 193, 210-212), so it is intended to handle both types.
2. The catchment filter should match the data being filtered -- parasitic pathogens should use `"parasitic"` or `"both"`.
3. After Step 2 (removing `CYCLOSPORA_ANALYSIS` and `SALMONELLA_ANALYSIS`), `PATH_ANALYSIS` is the sole processing path for all pathogens, making this fix essential.

### Old code (line 243)

```r
  selectDf <- apply_catchment_filter(selectDf, catchment_config, "bacterial")
```

### New code

```r
  # Apply catchment filter separately for bacterial and parasitic pathogens
  # to ensure each pathogen type uses its appropriate surveillance periods
  bacterial_subset <- selectDf %>% filter(!pathogen %in% parasitic_pathogens)
  parasitic_subset <- selectDf %>% filter(pathogen %in% parasitic_pathogens)

  bacterial_subset <- apply_catchment_filter(bacterial_subset, catchment_config, "bacterial")
  parasitic_subset <- apply_catchment_filter(parasitic_subset, catchment_config, "parasitic")

  selectDf <- bind_rows(bacterial_subset, parasitic_subset)
```

Note: `parasitic_pathogens` is already defined at line 193 (`c("CRYPTOSPORIDIUM", "CYCLOSPORA")`), so it is in scope.

### Downstream effects

- With the default config, no change (all states have `pathogen_type = "both"`, which matches both `"bacterial"` and `"parasitic"`).
- With custom configs that differentiate bacterial/parasitic surveillance periods, parasitic pathogens will now be correctly filtered.

### Changes results: NO with default config; potentially YES with custom configs

### Test strategy

1. **Default config test:** Run with the default config and verify output is identical to pre-fix output.
2. **Custom config test:** Create a test config where one state has `pathogen_type = "bacterial"` (meaning it only participates in bacterial surveillance). Verify that CYCLOSPORA and CRYPTOSPORIDIUM data for that state is correctly excluded.

---

## Step 8: Fix Error Handler to Preserve Original Error (M5)

**Priority:** MEDIUM -- makes debugging much easier
**File:** `bin/functions.R`, lines 412-414

### What is wrong

The `tryCatch` in `PROPOSED_BM()` replaces the specific error from brms/Stan with a generic "Model did not converge" message. This discards critical debugging information (compilation errors, data format errors, Stan-specific messages).

### Old code (lines 412-414)

```r
  }, error = function(e) {
    stop("Model did not converge. May need to run a simpler version, use more iterations, or more robust adapt_delta/max_treedepth values.")
  })
```

### New code

```r
  }, error = function(e) {
    stop(paste0("Model fitting failed for this dataset. Original error: ", e$message,
                "\nConsider: more iterations, higher adapt_delta, or higher max_treedepth."))
  })
```

### Changes results: NO

This only affects error messages, not statistical output.

### Test strategy

1. **Negative test:** Feed deliberately malformed data (e.g., all-zero population column) to `PROPOSED_BM()` and verify the error message includes the original brms/Stan error text.

---

## Step 9: Fix Travel Label Logic Bug (M3)

**Priority:** MEDIUM -- unreachable code branch, introduced by refactoring
**File:** `bin/trendy.R`, line 271

### What is wrong

The pipeline uses `||` (OR) where the original source uses `&` (AND). This makes the second `else if` branch unreachable. If `"UNKNOWN"` is in the travel vector, the first condition (`("YES" %in% travel) || ("UNKNOWN" %in% travel)`) is TRUE, and the label is "All Cases" -- even when only "UNKNOWN" (without "YES") is present.

### Why objectively correct

The original source at line 223 uses `&`:
```r
if(("YES" %in% travel) & ("UNKNOWN" %in% travel)){
    travel<-"Travel Included"
```

The second branch should be reachable when travel includes UNKNOWN but not YES, producing a "Domestically-Acquired (UNK Travel Included)" label.

### Old code (line 271)

```r
if (("YES" %in% travel) || ("UNKNOWN" %in% travel)) {
```

### New code

```r
if (("YES" %in% travel) & ("UNKNOWN" %in% travel)) {
```

### Changes results: Only output labels change, not statistical values

The `travelLabel` variable is used for output labeling only (appended to CSV metadata, file names). Statistical computations are unaffected.

### Test strategy

1. **Unit test:** Set `travel <- c("NO", "UNKNOWN")` and verify `travelLabel == "Domestically-Acquired (UNK Travel Included)"`.
2. **Unit test:** Set `travel <- c("NO", "UNKNOWN", "YES")` and verify `travelLabel == "All Cases"`.
3. **Unit test:** Set `travel <- c("NO")` and verify `travelLabel == "Domestically-Acquired (UNK Travel Excluded)"`.

---

## Implementation Order and Conflict Analysis

### Order

The steps are numbered in implementation order. Dependencies:

1. **Step 1** (Baseline IR) -- standalone, no dependencies
2. **Step 2** (Remove dual processing) -- standalone, no dependencies on Step 1
3. **Step 3** (HDI log-scale) -- depends on Step 4 (HDInterval must be a hard dependency before we rely on `hdi()` in the log-scale computation). **Execute Step 4 before Step 3.**
4. **Step 4** (HDInterval hard dependency) -- standalone, should be done before Step 3
5. **Step 5** (Convergence diagnostics) -- standalone, no dependencies. Must be done after Step 2 is integrated into trendy.R since the insertion point is in the same model loop.
6. **Step 6** (COEX conditional exclusion) -- standalone, in preprocess.R, no conflicts
7. **Step 7** (Catchment filter pathogen type) -- depends on Step 2 (after removing dual processing, `PATH_ANALYSIS` is the sole path, making this fix essential). Both modify `functions.R` but in different functions (Step 2 removes calls in trendy.R; Step 7 changes line 243 in `PATH_ANALYSIS`).
8. **Step 8** (Error handler) -- standalone, no conflicts
9. **Step 9** (Travel label) -- standalone, in trendy.R, no conflicts

### Recommended execution order

```
Step 4 (HDInterval hard dep)     -- functions.R lines 47-60
Step 3 (HDI log-scale)           -- functions.R 8 sites in 3 functions
Step 1 (Baseline IR)             -- functions.R lines 670-675
Step 7 (Catchment filter)        -- functions.R line 243
Step 8 (Error handler)           -- functions.R lines 412-414
Step 2 (Remove dual processing)  -- trendy.R lines 467-480
Step 5 (Convergence diagnostics) -- functions.R new function + trendy.R insertion
Step 9 (Travel label)            -- trendy.R line 271
Step 6 (COEX)                    -- preprocess.R line 328
```

This order groups changes by file to minimize context switching, and ensures Step 4 precedes Step 3.

### Conflict check

- **functions.R Steps 1, 3, 4, 7, 8:** These modify different functions/sections with no overlapping lines. No conflicts.
  - Step 4: lines 47-60
  - Step 3: lines 512-513, 519-520, 557-558, 564-565, 703-704, 710-711 (plus new helper function after line 60)
  - Step 1: lines 670-675
  - Step 7: line 243
  - Step 8: lines 412-414
  - Step 5 (new function): inserted after line 417

- **trendy.R Steps 2, 5, 9:** These modify different sections.
  - Step 2: lines 467-480
  - Step 5: insertion after line 593
  - Step 9: line 271

- No two steps modify the same line. No combined edits needed.

---

## Summary of Result Changes

| Step | Fix | Changes Statistical Results? | Scope of Change |
|------|-----|------------------------------|-----------------|
| 1 | Baseline IR computation | YES | All IRR and percent change estimates |
| 2 | Remove dual processing | NO (in Nextflow mode) | Prevents future data corruption |
| 3 | HDI log-scale | YES | All HDI interval bounds |
| 4 | HDInterval hard dependency | NO | Error behavior only |
| 5 | Convergence diagnostics | NO | Adds quality control output |
| 6 | COEX conditional exclusion | YES (2023+ data) | Colorado cases and population |
| 7 | Catchment filter type | NO (default config) | Prevents future data loss |
| 8 | Error handler | NO | Error messages only |
| 9 | Travel label | NO (labels only) | Output file labels |

Steps 1, 3, and 6 change statistical results. Step 1 is the most consequential -- it affects every pathogen's primary deliverables (IRR and percent change for Healthy People 2030 tracking).

---

## Validation Plan

After all 9 steps are implemented:

1. **Full regression test:** Run the pipeline with `--pathogen CAMPYLOBACTER` using publication settings (6 chains, 10001 iterations, adapt_delta 0.99, seed 123). Compare output against the reference CSV to verify IRR and percent change values are closer to the published reference than the pre-fix pipeline output.

2. **All-pathogen smoke test:** Run all 9 pathogens with reduced settings (2 chains, 500 iterations) to verify the pipeline completes without errors for every pathogen.

3. **Diagnostics check:** Verify that `_convergence_diagnostics.csv` files are produced for each pathogen.

4. **COEX check:** For a 2023+ dataset, verify Colorado records include COEX data and population denominators reflect the expanded catchment.

5. **Backward compatibility:** For a pre-2023 dataset, verify that output is identical to the pre-fix pipeline output for Steps 2, 4, 5, 6, 7, 8, and 9 (which should not change pre-2023 results). Only Steps 1 and 3 should change pre-2023 results.

---

## Architect Review

**Reviewer:** Senior Nextflow DSL2 Bioinformatics Architect
**Date:** 2026-03-14
**Scope:** Model/Statistics plan validation, cross-plan conflict analysis, DSL2 integration, best practices

---

### 1. Cross-Plan Conflict Analysis

This plan modifies `functions.R` (Steps 1, 3, 4, 5, 7, 8), `trendy.R` (Steps 2, 5, 9), and `preprocess.R` (Step 6).

**functions.R -- shared with Profiler Plan (Changes 5-8):** Model Plan Step 8 modifies `PROPOSED_BM()` error handler at lines 412-414. The Profiler Plan Change 8 modifies the same function's signature (line 348) and `backend` parameter (line 410). No textual conflict -- different lines within the same function. Merge order: Model Step 8 first, then Profiler Change 8. Both are additive.

Model Plan Step 5 adds `CHECK_CONVERGENCE()` after `PROPOSED_BM` (~line 417). After Model Step 8 and Profiler Change 8, line numbers shift. Use function-name anchoring, not line numbers.

**trendy.R -- shared with Profiler Plan (Change 7):** Model Steps 2, 5, 9 and Profiler Change 7 all modify `trendy.R` but in different sections (lines 271, 467-480, 573-581, 593). No textual conflicts. The Profiler Plan adds `backend = backend` to the `PROPOSED_BM()` call -- purely additive and orthogonal to Model Plan changes.

**preprocess.R -- not shared.** Only this plan touches preprocess.R (Step 6). No conflicts.

**foodnet.def, foodnet.yml, nextflow.config, modules.config** -- this plan does NOT modify these files. The Profiler Plan and Container Plan do. No conflicts with this plan.

**run_workflow.sh** -- this plan does NOT modify run_workflow.sh. The Profiler Plan does. No conflicts.

### 2. DSL2 Integration Validation

This plan's changes are entirely within R scripts (`functions.R`, `trendy.R`, `preprocess.R`). No Nextflow process definitions, channels, or config files are modified.

**Critical `-resume` caching issue:** `functions.R` is copied via `cp ${workflow.projectDir}/bin/functions.R .` in the `trendy.nf` script block. This `cp` command text is part of the cache key, but the *content* of `functions.R` is NOT. Nextflow hashes the script block template, not the files it references at runtime. Steps 1, 3, 4, 7, and 8 all modify only `functions.R`. A `-resume` run after deploying these fixes would use stale cached results from pre-fix code.

Changes to `trendy.R` (Steps 2, 5, 9) are also problematic: `trendy.R` is referenced via `params.trendyScript` which resolves to `${launchDir}/bin/trendy.R`. Nextflow interpolates this into the script block, but the file content itself is not hashed -- only the resolved path string. So even `trendy.R` changes may not invalidate caches if the path stays the same.

**Recommendation:** After deploying model fixes, run `nextflow clean -f` or use a fresh work directory. Long-term: consider declaring `functions.R` as a `path` input to TRENDY (instead of copying it in the script block), which would make its content part of the cache key. This is a broader refactoring that could be coordinated with the Profiler Plan.

### 3. nf-core Compliance

All changes are in `bin/` R scripts -- nf-core compliance unaffected. However, Step 5's new `_convergence_diagnostics.csv` output file is NOT declared in `trendy.nf` outputs. Without a matching `path` declaration, the file stays in the work directory and is not published to `spline_results/`. Add this output declaration (coordinate with Profiler Plan which also modifies `trendy.nf`):

```groovy
path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_\$', '')}_convergence_diagnostics.csv", emit: diagnostics, optional: true
```

### 4. Best Practices Assessment (March 2026)

- **Step 1 (Baseline IR):** Correct. Population-weighted mean is the standard epidemiological definition. Implementation is algebraically sound.
- **Step 3 (HDI log-scale):** The statistical justification review (H3) concluded both approaches are defensible and the response-scale HDI is arguably more interpretable. This plan overrides that finding to match the original source code. The `log_hdi()` helper is well-designed, but the plan should explicitly acknowledge this is a "match the source" decision, not a "current code is objectively wrong" finding.
- **Step 5 (Convergence diagnostics):** R-hat < 1.01 / ESS > 400 thresholds are current with Stan 2.35+ (2026). Soft-failure design is appropriate. However, `nrow(as.matrix(model))` loads the full posterior matrix into memory. For a 6-chain, 10001-iteration model this is ~30,000 rows x N parameters. Consider `posterior::summarise_draws()` for a lighter-weight approach.
- **Step 6 (COEX):** Filter logic `!(siteid == "COEX" & year < 2023)` is correct. Uses vector `&` (not short-circuit `&&`) as required inside dplyr `filter()`.
- **Step 9 (Travel label):** `||` to `&` fix is correct per source code comparison. With `||`, the second branch is unreachable whenever UNKNOWN is in the travel vector.

### 5. Issues and Concerns

1. **log_hdi zero filtering:** Dropping zeros silently could bias HDI if many draws are zero. Add a warning if >5% of draws are dropped.
2. **Step 1 new columns:** `baseline_value` and `baseline_pop` propagate through `left_join` -- verified safe (downstream uses named columns, not positions).
3. **Step 2 smartbind dead code:** After removing Cyclospora/Salmonella calls, `gtools::smartbind` is no longer called in `trendy.R`. Note for Cleanup Plan.
4. **Step 5 output not published:** The `_convergence_diagnostics.csv` file needs a `path` output declaration in `trendy.nf`. Coordinate with Profiler Plan.
5. **`-resume` cache invalidation:** This is the most operationally dangerous issue. See Section 2 above.

### 6. Implementation Sequencing (cross-plan)

This plan should be implemented **FIRST** among all four plans: highest-priority statistical fixes, no dependencies on other plans, and other plans' changes to shared files are additive. Internal execution order (4, 3, 1, 7, 8, 2, 5, 9, 6) is correct.

### 7. Verdict

**APPROVE with minor additions:** (1) Add convergence diagnostics output to `trendy.nf`, (2) Document `-resume` cache invalidation for `functions.R` changes, (3) Acknowledge Step 3 is a source-matching decision per stat review, (4) Consider `posterior::summarise_draws()` in `CHECK_CONVERGENCE`.
