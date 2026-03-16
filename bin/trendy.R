#!/usr/bin/env Rscript
# trendy.R - Main Bayesian modeling pipeline for FoodNet surveillance data
# Fits hierarchical spline models per pathogen; generates incidence estimates and plots.

suppressPackageStartupMessages(library("argparse"))
options(warn = 1)

script_path <- commandArgs(trailingOnly = FALSE)
script_path <- sub("--file=", "", script_path[grep("--file=", script_path)])
script_dir <- dirname(script_path)

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

if (opts$debug == FALSE) {
  mmwrFile <- opts$mmwrFile
  censusFileB <- opts$censusFileB
  censusFileP <- opts$censusFileP
  projID <- opts$projID
  outDir <- opts$outDir

  travel <- CLEAN_LIST(opts$travel)
  cidt <- CLEAN_LIST(opts$cidt)

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
tryCatch({
  census <- haven::read_sas(censusFileB) %>%
    setNames(tolower(names(.))) %>%
    group_by(year, state) %>%
    dplyr::summarize(population = sum(population, na.rm=TRUE)) %>%
    mutate(pathogentype = "Bacterial") %>%
    bind_rows(
      haven::read_sas(censusFileP) %>%
        setNames(tolower(names(.))) %>%
        group_by(year, state) %>%
        dplyr::summarize(population = sum(population, na.rm=TRUE)) %>%
        mutate(pathogentype = "Parasitic")
    ) %>%
    ungroup()

  census <- as.data.frame(census)
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
if (!is.null(opts$`catchment-config`)) {
  report_progress("CONFIG", message=paste("Loading catchment configuration from:", opts$`catchment-config`))
  tryCatch({
    catchment_config <- read_catchment_config(opts$`catchment-config`)
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

    if (opts$subgroup != "combined") {
      if (opts$pathogen == "STEC" && opts$subgroup %in% c("O157", "nonO157")) {
        if ("stec_class" %in% names(mmwrdata_filtered)) {
          if (opts$subgroup == "O157") {
            mmwrdata_filtered <- mmwrdata_filtered %>%
              filter(stec_class == "STEC O157")
          } else if (opts$subgroup == "nonO157") {
            mmwrdata_filtered <- mmwrdata_filtered %>%
              filter(stec_class %in% c("STEC NONO157", "STEC O AG UNDET"))
          }
          report_progress("ANALYSIS", message=paste("Filtered STEC to subgroup:", opts$subgroup))
        } else {
          stop("stec_class column not found - cannot filter by STEC subgroup")
        }
      } else if (opts$pathogen == "SALMONELLA") {
        if ("serotypesummary" %in% names(mmwrdata_filtered)) {
          mmwrdata_filtered <- mmwrdata_filtered %>%
            filter(serotypesummary == opts$subgroup)
          report_progress("ANALYSIS", message=paste("Filtered Salmonella to serotype:", opts$subgroup))
        } else {
          stop("serotypesummary column not found - cannot filter by serotype")
        }
      } else {
        if ("serotypesummary" %in% names(mmwrdata_filtered)) {
          mmwrdata_filtered <- mmwrdata_filtered %>%
            filter(serotypesummary == opts$subgroup | is.na(serotypesummary))
          report_progress("ANALYSIS", message=paste("Filtered", opts$pathogen, "to subgroup:", opts$subgroup))
        } else if ("serogroup" %in% names(mmwrdata_filtered)) {
          mmwrdata_filtered <- mmwrdata_filtered %>%
            filter(serogroup == opts$subgroup | is.na(serogroup))
          report_progress("ANALYSIS", message=paste("Filtered", opts$pathogen, "to serogroup:", opts$subgroup))
        }
      }
    }

    if (nrow(mmwrdata_filtered) == 0) {
      pathogen_desc <- ifelse(opts$subgroup == "combined",
                              opts$pathogen,
                              paste(opts$pathogen, opts$subgroup, sep=":"))
      stop(paste("No data found for:", pathogen_desc, "after filtering"))
    }

    report_progress("ANALYSIS", message=paste("Filtered data contains", nrow(mmwrdata_filtered), "records"))
  }

  pathDf <- PATH_ANALYSIS(mmwrdata_filtered, census, catchment_config)%>%as.data.frame()
  report_progress("ANALYSIS", message=paste("Processed",
                                            length(unique(pathDf$pathogen)),
                                            "pathogens"))

  bact <- pathDf

  report_progress("ANALYSIS", message="Post-processing pathogen data")

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

      stop(paste("No data found for:", pathogen_desc, "- see error file for details"))
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

    # Healthy People 2030 baseline period
    hp30<-IR_COMP_CATCH(catch, 2016, 2018,
                  paste0(outDir, "/", output_prefix, "_EstIRRCatch_2016_2018.csv"))

    if (requireNamespace("ggplot2", quietly = TRUE)) {
      tryCatch({
        if (exists("PLOT_SITE_TRENDS", mode = "function")) {
          site_plot <- PLOT_SITE_TRENDS(site, pathogen_name, outDir, opts$subgroup)
          ggsave(paste0(outDir, "/", output_prefix, "_site_trends.png"), site_plot,
                 width = 10, height = 8, dpi = 300)
        }

        if (exists("PLOT_OVERALL_TREND", mode = "function")) {
          overall_plot <- PLOT_OVERALL_TREND(catchir.linpred, pathogen_name, outDir, opts$subgroup)
          ggsave(paste0(outDir, "/", output_prefix, "_overall_trend.png"), overall_plot,
                 width = 10, height = 6, dpi = 300)
        }

        # Per-state individual trend charts
        if (exists("PLOT_STATE_TREND", mode = "function")) {
          for (st in unique(as.character(site$state))) {
            state_plot <- PLOT_STATE_TREND(site, st, pathogen_name, outDir, opts$subgroup)
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
