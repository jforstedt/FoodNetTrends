#!/usr/bin/env Rscript
# functions.R - Statistical modeling and analysis functions for FoodNetTrends
# Sourced by trendy.R. Expects lowercase column names from preprocess.R.
suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(gtools)
  library(brms)
  library(ggplot2)
  library(tidybayes)
  library(haven)
  library(tibble)
  library(readr)
  library(gridExtra)
})

# HDInterval is required -- the fallback of labeling ETI as HDI is incorrect
if (!requireNamespace("HDInterval", quietly = TRUE)) {
  stop("Required package 'HDInterval' is not installed. ",
       "Install with: install.packages('HDInterval')")
}
suppressPackageStartupMessages(library(HDInterval))

# Compute HDI on log scale and back-transform (matches published methodology).
# Positive draws only; warns if >5% of draws are zero.
log_hdi <- function(x, credMass = 0.95) {
  n_total <- length(x)
  x_pos <- x[x > 0]
  if (length(x_pos) < n_total * 0.95) {
    warning("log_hdi: >5% of draws are zero or negative (",
            n_total - length(x_pos), "/", n_total, ")")
  }
  if (length(x_pos) < 2) return(c(NA_real_, NA_real_))
  exp(hdi(log(x_pos), credMass = credMass))
}

# Return default FoodNet catchment start years or read from CSV
read_catchment_config <- function(config_path = NULL) {
  if (is.null(config_path)) {
    return(data.frame(
      state = c("CA", "CO", "CT", "GA", "MD", "MN", "NM", "NY", "OR", "TN"),
      start_year = c(1996, 2001, 1996, 1996, 1998, 1996, 2004, 1998, 1996, 2000),
      end_year = rep(9999, 10),  # 9999 = ongoing participation
      pathogen_type = rep("both", 10),
      stringsAsFactors = FALSE
    ))
  }
  config <- read.csv(config_path, stringsAsFactors = FALSE)
  validate_catchment_config(config)
  return(config)
}

# Year all catchment sites were active (latest join year)
get_catchment_stable_year <- function(catchment_config = NULL) {
  if (is.null(catchment_config)) catchment_config <- read_catchment_config()
  max(catchment_config$start_year, na.rm = TRUE)
}

# Validate catchment config structure and values
validate_catchment_config <- function(config) {
  required_cols <- c("state", "start_year", "end_year")
  missing_cols <- setdiff(required_cols, names(config))
  if (length(missing_cols) > 0) {
    stop("Missing required columns in catchment config: ", paste(missing_cols, collapse = ", "))
  }

  if (!is.numeric(config$start_year) || !is.numeric(config$end_year)) {
    stop("start_year and end_year must be numeric")
  }

  invalid_years <- config$start_year > config$end_year
  if (any(invalid_years)) {
    stop("start_year must be less than or equal to end_year for all entries")
  }

  if (!"pathogen_type" %in% names(config)) {
    config$pathogen_type <- "both"
  }

  return(config)
}

# Filter data to state-years within the catchment surveillance window
apply_catchment_filter <- function(data, catchment_config, pathogen_type = "both") {
  if (pathogen_type != "both" && "pathogen_type" %in% names(catchment_config)) {
    relevant_config <- catchment_config[
      catchment_config$pathogen_type %in% c("both", pathogen_type),
    ]
  } else {
    relevant_config <- catchment_config
  }

  valid_rows <- rep(FALSE, nrow(data))

  for (i in seq_len(nrow(relevant_config))) {
    state_match <- data$state == relevant_config$state[i]
    year_match <- data$year >= relevant_config$start_year[i] &
                  data$year <= relevant_config$end_year[i]
    valid_rows <- valid_rows | (state_match & year_match)
  }

  return(data[valid_rows, ])
}

# Parse comma-separated CLI strings into character vectors
CLEAN_LIST <- function(input_string) {
  if (length(input_string) > 1) {
    input_string <- paste(input_string, collapse = ",")
  }
  cleanedString <- gsub('[\\[\\]\"]', '', input_string)
  strsplit(cleanedString, ",")[[1]]
}

