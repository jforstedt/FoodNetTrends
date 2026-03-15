#!/usr/bin/env Rscript
################################################################################
# generate_test_data.R - Create synthetic pipeline output for dashboard testing
#
# Usage:
#   Rscript dashboard/test/generate_test_data.R --output_dir test_output
#
# Creates a complete synthetic FoodNetTrends pipeline output directory with
# realistic data matching the exact column schemas produced by the pipeline.
################################################################################

suppressPackageStartupMessages(library("argparse"))

parser <- ArgumentParser(description = "Generate synthetic FoodNetTrends pipeline output for testing")
parser$add_argument("--output_dir", type = "character", default = "test_output",
                    help = "Output directory for synthetic data (default: test_output)")
args <- parser$parse_args()

set.seed(42)

output_dir <- args$output_dir

# Create directory structure
dir.create(file.path(output_dir, "preprocessed"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(output_dir, "spline_results"), recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(output_dir, "pipeline_info"), recursive = TRUE, showWarnings = FALSE)

cat("Creating synthetic test data in:", output_dir, "\n")

################################################################################
# Configuration
################################################################################

# FoodNet states with join years
state_config <- data.frame(
  state = c("CA", "CO", "CT", "GA", "MD", "MN", "NM", "NY", "OR", "TN"),
  start_year = c(1996, 2001, 1996, 1996, 1998, 1996, 2004, 1998, 1996, 2000),
  stringsAsFactors = FALSE
)

# Pathogens and their analysis units
# Each entry: pathogen, subgroup, typical_ir (per 100K), ir_trend_slope
analysis_units <- list(
  list(pathogen = "CAMPYLOBACTER", subgroup = "combined", base_ir = 17.0, slope = 0.15),
  list(pathogen = "SALMONELLA",    subgroup = "combined", base_ir = 16.0, slope = -0.05),
  list(pathogen = "SALMONELLA",    subgroup = "Enteritidis", base_ir = 4.5, slope = -0.10),
  list(pathogen = "STEC",          subgroup = "combined", base_ir = 3.0, slope = 0.08),
  list(pathogen = "STEC",          subgroup = "O157", base_ir = 1.2, slope = -0.03),
  list(pathogen = "SHIGELLA",      subgroup = "combined", base_ir = 4.5, slope = 0.02),
  list(pathogen = "VIBRIO",        subgroup = "combined", base_ir = 0.9, slope = 0.05),
  list(pathogen = "YERSINIA",      subgroup = "combined", base_ir = 0.6, slope = 0.04),
  list(pathogen = "CYCLOSPORA",    subgroup = "combined", base_ir = 0.4, slope = 0.06)
)

# Year range
years <- 1996:2023
n_years <- length(years)

# Typical state populations in FoodNet catchment (approximate, in thousands)
state_pops <- c(
  CA = 4800, CO = 4200, CT = 3500, GA = 7500, MD = 4800,
  MN = 4600, NM = 1500, NY = 6000, OR = 3200, TN = 5200
)

################################################################################
# Helper: Generate realistic population time series for a state
################################################################################
generate_population <- function(state, year) {
  base <- state_pops[state] * 1000  # Convert to actual population
  # ~1% annual growth with slight variation
  growth <- (year - 1996) * 0.008 + rnorm(1, 0, 0.002)
  round(base * (1 + growth))
}

################################################################################
# Helper: File prefix for an analysis unit
################################################################################
file_prefix <- function(pathogen, subgroup) {
  paste0(pathogen, "_", subgroup)
}

################################################################################
# Generate IRCatch.csv for one analysis unit
################################################################################
generate_ircatch <- function(unit) {
  prefix <- file_prefix(unit$pathogen, unit$subgroup)
  cat("  Generating", prefix, "IRCatch.csv\n")

  rows <- lapply(years, function(yr) {
    # Aggregate population across eligible states
    eligible <- state_config$state[state_config$start_year <= yr]
    pop <- sum(sapply(eligible, function(s) generate_population(s, yr)))

    # Trend: base IR with linear trend + noise + COVID dip
    year_offset <- yr - 2010
    ir_base <- unit$base_ir + unit$slope * year_offset
    covid_effect <- if (yr %in% 2020:2021) -0.15 * unit$base_ir else 0
    ir_true <- max(0.1, ir_base + covid_effect + rnorm(1, 0, unit$base_ir * 0.03))

    # Derive counts from IR
    raw_count <- round(ir_true * pop / 100000)
    raw_ir <- round(raw_count / (pop / 100000), 6)

    # Simulate posterior summary: median close to raw but smoothed
    est_count <- raw_count + rnorm(1, 0, sqrt(raw_count) * 0.3)
    est_count <- max(1, round(est_count, 6))
    est_ir <- round(est_count / (pop / 100000), 6)

    # Credible intervals (narrower for larger counts)
    ci_width_count <- sqrt(est_count) * 2.5
    ci_width_ir <- ci_width_count / (pop / 100000)

    data.frame(
      year = yr,
      population = pop,
      population_check = 0,
      raw_count = raw_count,
      raw_check = 0,
      raw_ir = raw_ir,
      median = round(est_count, 6),
      mean = round(est_count * 1.002, 6),
      lower_equitailed = round(max(0, est_count - ci_width_count * 1.02), 6),
      upper_equitailed = round(est_count + ci_width_count * 1.02, 6),
      lower_hdi = round(max(0, est_count - ci_width_count), 6),
      upper_hdi = round(est_count + ci_width_count, 6),
      median_ir = est_ir,
      mean_ir = round(est_ir * 1.002, 6),
      lower_equitailed_ir = round(max(0, est_ir - ci_width_ir * 1.02), 6),
      upper_equitailed_ir = round(est_ir + ci_width_ir * 1.02, 6),
      lower_hdi_ir = round(max(0, est_ir - ci_width_ir), 6),
      upper_hdi_ir = round(est_ir + ci_width_ir, 6),
      pathogen = unit$pathogen,
      travel = "All Cases",
      culture = "CxCIDT",
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

################################################################################
# Generate IRSite.csv for one analysis unit
################################################################################
generate_irsite <- function(unit) {
  prefix <- file_prefix(unit$pathogen, unit$subgroup)
  cat("  Generating", prefix, "IRSite.csv\n")

  rows <- list()
  idx <- 1
  for (i in seq_len(nrow(state_config))) {
    st <- state_config$state[i]
    start_yr <- state_config$start_year[i]
    eligible_years <- years[years >= start_yr]

    for (yr in eligible_years) {
      pop <- generate_population(st, yr)

      # State-specific variation around the base IR
      state_offset <- rnorm(1, 0, unit$base_ir * 0.15)
      year_offset <- yr - 2010
      ir_base <- unit$base_ir + unit$slope * year_offset + state_offset
      covid_effect <- if (yr %in% 2020:2021) -0.12 * unit$base_ir else 0
      ir_true <- max(0.05, ir_base + covid_effect + rnorm(1, 0, unit$base_ir * 0.05))

      raw_count <- max(0, round(ir_true * pop / 100000))
      raw_ir <- round(raw_count / (pop / 100000), 6)

      est_count <- max(0.1, raw_count + rnorm(1, 0, max(1, sqrt(raw_count)) * 0.4))
      est_count <- round(est_count, 6)
      est_ir <- round(est_count / (pop / 100000), 6)

      ci_width_count <- max(1, sqrt(abs(est_count))) * 3.0
      ci_width_ir <- ci_width_count / (pop / 100000)

      rows[[idx]] <- data.frame(
        year = yr,
        state = st,
        population = pop,
        population_check = 0,
        raw_count = raw_count,
        raw_check = 0,
        raw_ir = raw_ir,
        median = round(est_count, 6),
        mean = round(est_count * 1.003, 6),
        lower_equitailed = round(max(0, est_count - ci_width_count * 1.02), 6),
        upper_equitailed = round(est_count + ci_width_count * 1.02, 6),
        lower_hdi = round(max(0, est_count - ci_width_count), 6),
        upper_hdi = round(est_count + ci_width_count, 6),
        median_ir = est_ir,
        mean_ir = round(est_ir * 1.003, 6),
        lower_equitailed_ir = round(max(0, est_ir - ci_width_ir * 1.02), 6),
        upper_equitailed_ir = round(est_ir + ci_width_ir * 1.02, 6),
        lower_hdi_ir = round(max(0, est_ir - ci_width_ir), 6),
        upper_hdi_ir = round(est_ir + ci_width_ir, 6),
        pathogen = unit$pathogen,
        travel = "All Cases",
        culture = "CxCIDT",
        stringsAsFactors = FALSE
      )
      idx <- idx + 1
    }
  }
  do.call(rbind, rows)
}

################################################################################
# Generate EstIRRCatch.csv for one analysis unit
################################################################################
generate_estirrcatch <- function(unit, ircatch) {
  prefix <- file_prefix(unit$pathogen, unit$subgroup)
  cat("  Generating", prefix, "EstIRRCatch_2016_2018.csv\n")

  # The baseline is the average IR from 2016-2018
  baseline_rows <- ircatch[ircatch$year >= 2016 & ircatch$year <= 2018, ]
  baseline_ir <- mean(baseline_rows$median_ir)

  rows <- lapply(seq_len(nrow(ircatch)), function(i) {
    row <- ircatch[i, ]
    rr_est <- row$median_ir / baseline_ir
    # Add uncertainty
    rr_noise <- rnorm(1, 0, 0.03)
    rr_est_final <- round(rr_est + rr_noise, 6)
    rr_width <- 0.08 + abs(row$year - 2017) * 0.005

    # Make some years significant (HDI not spanning 1.0)
    # Early years and 2020-2021 tend to be significantly different
    if (row$year <= 2000 || row$year %in% 2020:2021) {
      # Force significance by keeping interval away from 1.0
      if (rr_est_final < 1.0) {
        rr_lower <- round(rr_est_final - rr_width * 0.6, 6)
        rr_upper <- round(min(0.98, rr_est_final + rr_width * 0.6), 6)
      } else {
        rr_lower <- round(max(1.02, rr_est_final - rr_width * 0.6), 6)
        rr_upper <- round(rr_est_final + rr_width * 0.6, 6)
      }
    } else if (row$year >= 2016 & row$year <= 2018) {
      # Baseline period: close to 1.0
      rr_est_final <- round(1.0 + rnorm(1, 0, 0.01), 6)
      rr_lower <- round(rr_est_final - rr_width * 0.5, 6)
      rr_upper <- round(rr_est_final + rr_width * 0.5, 6)
    } else {
      # Most other years: interval spans 1.0 (not significant)
      rr_lower <- round(rr_est_final - rr_width, 6)
      rr_upper <- round(rr_est_final + rr_width, 6)
    }

    pct_est <- round((rr_est_final - 1) * 100, 6)
    pct_lower <- round((rr_lower - 1) * 100, 6)
    pct_upper <- round((rr_upper - 1) * 100, 6)

    data.frame(
      year = row$year,
      population = row$population,
      population_check = row$population_check,
      raw_count = row$raw_count,
      raw_check = row$raw_check,
      raw_ir = row$raw_ir,
      median = row$median,
      mean = row$mean,
      lower_equitailed = row$lower_equitailed,
      upper_equitailed = row$upper_equitailed,
      lower_hdi = row$lower_hdi,
      upper_hdi = row$upper_hdi,
      median_ir = row$median_ir,
      mean_ir = row$mean_ir,
      lower_equitailed_ir = row$lower_equitailed_ir,
      upper_equitailed_ir = row$upper_equitailed_ir,
      lower_hdi_ir = row$lower_hdi_ir,
      upper_hdi_ir = row$upper_hdi_ir,
      relative_risk_lower_hdi = rr_lower,
      relative_risk_upper_hdi = rr_upper,
      relative_risk_est = rr_est_final,
      percent_change_lower_hdi = pct_lower,
      percent_change_upper_hdi = pct_upper,
      percent_change_est = pct_est,
      comparison_period = "2016-2018",
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

################################################################################
# Generate summary.txt (fake brms model summary)
################################################################################
generate_summary <- function(unit) {
  prefix <- file_prefix(unit$pathogen, unit$subgroup)
  cat("  Generating", prefix, "summary.txt\n")

  # Generate realistic parameter names for a spline model with 10 states
  states <- state_config$state
  param_lines <- c()

  # Intercept
  param_lines <- c(param_lines, sprintf(
    "%-35s %10.2f %10.2f %10.2f %10.2f %8.2f %8d %8d",
    "Intercept", -8.52, 0.14, -8.79, -8.25, 1.00,
    round(runif(1, 1200, 1800)), round(runif(1, 900, 1400))
  ))

  # State effects
  for (st in states[-1]) {  # First state is reference
    est <- rnorm(1, 0, 0.5)
    se <- abs(rnorm(1, 0.1, 0.02))
    param_lines <- c(param_lines, sprintf(
      "%-35s %10.2f %10.2f %10.2f %10.2f %8.2f %8d %8d",
      paste0("state", st), est, se, est - 1.96 * se, est + 1.96 * se,
      round(runif(1, 0.99, 1.01), 2),
      round(runif(1, 1000, 2000)), round(runif(1, 800, 1500))
    ))
  }

  # Spline parameters
  for (st in states) {
    for (k in 1:9) {
      est <- rnorm(1, 0, 2)
      se <- abs(rnorm(1, 0.5, 0.1))
      param_lines <- c(param_lines, sprintf(
        "%-35s %10.2f %10.2f %10.2f %10.2f %8.2f %8d %8d",
        paste0("s(year,by=state", st, ")_", k), est, se,
        est - 1.96 * se, est + 1.96 * se,
        round(runif(1, 0.99, 1.01), 2),
        round(runif(1, 1000, 2000)), round(runif(1, 800, 1500))
      ))
    }
  }

  # Shape parameter
  param_lines <- c(param_lines, sprintf(
    "%-35s %10.2f %10.2f %10.2f %10.2f %8.2f %8d %8d",
    "shape", 2.34, 0.08, 2.19, 2.50, 1.00,
    round(runif(1, 1500, 2000)), round(runif(1, 1100, 1600))
  ))

  summary_text <- paste0(c(
    " Family: negbinomial ",
    "  Links: mu = log; shape = identity ",
    "Formula: count ~ s(year, by = state) + state + offset(log(population)) ",
    "   Data: data (Number of observations: 260) ",
    paste0("  Draws: 2 chains, each with iter = 500; warmup = 250; thin = 1;"),
    "         total post-warmup draws = 500",
    "",
    "Smoothing Spline Coefficients:",
    sprintf("%-35s %10s %10s %10s %10s %8s %8s %8s",
            "", "Estimate", "Est.Error", "l-95% CI", "u-95% CI", "Rhat", "Bulk_ESS", "Tail_ESS"),
    param_lines,
    "",
    "Further Distributional Parameters:",
    sprintf("%-35s %10s %10s %10s %10s %8s %8s %8s",
            "", "Estimate", "Est.Error", "l-95% CI", "u-95% CI", "Rhat", "Bulk_ESS", "Tail_ESS"),
    sprintf("%-35s %10.2f %10.2f %10.2f %10.2f %8.2f %8d %8d",
            "shape", 2.34, 0.08, 2.19, 2.50, 1.00, 1650, 1230),
    "",
    "Draws were sampled using sampling(NUTS). For each parameter, Bulk_ESS",
    "and Tail_ESS are effective sample size measures, and Rhat is the potential",
    "scale reduction factor on split chains (at convergence, Rhat = 1)."
  ), collapse = "\n")

  summary_text
}

################################################################################
# Generate minimal valid PNG using base R
################################################################################
generate_png <- function(filepath, width_in, height_in, title_text) {
  png(filepath, width = width_in, height = height_in, units = "in", res = 72)
  par(mar = c(4, 4, 3, 1))
  # Simple placeholder plot
  x <- 1996:2023
  y <- cumsum(rnorm(length(x), 0, 1)) + 10
  plot(x, y, type = "l", lwd = 2, col = "steelblue",
       main = title_text, xlab = "Year",
       ylab = "Incidence per 100,000", cex.main = 0.9)
  polygon(c(x, rev(x)), c(y + 1.5, rev(y - 1.5)),
          col = rgb(0.27, 0.51, 0.71, 0.2), border = NA)
  dev.off()
}

################################################################################
# Generate clean_mmwr.csv (~2000 rows)
################################################################################
generate_clean_mmwr <- function() {
  cat("  Generating clean_mmwr.csv\n")

  pathogens <- c("CAMPYLOBACTER", "SALMONELLA", "STEC", "SHIGELLA",
                 "VIBRIO", "YERSINIA", "CYCLOSPORA")
  pathogen_weights <- c(0.30, 0.28, 0.10, 0.10, 0.05, 0.05, 0.02)
  # Normalize (LISTERIA excluded from test for simplicity)
  pathogen_weights <- pathogen_weights / sum(pathogen_weights)

  n_rows <- 2000
  pathogen_col <- sample(pathogens, n_rows, replace = TRUE, prob = pathogen_weights)

  # Assign years with slight upward trend in recent years
  year_weights <- 1 + (years - 1996) * 0.01
  year_col <- sample(years, n_rows, replace = TRUE, prob = year_weights / sum(year_weights))

  # Assign states respecting join years
  state_col <- character(n_rows)
  for (i in seq_len(n_rows)) {
    eligible <- state_config$state[state_config$start_year <= year_col[i]]
    state_col[i] <- sample(eligible, 1)
  }

  # County placeholder
  county_col <- paste0("COUNTY_", sample(1:50, n_rows, replace = TRUE))

  # CIDT categories
  cxcidt_col <- sample(c("CX+", "CIDT+", "PARASITIC"), n_rows, replace = TRUE,
                       prob = c(0.45, 0.45, 0.10))
  # Fix: parasitic pathogens should have PARASITIC cxcidt
  parasitic_mask <- pathogen_col %in% c("CYCLOSPORA", "CRYPTOSPORIDIUM")
  cxcidt_col[parasitic_mask] <- "PARASITIC"

  # Travel
  travelint_col <- sample(c("NO", "UNKNOWN", "YES"), n_rows, replace = TRUE,
                          prob = c(0.70, 0.20, 0.10))

  # Serotype (mostly for Salmonella)
  serotype_col <- rep(NA_character_, n_rows)
  sal_mask <- pathogen_col == "SALMONELLA"
  serotypes <- c("Enteritidis", "Typhimurium", "Newport", "I 4,[5],12:i:-",
                 "Javiana", "Infantis", "Missing", "Heidelberg", "Thompson")
  serotype_col[sal_mask] <- sample(serotypes, sum(sal_mask), replace = TRUE,
                                   prob = c(0.20, 0.15, 0.12, 0.10, 0.08, 0.05, 0.15, 0.08, 0.07))

  # Pathogentype
  pathogentype_col <- ifelse(pathogen_col %in% c("CYCLOSPORA", "CRYPTOSPORIDIUM"),
                             "Parasitic", "Bacterial")

  # STEC class
  stec_class_col <- rep(NA_character_, n_rows)
  stec_mask <- pathogen_col == "STEC"
  stec_class_col[stec_mask] <- sample(c("STEC O157", "STEC NONO157", "STEC O AG UNDET"),
                                      sum(stec_mask), replace = TRUE,
                                      prob = c(0.35, 0.55, 0.10))

  data.frame(
    pathogen = pathogen_col,
    year = year_col,
    state = state_col,
    county = county_col,
    cxcidt = cxcidt_col,
    travelint = travelint_col,
    serotypesummary = serotype_col,
    pathogentype = pathogentype_col,
    stec_class = stec_class_col,
    stringsAsFactors = FALSE
  )
}

################################################################################
# Generate preprocessing report
################################################################################
generate_preprocessing_report <- function() {
  cat("  Generating preprocessing_report.csv\n")

  pathogens <- c("CAMPYLOBACTER", "SALMONELLA", "STEC", "SHIGELLA",
                 "VIBRIO", "YERSINIA", "CYCLOSPORA", "LISTERIA", "CRYPTOSPORIDIUM")
  data.frame(
    original = c(pathogens, "CAMPY", "SAL", "E. COLI O157:H7"),
    standardized = c(pathogens, "CAMPYLOBACTER", "SALMONELLA", "STEC"),
    match_type = c(rep("exact", length(pathogens)), "prefix", "prefix", "exact"),
    confidence = c(rep(100, length(pathogens)), 90, 90, 100),
    count = c(8500, 7200, 2100, 2000, 900, 800, 500, 350, 450, 120, 80, 50),
    stringsAsFactors = FALSE
  )
}

################################################################################
# Generate resource_profile.csv
################################################################################
generate_resource_profile <- function() {
  cat("  Generating resource_profile.csv\n")

  pathogens <- c("CAMPYLOBACTER", "SALMONELLA", "STEC", "SHIGELLA",
                 "VIBRIO", "YERSINIA", "CYCLOSPORA", "LISTERIA")
  rows_vec <- c(8500, 7200, 2100, 2000, 900, 800, 500, 350)
  sites_vec <- c(10, 10, 10, 10, 10, 10, 10, 10)
  years_vec <- c(28, 28, 28, 28, 28, 28, 28, 28)

  data.frame(
    pathogen = pathogens,
    rows = rows_vec,
    sites = sites_vec,
    years = years_vec,
    complexity = rows_vec * sites_vec * years_vec,
    size_category = ifelse(rows_vec > 5000, "medium",
                    ifelse(rows_vec > 1000, "small", "tiny")),
    stringsAsFactors = FALSE
  )
}

################################################################################
# Generate metadata CSVs
################################################################################
generate_metadata_states <- function() {
  cat("  Generating metadata_states.csv\n")
  data.frame(
    state = state_config$state,
    first_year = state_config$start_year,
    last_year = rep(2023, nrow(state_config)),
    total_cases = c(4200, 3100, 2800, 5800, 3600, 3900, 1100, 4500, 2600, 3800),
    n_pathogens = rep(8, nrow(state_config)),
    stringsAsFactors = FALSE
  )
}

generate_metadata_cidt <- function() {
  cat("  Generating metadata_cidt.csv\n")
  data.frame(
    cxcidt = c("CX+", "CIDT+", "PARASITIC"),
    count = c(12000, 10500, 950),
    first_year = c(1996, 2006, 1996),
    last_year = c(2023, 2023, 2023),
    percentage = c(51.2, 44.8, 4.0),
    stringsAsFactors = FALSE
  )
}

generate_metadata_travel <- function() {
  cat("  Generating metadata_travel.csv\n")
  data.frame(
    travelint = c("NO", "UNKNOWN", "YES"),
    count = c(16400, 4700, 2350),
    percentage = c(69.9, 20.0, 10.0),
    stringsAsFactors = FALSE
  )
}

################################################################################
# Generate error file for VIBRIO
################################################################################
generate_error_file <- function() {
  cat("  Generating VIBRIO_combined_error.txt\n")
  paste0(c(
    "Error processing VIBRIO at 2024-01-15 14:28:33",
    "Error message: Model did not converge. May need to run a simpler version, use more iterations, or more robust adapt_delta/max_treedepth values.",
    "Traceback:",
    "7: stop(\"Model did not converge. May need to run a simpler version, use more iterations, or more robust adapt_delta/max_treedepth values.\")",
    "6: tryCatch(brm(count ~ s(year, by = state) + state + offset(log(population)), ",
    "     data = data, family = negbinomial(), chains = chains, iter = iterations, ",
    "     cores = cores, seed = seed, control = list(adapt_delta = adapt_delta, ",
    "     max_treedepth = max_treedepth), backend = \"rstan\"), error = function(e) {",
    "     stop(\"Model did not converge. May need to run a simpler version, use more iterations, or more robust adapt_delta/max_treedepth values.\")",
    "   })",
    "5: PROPOSED_BM(current_data, cores = modelcores, chains = chains, ",
    "     iterations = iterations, adapt_delta = adapt_delta, max_treedepth = max_treedepth, ",
    "     seed = seed)",
    "4: eval(expr, p)",
    "3: eval(expr, p)",
    "2: eval(ei, envir)",
    "1: eval(ei, envir)",
    "",
    "Additional diagnostic information:",
    "  Number of divergent transitions: 127 / 500",
    "  Maximum treedepth exceeded: 89 times",
    "  Low Bulk_ESS for parameters: Intercept (ESS=42), shape (ESS=38)",
    "  Rhat warnings: 3 parameters had Rhat > 1.05"
  ), collapse = "\n")
}

################################################################################
# Generate pipeline_info files
################################################################################
generate_pipeline_info <- function() {
  cat("  Generating pipeline_info files\n")

  timestamp <- "2024-01-15_14-30-22"

  # Execution report HTML
  report_html <- paste0('<!DOCTYPE html>\n<html>\n<head>\n',
    '<title>Nextflow Execution Report</title>\n',
    '<meta charset="utf-8">\n</head>\n<body>\n',
    '<h1>Nextflow Execution Report</h1>\n',
    '<p>Pipeline: FoodNetTrends</p>\n',
    '<p>Start: 2024-01-15 14:00:00</p>\n',
    '<p>End: 2024-01-15 14:30:22</p>\n',
    '<p>Duration: 30m 22s</p>\n',
    '<table><tr><th>Process</th><th>Status</th></tr>\n',
    '<tr><td>PREPROCESS</td><td>COMPLETED</td></tr>\n',
    '<tr><td>RESOURCE_PROFILER</td><td>COMPLETED</td></tr>\n',
    '<tr><td>TRENDY (CAMPYLOBACTER)</td><td>COMPLETED</td></tr>\n',
    '<tr><td>TRENDY (SALMONELLA)</td><td>COMPLETED</td></tr>\n',
    '<tr><td>TRENDY (STEC)</td><td>COMPLETED</td></tr>\n',
    '<tr><td>TRENDY (VIBRIO)</td><td>FAILED</td></tr>\n',
    '</table>\n</body>\n</html>')
  writeLines(report_html, file.path(output_dir, "pipeline_info",
             paste0("execution_report_", timestamp, ".html")))

  # Timeline HTML
  timeline_html <- paste0('<!DOCTYPE html>\n<html>\n<head>\n',
    '<title>Nextflow Execution Timeline</title>\n',
    '<meta charset="utf-8">\n</head>\n<body>\n',
    '<h1>Execution Timeline</h1>\n',
    '<p>Placeholder timeline visualization</p>\n',
    '</body>\n</html>')
  writeLines(timeline_html, file.path(output_dir, "pipeline_info",
             paste0("execution_timeline_", timestamp, ".html")))

  # DAG HTML
  dag_html <- paste0('<!DOCTYPE html>\n<html>\n<head>\n',
    '<title>Nextflow Pipeline DAG</title>\n',
    '<meta charset="utf-8">\n</head>\n<body>\n',
    '<h1>Pipeline DAG</h1>\n',
    '<p>Placeholder DAG visualization</p>\n',
    '</body>\n</html>')
  writeLines(dag_html, file.path(output_dir, "pipeline_info",
             paste0("pipeline_dag_", timestamp, ".html")))

  # Execution trace TSV
  trace_header <- paste(c("task_id", "hash", "native_id", "name", "status",
                          "exit", "submit", "duration", "realtime", "%cpu",
                          "peak_rss", "peak_vmem", "rchar", "wchar"),
                        collapse = "\t")

  trace_rows <- c(
    paste(c("1", "ab/123456", "12345", "PREPROCESS", "COMPLETED", "0",
            "2024-01-15 14:00:05", "2m 15s", "2m 10s", "95.2%",
            "1.2 GB", "2.5 GB", "500 MB", "120 MB"), collapse = "\t"),
    paste(c("2", "cd/789012", "12346", "RESOURCE_PROFILER", "COMPLETED", "0",
            "2024-01-15 14:02:20", "30s", "25s", "45.1%",
            "256 MB", "512 MB", "120 MB", "1 MB"), collapse = "\t"),
    paste(c("3", "ef/345678", "12347", "TRENDY (CAMPYLOBACTER_combined)", "COMPLETED", "0",
            "2024-01-15 14:02:50", "8m 30s", "8m 20s", "780.5%",
            "24.1 GB", "48.2 GB", "2.1 GB", "450 MB"), collapse = "\t"),
    paste(c("4", "gh/901234", "12348", "TRENDY (SALMONELLA_combined)", "COMPLETED", "0",
            "2024-01-15 14:02:55", "9m 15s", "9m 5s", "750.3%",
            "23.8 GB", "47.6 GB", "2.0 GB", "430 MB"), collapse = "\t"),
    paste(c("5", "ij/567890", "12349", "TRENDY (SALMONELLA_Enteritidis)", "COMPLETED", "0",
            "2024-01-15 14:03:00", "7m 45s", "7m 35s", "720.1%",
            "22.5 GB", "45.0 GB", "1.8 GB", "380 MB"), collapse = "\t"),
    paste(c("6", "kl/123789", "12350", "TRENDY (STEC_combined)", "COMPLETED", "0",
            "2024-01-15 14:03:05", "6m 20s", "6m 10s", "690.8%",
            "21.2 GB", "42.4 GB", "1.5 GB", "320 MB"), collapse = "\t"),
    paste(c("7", "mn/456012", "12351", "TRENDY (STEC_O157)", "COMPLETED", "0",
            "2024-01-15 14:03:10", "5m 50s", "5m 40s", "680.2%",
            "20.8 GB", "41.6 GB", "1.4 GB", "300 MB"), collapse = "\t"),
    paste(c("8", "op/789345", "12352", "TRENDY (SHIGELLA_combined)", "COMPLETED", "0",
            "2024-01-15 14:03:15", "6m 10s", "6m 0s", "700.5%",
            "21.0 GB", "42.0 GB", "1.5 GB", "310 MB"), collapse = "\t"),
    paste(c("9", "qr/012678", "12353", "TRENDY (VIBRIO_combined)", "FAILED", "1",
            "2024-01-15 14:03:20", "4m 30s", "4m 20s", "650.1%",
            "19.5 GB", "39.0 GB", "1.2 GB", "50 MB"), collapse = "\t"),
    paste(c("10", "st/345901", "12354", "TRENDY (YERSINIA_combined)", "COMPLETED", "0",
            "2024-01-15 14:03:25", "5m 30s", "5m 20s", "670.3%",
            "20.2 GB", "40.4 GB", "1.3 GB", "280 MB"), collapse = "\t"),
    paste(c("11", "uv/678234", "12355", "TRENDY (CYCLOSPORA_combined)", "COMPLETED", "0",
            "2024-01-15 14:03:30", "4m 50s", "4m 40s", "660.7%",
            "19.8 GB", "39.6 GB", "1.2 GB", "260 MB"), collapse = "\t")
  )

  writeLines(c(trace_header, trace_rows),
             file.path(output_dir, "pipeline_info",
                       paste0("execution_trace_", timestamp, ".txt")))
}

################################################################################
# Main execution
################################################################################

cat("\n=== Generating preprocessed files ===\n")

# clean_mmwr.csv
clean_mmwr <- generate_clean_mmwr()
write.csv(clean_mmwr, file.path(output_dir, "preprocessed", "clean_mmwr.csv"),
          row.names = FALSE)

# Preprocessing report
preproc_report <- generate_preprocessing_report()
write.csv(preproc_report, file.path(output_dir, "preprocessed",
          "clean_mmwr_preprocessing_report.csv"), row.names = FALSE)

# Resource profile
resource_profile <- generate_resource_profile()
write.csv(resource_profile, file.path(output_dir, "preprocessed",
          "resource_profile.csv"), row.names = FALSE)

# Metadata files
metadata_states <- generate_metadata_states()
write.csv(metadata_states, file.path(output_dir, "preprocessed",
          "metadata_states.csv"), row.names = FALSE)

metadata_cidt <- generate_metadata_cidt()
write.csv(metadata_cidt, file.path(output_dir, "preprocessed",
          "metadata_cidt.csv"), row.names = FALSE)

metadata_travel <- generate_metadata_travel()
write.csv(metadata_travel, file.path(output_dir, "preprocessed",
          "metadata_travel.csv"), row.names = FALSE)

cat("\n=== Generating spline results ===\n")

# Generate results for each analysis unit (except VIBRIO which "fails")
for (unit in analysis_units) {
  prefix <- file_prefix(unit$pathogen, unit$subgroup)

  if (unit$pathogen == "VIBRIO") {
    # VIBRIO "fails" - only write error file
    error_content <- generate_error_file()
    writeLines(error_content, file.path(output_dir, "spline_results",
               paste0(prefix, "_error.txt")))
    next
  }

  # IRCatch
  ircatch <- generate_ircatch(unit)
  write.csv(ircatch, file.path(output_dir, "spline_results",
            paste0(prefix, "_IRCatch.csv")), row.names = FALSE)

  # IRSite
  irsite <- generate_irsite(unit)
  write.csv(irsite, file.path(output_dir, "spline_results",
            paste0(prefix, "_IRSite.csv")), row.names = FALSE)

  # EstIRRCatch
  estirr <- generate_estirrcatch(unit, ircatch)
  write.csv(estirr, file.path(output_dir, "spline_results",
            paste0(prefix, "_EstIRRCatch_2016_2018.csv")), row.names = FALSE)

  # summary.txt
  summary_txt <- generate_summary(unit)
  writeLines(summary_txt, file.path(output_dir, "spline_results",
             paste0(prefix, "_summary.txt")))

  # PNG plots
  generate_png(
    file.path(output_dir, "spline_results", paste0(prefix, "_overall_trend.png")),
    10, 6,
    paste("Overall Trend for", unit$pathogen, unit$subgroup)
  )

  generate_png(
    file.path(output_dir, "spline_results", paste0(prefix, "_site_trends.png")),
    10, 8,
    paste("Site Trends for", unit$pathogen, unit$subgroup)
  )
}

cat("\n=== Generating pipeline info ===\n")
generate_pipeline_info()

cat("\n=== Test data generation complete ===\n")
cat("Output directory:", output_dir, "\n")

# Print summary of generated files
all_files <- list.files(output_dir, recursive = TRUE)
cat("\nGenerated", length(all_files), "files:\n")
for (f in all_files) {
  fpath <- file.path(output_dir, f)
  size <- file.info(fpath)$size
  size_str <- if (size > 1024 * 1024) {
    sprintf("%.1f MB", size / 1024 / 1024)
  } else if (size > 1024) {
    sprintf("%.1f KB", size / 1024)
  } else {
    sprintf("%d B", size)
  }
  cat(sprintf("  %-60s %s\n", f, size_str))
}
