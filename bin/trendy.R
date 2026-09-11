#!/usr/bin/env Rscript
# trendy.R - Main Bayesian modeling pipeline for FoodNet surveillance data
# Fits hierarchical spline models per pathogen; generates incidence estimates and plots.

suppressPackageStartupMessages(library("argparse"))
options(warn = 1)

script_path <- commandArgs(trailingOnly = FALSE)
script_path <- sub("--file=", "", script_path[grep("--file=", script_path)])
script_dir <- dirname(script_path)
source(file.path(script_dir, "classification.R"))
source(file.path(script_dir, "input_validation.R"))

tryCatch({
  source(file.path(script_dir, "functions.R"))
}, error = function(e) {
  tryCatch({
    parent_dir <- dirname(script_dir)
    source(file.path(parent_dir, "bin", "functions.R"))
  }, error = function(e2) {
    tryCatch({
      source("functions.R")
    }, error = function(e3) {
      cat("Failed to locate functions.R. Script directory:", script_dir, "\n")
      cat("Current working directory:", getwd(), "\n")
      stop("Error loading functions.R: ", e3$message)
    })
  })
})

LOAD_PACKAGES <- function(packages) {
  for(pkg in packages) {
    if(!requireNamespace(pkg, quietly = TRUE)) {
      stop(paste("Required package", pkg, "is not installed"))
    }
    suppressPackageStartupMessages(library(pkg, character.only = TRUE))
  }
}

##############################################################
# Argument parsing
##############################################################

parser <- ArgumentParser(description="FoodNetTrends Bayesian Modeling Pipeline")
parser$add_argument("--baseline_start", type = "integer", default = 2016L)
parser$add_argument("--baseline_end", type = "integer", default = 2018L)
parser$add_argument("--classification_rules", default = file.path(dirname(script_dir), "analysis_configs", "classification_rules.csv"))
parser$add_argument("--serotype_source", default = "auto")
parser$add_argument("--colorado_coverage", default = "historical", choices = c("historical", "expanded"))
parser$add_argument("--parasite_end_year", type = "integer", default = 2024L)
parser$add_argument("--selected_serotypes", default = "",
                    help = "Pipe-separated individually selected Salmonella serotypes")

parser$add_argument("--mmwrFile", type="character",
                    help="Path to FoodNet MMWR SAS data file")
parser$add_argument("--censusFileB", type="character",
                    help="Path to census file for bacterial pathogens")
parser$add_argument("--censusFileP", type="character",
                    help="Path to census file for parasitic pathogens")

parser$add_argument("--states", type="character", default=NULL,
                    help="List of states to include (default: all states)")
parser$add_argument("--travel", type="character", default="NO,UNKNOWN,YES",
                    help="List of travel types to include (default: NO,UNKNOWN,YES)")
parser$add_argument("--cidt", type="character", default="CIDT+,CX+,PARASITIC",
                    help="List of diagnostic methods to include (default: CIDT+,CX+,PARASITIC)")
parser$add_argument("--travel_stratify", type="character", default="false",
                    help="Run separate models for domestic and travel-associated cases")

parser$add_argument("--projID", type="character",
                    help="Project identifier for output naming")
parser$add_argument("--outDir", type="character", default="output",
                    help="Base output directory (default: output)")
parser$add_argument("--pathogen", type="character",
                    help="Specific pathogen to analyze (if not processing all)")
parser$add_argument("--subgroup", type="character", default="combined",
                    help="Pathogen subgroup to analyze (e.g., O157, Enteritidis)")

parser$add_argument("--preprocessed", type="logical", default=FALSE,
                    help="Use preprocessed CSV data (default: FALSE)")
parser$add_argument("--cleanFile", type="character", default=NULL,
                    help="Path to cleaned CSV file if preprocessed is TRUE")

parser$add_argument("--cores", type="integer", default=16,
                    help="Number of cores to use for model fitting (default: 16)")
parser$add_argument("--chains", type="integer", default=2,
                    help="Number of MCMC chains (default: 2)")
parser$add_argument("--iterations", type="integer", default=500,
                    help="Number of MCMC iterations (default: 500)")
parser$add_argument("--adapt_delta", type="double", default=0.95,
                    help="Adaptation parameter for MCMC (default: 0.95)")