# Write data to CSV (append if exists) or RDS, creating directories as needed
SAFE_WRITE <- function(data, file_path) {
  tryCatch({
    dir_path <- dirname(file_path)
    if (!dir.exists(dir_path)) {
      dir.create(dir_path, recursive = TRUE, showWarnings = FALSE)
    }

    if (endsWith(file_path, ".csv")) {
      if (file.exists(file_path)) {
        write.table(data, file = file_path, append = TRUE, quote = TRUE, sep = ",",
                    col.names = FALSE, row.names = FALSE)
      } else {
        write.table(data, file = file_path, append = FALSE, quote = TRUE, sep = ",",
                    col.names = TRUE, row.names = FALSE)
      }
    } else if (endsWith(file_path, ".Rds")) {
      saveRDS(data, file = file_path)
    }
  }, error = function(e) {
    message("Error writing file: ", e$message)
  })
}

# Aggregate case counts by year/state/pathogen and join census denominators
PATH_ANALYSIS <- function(mmwrdata, census, catchment_config = NULL) {
  all_pathogens <- unique(mmwrdata$pathogen)

  if (length(all_pathogens) == 0) {
    stop("No pathogens found in the MMWR data")
  }

  parasitic_pathogens <- c("CRYPTOSPORIDIUM", "CYCLOSPORA")

  selectDf <- mmwrdata %>%
    filter(pathogen %in% all_pathogens) %>%
    group_by(year, state, pathogen) %>%
    summarise(count = n(), .groups = "drop") %>%
    # complete() fills zero counts — FoodNet is active surveillance
    complete(year, state, pathogen = unique(pathogen), fill = list(count = 0))

  # Join bacterial and parasitic with their respective census denominators
  bacterial_data <- selectDf %>%
    filter(!pathogen %in% parasitic_pathogens) %>%
    left_join(census %>% filter(pathogentype == "Bacterial"), by = c("year", "state"))

  parasitic_data <- selectDf %>%
    filter(pathogen %in% parasitic_pathogens) %>%
    left_join(census %>% filter(pathogentype == "Parasitic"), by = c("year", "state"))

  selectDf <- bind_rows(bacterial_data, parasitic_data) %>%
    mutate(year = as.numeric(as.character(year)))

  if (all(is.na(selectDf$population))) {
    stop("No population data found after joining with census data. Check that census data contains 'Bacterial' pathogentype.")
  }

  rows_before <- nrow(selectDf)
  selectDf <- selectDf %>% filter(!is.na(population))
  rows_after <- nrow(selectDf)

  if (rows_before > rows_after) {
    warning(paste("Removed", rows_before - rows_after, "rows with missing population data"))
  }

  if (nrow(selectDf) == 0) {
    stop("No data remaining after removing rows with missing population")
  }

  # Drop state-years before the state entered the FoodNet catchment
  if (is.null(catchment_config)) {
    catchment_config <- read_catchment_config()
  }

  bacterial_subset <- selectDf %>% filter(!pathogen %in% parasitic_pathogens)
  parasitic_subset <- selectDf %>% filter(pathogen %in% parasitic_pathogens)
  bacterial_subset <- apply_catchment_filter(bacterial_subset, catchment_config, "bacterial")
  parasitic_subset <- apply_catchment_filter(parasitic_subset, catchment_config, "parasitic")
  selectDf <- bind_rows(bacterial_subset, parasitic_subset)

  return(selectDf)
}

# Fit negative binomial GAM with state-specific splines via brms
#
# Memory: ~24GB for 2 chains, ~56GB for 6 chains (publication quality)
# Increase adapt_delta (0.95-0.99) if divergent transitions occur
PROPOSED_BM <- function(data, cores = 16, chains = 2, iterations = 500,
                        adapt_delta = 0.95, max_treedepth = 10, seed = 123,
                        backend = "rstan") {
  data <- as.data.frame(data)

  required_cols <- c("count", "year", "state", "population")
  missing_cols <- required_cols[!required_cols %in% names(data)]
  if (length(missing_cols) > 0) {
    stop("Missing required columns in data: ", paste(missing_cols, collapse = ", "))
  }

  data$population <- as.numeric(data$population)
  if (any(is.na(data$population))) {
    stop("Population column contains NA values after conversion")
  }
  if (any(data$population <= 0)) {
    stop("Population column contains zero or negative values")
  }

  data$count <- as.integer(as.numeric(data$count))
  if (any(is.na(data$count))) {
    stop("Count column contains NA values after conversion")
  }

  if (all(data$count == 0) || sum(data$count) == 0) {
    stop("All counts zero. Cannot fit model")
  }

  # Spline requires numeric year, not factor
  if (is.factor(data$year)) {
    data$year <- as.numeric(as.character(data$year))
  }

  if (!is.factor(data$state)) {
    data$state <- as.factor(data$state)
  }

  # Set CmdStan path from env var (set in trendy.nf to a writable copy)
  if (backend == "cmdstanr") {
    cmdstan_env <- Sys.getenv("CMDSTAN", unset = "")
    if (nchar(cmdstan_env) > 0 && dir.exists(cmdstan_env)) {
      cmdstanr::set_cmdstan_path(cmdstan_env)
    }
  }

  set.seed(seed)

  # Pin shape prior; let brms auto-center the intercept on the data
  model_priors <- c(
    prior(inv_gamma(0.4, 0.3), class = "shape")
  )

  model <- tryCatch({
    brm(
      count ~ s(year, by = state) + state + offset(log(population)),
      data = data,
      family = negbinomial(),
      prior = model_priors,
      chains = chains,
      iter = iterations,
      cores = cores,
      seed = seed,
      control = list(adapt_delta = adapt_delta, max_treedepth = max_treedepth),
      backend = backend
    )
  }, error = function(e) {
    stop(paste0("Model fitting failed. Original error: ", e$message,
                "\nConsider: more iterations, higher adapt_delta, or higher max_treedepth."))
  })

  return(model)
}

