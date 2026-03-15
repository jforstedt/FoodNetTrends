# Statistical Justification Review: HIGH-Priority Findings

**Reviewer role:** Senior biostatistician and epidemiologist
**Date:** 2026-03-13
**Scope:** Evidence-based evaluation of 6 HIGH-priority findings from the FoodNetTrends pipeline arbitration review

---

## H1: Baseline IR Computation -- median-of-rates vs. population-weighted mean

### The Claim

The pipeline's `IR_COMP_CATCH()` function (functions.R line 673) computes a baseline incidence rate per posterior draw by taking `median(ir)` across the 3 baseline years (e.g., 2016-2018). The arbiter states the original method uses `mean(count)/mean(population)` (i.e., a population-weighted mean rate) across the baseline years per draw.

### The Evidence

**Epidemiological first principles.** A catchment-level incidence rate for a multi-year period is defined as:

> IR = (total cases across years) / (total person-years across years) x 100,000

This is algebraically equivalent to `sum(count) / sum(population) * 100000`, which is what `mean(count)/mean(population)*100000` yields when the number of years is constant (sum/3 divided by sum/3 = sum/sum). This is the standard definition used by CDC in MMWR reports and by the Healthy People 2030 framework (see [HP2030 Methods](https://odphp.health.gov/healthypeople/objectives-and-data/data-sources-and-methods/target-setting-methods)).

**What FoodNet actually does.** The paper (Weller et al. 2026, page 5) states: "incidence estimates for 2023 were compared with average incidence estimates for 2016-2018, which is the baseline period used to track progress toward federal disease reduction goals." The MMWR 2024 FoodNet report ([mm7326a1](https://www.cdc.gov/mmwr/volumes/73/wr/mm7326a1.htm)) describes comparing current-year incidence to "average annual incidence during 2016-2018." In surveillance epidemiology, "average incidence" for a catchment means total cases / total person-time, not the median of per-year rates.

**Why median-of-rates is wrong for a 3-year baseline.** The `median(ir)` of 3 annual rates simply picks the middle value. With only 3 values, the median discards information from the other two years entirely. It is not a recognized method for computing a baseline incidence rate in any CDC methodology document, MMWR report, or Healthy People framework. Furthermore, if population changes across years (as it does with FoodNet catchment expansion), the median-of-rates gives equal weight to each year regardless of population size. This violates the fundamental principle that incidence rates for combined periods should reflect total person-time at risk.

**Is population-weighting necessary?** Yes. The population-weighted mean (sum of counts / sum of populations) is not merely conventional -- it is the epidemiologically correct definition of incidence rate for a combined period. An unweighted average of rates would only be appropriate if the population at risk were identical across all years, which is not the case for FoodNet (population grew and catchment expanded).

### The Verdict

**The fix is OBJECTIVELY CORRECT.** Using `median(ir)` is statistically incorrect for computing a baseline incidence rate. The correct computation is `sum(.epred)/sum(population)*100000` (equivalently `mean(count)/mean(population)*100000`) across the baseline years per draw. This is not a matter of matching the original -- it is a matter of using the correct epidemiological definition.

### Recommendation

Replace `median(ir)` in `IR_COMP_CATCH()` with `sum(.epred)/sum(population)*100000` for `baseline_ir`, and `sum(count)` for `baseline_count`. This aligns with CDC methodology, the paper's own description, and the fundamental definition of incidence rate.

---

## H2: Convergence Diagnostics

### The Claim

The pipeline does not programmatically check R-hat, effective sample size (ESS), or divergent transitions after model fitting. Model summary is printed to a file, but no automated thresholds are applied.

### The Evidence

**Current best practices (Stan/brms ecosystem, 2024-2025).** The Stan development team [recommends](https://mc-stan.org/learn-stan/diagnostics-warnings.html):

- R-hat < 1.01 for final inference (< 1.05 acceptable in early workflow)
- Bulk-ESS and Tail-ESS of at least 100 per chain (i.e., 400 total for 4 chains)
- Zero divergent transitions for fully reliable inference, though a small number with good R-hat/ESS may be acceptable for practical purposes

The brms package provides programmatic access to all of these via `rhat()`, `neff_ratio()`, and `nuts_params()` ([brms diagnostic quantities](https://paulbuerkner.com/brms/reference/diagnostic-quantities.html)).

**What the pipeline currently does.** The pipeline (trendy.R lines 589-593) saves `summary(proposed)` to a text file. The brms `summary()` output does include R-hat and ESS columns, and brms/Stan will print warnings to the console about divergent transitions. However, these are not captured, checked, or acted upon programmatically. A pipeline run could complete with terrible convergence and the user would only discover this by manually inspecting the summary file.

**Is visual/manual inspection sufficient?** For a one-off research analysis, manual inspection of summary output is common practice. However, this is a production pipeline designed to run across multiple pathogens and serotypes in an automated Nextflow workflow. The paper itself emphasizes reproducibility and transparency. In a production context, automated convergence checks are a best practice -- not because manual inspection is wrong, but because it is unreliable at scale. The WAMBS checklist ([van de Schoot](https://www.rensvandeschoot.com/tutorials/wambs-checklist-in-r-using-brms/)) explicitly recommends programmatic checks.

### The Verdict

**The fix is OBJECTIVELY CORRECT, but the severity depends on context.** For a production pipeline processing dozens of pathogen-serotype combinations, failing to programmatically check convergence is a genuine methodological gap, not just a style preference. Any published result from a non-converged model would be scientifically invalid.

### Recommendation

Add a post-fitting diagnostic step that:

1. Extracts R-hat values via `brms::rhat(model)` and flags any > 1.01 (warning) or > 1.05 (error).
2. Extracts bulk-ESS and tail-ESS and flags if below 400 total.
3. Extracts divergent transitions via `nuts_params(model)` and flags if > 0.
4. Writes a convergence diagnostics summary file alongside the model output.
5. Optionally halts or warns the pipeline if critical thresholds are breached.

This does not require changing the statistical methodology -- only adding quality control around it.

---

## H3: HDI on Response-Scale vs. Log-Scale

### The Claim

The pipeline computes HDI on the response scale (i.e., on the incidence rate or count directly). The arbiter states the original computes HDI on the log scale then exponentiates.

### The Evidence

**Transformation invariance.** This is a well-established property in Bayesian statistics: Equal-Tailed Intervals (ETI) are invariant under monotonic transformations. That is, if you compute a 95% ETI on the log scale and exponentiate the bounds, you get the same interval as computing the 95% ETI on the original scale. **HDI does NOT have this property.** Computing HDI on the log scale and exponentiating will generally NOT give the same interval as computing HDI on the response scale, unlike with equal-tailed intervals where the transformation property holds ([bayestestR documentation](https://easystats.github.io/bayestestR/reference/hdi.html), [Kruschke 2012](https://doingbayesiandataanalysis.blogspot.com/2012/04/why-to-use-highest-density-intervals.html)).

**Which is correct?** There is no single "correct" answer -- it depends on which scale you want the HDI property to hold. The HDI is defined as the narrowest interval containing 95% of the probability mass. If you compute HDI on the log scale, you are finding the narrowest interval on the log scale, which may not be the narrowest on the response scale after exponentiation.

**What the paper says.** Weller et al. (page 5) state: "the highest density interval and equal-tailed 95% CrI were calculated for each year for each site and the entire FoodNet catchment." The paper also states they used `add_linpred_draws` and "exponentiated them" before computing summary statistics. This implies computation on the response scale after back-transformation, consistent with the pipeline's current approach.

**Practical significance.** For moderately skewed posterior predictive distributions of incidence rates (which are what these models produce), the difference between HDI computed on the log scale vs. response scale is generally small. The posterior predictive distributions from a negative binomial model with many observations tend to be approximately symmetric on the log scale and right-skewed on the response scale. The HDI on the response scale will tend to be slightly shifted left (toward lower values) compared to the exponentiated log-scale HDI, but the difference is typically within the rounding precision already applied (6 decimal places).

### The Verdict

**This is NEITHER objectively correct NOR just "match the original."** Both approaches are defensible. Computing HDI on the response scale is arguably more interpretable (it is the narrowest interval in the units the reader cares about). Computing on the log scale then exponentiating is convenient but does not preserve the HDI property. The paper's own description is consistent with the pipeline's current approach (response-scale computation).

### Recommendation

The current pipeline approach (HDI on response scale) is defensible and consistent with the paper. If the goal is to match the original code exactly, verify what the original actually does. But there is no statistical reason to prefer log-scale HDI for reporting purposes. The more important issue is ensuring the ETI (which IS reported alongside HDI) is computed consistently, since ETI is transformation-invariant and the choice of scale does not matter for it. **No change needed unless matching the original is an explicit requirement.**

---

## H4: HDI Fallback Silently Mislabels

### The Claim

When the HDInterval package is not available, the pipeline falls back to computing equal-tailed intervals (quantile-based) but labels them as HDI.

### The Evidence

**Are HDI and ETI meaningfully different?** For symmetric (or near-symmetric) distributions, HDI and ETI are identical. For skewed distributions, they can differ substantially. The posterior predictive distribution of incidence rates from a negative binomial model is typically right-skewed on the response scale. For such distributions, the HDI will be shifted toward the mode (narrower, capturing the high-density region), while the ETI will be symmetric in tail probability (2.5% in each tail) ([Kruschke 2012](https://doingbayesiandataanalysis.blogspot.com/2012/04/why-to-use-highest-density-intervals.html)).

**How different in practice?** For catchment-level aggregated posterior draws (summed across 10 states with substantial total counts), the posterior will be much less skewed than for individual site-year combinations. At the catchment level, the difference between HDI and ETI is likely small (often less than 1-2% of the interval width). At the site level for low-incidence pathogens (e.g., Cyclospora in small states), the posterior can be highly skewed and the difference could be substantial.

**Is mislabeling objectively wrong?** Yes, unambiguously. Regardless of whether the numerical difference is large or small, labeling an equal-tailed interval as "HDI" is factually incorrect. It misrepresents the statistical method used. This is a scientific integrity issue, not just a cosmetic one. A reader or reviewer relying on the stated HDI property (narrowest interval containing 95% of the mass) would be misled.

### The Verdict

**The fix is OBJECTIVELY CORRECT.** Mislabeling a statistical quantity is always wrong. The fix should either: (a) make HDInterval a hard dependency so the fallback never triggers, or (b) label the fallback output correctly as "ETI" or "quantile-based CI" rather than "HDI."

### Recommendation

Make `HDInterval` a required package dependency (add it to the package loading in trendy.R alongside the other required packages). If a soft dependency is preferred, the fallback must label the output as `lower_eti` / `upper_eti` (not `lower_hdi` / `upper_hdi`) and emit a clear warning in the output files. The current `warning()` call is insufficient because it only prints to the console and does not change the column labels.

---

## H5: Cyclospora Dual Processing

### The Claim

`PATH_ANALYSIS()` processes ALL pathogens including Cyclospora (with parasitic census data), and then `CYCLOSPORA_ANALYSIS()` processes Cyclospora again separately. This results in Cyclospora appearing twice in the combined dataset.

### The Evidence

**What the code actually does.**

1. `PATH_ANALYSIS()` (functions.R lines 182-246) processes all pathogens in the data, including Cyclospora. It correctly identifies parasitic pathogens (line 193: `parasitic_pathogens <- c("CRYPTOSPORIDIUM", "CYCLOSPORA")`) and joins them with the Parasitic census data (lines 210-212). So Cyclospora is processed with the correct denominator in `PATH_ANALYSIS()`.

2. `CYCLOSPORA_ANALYSIS()` (functions.R lines 260-281) then processes Cyclospora again, also with Parasitic census data.

3. In trendy.R (lines 476-477), the results are combined: `bact <- gtools::smartbind(pathDf, cyloDF)`. Since `pathDf` already contains Cyclospora rows (from `PATH_ANALYSIS`), and `cyloDF` also contains Cyclospora rows (from `CYCLOSPORA_ANALYSIS`), Cyclospora is now duplicated in `bact`.

4. However, at line 493, `bact <- subset(bact, pathogen == opts$pathogen)` filters to only the requested pathogen. If `--pathogen CYCLOSPORA` is specified, it would get both copies. If another pathogen is specified, Cyclospora rows are dropped.

**Does downstream filtering prevent double-counting?** Partially. When `--pathogen` is specified (the Nextflow pipeline always specifies a single pathogen), `subset(bact, pathogen == opts$pathogen)` will select only that pathogen. But if the pathogen IS Cyclospora, both copies are selected. The `split(bact, bact$pathogen)` at line 541 would then produce a single "CYCLOSPORA" entry with doubled rows (duplicate year-site combinations). This would corrupt the model fitting because each observation would appear twice, artificially inflating sample size and narrowing uncertainty estimates.

**Is there a statistical reason for separate processing?** No. The `PATH_ANALYSIS()` function already handles the parasitic census join correctly. The `CYCLOSPORA_ANALYSIS()` function is redundant. It exists because the original pipeline architecture likely processed bacterial and parasitic pathogens in separate streams, but the refactored `PATH_ANALYSIS()` now handles both.

**What is the difference between bacterial and parasitic census data?** Not all FoodNet sites began transmitting parasitic illness data in the same year they began transmitting bacterial illness data. The "parasitic" census data reflects the population under surveillance for parasitic pathogens specifically, which may differ from the bacterial census for certain site-years. This distinction is real and important -- but `PATH_ANALYSIS()` already handles it correctly by splitting pathogens by type and joining each with the appropriate census denominator.

### The Verdict

**The concern is OBJECTIVELY VALID and the fix is correct.** The dual processing creates genuine duplicate rows that would corrupt model fitting for Cyclospora. This is not a theoretical concern -- it is a data integrity bug. Either:

- `PATH_ANALYSIS()` should exclude parasitic pathogens (as it apparently did in an earlier version), or
- `CYCLOSPORA_ANALYSIS()` should be removed and Cyclospora handled entirely by `PATH_ANALYSIS()`.

### Recommendation

The cleanest fix is to remove the `CYCLOSPORA_ANALYSIS()` call from trendy.R (lines 469-470) and the `smartbind(pathDf, cyloDF)` at line 476, since `PATH_ANALYSIS()` already correctly handles Cyclospora with parasitic census denominators. The same logic should be verified for `SALMONELLA_ANALYSIS()` (lines 472-473) -- if Salmonella is also present in `pathDf`, the same duplication bug would apply.

---

## H6: Colorado 2023 Catchment Expansion (COEX)

### The Claim

The pipeline unconditionally excludes COEX (Colorado Extended) site records in preprocess.R (line 328: `filter(siteid != "COEX")`). However, Colorado expanded to the full state in 2023, so COEX data from 2023 onward represents legitimate surveillance data that should be included.

### The Evidence

**What is COEX?** COEX refers to the "Colorado Extended" catchment -- the counties in Colorado that were NOT part of the original 7-county FoodNet surveillance area (Adams, Arapahoe, Boulder, Broomfield, Denver, Douglas, Jefferson). Before 2023, FoodNet only conducted active surveillance in these 7 counties. The remaining Colorado counties were tracked as "COEX" but were not part of the official catchment. Including COEX data before 2023 would be incorrect because those counties were not under active population-based surveillance.

**What happened in 2023.** According to the MMWR 2024 report ([mm7326a1](https://www.cdc.gov/mmwr/volumes/73/wr/mm7326a1.htm)) and the Weller et al. paper (page 3): "the catchment area remained constant but expanded again in 2023 to include the remainder of CO." The 2023 expansion brought all remaining Colorado counties into the FoodNet catchment, increasing the catchment population from approximately 50.1 million to approximately 53.6 million (16% of the US population).

**Is unconditional exclusion correct?** For data through 2022, excluding COEX is correct -- those counties were not under active population-based surveillance. For data from 2023 onward, excluding COEX means discarding legitimate surveillance data from the majority of Colorado's counties (approximately 2.7 million additional people). This would undercount Colorado's population and cases, biasing incidence rate estimates downward for Colorado and slightly for the overall catchment.

**Is the proposed fix (conditional exclusion by year) sound?** Yes. The fix should exclude COEX for years before 2023 and include it from 2023 onward. This is epidemiologically necessary to reflect the actual surveillance catchment in each year. The census population denominators should also reflect the expanded catchment from 2023 onward (which they presumably do if the census data is updated correctly).

**A subtlety: handling the discontinuity.** The expansion creates a structural break in the Colorado time series. Including COEX from 2023 changes both the numerator (more cases) and denominator (more population) for Colorado. The enhanced Bayesian spline model with site-year interactions (as described in the paper) should be able to accommodate this, but analysts should be aware that trend estimates spanning 2022-2023 for Colorado may reflect the catchment change rather than a true disease trend. This is analogous to how the model already handles FoodNet's 1996-2004 expansion.

### The Verdict

**The fix is OBJECTIVELY CORRECT.** Unconditionally excluding COEX is a data loss bug for 2023+ data. The conditional exclusion by year is the epidemiologically sound approach and aligns with how FoodNet itself handles the expansion in its official reporting.

### Recommendation

Change preprocess.R line 328 from:

```r
filter(siteid != "COEX")
```

to:

```r
filter(!(siteid == "COEX" & year < 2023))
```

This preserves the exclusion for pre-2023 data (when COEX counties were not under active surveillance) while including them from 2023 onward (when they became part of the official catchment). Ensure the census population files also include the expanded Colorado population for 2023+.

Additionally, this should be made configurable (perhaps via the catchment config mechanism already in the pipeline) rather than hardcoded, to accommodate future catchment changes without code modifications.

---

## Summary Table

| Finding | Verdict | Classification |
|---------|---------|----------------|
| H1: Baseline IR (median vs. weighted mean) | **Objectively incorrect** -- median(ir) is not a valid baseline computation | Must fix |
| H2: Convergence diagnostics | **Objectively needed** -- production pipelines require automated checks | Should fix |
| H3: HDI scale (response vs. log) | **Both defensible** -- current approach is consistent with the paper | No change needed |
| H4: HDI fallback mislabeling | **Objectively wrong** -- mislabeling a statistical method is always incorrect | Must fix |
| H5: Cyclospora dual processing | **Objectively a bug** -- creates duplicate rows corrupting model input | Must fix |
| H6: COEX unconditional exclusion | **Objectively incorrect** for 2023+ data -- discards legitimate surveillance data | Must fix |

---

## Sources

- [Healthy People 2030 Methods](https://odphp.health.gov/healthypeople/objectives-and-data/data-sources-and-methods/target-setting-methods)
- [Stan Convergence Diagnostics](https://mc-stan.org/learn-stan/diagnostics-warnings.html)
- [brms Diagnostic Quantities](https://paulbuerkner.com/brms/reference/diagnostic-quantities.html)
- [bayestestR HDI Documentation](https://easystats.github.io/bayestestR/reference/hdi.html)
- [Kruschke: Why HDI instead of ETI](https://doingbayesiandataanalysis.blogspot.com/2012/04/why-to-use-highest-density-intervals.html)
- [FoodNet 2023 Preliminary Data (MMWR)](https://www.cdc.gov/mmwr/volumes/73/wr/mm7326a1.htm)
- [WAMBS Checklist for brms](https://www.rensvandeschoot.com/tutorials/wambs-checklist-in-r-using-brms/)
- [Weller et al. 2026, Zoonoses 6:3](https://doi.org/10.15212/ZOONOSES-2025-0030)