parser$add_argument("--max_treedepth", type="integer", default=10,
                    help="Maximum tree depth for MCMC (default: 10)")
parser$add_argument("--seed", type="integer", default=123,
                    help="Random seed for reproducibility (default: 123)")
parser$add_argument("--backend", type="character", default="rstan",
                    help="Stan backend: rstan or cmdstanr (default: rstan)")

parser$add_argument("--catchment-config", type="character", default=NULL,
                    help="Path to CSV file with catchment definitions (optional)")

parser$add_argument("--debug", type="logical", default=FALSE,
                    help="Run in debug mode with default parameters (default: FALSE)")

tryCatch({
  opts <- parser$parse_args()
}, error = function(e) {
  cat("Error parsing command line arguments:", e$message, "\n")
  cat("Run with --help for usage information\n")
  quit(status = 1)
})

##############################################################
# Initialize variables
##############################################################

report_progress <- function(stage, percent=NULL, message=NULL) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  if (!is.null(message)) {
    cat(sprintf("[%s] %s: %s\n", timestamp, stage, message))
  } else if (!is.null(percent)) {
    cat(sprintf("[%s] %s: %d%%\n", timestamp, stage, percent))
  } else {
    cat(sprintf("[%s] %s\n", timestamp, stage))
  }
  flush.console()
}

report_progress("SETUP", message="Initializing pipeline")
baseline_start <- opts$baseline_start
baseline_end <- if (is.null(opts$baseline_end)) baseline_start else opts$baseline_end
if (baseline_start > baseline_end) stop("baseline_start must not exceed baseline_end")
classification_rules <- read_classification_rules(opts$classification_rules)
selected_serotypes <- strsplit(opts$selected_serotypes, "|", fixed = TRUE)[[1]]

if (opts$debug == FALSE) {
  mmwrFile <- opts$mmwrFile
  censusFileB <- opts$censusFileB
  censusFileP <- opts$censusFileP
  projID <- opts$projID
  outDir <- opts$outDir

  travel <- CLEAN_LIST(opts$travel)
  cidt <- CLEAN_LIST(opts$cidt)
  travel_stratify <- tolower(opts$travel_stratify) %in% c("true", "yes", "1")

  modelcores <- opts$cores
  chains <- opts$chains
  iterations <- opts$iterations
  adapt_delta <- opts$adapt_delta
  max_treedepth <- opts$max_treedepth
  seed <- opts$seed
  backend <- opts$backend

  preprocessed <- opts$preprocessed
  cleanFile <- opts$cleanFile

} else {
  report_progress("SETUP", message="Running in DEBUG mode with default parameters")

  mmwrFile <- "/scicomp/groups-pure/OID/NCEZID/DFWED/EDEB/foodnet/trends/data/mmwr9624_May2025.sas7bdat"
  censusFileB <- "/scicomp/groups-pure/OID/NCEZID/DFWED/EDEB/foodnet/trends/data/cen9624.sas7bdat"
  censusFileP <- "/scicomp/groups-pure/OID/NCEZID/DFWED/EDEB/foodnet/trends/data/cen9624_para.sas7bdat"
  projID <- format(Sys.time(), "%Y%m%d%H%M")
  outDir <- "debug_output"

  travel <- CLEAN_LIST("NO,UNKNOWN,YES")
  cidt <- CLEAN_LIST("CIDT+,CX+,PARASITIC")
  travel_stratify <- FALSE

  modelcores <- min(parallel::detectCores(), 8)
  chains <- 2
  iterations <- 100
  adapt_delta <- 0.8
  max_treedepth <- 8
  seed <- 123
  backend <- "rstan"

  preprocessed <- FALSE
  cleanFile <- NULL
}