# Programmatic convergence diagnostics (R-hat, ESS, divergent transitions)
CHECK_CONVERGENCE <- function(model, pathogen_name, output_dir) {
  diagnostics <- list(pathogen = pathogen_name, converged = TRUE, warnings = character(0))

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

  neff_values <- brms::neff_ratio(model)
  neff_values <- neff_values[!is.na(neff_values)]
  total_draws <- nrow(as.matrix(model))
  min_ess <- min(neff_values) * total_draws
  n_low_ess <- sum(neff_values * total_draws < 400)

  if (n_low_ess > 0) {
    diagnostics$warnings <- c(diagnostics$warnings,
      paste0("ESS WARNING: ", n_low_ess,
             " parameters with ESS < 400 (min ESS: ", round(min_ess, 0), ")"))
  }

  n_divergent <- NA
  tryCatch({
    np <- brms::nuts_params(model)
    n_divergent <- sum(np$Value[np$Parameter == "divergent__"])
    if (n_divergent > 0) {
      diagnostics$warnings <- c(diagnostics$warnings,
        paste0("DIVERGENCE WARNING: ", n_divergent, " divergent transitions"))
    }
  }, error = function(e) {
    diagnostics$warnings <<- c(diagnostics$warnings,
      paste0("Could not extract divergent transition info: ", e$message))
  })

  diagnostics$max_rhat <- max_rhat
  diagnostics$min_ess <- min_ess
  diagnostics$n_divergent <- n_divergent

  diag_df <- data.frame(
    pathogen = pathogen_name,
    max_rhat = round(max_rhat, 4),
    n_rhat_above_1.01 = n_rhat_warn,
    n_rhat_above_1.05 = n_rhat_fail,
    min_ess = round(min_ess, 0),
    n_params_low_ess = n_low_ess,
    n_divergent = n_divergent,
    converged = diagnostics$converged,
    warnings = paste(diagnostics$warnings, collapse = "; "),
    stringsAsFactors = FALSE
  )
  diag_file <- file.path(output_dir,
    paste0(pathogen_name, "_convergence_diagnostics.csv"))
  write.csv(diag_df, diag_file, row.names = FALSE)

  if (length(diagnostics$warnings) > 0) {
    for (w in diagnostics$warnings) {
      warning(paste0("[", pathogen_name, "] ", w))
    }
  }

  return(diagnostics)
}

# Extract posterior expected-value draws per state-year
LINPREAD_DRAW_FN <- function(data, model) {
  data <- as_tibble(data) %>%
    ungroup() %>%
    mutate(.row = row_number())

  tryCatch({
    draws <- epred_draws(model, newdata = data) %>%
              ungroup()

    if (!is.numeric(draws$population) || any(is.na(draws$population))) {
      stop("Population column is not numeric in the joined data")
    }

    return(draws)
  }, error = function(e) {
    stop("Error generating predictions: ", e$message)
  })
}

# Sum state-level draws to catchment-level totals per draw
CATCHMENT <- function(draws) {
  catchment_data <- draws %>%
    group_by(year, .draw) %>%
    summarise(
      count = sum(count),
      population = sum(population),
      .epred = sum(.epred),
      .groups = "drop"
    )

  return(catchment_data)
}

