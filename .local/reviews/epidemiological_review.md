# Epidemiological Review: FoodNetTrends Pipeline

**Reviewer:** Senior Epidemiologist / Biostatistician
**Date:** 2026-03-13
**Pipeline Version:** 1.0dev
**Files Reviewed:** `bin/functions.R`, `bin/trendy.R`, `bin/preprocess.R`, `modules/local/resource_profiler.nf`, `modules/local/trendy.nf`, `workflows/spline.nf`, `nextflow.config`, `run_workflow.sh`, `source/splinesmodel_16Mar2024_OrCatch.R`, `source/Unspeciated_Shigella.R`

---

## 1. FoodNet Catchment Methodology

### 1.1 Catchment State Definitions

The pipeline defines 10 FoodNet catchment states in `functions.R` lines 71-77 via `read_catchment_config()`:

```r
state = c("CA", "CO", "CT", "GA", "MD", "MN", "NM", "NY", "OR", "TN")
```

**Assessment:** This list is correct and matches the published FoodNet surveillance area. All 10 sites are included. Note that California participates through selected counties only (Alameda, Contra Costa, and San Francisco counties), not the entire state. The pipeline does not explicitly annotate this sub-state geography for CA, but this is handled implicitly through the census denominator files, which should contain only the relevant county populations. **Recommendation:** Add a comment in `read_catchment_config()` clarifying that CA represents selected counties, not the full state, so future maintainers do not inadvertently substitute state-level census data.

### 1.2 Join Years

The start years defined at `functions.R` line 73 are:

| State | Pipeline Start Year | Published Start Year | Status |
|-------|-------------------|---------------------|--------|
| CA    | 1996              | 1996                | Correct |
| CT    | 1996              | 1996                | Correct |
| GA    | 1996              | 1996                | Correct |
| MN    | 1996              | 1996                | Correct |
| OR    | 1996              | 1996                | Correct |
| MD    | 1998              | 1998                | Correct |
| NY    | 1998              | 1998                | Correct |
| TN    | 2000              | 2000                | Correct |
| CO    | 2001              | 2001                | Correct |
| NM    | 2004              | 2004                | Correct |

**Assessment:** All join years are accurate and consistent with published FoodNet methodology. The original source script (`source/splinesmodel_16Mar2024_OrCatch.R`, line 128) uses the same years in a hardcoded subset call, confirming internal consistency.

### 1.3 Handling of Changing Catchment Composition Over Time

The catchment filter is applied via `apply_catchment_filter()` (`functions.R` lines 111-132). This function iterates over each state in the configuration and retains only rows where `data$state == config$state[i]` AND `data$year >= config$start_year[i]`.

**Issue -- catchment-level aggregation with unbalanced panels:** The `CATCHMENT()` function (`functions.R` lines 468-480) sums `.epred`, `count`, and `population` across all states for a given `year` and `.draw`. This means that for years before all 10 states joined (1996-2003), the catchment denominator is smaller. For example, in 1996-1997, only 5 sites contribute. In 1998-1999, 7 sites contribute. The incidence rate is then calculated as `sum(.epred) / sum(population) * 100,000`.

This is **epidemiologically appropriate** for computing a weighted average incidence rate across the active catchment in each year, and is consistent with published FoodNet MMWR methodology. However, there are two caveats:

1. **Comparability across years:** The catchment composition changes materially between 1996 and 2004. Comparing the 1996 incidence rate (5 states) to the 2023 rate (10 states) is comparing different underlying populations with potentially different disease ecologies. The Bayesian model with state-specific splines (`s(year, by = state)`) partially addresses this by modeling each state's trajectory independently, but the catchment-level summary still aggregates heterogeneous populations.

2. **The vertical red line at 2004:** Both `PLOT_SITE_TRENDS` (line 602) and `PLOT_OVERALL_TREND` (line 635) draw a vertical dashed red line at `x = 2004`. This is the year NM joined, completing the current 10-state catchment. This is a helpful visual cue, but it lacks a legend or annotation. **Recommendation:** Add a legend entry or text annotation explaining the significance of the 2004 line.

### 1.4 Catchment Filter Applied Only to "Bacterial" Type

**Bug (Medium Severity):** In `PATH_ANALYSIS()` (`functions.R` line 243), the catchment filter is applied with `pathogen_type = "bacterial"`:

```r
selectDf <- apply_catchment_filter(selectDf, catchment_config, "bacterial")
```

However, `PATH_ANALYSIS()` also processes parasitic pathogens (CRYPTOSPORIDIUM, CYCLOSPORA) at lines 206-214, joining them with the Parasitic census data. The catchment filter with `pathogen_type = "bacterial"` will only retain config rows where `pathogen_type %in% c("both", "bacterial")`. Since the default config sets all states to `pathogen_type = "both"` (line 75), this does not currently cause data loss. But if a custom catchment config were provided with `pathogen_type = "bacterial"` for some states, parasitic pathogens processed through `PATH_ANALYSIS()` would be incorrectly excluded.

**Recommendation:** Either (a) split bacterial and parasitic pathogen processing with appropriate filter types, or (b) pass `"both"` instead of `"bacterial"` in `PATH_ANALYSIS()`.

---

## 2. Pathogen-Specific Considerations

### 2.1 STEC O157 / Non-O157 Split

The pipeline handles the STEC split via the `--subgroup` parameter in `trendy.R` (lines 413-423):

```r
if (opts$subgroup == "O157") {
  mmwrdata_filtered <- mmwrdata_filtered %>%
    filter(stec_class == "STEC O157")
} else if (opts$subgroup == "nonO157") {
  mmwrdata_filtered <- mmwrdata_filtered %>%
    filter(stec_class %in% c("STEC NONO157", "STEC O AG UNDET"))
}
```

**Assessment:** This correctly mirrors the original source code (`source/splinesmodel_16Mar2024_OrCatch.R` lines 108-109), which classifies "STEC O AG UNDET" (O antigen undetermined) into the non-O157 category. This is consistent with standard FoodNet practice where non-O157 includes all STEC with serogroups other than O157 plus those with undetermined serogroups.

**Improvement over source:** The pipeline version treats STEC combined, O157, and nonO157 as separate analysis tasks that can be run independently or in parallel, which is a good design decision.

### 2.2 Salmonella Serotype Analysis

**Significant methodological difference from source:** The original source code (`source/splinesmodel_16Mar2024_OrCatch.R` lines 162-203) identifies the top 10 most common serotypes in the most recent year and runs models for each. The new pipeline (`trendy.R` lines 427-435) instead requires the user to explicitly specify a serotype via the `--subgroup` parameter:

```r
mmwrdata_filtered <- mmwrdata_filtered %>%
  filter(serotypesummary == opts$subgroup)
```

**Implications:**
- The dynamic "top 10 in most recent year" logic is no longer automated. The user or workflow script must decide which serotypes to analyze.
- The `run_workflow.sh` interactive menu (lines 67-83 and the serotype extraction logic) partially compensates, but it requires manual user input rather than being programmatic.
- **Recommendation:** Consider adding an `AUTO_TOP_N` option that replicates the original behavior of identifying the N most common serotypes from the data.

### 2.3 Cyclospora and Census Denominators

Cyclospora is correctly handled with separate parasitic census denominators:

- `CYCLOSPORA_ANALYSIS()` (`functions.R` lines 260-281) joins with `census %>% filter(pathogentype == "Parasitic")`.
- `PATH_ANALYSIS()` (`functions.R` lines 206-214) also correctly routes parasitic pathogens to the Parasitic census.

**Assessment:** This is correct. The FoodNet catchment for parasitic pathogens differs slightly from that for bacterial pathogens in some state-year combinations (different counties may be included). Using separate census files ensures accurate denominators.

**Issue -- Duplicate Cyclospora processing:** When `CIDT+` is in the CIDT filter, `trendy.R` lines 468-477 run both `CYCLOSPORA_ANALYSIS()` and then combine it with the output of `PATH_ANALYSIS()`. However, `PATH_ANALYSIS()` at line 193 defines `parasitic_pathogens <- c("CRYPTOSPORIDIUM", "CYCLOSPORA")` and processes them with Parasitic census data. This means Cyclospora data is prepared twice -- once through `PATH_ANALYSIS()` and once through `CYCLOSPORA_ANALYSIS()` -- and then combined via `gtools::smartbind()`. The `smartbind` will produce duplicate rows for Cyclospora. When a specific `--pathogen CYCLOSPORA` is specified, line 493 filters to only that pathogen, but duplicates from the `smartbind` could remain.

**Severity:** High. This could double-count Cyclospora cases or produce duplicate state-year-pathogen rows that inflate counts or cause model fitting issues.

**Recommendation:** Either exclude CYCLOSPORA from `PATH_ANALYSIS()` (add it to an exclusion list), or remove the separate `CYCLOSPORA_ANALYSIS()` call when using the combined pipeline.

### 2.4 Pathogen Name Standardization

The pathogen standardization in `preprocess.R` (lines 123-316) implements a multi-tier matching strategy (exact, prefix, contains, fuzzy). The known pathogen patterns (lines 123-171) cover all nine FoodNet pathogens.

**Concerns:**

1. **Prefix pattern collision:** The prefix pattern `"^C\\."` is defined for both CAMPYLOBACTER (line 133) and could potentially match "C. cayetanensis" (Cyclospora) if the data ever contains that format. The matching iterates through pathogens in dictionary order, so CAMPYLOBACTER would be matched first. **Risk:** Low, but worth noting.

2. **STEC prefix patterns:** `"^E.*COLI"` (line 147) is very broad and could match non-STEC E. coli references. In FoodNet data, STEC is the standard designation, so this is unlikely to cause issues in practice.

3. **LISTERIA not in ALL_PATHOGENS:** The `run_workflow.sh` line 24 defines `ALL_PATHOGENS="CAMPYLOBACTER,CYCLOSPORA,SALMONELLA,SHIGELLA,STEC,VIBRIO,YERSINIA"`, omitting LISTERIA and CRYPTOSPORIDIUM. While the original source scripts analyze Listeria separately with a CSTE filter, the pipeline's `preprocess.R` applies the CSTE filter (lines 393-399), so Listeria data is available in the cleaned file. However, users relying on the `ALL_PATHOGENS` variable will not analyze Listeria or Cryptosporidium unless they manually add them. **Recommendation:** Add LISTERIA and CRYPTOSPORIDIUM to the ALL_PATHOGENS list, or document their intentional exclusion.

### 2.5 CIDT Handling

The CIDT (culture-independent diagnostic test) filter uses three categories: `CIDT+`, `CX+`, and `PARASITIC` (`trendy.R` line 83, `nextflow.config` line 17).

**Assessment:** This is consistent with FoodNet methodology. Since 2012, FoodNet has tracked CIDT-positive cases separately from culture-confirmed cases. The default inclusion of all three categories (`CIDT+,CX+,PARASITIC`) provides the most complete picture of disease burden, which aligns with how FoodNet now reports incidence (including CIDT-positive cases).