validate_params <- function() {
  errors <- c()

  if (is.null(mmwrFile) || mmwrFile == "")
    errors <- c(errors, "Missing required parameter: mmwrFile")
  if (is.null(censusFileB) || censusFileB == "")
    errors <- c(errors, "Missing required parameter: censusFileB")
  if (is.null(censusFileP) || censusFileP == "")
    errors <- c(errors, "Missing required parameter: censusFileP")

  if (length(errors) == 0) {
    if (!file.exists(mmwrFile))
      errors <- c(errors, paste("MMWR file does not exist:", mmwrFile))
    if (!file.exists(censusFileB))
      errors <- c(errors, paste("Census bacterial file does not exist:", censusFileB))
    if (!file.exists(censusFileP))
      errors <- c(errors, paste("Census parasitic file does not exist:", censusFileP))
  }

  if (preprocessed && !is.null(cleanFile)) {
    if (!file.exists(cleanFile))
      errors <- c(errors, paste("Clean file does not exist:", cleanFile))
  }

  if (is.null(projID) || projID == "") {
    projID <<- format(Sys.time(), "%Y%m%d%H%M")
    report_progress("SETUP", message=paste("No projID provided, using timestamp:", projID))
  }

  if (length(errors) > 0) {
    for (err in errors) {
      report_progress("ERROR", message=err)
    }
    stop(paste(errors, collapse="\n"))
  }
}

validate_params()

dir.create(outDir, showWarnings = FALSE, recursive = TRUE)
if (!dir.exists(outDir)) {
  stop("Failed to create output directory: ", outDir)
}

report_progress("SETUP", message="Loading required packages")
pkgs <- c('haven', 'gtools', 'brms', 'ggplot2', 'tidybayes', 'HDInterval', 'tidyverse')
tryCatch({
  LOAD_PACKAGES(pkgs)
}, error = function(e) {
  stop("Failed to load required packages: ", e$message)
})

##############################################################
# Analysis parameters
##############################################################

if (("YES" %in% travel) & ("UNKNOWN" %in% travel)) {
  travelLabel <- "All Cases"
} else if (!("YES" %in% travel) & ("UNKNOWN" %in% travel)) {
  travelLabel <- "Domestically-Acquired (UNK Travel Included)"
} else {
  travelLabel <- "Domestically-Acquired (UNK Travel Excluded)"
}

culture <- ifelse("CIDT+" %in% cidt, "CxCIDT", "Cx")

outBase <- file.path(outDir, paste0(
  projID, "_", "splinesmodel_",
  gsub(" ", "", travelLabel), "_",
  paste(culture, collapse=""), "_"
))

report_progress("ANALYSIS DETAILS", message=paste0(
  "mmwrFile: ", mmwrFile, " | ",
  "censusFileB: ", censusFileB, " | ",
  "censusFileP: ", censusFileP, " | ",
  "projID: ", projID, " | ",
  "travel: ", paste(travel, collapse=","), " | ",
  "cidt: ", paste(cidt, collapse=","), " | ",
  "cores: ", modelcores, " | ",
  "chains: ", chains, " | ",
  "iterations: ", iterations
))

##############################################################
# Data Import and Preprocessing
##############################################################

report_progress("DATA", message="Importing MMWR data")
tryCatch({
  if (preprocessed) {
    if (is.null(cleanFile) || cleanFile == "") {
      stop("preprocessed=TRUE but no cleanFile path provided")
    }
    if (!file.exists(cleanFile)) {
      stop("Preprocessed file not found: ", cleanFile)
    }
    report_progress("DATA", message=paste("Using preprocessed data from:", cleanFile))
    mmwrdata <- readr::read_csv(cleanFile, show_col_types = FALSE)
  } else {
    stop("This script is designed to work with preprocessed data. Please ensure preprocess.R has been run first.")
  }

  mmwrdata <- classify_cases(mmwrdata, classification_rules, opts$serotype_source)
  # Establish observation years and selected sites before case/subgroup filtering.
  surveillance_years <- seq.int(min(mmwrdata$year, na.rm = TRUE), max(mmwrdata$year, na.rm = TRUE))
  surveillance_states <- if (!is.null(opts$states) && nzchar(opts$states))
    CLEAN_LIST(opts$states) else NULL
  classification_audit <- classification_counts(mmwrdata)

  mmwrdata <- mmwrdata %>%
    filter((cxcidt %in% cidt) & (travelint %in% travel)) %>%
    filter(!county %in% c("OUT OF STATE", "UNKNOWN", "99997"))

  if (!is.null(opts$states) && opts$states != "") {
    states_list <- CLEAN_LIST(opts$states)
    mmwrdata <- mmwrdata %>%
      filter(state %in% states_list)
    report_progress("DATA", message=paste("Filtered to states:", paste(states_list, collapse=", ")))
  }

  required_cols <- c("pathogen", "year", "state", "pathogentype")
  missing_cols <- required_cols[!required_cols %in% names(mmwrdata)]
  if (length(missing_cols) > 0) {
    stop("Required columns missing from preprocessed data: ", paste(missing_cols, collapse=", "))
  }

  report_progress("DATA", message=paste("Processed", nrow(mmwrdata), "MMWR records"))
}, error = function(e) {
  stop("Error importing MMWR data: ", e$message)
})