# Summarize catchment-level draws into point estimates and CIs
LINPRED_TO_CATCHIR <- function(catchment_data) {
  ir_data<-catchment_data %>%
    mutate(ir=.epred/(population/100000))%>%
    group_by(year)%>%
    summarise(
      population=round(median(population),6),
      population_check=round(sd(population),6),  # SD check — should be 0
      raw_count=round(median(count),6),
      raw_check=round(sd(count),6),
      raw_ir=round(raw_count/(population/100000),6),
      median=round(median(.epred),6),
      mean=round(mean(.epred),6),
      lower_equitailed=round(quantile(.epred, probs = 0.025, na.rm=TRUE),6),
      upper_equitailed=round(quantile(.epred, probs = 0.975, na.rm=TRUE),6),
      lower_hdi = round(log_hdi(.epred)[1],6),
      upper_hdi = round(log_hdi(.epred)[2],6),
      median_ir= round(median(ir),6),
      mean_ir= round(mean(ir),6),
      lower_equitailed_ir=round(quantile(ir, probs = 0.025, na.rm=TRUE),6),
      upper_equitailed_ir=round(quantile(ir, probs = 0.975, na.rm=TRUE),6),
      lower_hdi_ir = round(log_hdi(ir)[1],6),
      upper_hdi_ir = round(log_hdi(ir)[2],6))%>%
    arrange(year)
  return(ir_data)
}

# Summarize state-level draws into point estimates and CIs per site
LINPRED_TO_SITEIR <- function(site_data) {
  ir_data<-site_data %>%
    mutate(ir=.epred/(population/100000))%>%
    group_by(year, state)%>%
    summarise(
      population=round(median(population),6),
      population_check=round(sd(population),6),  # SD check — should be 0
      raw_count=round(median(count),6),
      raw_check=round(sd(count),6),
      raw_ir=round(raw_count/(population/100000),6),
      median=round(median(.epred),6),
      mean=round(mean(.epred),6),
      lower_equitailed=round(quantile(.epred, probs = 0.025, na.rm=TRUE),6),
      upper_equitailed=round(quantile(.epred, probs = 0.975, na.rm=TRUE),6),
      lower_hdi = round(log_hdi(.epred)[1],6),
      upper_hdi = round(log_hdi(.epred)[2],6),
      median_ir= round(median(ir),6),
      mean_ir= round(mean(ir),6),
      lower_equitailed_ir=round(quantile(ir, probs = 0.025, na.rm=TRUE),6),
      upper_equitailed_ir=round(quantile(ir, probs = 0.975, na.rm=TRUE),6),
      lower_hdi_ir = round(log_hdi(ir)[1],6),
      upper_hdi_ir = round(log_hdi(ir)[2],6))%>%
    arrange(year)
  return(ir_data)
}

# Faceted site-level incidence trend plot with 95% HDI ribbon
PLOT_SITE_TRENDS <- function(site, pathogen, outDir, subgroup = "combined", stable_year = NULL) {
  display_name <- if (subgroup != "combined") paste(pathogen, subgroup) else pathogen

  p <- ggplot(site, aes(x = year, y = median_ir)) +
    geom_line(linewidth = 1) +
    geom_ribbon(aes(ymin = lower_hdi_ir, ymax = upper_hdi_ir), alpha = 0.3) +
    facet_wrap(~ state, scales = "free_y") +
    labs(
      title = paste("Site-Specific Trends for", display_name),
      subtitle = "Median incidence with 95% HDI intervals",
      y = "Incidence per 100,000 population",
      x = "Year"
    ) +
    theme_minimal() +
    { if (!is.null(stable_year)) geom_vline(xintercept = stable_year, linetype="dashed", color="red") } +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      plot.subtitle = element_text(hjust = 0.5),
      strip.text = element_text(face = "bold")
    )

  return(p)
}

# Individual per-state incidence trend plot with 95% HDI ribbon
PLOT_STATE_TREND <- function(site_data, state_code, pathogen, outDir, subgroup = "combined", stable_year = NULL) {
  state_df <- site_data %>% filter(state == state_code)
  if (nrow(state_df) == 0) return(NULL)

  display_name <- if (subgroup != "combined") {
    paste(pathogen, subgroup, "\u2014", state_code)
  } else {
    paste(pathogen, "\u2014", state_code)
  }

  p <- ggplot(state_df, aes(x = year, y = median_ir)) +
    geom_line(linewidth = 1.5) +
    geom_ribbon(aes(ymin = lower_hdi_ir, ymax = upper_hdi_ir), alpha = 0.3) +
    { if (!is.null(stable_year)) geom_vline(xintercept = stable_year, linetype = "dashed", color = "red") } +
    labs(
      title = display_name,
      subtitle = "Median incidence with 95% HDI intervals",
      y = "Incidence per 100,000 population",
      x = "Year"
    ) +
    theme_minimal() +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      plot.subtitle = element_text(hjust = 0.5)
    )

  return(p)
}