**Note:** Excluding `CIDT+` (culture-only analysis) is useful for trend comparisons with pre-2012 data, and the pipeline correctly supports this via the `--cidt` parameter. The `run_workflow.sh` provides interactive options for this.

---

## 3. Baseline Comparison Periods

### 3.1 Healthy People 2030 Baseline (2016-2018)

The pipeline calculates IRR relative to 2016-2018 at `trendy.R` line 637:

```r
hp30 <- IR_COMP_CATCH(catch, 2016, 2018, ...)
```

**Assessment:** Correct. The Healthy People 2030 foodborne illness objectives use 2016-2018 as the baseline period for most pathogens. This is the primary comparison period and is the only one actively computed (not commented out) in the current pipeline.

### 3.2 Other Comparison Periods

The following periods are defined but **commented out** in `trendy.R` (lines 641-650):
- 2020-2022 (COVID-19 period)
- 2004-2006 (first years of complete 10-state catchment)
- 2006-2008 (Healthy People 2020 baseline)

The original source scripts (`source/splinesmodel_16Mar2024_OrCatch.R` lines 365-399, `source/Unspeciated_Shigella.R` lines 366-409) compute all four periods plus 2010-2012.

**Assessment:** All periods are epidemiologically meaningful:
- **2004-2006:** First three years after full catchment stabilization. Appropriate for long-term trend assessment.
- **2006-2008:** Healthy People 2020 baseline. Necessary for HP2020 target evaluation.
- **2010-2012:** Useful for medium-term trend assessment.
- **2016-2018:** HP2030 baseline. Correctly active.
- **2020-2022:** COVID-19 pandemic period. Important for context but requires careful interpretation (see Section 6.4).

**Recommendation:** Uncomment the additional comparison periods or make them configurable via command-line parameters. Published MMWR FoodNet reports include multiple comparison periods.

### 3.3 Relative Risk Computation

The `IR_COMP_CATCH()` function (`functions.R` lines 667-743) computes relative risk correctly at the draw level before summarizing:

```r
relative_risk = est_ir / baseline_ir
percent_change = ((est_ir - baseline_ir) / baseline_ir) * 100
```

**Methodological difference from source:** The original source (`source/splinesmodel_16Mar2024_OrCatch.R` lines 329-361) uses `mean` to aggregate the baseline period across draws:

```r
summarise_at(.vars = c("count", "population", ".value"), .funs = list(mean=mean))
```

The new pipeline (`functions.R` lines 670-674) uses `median`:

```r
summarise(baseline_ir = median(ir), baseline_count = median(count))
```

**Impact:** Using median vs. mean for the baseline IR calculation will produce slightly different results. The median is more robust to skewed posterior distributions, which is a defensible choice. However, this creates a **methodological divergence from published results** that should be documented. For consistency with published MMWR reports, consider using mean, or at minimum, report both.

---

## 4. Data Quality and Preprocessing

### 4.1 COEX Site Exclusion

`preprocess.R` line 328:
```r
mmwrdata <- mmwrdata %>% filter(siteid != "COEX")
```

**Assessment:** Correct. COEX refers to the expanded Colorado catchment area. FoodNet standard analyses use the original Colorado catchment (a subset of counties). Excluding COEX prevents double-counting of Colorado cases. The original source scripts confirm this practice (`source/splinesmodel_16Mar2024_OrCatch.R` line 68).

### 4.2 Listeria CSTE Filter

`preprocess.R` lines 393-399:
```r
mmwrdata <- mmwrdata %>%
  filter(!(pathogen == "LISTERIA" & cste != "YES"))
```

**Assessment:** Correct. This retains only CSTE case definition-confirmed Listeria cases, which is standard for FoodNet Listeria surveillance. Non-invasive Listeria cases (e.g., febrile gastroenteritis) are excluded. The original source code (`source/splinesmodel_16Mar2024_OrCatch.R` line 110) applies the same filter: `filter(pathogen == "LISTERIA" & cste=="YES")`.

**Note:** The filter is applied during preprocessing, meaning the cleaned CSV file permanently excludes non-CSTE Listeria cases. This is appropriate for the standard use case but removes the ability to analyze all Listeria cases without re-preprocessing. Consider making this a configurable option.

### 4.3 Serotype Recoding

`preprocess.R` lines 52-114 implement configurable serotype recoding. The default rules (`read_serotype_config()`, lines 55-57) recode:

- `"NOT SPECIATED"` --> `"Missing"`
- `"UNKNOWN"` --> `"Missing"`
- `"PARTIAL SERO"` --> `"Missing"`
- `"NOT SERO"` --> `"Missing"`
- `""` (empty) --> `"Missing"`
- Contains `"UNDET"` --> `"Missing"`

**Assessment:** This is consistent with the original source code (`source/Unspeciated_Shigella.R` lines 71-73):
```r
mmwrdata$SERO2 <- ifelse(mmwrdata$SERO1=="NOT SPECIATED" | ... , "Missing", mmwrdata$SERO1)
mmwrdata$SERO2 <- ifelse(grepl("UNDET", mmwrdata$SERO2), "Missing", mmwrdata$SERO2)
```

The recoding is appropriate for Salmonella serotype analysis and Shigella species analysis. Cases coded as "Missing" can still be included in overall pathogen-level analyses but are excluded from serotype-specific subgroup analyses.

**Improvement over source:** The pipeline allows external serotype configuration via `--serotype-config`, enabling future flexibility.

### 4.4 County Name Corrections

`preprocess.R` lines 359-365:
```r
county = if_else(county %in% c("ST. MARYS'S", "ST. MARYS"), "ST. MARY'S", county)
county = if_else(county == "PRINCE GEORGES", "PRINCE GEORGE'S", county)
county = if_else(county == "QUEEN ANNES", "QUEEN ANNE'S", county)
county = if_else(county == "DE BACA", "DEBACA", county)
```