report_progress("DATA", message="Importing census data")
# Read SAS or CSV based on file extension
read_data_file <- function(path) {
  if (grepl("\\.csv$", path, ignore.case = TRUE)) readr::read_csv(path, show_col_types = FALSE)
  else haven::read_sas(path)
}
tryCatch({
  bacterial <- read_data_file(censusFileB)
  parasitic <- read_data_file(censusFileP)
  # Validate the selected states only; unselected sites do not define this run.
  if (!is.null(surveillance_states)) {
    names(bacterial) <- tolower(names(bacterial)); names(parasitic) <- tolower(names(parasitic))
    bacterial <- bacterial[bacterial$state %in% surveillance_states, , drop = FALSE]
    parasitic <- parasitic[parasitic$state %in% surveillance_states, , drop = FALSE]
  }
  if (is.null(opts$pathogen) || length(opts$pathogen) != 1) stop("One pathogen per model process is required")
  inputs <- prepare_analysis_inputs(mmwrdata, bacterial, parasitic, opts$pathogen,
                                    opts$colorado_coverage, opts$parasite_end_year, surveillance_years)
  mmwrdata <- inputs$cases
  census <- inputs$census
  surveillance <- expand.grid(year=inputs$years, state=unique(census$state), stringsAsFactors=FALSE)
  input_exclusions <- inputs$excluded
  report_progress("INPUT_VALIDATION", message=paste("Colorado coverage:", opts$colorado_coverage,
    "| parasite end year:", opts$parasite_end_year, "| population years:",
    paste(range(census$year), collapse="-")))
  if (nrow(input_exclusions)) for (i in seq_len(nrow(input_exclusions)))
    report_progress("WARNING", message=paste(input_exclusions$reason[i],
      "year", input_exclusions$year[i], "records", input_exclusions$records[i]))
  missing_baseline <- setdiff(seq.int(baseline_start, baseline_end), unique(surveillance$year))
  if (length(missing_baseline)) stop("Baseline years unavailable: ", paste(missing_baseline, collapse = ", "))
  report_progress("DATA", message=paste("Processed census data with",
                                        length(unique(census$year)), "years and",
                                        length(unique(census$state)), "states"))
}, error = function(e) {
  stop("Error importing census data: ", e$message)
})

##############################################################
# Catchment Configuration
##############################################################

catchment_config <- NULL
if (!is.null(opts$catchment_config)) {
  report_progress("CONFIG", message=paste("Loading catchment configuration from:", opts$catchment_config))
  tryCatch({
    catchment_config <- read_catchment_config(opts$catchment_config)
    report_progress("CONFIG", message=paste("Loaded catchment configuration with", nrow(catchment_config), "sites"))
  }, error = function(e) {
    stop("Error loading catchment configuration: ", e$message)
  })
} else {
  report_progress("CONFIG", message="Using default FoodNet catchment definitions")
}

##############################################################
# Pathogen Analysis
##############################################################