# Catchment-wide incidence trend plot with 95% HDI ribbon
PLOT_OVERALL_TREND <- function(catchir_data, pathogen, outDir, subgroup = "combined", stable_year = NULL) {
  display_name <- if (subgroup != "combined") paste(pathogen, subgroup) else pathogen

  p <- ggplot(catchir_data, aes(x = year, y = median_ir)) +
    geom_line(linewidth = 1.5) +
    geom_ribbon(aes(ymin = lower_hdi_ir, ymax = upper_hdi_ir), alpha = 0.3) +
    { if (!is.null(stable_year)) geom_vline(xintercept = stable_year, linetype="dashed", color="red") } +
    labs(
      title = paste("Overall Trend for", display_name),
      subtitle = "Median incidence with 95% HDI intervals",
      y = "Incidence per 100,000 population",
      x = "Year"
    ) +
    theme_minimal() +
    theme(
      plot.title = element_text(hjust = 0.5, face = "bold"),
      plot.subtitle = element_text(hjust = 0.5)
    )

  return(p)
}

# Compare incidence rates between a baseline period and all other years
IR_COMP_CATCH <- function(catch, start_year, end_year, output_file = NULL) {

  # Baseline IR: mean across baseline period per draw
  # IR = sum(cases) / sum(person-time), standard epidemiological definition
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

  if (nrow(period_data) == 0) {
    stop(paste("No data available for period", start_year, "to", end_year))
  }

  # All calculations on draws THEN summarize
  comb<-left_join(catch, period_data, by=c(".draw"))%>%
   mutate(ir=.epred/(population/100000),
          est_ir=.epred/(population/100000),
          relative_risk=  est_ir/baseline_ir,
          percent_change= ((est_ir-baseline_ir)/baseline_ir)*100)%>%
   group_by(year)%>%
   summarise(
     population=round(median(population),6),
     population_check=round(sd(population),6),  # SD check — should be 0
     raw_count=round(median(count),6),
     raw_check=round(sd(count),6),
     raw_ir=round(raw_count/(population/100000),6),
     median=round(median(.epred),6),
     mean=round(mean(.epred),6),
     lower_equitailed=round(quantile(.epred, probs = 0.025, na.rm=TRUE),6),
     upper_equitailed=round(quantile(.epred, probs = 0.975, na.rm=TRUE),6),
     lower_hdi = round(log_hdi(.epred)[1],6),
     upper_hdi = round(log_hdi(.epred)[2],6),
     median_ir= round(median(ir),6),
     mean_ir= round(mean(ir),6),
     lower_equitailed_ir=round(quantile(ir, probs = 0.025, na.rm=TRUE),6),
     upper_equitailed_ir=round(quantile(ir, probs = 0.975, na.rm=TRUE),6),
     lower_hdi_ir = round(log_hdi(ir)[1],6),
     upper_hdi_ir = round(log_hdi(ir)[2],6),
     relative_risk_lower_hdi = round(hdi(relative_risk, credMass = 0.95)[1],6),
     relative_risk_upper_hdi = round(hdi(relative_risk, credMass = 0.95)[2],6),
     relative_risk_est=round(median(relative_risk),6),
     percent_change_lower_hdi = round(hdi(percent_change, credMass = 0.95)[1],6),
     percent_change_upper_hdi = round(hdi(percent_change, credMass = 0.95)[2],6),
     percent_change_est=round(median(percent_change),6))%>%
     mutate(comparison_period = paste0(start_year, "-", end_year))

  result <- comb %>%
    mutate(across(where(is.numeric), ~round(., 6)))

  if (!is.null(output_file)) {
    dir_path <- dirname(output_file)
    if (!dir.exists(dir_path)) {
      dir.create(dir_path, recursive = TRUE, showWarnings = FALSE)
    }
    write.csv(result, output_file, row.names = FALSE)
  }

  return(result)
}