**Assessment:** These corrections are Maryland-specific (ST. MARY'S, PRINCE GEORGE'S, QUEEN ANNE'S) and New Mexico-specific (DEBACA). They are accurate and match the original source code. The corrections standardize county names for proper census data joins.

**Note:** These corrections are applied to the county names but the pipeline does not appear to use county-level data for modeling (the model aggregates to state level). The county corrections are primarily important for data quality and potential future county-level analyses.

### 4.5 Fuzzy Matching Risk

The fuzzy matching feature (`preprocess.R` lines 283-298) uses Levenshtein distance with configurable thresholds:
- STRICT: No fuzzy matching
- MEDIUM: Distance <= 1
- RELAXED: Distance <= 2

**Risk Assessment:** At MEDIUM sensitivity (default), a distance of 1 could misclassify:
- `"VIBRIO"` (6 chars) could match `"VIBRID"` or similar typos -- acceptable
- `"STEC"` (4 chars) -- with distance 1, very few false matches possible
- `"YERSINIA"` (8 chars) could theoretically match `"VERSINIA"` -- acceptable

At RELAXED sensitivity (distance 2):
- `"SHIGELLA"` could match `"SHIGELA"` (common misspelling) -- acceptable
- **But** `"VIBRIO"` (6 chars) with distance 2 could match unexpected strings if the edit path is favorable -- warrants caution

**Recommendation:** The MEDIUM default is a reasonable balance. The standardization report output (`preprocess.R` line 339) provides an audit trail. **Always review the preprocessing report for unexpected matches**, especially when using RELAXED mode.

---

## 5. Travel Case Handling

### 5.1 Default Inclusion

The pipeline defaults to including all travel statuses (`trendy.R` line 82, `nextflow.config` line 16):

```
--travel "NO,UNKNOWN,YES"
```

**Assessment:** This is consistent with the primary FoodNet reporting approach for the annual MMWR FoodNet surveillance summary, which reports overall incidence including travel-associated cases. The published MMWR FoodNet reports present "All Cases" as the primary analysis.

However, for Healthy People targets and for understanding domestically acquired disease burden, analyses typically exclude known travel-associated cases. The pipeline's `run_workflow.sh` provides interactive options for:
- All cases (NO, UNKNOWN, YES)
- Domestically acquired, unknown included (NO, UNKNOWN)
- Domestically acquired, unknown excluded (NO only)

**Concern with travel label logic:** `trendy.R` lines 271-277:
```r
if (("YES" %in% travel) || ("UNKNOWN" %in% travel)) {
  travelLabel <- "All Cases"
} else if (!("YES" %in% travel) & ("UNKNOWN" %in% travel)) {
  travelLabel <- "Domestically-Acquired (UNK Travel Included)"
} ...
```

**Bug (Low Severity):** The second `else if` condition is unreachable. If `"UNKNOWN" %in% travel` is TRUE, the first `if` (which uses `||`) will already catch it. The label "Domestically-Acquired (UNK Travel Included)" can never be assigned. This should be:

```r
if (("YES" %in% travel) & ("UNKNOWN" %in% travel)) {
  travelLabel <- "All Cases"
} else if (!("YES" %in% travel) & ("UNKNOWN" %in% travel)) {
  travelLabel <- "Domestically-Acquired (UNK Travel Included)"
} ...
```

The original source code (`source/splinesmodel_16Mar2024_OrCatch.R` lines 223-229) has a similar pattern with `&` instead of `||`, which is correct. The pipeline introduced a bug by changing `&` to `||`.

---

## 6. Interpretation Concerns

### 6.1 Model Specification and Default Parameters

The Bayesian model (`functions.R` lines 394-416) specifies:

```r
brm(count ~ s(year, by = state) + state + offset(log(population)),
    data = data, family = negbinomial(), ...)
```

**Assessment of model form:** The model is well-specified for this application:
- Negative binomial family appropriately handles overdispersed count data
- State-specific splines (`s(year, by = state)`) allow different temporal trends by state
- State fixed effects capture baseline differences
- Log population offset converts to rate modeling
- This matches the original source code specification

**Serious concern -- default parameters vs. publication quality:**

| Parameter | Pipeline Default | Production Profile | Original Source | Publication Standard |
|-----------|-----------------|-------------------|-----------------|---------------------|
| Chains    | 2               | 4                 | 6               | 4-6                 |
| Iterations| 500             | 2000              | 5001            | 5000-10000          |
| adapt_delta| 0.95           | 0.99              | 0.999           | 0.99-0.999          |
| max_treedepth| 10          | 15                | 19              | 15-20               |
| Seed      | 123             | 123               | 47              | --                  |

The pipeline defaults produce **screening-quality results only**. With 2 chains and 500 iterations, convergence diagnostics (R-hat, effective sample size) will be unreliable, and posterior estimates may be inaccurate. The `production` profile in `nextflow.config` (lines 102-107) improves this but still uses fewer chains and iterations than the original source.

**Recommendation:**
- Document prominently that default parameters are for testing only
- The `production` profile should match or exceed the original source parameters (6 chains, 5001 iterations, adapt_delta = 0.999, max_treedepth = 19)
- Add convergence diagnostics (R-hat, ESS, divergent transitions) to the output

### 6.2 Posterior Prediction Method Change

**Important methodological difference:** The original source code uses `add_linpred_draws()` with `transform=FALSE` to get link-scale (log) predictions, then manually exponentiates them during catchment aggregation (`source/splinesmodel_16Mar2024_OrCatch.R` lines 247-261):

```r
add_linpred_draws(newdata = data, model, n=NULL, transform=FALSE, value=".linpred")
...
value[,col_list] <- exp(value[,col_list])  # Exponentiate to response scale
```

The new pipeline uses `epred_draws()` (`functions.R` line 442):

```r
draws <- epred_draws(model, newdata = data) %>% ungroup()
```

`epred_draws()` returns expected values on the **response scale** (i.e., already exponentiated and accounting for the negative binomial mean structure). This is **not identical** to `exp(linear predictor)` for a negative binomial model. Specifically:

- `exp(linear predictor)` gives the conditional mean of the Poisson component
- `epred_draws()` gives the expected value of the negative binomial distribution, which equals the conditional mean

For a negative binomial with log link, these are mathematically equivalent for the mean, so the practical difference is negligible. However, the uncertainty propagation differs because `epred_draws()` integrates over all posterior uncertainty (including the shape parameter), while the original approach only transforms the linear predictor.

**Impact:** Results will differ slightly from the published source analysis. This should be documented.

### 6.3 HDI Computation Difference

The original source code (`source/splinesmodel_16Mar2024_OrCatch.R` lines 299-309) computes HDI on the **log-transformed** predicted values and then exponentiates:

```r
splits <- split(catchments %>% mutate(.value = log(.value)) %>% select(.value), catchments$yearn)
t <- lapply(splits, function(x) HDInterval::hdi(x) %>% exp() %>% as.data.frame())
```

The new pipeline (`functions.R` lines 512-513, 519-520) computes HDI directly on the response-scale values:

```r
lower_hdi = round(hdi(.epred, credMass = 0.95)[1], 6)
upper_hdi = round(hdi(.epred, credMass = 0.95)[2], 6)
```

**Impact:** Computing HDI on log-scale vs. response-scale produces different intervals. The log-scale HDI, when exponentiated, better captures the asymmetric nature of count/rate distributions. The response-scale HDI may be wider or narrower depending on the skew. This is a methodological difference that could affect reported uncertainty intervals.

**Additionally**, the fallback HDI function (`functions.R` lines 53-58) uses equal-tailed quantile intervals, not true highest density intervals. If the `HDInterval` package is not available, this silently changes the interval type, potentially affecting reproducibility.

### 6.4 COVID-19 Pandemic Period (2020-2022)

The pipeline does not include any special handling for the COVID-19 pandemic period. This is a significant concern:

1. **Healthcare-seeking behavior changed dramatically** in 2020-2021. Reduced ED visits and healthcare avoidance led to decreased surveillance sensitivity. FoodNet case counts dropped substantially for most pathogens in 2020, not necessarily reflecting true disease incidence.

2. **Laboratory testing patterns changed.** With the surge in molecular testing (PCR platforms), CIDT-positive cases may have increased disproportionately in some jurisdictions.

3. **The spline model has no mechanism to distinguish** between genuine disease incidence changes and surveillance artifacts during 2020-2022. The state-specific splines will fit through the pandemic dip, which could:
   - Bias post-pandemic trend estimates downward
   - Make 2023+ incidence appear artificially elevated relative to the smoothed trend
   - Distort the IRR calculations when 2020-2022 is used as a comparison period

**Recommendation:** Consider:
- Adding a pandemic indicator variable to the model (e.g., a binary covariate for 2020-2021)
- Documenting the pandemic caveat prominently in all outputs
- Providing an option to exclude 2020-2021 from the spline fit
- Flagging IRR calculations involving pandemic years with a warning

### 6.5 SAFE_WRITE Append Behavior

`functions.R` lines 156-158:
```r
if (file.exists(file_path)) {
  write.table(data, file = file_path, append = TRUE, quote = TRUE, sep = ",",
              col.names = FALSE, row.names = FALSE)
}
```

**Concern:** If the pipeline is re-run without cleaning the output directory, CSV files will have data appended rather than overwritten. This could produce files with duplicate rows, leading to incorrect downstream analyses (e.g., if someone reads the combined CSV for multi-pathogen tables). The `combine_files()` function (`functions.R` lines 773-784) reads all matching CSVs and combines them, compounding this risk.

**Recommendation:** Either warn when appending to existing files or default to overwrite behavior.

---

## 7. Comparison to Published FoodNet Methods

### 7.1 Concordance with MMWR FoodNet Surveillance Reports

The pipeline's overall approach aligns well with published MMWR FoodNet methodology:
- Negative binomial regression with splines is the standard FoodNet trend modeling approach
- State-specific splines allow heterogeneous trends across sites
- Bayesian estimation with MCMC sampling enables proper uncertainty quantification
- Catchment-level incidence is correctly computed as a population-weighted average

### 7.2 Key Methodological Differences

| Aspect | Pipeline | Published MMWR | Impact |
|--------|----------|---------------|--------|
| Posterior predictions | `epred_draws()` | `add_linpred_draws(transform=FALSE)` + manual exp() | Minor numerical differences |
| HDI computation | Response-scale HDI | Log-scale HDI, then exponentiated | Different CI bounds |
| Baseline aggregation | Median across draws | Mean across draws | Slightly different baseline IRR |
| Default MCMC settings | 2 chains, 500 iter | 6 chains, 5001 iter | Unreliable convergence with defaults |
| Salmonella serotypes | User-specified | Dynamic top-10 | Missing automation |
| Comparison periods | Only HP2030 active | Multiple periods | Less comprehensive output |
| Catchment aggregation | Direct sum of .epred | Reshape + exp(linpred) + rowSums | Different computational path |

### 7.3 Missing Analyses Compared to Source

1. **Listeria** is excluded from `ALL_PATHOGENS` in `run_workflow.sh`
2. **Cryptosporidium** is excluded from `ALL_PATHOGENS`
3. **Multiple travel-status runs** -- the original source runs four separate analyses (all travel, no YES, no travel, culture-only). The pipeline supports this but does not automate it.
4. **Site-level IR comparisons** -- the original source computes site-level IRR; the pipeline computes site-level IR but only catchment-level IRR.
5. **Salmonella serotype top-10 automation** is lost.

---

## 8. Summary of Findings by Severity

### Critical Issues

1. **Duplicate Cyclospora processing** (`PATH_ANALYSIS` + `CYCLOSPORA_ANALYSIS` both process Cyclospora, then combined via `smartbind`; Section 2.3). Could double-count cases.

### High-Priority Issues

2. **Default MCMC parameters inadequate for publication** (Section 6.1). Production profile should match original source (6 chains, 5001 iter, adapt_delta=0.999).
3. **Posterior prediction method change** (`epred_draws` vs `add_linpred_draws` + exp; Section 6.2). Results will not exactly reproduce published analyses.
4. **HDI computation on different scale** (response vs. log-scale; Section 6.3). Reported credible intervals will differ from published values.

### Medium-Priority Issues

5. **Travel label logic bug** -- unreachable code branch (Section 5.1, `trendy.R` line 273).
6. **COVID-19 pandemic period unhandled** (Section 6.4). No adjustment or caveat for 2020-2022 surveillance artifacts.
7. **Comparison periods commented out** (Section 3.2). Only HP2030 baseline is active.
8. **SAFE_WRITE append behavior** could produce duplicate data (Section 6.5).
9. **Catchment filter pathogen_type mismatch** in `PATH_ANALYSIS` (Section 1.4).

### Low-Priority Issues

10. **Listeria and Cryptosporidium missing from ALL_PATHOGENS** (Section 2.4).
11. **Salmonella serotype auto-discovery not implemented** (Section 2.2).
12. **2004 vertical line lacks legend annotation** (Section 1.3).
13. **Fuzzy matching risk at RELAXED sensitivity** (Section 4.5).
14. **`PLOT_PCTCHange_TREND` function** (`functions.R` lines 747-770) references undefined variables `pathogen` and `outDir` (not passed as function arguments). This function will fail if called.
15. **Seed difference** (123 vs. 47 in original source) -- minor but results will not be exactly reproducible against the original.

---

## 9. Recommendations

1. Fix the Cyclospora duplicate processing bug immediately.
2. Update the `production` Nextflow profile to match original MCMC parameters.
3. Add convergence diagnostics (R-hat, ESS, divergent transitions) to output.
4. Document all methodological differences from published analyses in a methods supplement.
5. Add COVID-19 pandemic period handling (indicator variable or exclusion option).
6. Fix the travel label logic bug.
7. Uncomment and/or make configurable the additional comparison periods.
8. Add Listeria and Cryptosporidium to the default pathogen list.
9. Consider automating Salmonella top-N serotype discovery.
10. Add a data validation step that compares pipeline output against known published results for a reference dataset.

---

## Addendum: Response to Arbitration Review and Publication Analysis

**Date:** 2026-03-13
**Context:** This addendum responds to the independent arbitration review (`reviews/arbitration_review.md`) and incorporates analysis of the associated publication (doi:10.15212/ZOONOSES-2025-0030). Where direct access to the full publication text was unavailable, the analysis relies on the original source scripts (`source/splinesmodel_16Mar2024_OrCatch.R`, `source/Unspeciated_Shigella.R`) and their reference output (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) as proxies for the published methodology, since these scripts are the code that produced the published results.

---

### 1. Concessions

#### 1.1 Concession: epred_draws vs. add_linpred_draws -- Severity Overstated

The arbiter (Arbitration Section 2.2) is correct that I overstated the impact of switching from `add_linpred_draws(transform=FALSE)` + manual exponentiation to `epred_draws()`. My original review (Section 6.2) claimed that "the uncertainty propagation differs because `epred_draws()` integrates over all posterior uncertainty (including the shape parameter), while the original approach only transforms the linear predictor." The arbiter correctly identifies that this statement is technically incorrect.

For a negative binomial GLM with log link, E[Y|theta] = mu = exp(X*beta) for each posterior draw theta. The shape parameter phi does not enter the expected value calculation. Both `epred_draws()` and `exp(add_linpred_draws(transform=FALSE))` compute the same quantity -- the conditional mean -- from the same posterior draws. The results are algebraically identical: sum(exp(linpred_i)) = sum(epred_i) for catchment aggregation.

I now agree with the arbiter's assessment that the statistical method is equivalent and my HIGH severity rating was unwarranted. I revise this to **MEDIUM**, reflecting the naming/documentation confusion (the function is called `LINPREAD_DRAW_FN` and commented as "link-level predictions" at `trendy.R` line 595, when it actually returns response-scale values) rather than a substantive statistical difference.

I would note, however, that the arbiter's own finding (Arbitration Section 4.9) validates an observation I should have made more strongly: the original source script has a latent bug at `source/splinesmodel_16Mar2024_OrCatch.R` line 250, where `d.prop.fdraws$pinc <- (d.prop.fdraws$.linpred) / (d.prop.fdraws$population/100000)` divides the LOG-SCALE linear predictor by population -- producing a meaningless intermediate quantity. The pipeline's use of `epred_draws()` actually avoids this confusion entirely and is arguably an improvement in code clarity.

#### 1.2 Concession: Cyclospora/Salmonella Duplication Severity -- Mitigated in Standard Workflow

The arbiter (Arbitration Sections 1.3 and 2.1) provides a more nuanced analysis of the Cyclospora/Salmonella duplication issue than my original CRITICAL rating. I concede the following:

The dedicated analysis functions (`CYCLOSPORA_ANALYSIS` at `functions.R` lines 260-281 and `SALMONELLA_ANALYSIS` at lines 295-316) use `group_by(year, state)` without including `pathogen` in the grouping, meaning their output lacks a `pathogen` column. When `smartbind()` combines them with `PATH_ANALYSIS` output (which does include `pathogen`), the dedicated function rows get `pathogen = NA`. The `subset(bact, pathogen == opts$pathogen)` at `trendy.R` line 493 would exclude these NA rows.

Therefore, in the standard Nextflow workflow where `--pathogen` is always passed (per `trendy.nf` line 79), the duplication does not produce inflated counts. I revise this from CRITICAL to **MEDIUM** for the standard Nextflow workflow, while maintaining **HIGH** for standalone R script usage without `--pathogen`, where the NA-pathogen rows would create a spurious model group at `split(bact, bact$pathogen)` on `trendy.R` line 541.

#### 1.3 Concession: Production vs. Publication Profile Distinction

The arbiter (Arbitration Sections 1.4 and 2.5) correctly identifies that I conflated the Nextflow `production` profile (`nextflow.config` lines 102-107: 4 chains, 2000 iterations) with the `publication` bash flag in `run_workflow.sh` (lines 820-824: 6 chains, 10001 iterations). These are two separate configuration mechanisms that I should have distinguished. My comparison table in Section 6.1 only referenced the Nextflow `production` profile, which is the weaker of the two. The `publication` bash flag is closer to the original source parameters, though it still differs in `adapt_delta` (0.99 vs. 0.999 in the original) and `max_treedepth` (15 vs. 19 in the original).

I should have noted both configuration paths and the coordination gap between them. The arbiter's finding that there are THREE separate MCMC configuration mechanisms (nextflow.config defaults, nextflow.config `production` profile, run_workflow.sh flags) that are not clearly coordinated is an important observation I missed.

---

### 2. Rebuttals

#### 2.1 Rebuttal: HDI Computation Scale Difference Remains Methodologically Significant

The arbiter (Arbitration Section 2.3) downgrades my HDI scale difference finding from HIGH to MEDIUM, arguing that "computing HDI directly on the response scale is arguably more principled (it finds the actual highest density region of the posterior predictive distribution)" and that the log-transform approach "finds the HDI of a different distribution."

I respectfully maintain that this is more significant than MEDIUM, though I accept the arbiter's point that neither approach is objectively wrong. My reasoning:

1. **Reproducibility against published results:** The original source code (`source/splinesmodel_16Mar2024_OrCatch.R` lines 299-309) explicitly computes HDI on log-transformed values and back-transforms. The reference output file (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) contains the HDI bounds that were produced by this method. Any CDC report citing these intervals needs to be consistent. The pipeline cannot claim to reproduce published results while computing intervals differently.

2. **The log-scale HDI has epidemiological justification:** Count data and incidence rates are inherently right-skewed. The log transformation produces a more symmetric distribution, and the HDI of this symmetric distribution, when back-transformed, yields intervals that better respect the multiplicative nature of rate ratios. This is why the original authors chose this approach -- it produces intervals that are more interpretable for comparing rates across years.

3. **The reference output confirms practical differences:** Examining `source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`, the published intervals (e.g., Campylobacter 2023 vs. 2006-2008: IRR 0.73 [0.68, 0.77]) were produced using the log-scale HDI method. Computing HDI on the response scale would produce different bounds that would not match these published values.

I revise from HIGH to **MEDIUM-HIGH** -- it is a legitimate methodological choice, but one that must be documented and justified, especially if the pipeline is intended to reproduce or extend published analyses.

#### 2.2 Rebuttal: Baseline IR Computation Is a Genuine Methodological Error, Not Just a Divergence

The arbiter (Arbitration Sections 2.4 and 4.1) correctly identifies that the baseline IR computation issue is deeper than either reviewer initially articulated. I agree with and wish to reinforce the arbiter's analysis:

The original source code at `source/splinesmodel_16Mar2024_OrCatch.R` lines 331-334 computes baseline values as:
```r
summarise_at(.vars = c("count", "population", ".value"), .funs = list(mean=mean))
```
This averages the raw expected count (`.value`), raw count, and population **separately** across baseline years within each draw, then derives the baseline IR as `ref_value / (ref_pop / 100000)`. This is a population-weighted average rate -- the standard epidemiological method for pooling rates across multiple time periods with different denominators.

The pipeline at `functions.R` lines 670-674 instead computes:
```r
mutate(ir = .epred/(population/100000)) %>%
summarise(baseline_ir = median(ir), baseline_count = median(count))
```
This first computes year-specific rates, then takes the median. This gives equal weight to each year regardless of population size and uses the median instead of the mean.

I maintain this is **HIGH** severity. It is not a defensible alternative approach -- it is epidemiologically non-standard. When populations grow across baseline years (as they do for all FoodNet states), equal-weighting of year-specific rates differs materially from the population-weighted approach. Furthermore, using median instead of mean for a 3-year baseline produces the middle value, discarding information from the other two years. The arbiter's verdict (Arbitration Section 2.4: "This is a genuine methodological error in the pipeline") is correct.

#### 2.3 Rebuttal: COVID-19 Pandemic Period Remains a Significant Concern

The arbiter rates the lack of COVID-19 pandemic period handling as MEDIUM (Arbitration M7). While I accept that this is a modeling choice rather than a bug, I want to emphasize why it deserves ongoing attention from an epidemiological standpoint.

The original source scripts (`source/splinesmodel_16Mar2024_OrCatch.R` lines 375-381) compute IRR relative to the 2020-2022 baseline period, acknowledging the pandemic era as a distinct period. The reference output confirms these comparisons were generated and presumably reported. The pipeline comments out this comparison period (`trendy.R` lines 641-642), though this is easily re-enabled.

The deeper concern is not the comparison periods but the model specification itself. The spline model at `functions.R` line 402 will smooth through the 2020 surveillance disruption without distinguishing reduced case ascertainment from reduced disease incidence. For the 2016-2018 HP2030 baseline comparison specifically, this is less problematic (the baseline precedes the pandemic). But for overall trend interpretation and for any future baseline that includes pandemic years, the model's inability to distinguish surveillance artifacts from epidemiological changes is a limitation that should be prominently documented in pipeline outputs.

---

### 3. Publication Comparison

Note: Direct access to the publication at doi:10.15212/ZOONOSES-2025-0030 was unavailable during this review. The following analysis uses the original source scripts and their reference output as proxies for the published methodology, since these scripts generated the published results.

#### 3.1 Model Specification Fidelity

The pipeline's model specification at `functions.R` line 402 faithfully implements the published methodology:

| Aspect | Published (source line 232-236) | Pipeline (functions.R line 402) | Match |
|--------|--------------------------------|--------------------------------|-------|
| Response | `count` | `count` | Yes |
| Spline | `s(yearn, by=state)` | `s(year, by=state)` | Yes (variable name differs) |
| Fixed effect | `state` | `state` | Yes |
| Offset | `offset(log(population))` | `offset(log(population))` | Yes |
| Family | `negbinomial` | `negbinomial()` | Yes |

The model formula is correctly preserved. The only difference is the year variable name (`yearn` in source vs. `year` in pipeline), which is handled by the year-to-numeric conversion at `functions.R` lines 381-383.

#### 3.2 Pathogen Definitions and Handling

**Bacterial pathogens:** The original source at `source/splinesmodel_16Mar2024_OrCatch.R` line 104 defines the standard pathogen list as `c("CAMPYLOBACTER", "CYCLOSPORA", "SALMONELLA", "SHIGELLA", "STEC", "VIBRIO", "YERSINIA")`. The pipeline's `preprocess.R` (lines 123-171) covers all nine FoodNet pathogens (adding LISTERIA and CRYPTOSPORIDIUM), which is a superset.

**STEC O157/non-O157:** The original source at lines 108-109 creates STEC O157 and STEC NONO157 as separate pathogen entries by mutating the pathogen name. The pipeline handles this via the `--subgroup` parameter (`trendy.R` lines 413-423), which is functionally equivalent but architecturally different (separate runs vs. single combined dataset). Both approaches correctly classify "STEC O AG UNDET" into the non-O157 category.

**Listeria CSTE filter:** The original source at line 110 filters `pathogen == "LISTERIA" & cste=="YES"`. The pipeline applies this in `preprocess.R` lines 393-395 with `filter(!(pathogen == "LISTERIA" & cste != "YES"))`. These are logically equivalent. However, the pipeline applies this during preprocessing (permanently excluding non-CSTE Listeria from the cleaned CSV), while the original applies it at the data aggregation step (preserving the full dataset for potential alternate analyses).

**Cyclospora handling:** The original source at lines 137-157 processes Cyclospora separately with the Parasitic census and only when `CIDT+` is in the filter. The pipeline mirrors this structure with `CYCLOSPORA_ANALYSIS()` (`functions.R` lines 260-281). Both approaches are consistent with using different census denominators for parasitic pathogens.

**Salmonella serotype automation:** The original source at lines 162-203 dynamically identifies the top 10 most common serotypes in the most recent year via the `mostcommonsero()` function. The pipeline does not automate this -- it requires the user to specify serotypes via `--subgroup`. This is a loss of functionality relative to the published methodology.

**Shigella species analysis:** The `source/Unspeciated_Shigella.R` script at lines 166-176 applies the `mostcommonsero()` function to SHIGELLA (filtering on `serotypesummary`) to identify top Shigella species. The pipeline does not replicate this Shigella-species-specific analysis path, though the generic `--subgroup` mechanism could accommodate it manually.

#### 3.3 Catchment Areas and Census Denominators

The published methodology uses separate census files for bacterial and parasitic pathogens, reflecting that the FoodNet catchment for parasitic surveillance may cover different counties than for bacterial surveillance in some state-year combinations. The pipeline correctly implements this:

- Original: `census %>% filter(pathogentype=="Bacterial")` at line 131 for bacterial pathogens; `census %>% filter(pathogentype=="Parasitic")` at line 155 for Cyclospora.
- Pipeline: `census %>% filter(pathogentype == "Bacterial")` at `functions.R` line 208; `census %>% filter(pathogentype == "Parasitic")` at line 212.

The catchment state join years are identical between the original (line 128 hardcoded subset) and the pipeline (configurable at `functions.R` lines 71-73), as confirmed in my original review Section 1.2.

#### 3.4 Data Exclusion Criteria

| Criterion | Published (source) | Pipeline | Consistent |
|-----------|-------------------|----------|------------|
| COEX exclusion | Line 68: `filter(SiteID!="COEX")` | `preprocess.R` line 328: `filter(siteid != "COEX")` | Yes |
| County exclusions | Line 79: `filter(!county %in% c("OUT OF STATE", "UNKNOWN", "99997"))` | `trendy.R` line 331: same filter | Yes |
| County name corrections | Lines 80-83: ST. MARY'S, PRINCE GEORGE'S, QUEEN ANNE'S, DEBACA | `preprocess.R` lines 359-365: same corrections | Yes |
| Serotype recoding | `Unspeciated_Shigella.R` lines 71-73: NOT SPECIATED/UNKNOWN/PARTIAL SERO/NOT SERO/empty/UNDET to "Missing" | `preprocess.R` lines 55-57: same rules | Yes |

The data exclusion criteria are fully consistent between the published source and the pipeline.

#### 3.5 Baseline Comparison Periods

The original source computes four comparison periods:
1. **2016-2018** (HP2030 baseline) -- `source/splinesmodel_16Mar2024_OrCatch.R` line 366
2. **2020-2022** (COVID-19 period) -- line 375
3. **2004-2006** (full catchment stabilization) -- line 384
4. **2006-2008** (HP2020 baseline) -- line 393

The `source/Unspeciated_Shigella.R` additionally computes **2010-2012** (line 403).

The pipeline has all five periods defined but only **2016-2018** is active (`trendy.R` line 637). The remaining four are commented out at lines 641-650. The reference output file (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) confirms that the published results include all four periods from the main script.

This means the pipeline, as currently configured, produces only a subset of the published comparison period analyses. This is a significant gap for users expecting to reproduce or extend the full published results.

#### 3.6 Baseline IR Computation Method

The original source at `source/splinesmodel_16Mar2024_OrCatch.R` lines 331-334 computes the baseline as a mean of raw values across baseline years within each draw, then derives IR from the averaged values. The reference output confirms this population-weighted approach.

The pipeline at `functions.R` lines 670-674 computes year-specific IRs first, then takes the median. As detailed in Rebuttal 2.2, this is a methodological divergence from the published approach that produces materially different results.

Examining the reference output for Campylobacter 2023 vs. 2006-2008 baseline: the published IRR is 0.73 (0.68, 0.77). The pipeline's median-of-rates baseline computation would produce a different denominator for this ratio, potentially shifting the IRR estimate.

#### 3.7 COVID-19 Pandemic Effects

The original source computes IRR relative to 2020-2022 (line 375), implicitly acknowledging the pandemic period as worthy of separate comparison. The reference output includes these comparisons (e.g., rows with `startyear=2020, endyear=2022`).

Neither the original source nor the pipeline includes a pandemic indicator variable in the model. Both use unmodified spline models that smooth through the pandemic-era surveillance disruption. The original source's approach of computing the 2020-2022 comparison period at least provides context for interpreting pandemic-era effects, while the pipeline comments this out.

The published methodology appears to treat the pandemic period as a comparison baseline rather than as a model covariate -- the spline absorbs the dip and the reader interprets the IRR relative to 2020-2022 accordingly. This is a pragmatic approach but should be documented.

#### 3.8 Posterior Prediction and Catchment Aggregation

The original source at lines 246-253 uses `add_linpred_draws(transform=FALSE)` to obtain log-scale linear predictors, then at lines 258-261 reshapes to wide format, exponentiates each state column, and sums with `rowSums()`. The pipeline uses `epred_draws()` (response-scale) at `functions.R` line 442 and sums directly in the `CATCHMENT()` function at lines 468-480.

As conceded in Section 1.1 of this addendum, these approaches are algebraically equivalent for the conditional mean. The pipeline's approach is actually cleaner and avoids the intermediate log-scale incidence computation bug in the original source (line 250).

#### 3.9 HDI Computation

The original source at lines 299-309 computes HDI on log-transformed `.value`, then exponentiates. The pipeline computes HDI directly on response-scale `.epred` at `functions.R` lines 512-513. As discussed in Rebuttal 2.1, this produces different interval bounds and is not consistent with the published results.

---

### 4. Revised Severity Ratings

Based on the arbitration review, the publication analysis, and re-examination of the source code, I revise my severity ratings as follows:

| # | Finding | Original Rating | Revised Rating | Reason for Change |
|---|---------|----------------|----------------|-------------------|
| 1 | Cyclospora/Salmonella duplication | CRITICAL | MEDIUM (Nextflow) / HIGH (standalone) | Arbiter correctly identified mitigation via missing `pathogen` column in dedicated functions (Arbitration Section 1.3) |
| 2 | Default MCMC parameters | HIGH | HIGH (unchanged) | Still inadequate; arbiter agrees (Arbitration H2) |
| 3 | epred_draws vs. add_linpred_draws | HIGH | MEDIUM | Arbiter correctly identified algebraic equivalence for conditional mean (Arbitration Section 2.2) |
| 4 | HDI computation scale | HIGH | MEDIUM-HIGH | Arbiter makes fair point about principled response-scale HDI, but reproducibility against published results remains a concern |
| 5 | Travel label logic bug | MEDIUM | MEDIUM (unchanged) | Both reviewers and arbiter agree |
| 6 | COVID-19 unhandled | MEDIUM | MEDIUM (unchanged) | Arbiter agrees (Arbitration M7) |
| 7 | Comparison periods commented out | MEDIUM | MEDIUM (unchanged) | Publication comparison confirms all four periods were used in published results |
| 8 | SAFE_WRITE append | MEDIUM | LOW | Arbiter downgrades; I accept this is operational rather than statistical |
| 9 | Catchment filter pathogen_type | MEDIUM | MEDIUM (unchanged) | Arbiter confirms my finding was correct and Reviewer A missed it (Arbitration Section 3.5) |
| 10 | Baseline IR median-of-rates | (noted but not separately rated) | HIGH | Arbiter and re-analysis confirm this is a genuine methodological error (Arbitration Section 2.4 / H1) |

---

### 5. New Findings

#### 5.1 Original Source Contains a Latent Bug in Site-Level Incidence

The arbiter (Arbitration Section 4.9) identifies that the original source at `source/splinesmodel_16Mar2024_OrCatch.R` line 250 computes `pinc = .linpred / (population/100000)`, dividing the LOG-SCALE linear predictor by population. This produces a meaningless quantity (log(mu)/population, not an incidence rate). While this intermediate value is never directly reported in the published results (the catchment-level computation correctly exponentiates before deriving IR), it means the original source's site-level `pinc` variable is incorrect.

The pipeline's use of `epred_draws()` (response-scale) avoids this bug entirely. Any future extension of the pipeline to report site-level incidence rates would produce correct values, whereas the original source would not. This validates the pipeline's methodological change to `epred_draws()` as an improvement.

#### 5.2 Redundant ir/est_ir Columns in IR_COMP_CATCH

The arbiter (Arbitration Section 4.2) identifies that `functions.R` lines 683-684 compute identical `ir` and `est_ir` columns:
```r
ir = .epred/(population/100000),
est_ir = .epred/(population/100000),
```
This is a minor code quality issue suggesting incomplete refactoring, but it does not affect results.

#### 5.3 Division by Zero Risk in Relative Risk Calculation

The arbiter (Arbitration Section 4.6) identifies a potential division-by-zero at `functions.R` line 685 (`relative_risk = est_ir / baseline_ir`). For rare pathogens or serotype-specific analyses where the baseline period has very low counts, a posterior draw could produce a zero or near-zero expected count, leading to `Inf` values in relative risk. This is particularly relevant for Cyclospora (seasonally concentrated, low counts in some states) and for rare Salmonella serotypes. The pipeline should add a guard clause.

#### 5.4 No Validation Against Published Reference Output

The repository contains a reference output file (`source/EstRR12Apr2024_MMWRR1_OrCatchment.csv`) with published IRR estimates for all pathogens across all comparison periods. This file could serve as a validation benchmark. For example, the published Campylobacter 2023 vs. 2016-2018 result is IRR = 0.78 (0.74, 0.83) with estimated IR = 9.30 (8.83, 9.80). The pipeline should include a validation step that compares its output against these reference values (using the same MCMC parameters, seed, and data) to verify numerical agreement. No such validation step currently exists.

#### 5.5 Original Source Excludes Cyclospora from the Main Bacterial Path

A critical detail for understanding the duplication issue: the original source at `source/splinesmodel_16Mar2024_OrCatch.R` line 107 explicitly filters `pathogen != "CYCLOSPORA"` from the main bacterial pathogen dataset:
```r
gtools::smartbind(as.data.frame(fn %>% filter(pathogen %in% pathogens & pathogen!="CYCLOSPORA")), ...
```
This means in the original source, Cyclospora is processed ONLY through the dedicated Cyclospora path (lines 137-157), not through the main path. The pipeline's `PATH_ANALYSIS()` at `functions.R` line 185 processes ALL pathogens including Cyclospora (via `all_pathogens <- unique(mmwrdata$pathogen)`), then ALSO calls `CYCLOSPORA_ANALYSIS()` at `trendy.R` line 470. This is a divergence from the original source's design that creates the duplication issue. The fix is straightforward: either exclude CYCLOSPORA from `PATH_ANALYSIS()` (matching the original source's approach) or remove the `CYCLOSPORA_ANALYSIS()` call (since `PATH_ANALYSIS()` already handles it with the correct Parasitic census).

#### 5.6 The Unspeciated_Shigella.R Script Reveals Additional Comparison Period

The `source/Unspeciated_Shigella.R` script at lines 402-409 computes a 2010-2012 baseline comparison that is not present in the main source script or the pipeline. This fifth comparison period is relevant for medium-term trend assessment and should be added to the pipeline's configurable comparison periods, or at minimum documented as a period used in published Shigella species analyses.

#### 5.7 The Original Source Uses save_all_pars=TRUE

The original source at `source/splinesmodel_16Mar2024_OrCatch.R` line 234 passes `save_all_pars=TRUE` to `brm()`. The pipeline does not include this parameter. While `save_all_pars` is deprecated in newer versions of `brms` (replaced by `save_pars = save_pars(all = TRUE)`), its absence means the pipeline may not save all parameter draws needed for certain post-hoc analyses (e.g., LOO-CV via the `loo` package). This is a minor operational difference but relevant for reproducibility of any published model diagnostics.

---

*Addendum prepared in response to arbitration review. All severity ratings reflect the combined assessment of the original review, arbiter findings, and publication methodology comparison.*

---

## Addendum 2: Analysis Based on the Actual Published Paper

**Date:** 2026-03-13
**Paper:** Weller DL, Sevilla S, Hetrick E, Billig Rose E, Forstedt J, Caravas J, Ray LC, Payne DC, Steele MK, Hoekstra RM, Bruce BB. "Enhanced Bayesian Spline Regression Approach for Modelling Trends in Infections Caused by Pathogens Commonly Transmitted Through Food." *Zoonoses* (2026) 6:3. DOI: 10.15212/ZOONOSES-2025-0030. Published online February 26, 2026.
**Context:** My previous addendum (Addendum 1) was based on the source scripts in the repository (`source/splinesmodel_16Mar2024_OrCatch.R`, `source/Unspeciated_Shigella.R`) as proxies for the published methodology because direct access to the publication was unavailable. I have now read the full published paper. This addendum corrects, extends, and supersedes the publication-comparison sections of Addendum 1.

---

### 1. What the Paper Actually Says About Epidemiological Methodology

#### 1.1 Pathogens Analyzed

The paper states that FoodNet conducts population-based, active surveillance for laboratory-confirmed infections caused by **nine** pathogens: *Campylobacter*, *Cryptosporidium*, *Cyclospora*, *L. monocytogenes*, *Salmonella*, *Shigella*, STEC, *Vibrio*, and *Yersinia*, as well as pediatric hemolytic uremic syndrome (Methods, "Data" section).

Separate models were implemented for each of **eight** diseases monitored by FoodNet through 2019: *Campylobacter*, *Cyclospora*, *Listeria*, *Salmonella*, *Shigella*, *Vibrio*, and *Yersinia* infection, plus STEC overall, STEC O157, non-O157 STEC, and the 16 most frequently reported *Salmonella* serotypes during 2016-2018 (Methods, "Comparison of original and enhanced model performance").

**Key detail the paper provides:** FoodNet stopped collecting data for *Cryptosporidium* infections in 2017, and for *Campylobacter* infections that were not culture-confirmed in 2023. FoodNet made collection of data optional for all diseases except *Salmonella* and STEC infection in 2025 (Methods, "Data" section).

**Pipeline implication:** The pipeline's `preprocess.R` includes CRYPTOSPORIDIUM as a recognized pathogen (line 165), and the `functions.R` `PATH_ANALYSIS()` routes it to Parasitic census data (line 193). However, the pipeline has no mechanism to enforce the 2017 cutoff for *Cryptosporidium*. If input data includes post-2017 *Cryptosporidium* records (which should not exist per FoodNet data collection rules but could appear due to data entry errors), the pipeline would model them without warning. Similarly, the 2023 cutoff for non-culture-confirmed *Campylobacter* is not enforced.

#### 1.2 Catchment Definitions

The paper provides detailed catchment history (Introduction, paragraph 3):

- When FoodNet was founded (1996), the catchment included Minnesota, Oregon, and select counties in California, Connecticut, and Georgia.
- The catchment expanded consistently from 1996 through 2004 to include all of CT, GA, Maryland, MN, New Mexico, OR, and Tennessee, and select counties in CA (N=3), Colorado (N=7), and New York (N=34).
- During 2004-2022, the catchment area remained constant but expanded again in 2023 to include the remainder of CO.
- During 2004-2022, the catchment represented approximately 15% of the U.S. population; as of 2023, approximately 16%.

**Critical new information:** The paper explicitly states that in the initial 1996 catchment, CT and GA participated through **select counties only**, not the full state. They expanded to full state coverage by 2004. The pipeline's `read_catchment_config()` (`functions.R` lines 71-73) assigns start_year=1996 for both CT and GA, which is correct for when they entered FoodNet but does not capture the sub-state-to-full-state transition. This is handled by the census denominator files (which should reflect the actual participating county populations in each year), but the catchment configuration does not document this nuance.

**Also critical:** The 2023 expansion of CO to include the full state (not just N=7 counties) is not reflected anywhere in the pipeline. The COEX exclusion (`preprocess.R` line 328: `filter(siteid != "COEX")`) removes the expanded Colorado catchment data. For analyses through 2022, this is correct. For 2023+ analyses, the pipeline would need to either include COEX data or use an updated census denominator that reflects the full CO catchment.

#### 1.3 Diagnostic Criteria (CIDT)

The paper states: "FoodNet began collecting data on illnesses diagnosed using culture-independent diagnostic tests in 2012. FoodNet data collected during 1996-2019 were used to develop and compare the models reported here." (Methods, "Data" section).

The paper does not describe the CIDT/CX+/PARASITIC classification scheme in detail -- it refers to culture-confirmed and CIDT-diagnosed illnesses as categories but does not specify the exact filter values used. This is operational detail left to the code.

**Pipeline alignment:** The pipeline's default `--cidt "CIDT+,CX+,PARASITIC"` (`trendy.R` line 83) includes all diagnostic categories, which is consistent with the paper's approach of modeling all confirmed infections.

#### 1.4 Travel Exclusions

The paper states: "Cases were considered domestically acquired if the ill person did not report international travel or had an unknown travel history during the <=30 days before *Listeria*, *Salmonella* Typhi, and *Salmonella* Paratyphi symptom onset, <=14 days before cyclosporiasis onset, and <=7 days before symptom onset for other infections." (Methods, "Data" section).

**This is a significant finding.** The paper describes the **case classification criteria** for domestic acquisition, not a blanket travel exclusion. The pipeline's `--travel` parameter (`trendy.R` line 82, default `"NO,UNKNOWN,YES"`) operates as a simple filter on the `travelint` field. When set to "All Cases" (the default), all travel statuses are included, which is consistent with the paper's approach for total incidence modeling. However, when set to exclude travel-associated cases, the pipeline applies a uniform travel filter across all pathogens rather than using the pathogen-specific travel windows described in the paper. This pathogen-specific travel window logic would need to be implemented in the data source (the MMWR SAS file) rather than the pipeline, and presumably is -- the `travelint` field likely already reflects the pathogen-specific window classifications. But the pipeline does not document this dependency.

#### 1.5 Data Exclusion Criteria

The paper does not explicitly enumerate county exclusions ("OUT OF STATE", "UNKNOWN", "99997") or county name corrections. These are operational data cleaning steps that the paper reasonably omits.

The paper does explicitly mention the COEX exclusion implicitly: it states the catchment "expanded again in 2023 to include the remainder of CO" and describes the pre-2023 CO catchment as "select counties in Colorado (N=7)." The COEX exclusion in the pipeline is consistent with modeling the pre-2023 catchment.

#### 1.6 Training Data Period

The paper states: "FoodNet data collected during 1996-2019 were used to develop and compare the models reported here." (Methods, "Data" section). This is the **training window** for the paper's model comparison analysis.

**However**, the paper also demonstrates nowcasting capability: Figure 5 shows median annual incidence estimates generated for 2020 through 2023 for *Campylobacter*, with the model trained on 1996-2019 data. The paper states: "Median annual incidence estimates were generated for 2020 through 2023 using the enhanced model" and notes the discrepancy between estimated and observed incidence during 2020-2021 is "likely attributable to reduced foodborne illness exposure and reporting during the COVID-19 pandemic."

**Pipeline implication:** The pipeline does not enforce or document a training window. It models all years present in the data. This is actually more flexible than the paper's analysis, which froze at 1996-2019 for the comparison study. For operational use (as opposed to the methodological comparison in the paper), including all available years in the training data is appropriate.

#### 1.7 Baseline Periods

The paper mentions several baseline periods:

- **2016-2018:** "Healthy People 2030 foodborne disease reduction goals is monitored using average incidence during 2016-2018 as the baseline" (Methods, "Original model parameterization" section).
- **First year of FoodNet surveillance (1996):** Used in some analyses.
- **2004-2006:** "the first three years after FoodNet's catchment stabilized" (Methods, "Original model parameterization" section).
- **3 years preceding the year of interest:** Used in some comparison approaches.

The paper does not itself report IRR comparisons across all these periods -- it focuses on demonstrating methodological improvements rather than reporting surveillance results. The actual IRR computations are products of annual MMWR reports, not this methods paper.

#### 1.8 COVID-19 Handling

The paper explicitly addresses COVID-19 in its discussion of nowcasting (Figure 5 caption and accompanying text): "The discrepancy between estimated and observed incidence in 2020-2021 is likely attributable to reduced foodborne illness exposure and reporting during the COVID-19 pandemic, rather than to poor predictive performance."

The paper treats the COVID-19 period as a validation case for the model's nowcasting capability, not as something requiring special model parameterization. The enhanced model is presented as being **robust** to the pandemic disruption because splines smooth over aberrant years, and the discrepancy between modeled trend and observed counts during 2020-2021 is interpreted as reflecting the pandemic's effect on surveillance, not a model failure.

#### 1.9 Original vs. Enhanced Model -- Key Differences per the Paper

Table 1 in the paper provides a direct comparison:

| Aspect | Original Model | Enhanced Model |
|--------|---------------|----------------|
| Framework | Frequentist | Bayesian |
| Unit of analysis | County-year | State (site-level) |
| Bias | Toward more populous states | Not biased by site population |
| Site-specific trends | Same trend for all states | Site-specific trends |
| Year treatment | Categorical | Continuous |
| Non-linearity | Captured by treating year as categorical | Uses splines |
| Unidirectional nature of time | Not accounted for | Accounted for |
| Nowcasting | No | Yes |

**Key finding:** The paper describes the **final enhanced model** as aggregated to the **site level** (state level), not the county-year level used by the original model. The paper states: "Data were aggregated to the site level, and illness count was modeled as a function of site and year" (Methods, "Enhanced model parameterization"). The paper also states: "Models fit using county-level data performed comparably to but took an order of magnitude longer to run than site-level models, and the negative binomial distribution performed slightly better than models fit with other distributions" (Results/Enhanced model parameterization).

This confirms the pipeline's state-level aggregation approach (`PATH_ANALYSIS` groups by `year, state, pathogen` at `functions.R` line 198) is correct per the published methodology.

#### 1.10 Enhanced Model Specification per the Paper

The paper describes the enhanced model specification (Methods, "Enhanced model parameterization"):

1. Uses penalized thin plate regression splines to model the effect of year.
2. Treats year as a continuous variable.
3. Incorporates a year-site interaction.

Implementation details:
- 6 chains and 10,001 iterations using brms package (version 2.20.1).
- Splines implemented using the `s()` function with the `by` parameter set to site.
- Student-t prior: `student_t(3, -8.84, 2.5)` on the intercept, `student_t(3, 0, 2.5)` on standard deviation parameters.
- Inverse-gamma prior: `inv_gamma(0.4, 0.3)` on the shape parameter.
- Flat (uninformative) priors for all regression coefficients, including site effects and their interactions with year.
- Half Student-t prior on the spline scale parameter dependent on the standard deviation of the transformed response.
- Improper flat prior for fixed effects.

**Critical finding about priors:** The paper explicitly documents the priors used, which are the **brms package defaults** -- weakly informative or flat. The paper states: "The priors and the value of the basis function used to represent the smooth term for the thin plate regression splines were set to the package default." This is important because it means the pipeline's use of default brms priors is correct and consistent with the publication, resolving a question that was ambiguous from the source code alone.

#### 1.11 Model Performance Metrics

The paper evaluates models using:
- Root mean squared error (RMSE)
- Adjusted R-squared
- Expected log pointwise predictive density (ELPD)

All calculated from **in-sample fits** using the `performance` package (version 0.12.4). The paper explicitly states these are in-sample metrics: "which were calculated from in-sample fits using the performance package."

The pipeline does not compute or report any of these model performance metrics.

---

### 2. Where the Pipeline Matches the Paper -- Validated Findings

#### 2.1 Model Formula

The pipeline's model formula at `functions.R` line 402:
```r
count ~ s(year, by = state) + state + offset(log(population))
```
matches the paper's description: negative binomial model with penalized thin plate regression splines, year-site interaction via `s(year, by = state)`, state fixed effects, and log population offset. **Fully validated.**

#### 2.2 Negative Binomial Family

The paper confirms: "the negative binomial distribution performed slightly better than models fit with other distributions." The pipeline correctly uses `family = negbinomial()`. **Fully validated.**

#### 2.3 Site-Level Aggregation

The paper confirms the final enhanced model uses site-level (state-level) data, not county-year data. The pipeline aggregates to state level in `PATH_ANALYSIS()` (`functions.R` line 198: `group_by(year, state, pathogen)`). **Fully validated.**

#### 2.4 Catchment State Definitions and Join Years

The paper's description of catchment expansion (MN, OR, select CA counties in 1996; MD and NY added 1998; TN added 2000; CO added 2001; NM added 2004) matches the pipeline's `read_catchment_config()` start years. **Fully validated.**

#### 2.5 Nine FoodNet Pathogens

The paper lists the same nine pathogens that the pipeline's `preprocess.R` pathogen patterns recognize (lines 123-171). **Fully validated.**

#### 2.6 Listeria CSTE Filter

While not explicitly described in the paper, the paper lists *L. monocytogenes* (invasive listeriosis) as a monitored pathogen, consistent with the CSTE case definition filter applied in `preprocess.R` lines 393-399. **Consistent.**

#### 2.7 Default Priors

The paper confirms that brms default priors (weakly informative or flat) were used. The pipeline uses brms defaults by not specifying explicit priors in the `brm()` call (`functions.R` line 402). **Fully validated.**

#### 2.8 STEC O157/non-O157 Split

The paper separately models "STEC overall and for *E. coli* O157:H7, specifically" and by extension non-O157 STEC. The pipeline's `--subgroup` mechanism supports this. **Validated.**

#### 2.9 Salmonella Serotype Modeling

The paper states models were implemented for "the most frequently reported *Salmonella* serotypes during 2016-2018 (see Fig 2)." Figure 2 shows 16 serotypes. The pipeline can model individual serotypes via `--subgroup`. The specific serotypes shown in Figure 2 are: S. Oranienburg, S. Infantis, S. Bareilly, S. Typhimurium, S. Newport, S. Braenderup, S. Javiana, S. Enteritidis, S. Heidelberg, S. Montevideo, S. Muenchen, S. Paratyphi B var. L(+) Tartarate+, S. Berta, S. Mississippi, S. I 4,[5],12:i:-, and S. Typhi. **Validated in capability, though automation of the "top N" selection is absent from the pipeline.**

---

### 3. Where the Pipeline Diverges from the Paper

#### 3.1 MCMC Parameters

The paper specifies 6 chains and 10,001 iterations. The pipeline defaults to 2 chains and 500 iterations (`functions.R` line 348; `trendy.R` lines 106-108). Even the `production` Nextflow profile uses only 4 chains and 2000 iterations. The `run_workflow.sh` publication flag (6 chains, 10001 iterations) is closer but still differs in `adapt_delta` and `max_treedepth`.

The paper specifies brms version 2.20.1. The pipeline does not pin a brms version.

**Code references:** `functions.R` line 348 (defaults), `trendy.R` lines 103-108 (argument defaults), `nextflow.config` lines 102-107 (production profile).

#### 3.2 Number of Salmonella Serotypes and Selection Criterion

The paper models the **16** most frequently reported *Salmonella* serotypes during **2016-2018**. My previous addendum (Addendum 1, Section 3.2) stated the source code identifies the "top 10 most common serotypes in the most recent year." The paper clarifies it is actually 16 serotypes based on frequency during 2016-2018, not 10 based on the most recent year. The pipeline has no automated serotype selection.

**Code reference:** The `mostcommonsero()` function in the source scripts selects the top N, but the paper's analysis used N=16 and a fixed reference period (2016-2018), not a dynamic "most recent year" approach.

#### 3.3 Training Data Period

The paper used 1996-2019 data for model development and comparison. The pipeline does not enforce a training window -- it uses all data present in the input file. For the paper's specific comparison analysis, this means the pipeline could not exactly reproduce the paper's results without the user manually restricting the input data to 1996-2019.

**Code reference:** No explicit date-range filtering in `trendy.R` or `functions.R`. The year range is entirely determined by the input data.

#### 3.4 Model Performance Metrics

The paper reports RMSE, adjusted R-squared, and ELPD computed from in-sample fits using the `performance` R package. The pipeline computes none of these metrics. The model summary is saved (`trendy.R` lines 590-593) but does not include formal goodness-of-fit statistics.

**Code reference:** `trendy.R` lines 590-593 (summary output only).

#### 3.5 Colorado 2023 Catchment Expansion

The paper notes the catchment "expanded again in 2023 to include the remainder of CO." The pipeline's COEX exclusion (`preprocess.R` line 328) would need to be conditionally applied (excluding COEX before 2023, including it from 2023 onward) for analyses that span the 2023 boundary. Currently it unconditionally excludes COEX.

**Code reference:** `preprocess.R` line 328.

#### 3.6 Cryptosporidium Data Collection Cutoff

The paper states FoodNet stopped collecting *Cryptosporidium* data in 2017. The pipeline has no enforcement of this cutoff.

**Code reference:** No relevant code -- this is an absence.

#### 3.7 Campylobacter Non-Culture-Confirmed Cutoff

The paper states FoodNet stopped collecting data for *Campylobacter* infections that were not culture-confirmed in 2023. The pipeline has no enforcement of this cutoff. For analyses including 2023+ data, including non-culture-confirmed *Campylobacter* cases could inflate counts relative to the surveillance system's actual scope.

**Code reference:** No relevant code -- this is an absence.

#### 3.8 2025 Data Collection Changes

The paper states: "FoodNet made collection of data optional for all diseases except *Salmonella* and STEC infection in 2025." This means that from 2025 onward, the pipeline's assumption that FoodNet actively surveys all nine pathogens at all 10 sites is potentially invalid. The pipeline has no mechanism to handle partial or optional data collection.

**Code reference:** No relevant code -- this is an absence of future-proofing.

#### 3.9 Nowcasting Capability

The paper explicitly describes and demonstrates the enhanced model's nowcasting capability (generating estimates for years beyond the training data, such as 2020-2023 estimates from a model trained on 1996-2019 data; see Figure 5). The pipeline does not implement or document nowcasting as a feature, though the spline model inherently supports extrapolation. The pipeline does not generate or flag nowcast estimates distinctly from interpolated estimates.

**Code reference:** No explicit nowcasting logic in `functions.R` or `trendy.R`.

#### 3.10 Comparison with Original (Frequentist) Model

A substantial portion of the paper is devoted to comparing the enhanced Bayesian spline model against a Bayesian version of the original frequentist model, and against modified versions of both. The pipeline does not implement the original model or any comparison framework. This is understandable (the pipeline implements the enhanced model only), but it means the pipeline cannot independently validate the paper's central claims about model superiority.

---

### 4. Corrections to My Previous Addendum

#### 4.1 Correction: Source Scripts Are Not the Paper

My previous addendum (Addendum 1, Section 3, "Publication Comparison") stated: "Direct access to the publication at doi:10.15212/ZOONOSES-2025-0030 was unavailable during this review. The following analysis uses the original source scripts and their reference output as proxies for the published methodology, since these scripts generated the published results."

Having now read the paper, I can confirm that the source scripts are the **implementation** used to generate the paper's results, but the paper contains additional methodological context, design rationale, and interpretation that the scripts do not capture. Several findings in my previous addendum were incomplete or slightly incorrect because they lacked this context.

#### 4.2 Correction: Salmonella Serotype Count and Selection Period

**Previous claim (Addendum 1, Section 3.2):** "The original source at lines 162-203 dynamically identifies the top 10 most common serotypes in the most recent year."

**Correction:** The paper states 16 serotypes were modeled, selected based on frequency during 2016-2018, not the most recent year. The source code's `mostcommonsero()` function may select a different N and use a different reference period than what was done for the publication. The paper's Figure 2 explicitly shows 16 serotypes. The discrepancy between the source code's dynamic approach and the paper's fixed selection suggests that the published analysis involved manual curation or parameter adjustment beyond what the source scripts automate.

#### 4.3 Correction: COVID-19 Is Addressed in the Paper

**Previous claim (Addendum 1, Section 3.7):** "Neither the original source nor the pipeline includes a pandemic indicator variable in the model. Both use unmodified spline models that smooth through the pandemic-era surveillance disruption."

**Correction per the paper:** The paper explicitly addresses this as a feature, not a limitation. The enhanced model's ability to generate estimates for 2020-2023 from 1996-2019 training data is presented as demonstrating nowcasting capability. The discrepancy between modeled and observed 2020-2021 incidence is attributed to "reduced foodborne illness exposure and reporting during the COVID-19 pandemic" (Figure 5 caption). The paper frames the spline's smoothing behavior as appropriate: the model estimates what incidence *would have been* without the pandemic disruption, which is valuable for counterfactual analysis. My original recommendation to add a pandemic indicator variable conflicts with this stated purpose of the model.

I still maintain that for operational surveillance purposes (as opposed to the methodological demonstration in the paper), users should be aware that the model does not distinguish surveillance artifacts from epidemiological changes. But the paper's framing is valid for its stated purpose.

#### 4.4 Correction: The Paper's Training Period Is Specific to the Comparison Study

**Previous implicit assumption:** The 1996-2019 training period is the standard operational window.

**Correction:** The paper used 1996-2019 specifically "to develop and compare the models reported here." This was a methodological choice for the comparison study, not a prescription for operational use. The pipeline's approach of using all available data is actually more appropriate for operational trend modeling than the paper's fixed training window.

#### 4.5 Correction: Baseline Periods Are Not Central to the Paper

**Previous claim (Addendum 1, Section 3.5):** Extensive analysis of which comparison periods are active vs. commented out, implying the pipeline is missing published results.

**Correction:** The paper is a methods paper, not a surveillance report. It does not report IRR comparisons across multiple baseline periods. The IRR calculations in the source scripts and reference output are operational products (for MMWR annual reports), not part of this paper's published results. My emphasis on commented-out comparison periods, while operationally important, was not relevant to reproducibility of the paper's findings.

#### 4.6 Correction: The Paper Documents Prior Specifications That Resolve Ambiguity

**Previous uncertainty (Addendum 1, Section 5.7):** I noted the source code uses `save_all_pars=TRUE` and that the pipeline omits it, flagging this as a reproducibility concern.

**Correction:** The paper explicitly states that brms default priors were used (weakly informative or flat), and specifies the exact priors: Student-t(3, -8.84, 2.5) on the intercept, Student-t(3, 0, 2.5) on SD parameters, inv_gamma(0.4, 0.3) on the shape parameter, and flat priors for regression coefficients. The `save_all_pars` parameter is about storage of MCMC draws, not prior specification, and its deprecation in newer brms versions makes it a version-compatibility issue rather than a methodological one. My concern was overstated.

---

### 5. New Epidemiological Findings from the Paper

#### 5.1 The Original Model's Bias Toward Populous States Is Quantified

The paper provides quantitative evidence of the original model's population bias (Results, "By generating site-specific trend estimates..." section): "the 95% CI for estimated incidence in CO does not overlap actual incidence in CO for 43% of the time (N=10). Even for populous sites, such as GA, the original model estimates do not include actual incidence 52% of the time (N=12 years) with the model drastically over-estimating incidence in GA during 1996-2001."

The enhanced model's improvement: "The 95% CrI for estimated incidence in CO overlaps actual incidence in CO 91% of the time (N=21 years), while the 95% CrI for GA overlaps actual incidence in GA 78% (N=18) of the time."

**Pipeline relevance:** This validates the pipeline's use of the enhanced model with state-specific splines. But it also means that any regression to the original model's approach (e.g., dropping the `by = state` interaction) would re-introduce a quantified and significant bias.

#### 5.2 Nowcasting Performance Is Demonstrated with Specific Numbers

Figure 5 provides specific nowcast estimates for *Campylobacter*:

| Year | Estimated Median IR (95% CrI) | Actual IR |
|------|-------------------------------|-----------|
| 2020 | 20.4 (19.7, 21.2) | 14.3 |
| 2021 | 21.1 (20.2, 21.9) | 18.0 |
| 2022 | 21.8 (20.8, 22.7) | 19.2 |
| 2023 | 22.5 (21.4, 23.7) | 25.2 |

The 2020-2021 discrepancy (model overestimates relative to observed) is attributed to pandemic effects on surveillance. The 2022-2023 discrepancy "likely reflect the increased temporal distance from the years used to train the model, highlighting greater uncertainty when extrapolating beyond the training window."

**Pipeline relevance:** The pipeline could reproduce this analysis if configured to train on 1996-2019 data and then predict for 2020-2023. However, the pipeline does not currently distinguish training data from nowcast prediction targets, nor does it flag estimates for out-of-sample years. Adding a `--training-end-year` parameter would enable proper nowcasting with appropriate uncertainty flagging.

#### 5.3 The Paper Explicitly Describes R-INLA as a Future Direction

The paper states (Discussion, "Next steps"): "A logical next step for enhancing the model would be to implement a less computationally intensive approximation method, such as R-INLA. This would enable the generation of more granular estimates in the near-real time using standard laptops instead of requiring high-performance computing environments."

**Pipeline relevance:** This suggests the pipeline's computational demands (noted in my original review Section 6.1) are a recognized limitation, and that future pipeline versions may need to support R-INLA as an alternative backend.

#### 5.4 The Paper Identifies County-Level Modeling as a Future Direction

The paper states: "we recognize that site-level aggregation can mask within-site variability" and references a paper that adapted the FoodNet model to compare salmonellosis trends within Virginia counties. The paper further notes: "Once we can fit county-level models, we can incorporate spatial relationships into the model to improve estimates."

**Pipeline relevance:** The pipeline's state-level aggregation is correct for the current published methodology, but the architecture should anticipate county-level extension. The current `PATH_ANALYSIS()` aggregation at `functions.R` line 198 (`group_by(year, state, pathogen)`) would need to be modified to `group_by(year, state, county, pathogen)` or similar for county-level modeling.

#### 5.5 The Paper Discusses CIDT Trends as Complicating Incidence Interpretation

The paper states (Discussion): "new diagnostic methods are being differentially adopted by labs serving different communities. Because new diagnostic methods can detect illnesses that would have previously gone undiagnosed, disentangling signals due to increased use of these methods from true increases in incidence is complicating interpretation of trends." The paper suggests: "Incorporating a spline of the year with an interaction between the diagnostic method and site (or county) would allow us to, at least partially, overcome this complication."

**Pipeline relevance:** The pipeline's current model does not include diagnostic method as a covariate. The `--cidt` parameter controls which cases are included but does not model the CIDT transition as a time-varying covariate. The paper's suggestion of a diagnostic-method-by-site-by-year interaction is a more sophisticated approach that the pipeline's architecture could accommodate but does not currently implement.

#### 5.6 The Paper Addresses Intra-Annual Variation

The paper notes (Discussion, "Next steps"): "past studies have reported substantial intra-annual variation in foodborne and enteric disease incidence" and acknowledges that "the present study does not account for intra-annual variation." The pipeline similarly operates at annual resolution only.

#### 5.7 The Paper Explicitly States the Model Generates Annual Estimates

The paper confirms: "The original and enhanced FoodNet trends models both generate annual estimates" (Discussion). This validates the pipeline's annual aggregation approach.

---

### 6. Revised Priority List Incorporating the Paper's Methodology as Ground Truth

The following priority list supersedes the lists in my original review (Section 8) and Addendum 1 (Section 4), using the published paper as the definitive reference for intended methodology.

#### Critical

1. **Colorado 2023 catchment expansion not handled.** The paper documents the CO expansion in 2023. The pipeline unconditionally excludes COEX data (`preprocess.R` line 328), making it unable to correctly model 2023+ CO data. For any analysis including 2023 or later, this produces an incorrect catchment. Fix: make COEX exclusion conditional on year, or provide a parameter to control it.

#### High Priority

2. **Baseline IR computation uses median-of-rates instead of population-weighted mean.** This was identified in Addendum 1 and remains HIGH. The paper's methodology (via the source code) uses population-weighted mean. The pipeline's approach at `functions.R` lines 670-674 is epidemiologically non-standard. Fix: compute baseline as mean of expected counts divided by mean of populations across baseline years, per the source code approach.

3. **Default MCMC parameters inadequate for publication.** The paper specifies 6 chains, 10,001 iterations. Pipeline defaults are 2 chains, 500 iterations (`functions.R` line 348). The `production` Nextflow profile (4 chains, 2000 iterations) is still insufficient. Only the `run_workflow.sh` publication flag approaches the paper's parameters. Fix: align the `production` profile with the paper's specifications.

4. **No model performance metrics computed.** The paper reports RMSE, adjusted R-squared, and ELPD. The pipeline saves a model summary but no formal goodness-of-fit statistics. Fix: add `performance` package integration to compute and output these metrics after model fitting.

5. **HDI computation on response scale vs. log scale.** Maintained at MEDIUM-HIGH from Addendum 1. The paper does not specify which scale was used for HDI computation, but the source code (which generated the paper's results) uses log-scale HDI with back-transformation. For reproducibility of the paper's reported credible intervals, the pipeline should match the source code approach. Fix: compute HDI on log-transformed predictions, then exponentiate.

#### Medium Priority

6. **Cyclospora duplicate processing.** Maintained at MEDIUM for standard Nextflow workflow from Addendum 1. `PATH_ANALYSIS()` processes all pathogens including Cyclospora (`functions.R` line 185), then `CYCLOSPORA_ANALYSIS()` is also called (`trendy.R` line 470). The paper's methodology processes Cyclospora only through the dedicated parasitic path. Fix: exclude Cyclospora from `PATH_ANALYSIS()` to match the paper's approach.

7. **Cryptosporidium 2017 cutoff not enforced.** The paper states data collection stopped in 2017. The pipeline would model post-2017 Cryptosporidium records if present. Fix: add a warning or filter for post-2017 Cryptosporidium data.

8. **Campylobacter 2023 non-culture cutoff not enforced.** The paper states non-culture-confirmed Campylobacter data collection stopped in 2023. Fix: add documentation and optionally a filter for this change.

9. **Travel label logic bug.** Maintained at MEDIUM from original review. The `||` operator at `trendy.R` line 271 makes the second branch unreachable. Fix: change `||` to `&&` for the first condition.

10. **Comparison periods commented out.** Maintained at MEDIUM from Addendum 1, but **downgraded in relevance to the paper** since the paper is a methods paper, not a surveillance report. The comparison periods are operationally important for MMWR reporting but not for reproducing the paper's specific findings.

11. **No automated Salmonella serotype selection.** The paper modeled 16 serotypes based on frequency during 2016-2018. The pipeline requires manual specification. Fix: implement a function that identifies the top N serotypes based on a configurable reference period.

12. **No nowcasting framework.** The paper explicitly demonstrates and discusses nowcasting as a key capability of the enhanced model. The pipeline does not distinguish training data from nowcast predictions. Fix: add a `--training-end-year` parameter and flag nowcast estimates in the output.

#### Low Priority

13. **2025 data optionality not documented.** The paper notes FoodNet made data collection optional for most pathogens in 2025. The pipeline should document this limitation for 2025+ analyses.

14. **brms version not pinned.** The paper used brms 2.20.1. Different brms versions could produce slightly different results due to changes in default priors, spline implementations, or MCMC sampling. Fix: document the target brms version or add a version check.

15. **Listeria and Cryptosporidium missing from `ALL_PATHOGENS`.** Maintained from original review.

16. **`PLOT_PCTCHange_TREND` function broken.** Maintained from original review. References undefined variables.

17. **SAFE_WRITE append behavior.** Downgraded to LOW per Addendum 1 (operational, not statistical).

18. **Seed difference (123 vs. 47).** Minor. Results will not be exactly reproducible against the paper's analysis.

---

### 7. Summary

Reading the actual published paper reveals that my previous addendum's source-script-based analysis was largely accurate for operational details (model formula, catchment definitions, data exclusions) but missed important context about the paper's purpose and framing. The paper is fundamentally a **methods paper** demonstrating the enhanced model's superiority over the original frequentist approach, not a surveillance report. Several of my previous concerns (COVID-19 handling, comparison periods) were framed as deficiencies when the paper actually treats them differently.

The most significant new findings from the paper are:

1. **Data collection changes** (Cryptosporidium 2017, Campylobacter non-culture 2023, all-but-two optional 2025) that the pipeline does not enforce or document.
2. **Colorado 2023 expansion** that the pipeline's unconditional COEX exclusion cannot handle.
3. **Nowcasting** as an explicitly described capability that the pipeline does not formally support.
4. **16 Salmonella serotypes** (not 10 as I previously stated from the source code), selected from a fixed 2016-2018 reference period.
5. **R-INLA as a planned future direction**, suggesting the pipeline architecture should anticipate alternative computational backends.
6. **In-sample model performance metrics** (RMSE, R-squared, ELPD) that the pipeline does not compute.

The pipeline remains a faithful implementation of the enhanced model's core methodology (model formula, negative binomial family, state-specific splines, Bayesian framework). The divergences are primarily in operational details (MCMC parameters, baseline computation, HDI scale, automation of serotype selection) and in documentation/enforcement of data collection boundaries.

*Addendum 2 prepared after reading the full published paper: Weller et al., Zoonoses (2026) 6:3, DOI: 10.15212/ZOONOSES-2025-0030.*