report_progress("ANALYSIS", message="Processing pathogen data")
tryCatch({
  mmwrdata_filtered <- mmwrdata

  if (!is.null(opts$pathogen)) {
    mmwrdata_filtered <- mmwrdata_filtered %>%
      filter(pathogen == opts$pathogen)

    mmwrdata_filtered <- select_analysis_cases(mmwrdata, opts$pathogen, opts$subgroup, selected_serotypes)

    if (nrow(mmwrdata_filtered) == 0) {
      pathogen_desc <- ifelse(opts$subgroup == "combined",
                              opts$pathogen,
                              paste(opts$pathogen, opts$subgroup, sep=":"))
      empty_prefix <- sub("_$", "", gsub("_+", "_", gsub("[^a-zA-Z0-9_-]", "_",
        paste(opts$pathogen, opts$subgroup, sep = "_"))))
      writeLines(paste("No data found for:", pathogen_desc, "after filtering; no model fitted."),
                 file.path(outDir, paste0(empty_prefix, "_error.txt")))
      write.csv(data.frame(pathogen = opts$pathogen, subgroup = opts$subgroup,
        baseline_start = baseline_start, baseline_end = baseline_end),
        file.path(outDir, paste0(empty_prefix, "_analysis_settings.csv")), row.names = FALSE)
      report_progress("WARNING", message=paste("Skipping empty analysis:", pathogen_desc))
      quit(status = 0)
    }

    report_progress("ANALYSIS", message=paste("Filtered data contains", nrow(mmwrdata_filtered), "records"))
  }

  pathDf <- PATH_ANALYSIS(mmwrdata_filtered, census, catchment_config, surveillance)%>%as.data.frame()
  report_progress("ANALYSIS", message=paste("Processed",
                                            length(unique(pathDf$pathogen)),
                                            "pathogens"))

  bact <- pathDf

  report_progress("ANALYSIS", message="Post-processing pathogen data")

  if (travel_stratify) {
    mmwrdata_for_stratify <- mmwrdata_filtered
  }
  remove(mmwrdata_filtered)
  if (exists("mmwrdata")) remove(mmwrdata)

  if (!is.null(opts$pathogen)) {
    bact <- subset(bact, pathogen == opts$pathogen)

    if (nrow(bact) == 0) {
      pathogen_desc <- ifelse(opts$subgroup == "combined",
                              opts$pathogen,
                              paste(opts$pathogen, opts$subgroup, sep=":"))
      report_progress("ERROR", message=paste("No data found for:", pathogen_desc))

      safe_subgroup <- gsub("[^a-zA-Z0-9_-]", "_", opts$subgroup)
      safe_subgroup <- gsub("_+", "_", safe_subgroup)
      error_file <- paste0(outDir, "/", opts$pathogen, "_", safe_subgroup, "_error.txt")
      error_content <- c(
        paste("ERROR: No data found for:", pathogen_desc),
        paste("Date:", Sys.time()),
        paste("Project ID:", projID),
        "",
        "This pathogen/subgroup had no cases after applying filters:",
        paste("- Pathogen:", opts$pathogen),
        paste("- Subgroup:", opts$subgroup),
        paste("- Travel types:", paste(travel, collapse=", ")),
        paste("- CIDT types:", paste(cidt, collapse=", ")),
        "",
        "Verify pathogen name, subgroup, and filter settings."
      )
      writeLines(error_content, error_file)

      quit(status = 0)
    }
  } else {
    report_progress("ANALYSIS", message="No specific pathogen requested, analyzing all pathogens in dataset")

    if (nrow(bact) == 0) {
      stop("No data found after applying filters")
    }
  }

  bact$yearn <- as.numeric(as.character(bact$year))
  bact$year <- as.factor(bact$year)
  bact_list <- split(bact, bact$pathogen)
  target_pathogens <- names(bact_list)

  report_progress("ANALYSIS", message=paste("Prepared data for modeling",
                                            length(target_pathogens),
                                            "pathogens:",
                                            paste(target_pathogens, collapse=", ")))
}, error = function(e) {
  stop("Error in pathogen analysis: ", e$message)
})

##############################################################
# Model Fitting
##############################################################

for (pathogen_name in target_pathogens) {
  report_progress("MODEL", message=paste("Fitting model for", pathogen_name))

  current_data <- bact_list[[pathogen_name]]

  output_prefix <- paste(pathogen_name, opts$subgroup, sep="_")
  output_prefix <- gsub("[^a-zA-Z0-9_-]", "_", output_prefix)
  output_prefix <- gsub("_+", "_", output_prefix)
  output_prefix <- sub("_$", "", output_prefix)

  tryCatch({
    write.csv(classification_audit, file.path(outDir, paste0(output_prefix, "_classification_report.csv")), row.names = FALSE)
    write.csv(classification_rules, file.path(outDir, paste0(output_prefix, "_classification_rules.csv")), row.names = FALSE)
    write.csv(data.frame(pathogen = pathogen_name, subgroup = opts$subgroup,
      baseline_start = baseline_start, baseline_end = baseline_end,
      colorado_coverage = opts$colorado_coverage, parasite_end_year = opts$parasite_end_year,
      analysis_start_year = min(as.numeric(as.character(current_data$year))), analysis_end_year = max(as.numeric(as.character(current_data$year))),
      excluded_records = sum(input_exclusions$records),
      serotype_source = opts$serotype_source, selected_serotypes = opts$selected_serotypes,
      travel = opts$travel, cidt = opts$cidt, states = paste(surveillance_states, collapse = ",")),
      file.path(outDir, paste0(output_prefix, "_analysis_settings.csv")), row.names = FALSE)
    write.csv(input_exclusions, file.path(outDir, paste0(output_prefix, "_input_exclusions.csv")), row.names = FALSE)
    write.csv(census, file.path(outDir, paste0(output_prefix, "_population_used.csv")), row.names = FALSE)
    proposed <- PROPOSED_BM(
      current_data,
      cores = modelcores,
      chains = chains,
      iterations = iterations,
      adapt_delta = adapt_delta,
      max_treedepth = max_treedepth,
      seed = seed,
      backend = backend
    )

    saveFile <- paste0(outDir, "/", output_prefix, "_brm.Rds")
    saveRDS(proposed, saveFile)
    report_progress("MODEL", message=paste("Saved model to", saveFile))

    summaryFile <- paste0(outDir, "/", output_prefix, "_summary.txt")
    tryCatch({
      sink(summaryFile)
      on.exit(sink(), add = TRUE)
      print(summary(proposed))
      sink()
      on.exit(NULL)
    }, error = function(e) {
      try(sink(), silent = TRUE)
      warning("Failed to write model summary: ", e$message)
    })
    report_progress("MODEL", message=paste("Saved model summary to", summaryFile))

    report_progress("DIAGNOSTICS", message=paste("Checking convergence for", pathogen_name))
    convergence <- CHECK_CONVERGENCE(proposed, output_prefix, outDir)
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

    report_progress("POST-PROCESSING", message=paste("Generating predictions for", pathogen_name))
    posteriorLinpred <- LINPREAD_DRAW_FN(
      data = (proposed$data %>% group_by(state)),
      model = proposed
    )

    report_progress("POST-PROCESSING", message="Calculating site-level estimates")
    site <- LINPRED_TO_SITEIR(posteriorLinpred)
    site$pathogen <- pathogen_name
    site$travel <- travelLabel
    site$culture <- culture

    siteir_file <- paste0(outDir, "/", output_prefix, "_IRSite.csv")
    write.csv(site, siteir_file, row.names = FALSE)
    report_progress("OUTPUT", message=paste("Saved site incidence rate estimates to", siteir_file))

    report_progress("POST-PROCESSING", message="Calculating catchment-level draws")
    catch <- CATCHMENT(posteriorLinpred)

    report_progress("POST-PROCESSING", message="Calculating catchment-level estimates")
    catchir.linpred <- LINPRED_TO_CATCHIR(catch)

    catchir.linpred$pathogen <- pathogen_name
    catchir.linpred$travel <- travelLabel
    catchir.linpred$culture <- culture

    ir_file <- paste0(outDir, "/", output_prefix, "_IRCatch.csv")
    write.csv(catchir.linpred, ir_file, row.names = FALSE)
    report_progress("OUTPUT", message=paste("Saved incidence rate estimates to", ir_file))

    report_progress("ANALYSIS", message="Calculating relative risks and percent changes")

    baseline_comparison <- IR_COMP_CATCH(catch, baseline_start, baseline_end,
      paste0(outDir, "/", output_prefix, "_EstIRRCatch_", baseline_start, "_", baseline_end, ".csv"))

    if (requireNamespace("ggplot2", quietly = TRUE)) {
      stable_yr <- get_catchment_stable_year(catchment_config)
      tryCatch({
        if (exists("PLOT_SITE_TRENDS", mode = "function")) {
          site_plot <- PLOT_SITE_TRENDS(site, pathogen_name, outDir, opts$subgroup, stable_year = stable_yr)
          ggsave(paste0(outDir, "/", output_prefix, "_site_trends.png"), site_plot,
                 width = 10, height = 8, dpi = 300)
        }

        if (exists("PLOT_OVERALL_TREND", mode = "function")) {
          overall_plot <- PLOT_OVERALL_TREND(catchir.linpred, pathogen_name, outDir, opts$subgroup, stable_year = stable_yr)
          ggsave(paste0(outDir, "/", output_prefix, "_overall_trend.png"), overall_plot,
                 width = 10, height = 6, dpi = 300)
        }

        # Per-state individual trend charts
        if (exists("PLOT_STATE_TREND", mode = "function")) {
          for (st in unique(as.character(site$state))) {
            state_plot <- PLOT_STATE_TREND(site, st, pathogen_name, outDir, opts$subgroup, stable_year = stable_yr)
            if (!is.null(state_plot)) {
              ggsave(paste0(outDir, "/", output_prefix, "_", st, "_trend.png"),
                     state_plot, width = 8, height = 5, dpi = 300)
            }
          }
        }
      }, error = function(e) {
        report_progress("WARNING", message=paste("Visualization skipped:", e$message))
      })
    }

    # Travel stratification: fit separate models for domestic and travel-associated cases
    if (travel_stratify && exists("mmwrdata_for_stratify")) {
      report_progress("TRAVEL_STRATIFY", message=paste("Starting travel stratification for", pathogen_name))

      strat_data <- mmwrdata_for_stratify %>% filter(pathogen == pathogen_name)

      domestic_data <- strat_data %>% filter(travelint %in% c("NO", "UNKNOWN"))
      travel_data  <- strat_data %>% filter(travelint == "YES")

      domestic_catch <- NULL
      domestic_site  <- NULL
      travel_catch   <- NULL
      travel_site    <- NULL

      # Domestic stratum
      report_progress("TRAVEL_STRATIFY", message=paste("Fitting domestic model for", pathogen_name))
      tryCatch({
        dom_path <- PATH_ANALYSIS(domestic_data, census, catchment_config, surveillance) %>% as.data.frame()
        dom_path <- subset(dom_path, pathogen == pathogen_name)
        dom_path$yearn <- as.numeric(as.character(dom_path$year))
        dom_path$year  <- as.factor(dom_path$year)

        dom_model <- PROPOSED_BM(
          dom_path, cores = modelcores, chains = chains,
          iterations = iterations, adapt_delta = adapt_delta,
          max_treedepth = max_treedepth, seed = seed, backend = backend
        )

        CHECK_CONVERGENCE(dom_model, paste0(output_prefix, "_domestic"), outDir)
        dom_linpred <- LINPREAD_DRAW_FN(
          data  = (dom_model$data %>% group_by(state)),
          model = dom_model
        )

        domestic_site <- LINPRED_TO_SITEIR(dom_linpred)
        domestic_site$pathogen <- pathogen_name
        domestic_site$travel   <- "Domestic"
        domestic_site$culture  <- culture

        dom_catch_draws    <- CATCHMENT(dom_linpred)
        domestic_catch     <- LINPRED_TO_CATCHIR(dom_catch_draws)
        domestic_catch$pathogen <- pathogen_name
        domestic_catch$travel   <- "Domestic"
        domestic_catch$culture  <- culture
        IR_COMP_CATCH(dom_catch_draws, baseline_start, baseline_end,
          file.path(outDir, paste0(output_prefix, "_domestic_EstIRRCatch_", baseline_start, "_", baseline_end, ".csv")))

        write.csv(domestic_site,
                  paste0(outDir, "/", output_prefix, "_domestic_IRSite.csv"),
                  row.names = FALSE)
        write.csv(domestic_catch,
                  paste0(outDir, "/", output_prefix, "_domestic_IRCatch.csv"),
                  row.names = FALSE)
        report_progress("TRAVEL_STRATIFY", message=paste("Domestic stratum complete for", pathogen_name))
      }, error = function(e) {
        report_progress("WARNING", message=paste("Domestic stratum failed for", pathogen_name, ":", e$message))
      })

      # Travel stratum
      report_progress("TRAVEL_STRATIFY", message=paste("Fitting travel model for", pathogen_name))
      tryCatch({
        trv_path <- PATH_ANALYSIS(travel_data, census, catchment_config, surveillance) %>% as.data.frame()
        trv_path <- subset(trv_path, pathogen == pathogen_name)
        trv_path$yearn <- as.numeric(as.character(trv_path$year))
        trv_path$year  <- as.factor(trv_path$year)

        trv_model <- PROPOSED_BM(
          trv_path, cores = modelcores, chains = chains,
          iterations = iterations, adapt_delta = adapt_delta,
          max_treedepth = max_treedepth, seed = seed, backend = backend
        )

        CHECK_CONVERGENCE(trv_model, paste0(output_prefix, "_travel"), outDir)
        trv_linpred <- LINPREAD_DRAW_FN(
          data  = (trv_model$data %>% group_by(state)),
          model = trv_model
        )

        travel_site <- LINPRED_TO_SITEIR(trv_linpred)
        travel_site$pathogen <- pathogen_name
        travel_site$travel   <- "Travel"
        travel_site$culture  <- culture

        trv_catch_draws <- CATCHMENT(trv_linpred)
        travel_catch    <- LINPRED_TO_CATCHIR(trv_catch_draws)
        travel_catch$pathogen <- pathogen_name
        travel_catch$travel   <- "Travel"
        travel_catch$culture  <- culture
        IR_COMP_CATCH(trv_catch_draws, baseline_start, baseline_end,
          file.path(outDir, paste0(output_prefix, "_travel_EstIRRCatch_", baseline_start, "_", baseline_end, ".csv")))

        write.csv(travel_site,
                  paste0(outDir, "/", output_prefix, "_travel_IRSite.csv"),
                  row.names = FALSE)
        write.csv(travel_catch,
                  paste0(outDir, "/", output_prefix, "_travel_IRCatch.csv"),
                  row.names = FALSE)
        report_progress("TRAVEL_STRATIFY", message=paste("Travel stratum complete for", pathogen_name))
      }, error = function(e) {
        report_progress("WARNING", message=paste("Travel stratum failed for", pathogen_name,
                        ":", e$message, "- skipping comparison plots"))
      })

      # Comparison plots (require both strata)
      if (!is.null(domestic_catch) && !is.null(travel_catch)) {
        report_progress("TRAVEL_STRATIFY", message=paste("Generating comparison plots for", pathogen_name))
        tryCatch({
          if (exists("PLOT_TRAVEL_COMPARISON", mode = "function")) {
            PLOT_TRAVEL_COMPARISON(domestic_catch, travel_catch, pathogen_name,
                                  paste0(outDir, "/", output_prefix, "_travel_comparison.png"))
          }
          if (exists("PLOT_TRAVEL_COMPARISON_SITE", mode = "function")) {
            PLOT_TRAVEL_COMPARISON_SITE(domestic_site, travel_site, pathogen_name,
                                       paste0(outDir, "/", output_prefix, "_travel_comparison_site.png"))
          }
          if (exists("PLOT_TRAVEL_FRACTION", mode = "function")) {
            PLOT_TRAVEL_FRACTION(domestic_catch, travel_catch, pathogen_name,
                                paste0(outDir, "/", output_prefix, "_travel_fraction.png"))
          }
          report_progress("TRAVEL_STRATIFY", message=paste("Comparison plots complete for", pathogen_name))
        }, error = function(e) {
          report_progress("WARNING", message=paste("Comparison plot generation failed:", e$message))
        })
      }
    }

    report_progress("COMPLETE", message=paste("Completed analysis for", pathogen_name))
  }, error = function(e) {
    report_progress("ERROR", message=paste("Error in model fitting for", pathogen_name, ":", e$message))
    error_file <- paste0(outDir, "/", output_prefix, "_error.txt")
    tryCatch({
      sink(error_file)
      on.exit(sink(), add = TRUE)
      cat(paste("Error processing", pathogen_name, "at", Sys.time(), "\n"))
      cat(paste("Error message:", e$message, "\n"))
      cat("Traceback:\n")
      cat(paste(capture.output(traceback()), collapse = "\n"))
      sink()
      on.exit(NULL)
    }, error = function(e2) {
      try(sink(), silent = TRUE)
    })
  })
}

report_progress("PIPELINE", message="Analysis complete for all pathogens")
report_progress("PIPELINE", message=paste("Results saved to", outDir))

report_progress("SESSION", message="Session information:")
print(sessionInfo())
