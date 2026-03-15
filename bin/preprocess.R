#!/usr/bin/env Rscript
# preprocess.R - Clean raw MMWR SAS data for downstream Bayesian modeling
# Standardizes pathogen names, recodes serotypes, and writes a cleaned CSV.

suppressPackageStartupMessages(library("argparse"))
suppressPackageStartupMessages(library("dplyr"))
suppressPackageStartupMessages(library("haven"))
suppressPackageStartupMessages(library("gtools"))
# stringdist is optional - used for fuzzy pathogen matching if available
if (requireNamespace("stringdist", quietly = TRUE)) {
  suppressPackageStartupMessages(library("stringdist"))
}

parser <- ArgumentParser()
parser$add_argument("--mmwrFile", type = "character", help = "Path to the raw MMWR SAS file", required = TRUE)
parser$add_argument("--outputFile", type = "character", help = "Path to save the cleaned CSV file", required = TRUE)
parser$add_argument("--serotype-config", type = "character", help = "Path to CSV file with serotype recoding rules (optional)", required = FALSE, default = NULL)
parser$add_argument("--matching-sensitivity", type = "character", help = "Pathogen matching sensitivity: STRICT, MEDIUM, RELAXED (default: MEDIUM)",
                    required = FALSE, default = "MEDIUM", choices = c("STRICT", "MEDIUM", "RELAXED"))
args <- parser$parse_args()

# Return default serotype recoding rules or read from CSV
read_serotype_config <- function(config_path = NULL) {
  if (is.null(config_path)) {
    return(data.frame(
      serotype_value = c("NOT SPECIATED", "UNKNOWN", "PARTIAL SERO", "NOT SERO", "", "UNDET"),
      replacement = c("Missing", "Missing", "Missing", "Missing", "Missing", "Missing"),
      pathogen = rep("all", 6),
      match_type = c("exact", "exact", "exact", "exact", "exact", "contains"),
      stringsAsFactors = FALSE
    ))
  }
  config <- read.csv(config_path, stringsAsFactors = FALSE)
  validate_serotype_config(config)
  return(config)
}

# Validate serotype config structure
validate_serotype_config <- function(config) {
  required_cols <- c("serotype_value", "replacement", "pathogen", "match_type")
  missing_cols <- setdiff(required_cols, names(config))
  if (length(missing_cols) > 0) {
    stop("Missing required columns in serotype config: ", paste(missing_cols, collapse = ", "))
  }
  valid_match_types <- c("exact", "contains")
  invalid_types <- setdiff(unique(config$match_type), valid_match_types)
  if (length(invalid_types) > 0) {
    stop("Invalid match_type values: ", paste(invalid_types, collapse = ", "))
  }
}

# Apply serotype recoding rules (exact first, then pattern matches)
apply_serotype_config <- function(data, config) {
  data$sero2 <- data$sero1

  exact_rules <- config[config$match_type == "exact", ]
  for (i in seq_len(nrow(exact_rules))) {
    if (exact_rules$pathogen[i] == "all") {
      data$sero2[data$sero1 == exact_rules$serotype_value[i]] <- exact_rules$replacement[i]
    } else {
      mask <- (data$sero1 == exact_rules$serotype_value[i]) & (data$pathogen == exact_rules$pathogen[i])
      data$sero2[mask] <- exact_rules$replacement[i]
    }
  }

  pattern_rules <- config[config$match_type == "contains", ]
  for (i in seq_len(nrow(pattern_rules))) {
    if (pattern_rules$pathogen[i] == "all") {
      data$sero2[grepl(pattern_rules$serotype_value[i], data$sero2)] <- pattern_rules$replacement[i]
    } else {
      mask <- grepl(pattern_rules$serotype_value[i], data$sero2) & (data$pathogen == pattern_rules$pathogen[i])
      data$sero2[mask] <- pattern_rules$replacement[i]
    }
  }

  return(data)
}

# Known pathogen name patterns for standardization
get_pathogen_patterns <- function() {
  list(
    SALMONELLA = list(
      exact = c("SALMONELLA"),
      prefix = c("^SAL", "^S\\.", "^S "),
      contains = c("SALMONELLA", "SALMONEL")
    ),
    CAMPYLOBACTER = list(
      exact = c("CAMPYLOBACTER"),
      prefix = c("^CAMP", "^C\\.", "^C "),
      contains = c("CAMPYLOBACTER", "CAMPY")
    ),
    SHIGELLA = list(
      exact = c("SHIGELLA"),
      prefix = c("^SHIG"),
      contains = c("SHIGELL", "SHIGELA")
    ),
    LISTERIA = list(
      exact = c("LISTERIA"),
      prefix = c("^LIST", "^L\\.", "^L "),
      contains = c("LISTERIA")
    ),
    STEC = list(
      exact = c("STEC", "E. COLI O157:H7"),
      prefix = c("^STEC", "^E.*COLI", "^ECOLI"),
      contains = c("E.*COLI.*O157", "STEC")
    ),
    VIBRIO = list(
      exact = c("VIBRIO"),
      prefix = c("^VIB", "^V\\.", "^V "),
      contains = c("VIBRIO")
    ),
    YERSINIA = list(
      exact = c("YERSINIA"),
      prefix = c("^YERS", "^Y\\.", "^Y "),
      contains = c("YERSINIA")
    ),
    CYCLOSPORA = list(
      exact = c("CYCLOSPORA"),
      prefix = c("^CYCL", "^CYC"),
      contains = c("CYCLOSPORA", "CYCLO")
    ),
    CRYPTOSPORIDIUM = list(
      exact = c("CRYPTOSPORIDIUM"),
      prefix = c("^CRYP"),
      contains = c("CRYPTOSPORID", "CRYPTO")
    )
  )
}

# Matching sensitivity: STRICT (exact only), MEDIUM (+ prefix + fuzzy d=1), RELAXED (all methods)
get_matching_settings <- function(sensitivity) {
  settings <- list(
    STRICT = list(
      use_exact = TRUE,
      use_prefix = FALSE,
      use_contains = FALSE,
      use_fuzzy = FALSE,
      fuzzy_distance = 0,
      confidence_threshold = 95
    ),
    MEDIUM = list(
      use_exact = TRUE,
      use_prefix = TRUE,
      use_contains = FALSE,
      use_fuzzy = TRUE,
      fuzzy_distance = 1,
      confidence_threshold = 80
    ),
    RELAXED = list(
      use_exact = TRUE,
      use_prefix = TRUE,
      use_contains = TRUE,
      use_fuzzy = TRUE,
      fuzzy_distance = 2,
      confidence_threshold = 70
    )
  )
  return(settings[[sensitivity]])
}

# Map raw pathogen names to canonical forms using configurable matching
standardize_pathogens <- function(data, sensitivity = "MEDIUM") {
  cat("Standardizing pathogen names with", sensitivity, "sensitivity\n")

  settings <- get_matching_settings(sensitivity)
  patterns <- get_pathogen_patterns()

  data$pathogen_original <- data$pathogen

  standardization_log <- list()

  unique_pathogens <- unique(data$pathogen)

  for (orig_value in unique_pathogens) {
    orig_upper <- toupper(trimws(orig_value))
    matched <- FALSE
    match_info <- list(
      original = orig_value,
      standardized = NA,
      match_type = "no_match",
      confidence = 0,
      count = sum(data$pathogen == orig_value)
    )

    if (settings$use_exact && !matched) {
      for (pathogen in names(patterns)) {
        if (orig_upper %in% patterns[[pathogen]]$exact) {
          data$pathogen[data$pathogen == orig_value] <- pathogen
          match_info$standardized <- pathogen
          match_info$match_type <- "exact"
          match_info$confidence <- 100
          matched <- TRUE
          break
        }
      }
    }

    if (settings$use_prefix && !matched) {
      for (pathogen in names(patterns)) {
        for (pattern in patterns[[pathogen]]$prefix) {
          if (grepl(pattern, orig_upper)) {
            data$pathogen[data$pathogen == orig_value] <- pathogen
            match_info$standardized <- pathogen
            match_info$match_type <- "prefix"
            match_info$confidence <- 90
            matched <- TRUE
            break
          }
        }
        if (matched) break
      }
    }

    if (settings$use_contains && !matched) {
      for (pathogen in names(patterns)) {
        for (pattern in patterns[[pathogen]]$contains) {
          if (grepl(pattern, orig_upper)) {
            data$pathogen[data$pathogen == orig_value] <- pathogen
            match_info$standardized <- pathogen
            match_info$match_type <- "contains"
            match_info$confidence <- 80
            matched <- TRUE
            break
          }
        }
        if (matched) break
      }
    }

    if (settings$use_fuzzy && !matched) {
      if (requireNamespace("stringdist", quietly = TRUE)) {
        known_pathogens <- names(patterns)
        distances <- stringdist::stringdist(orig_upper, known_pathogens, method = "lv")
        min_dist <- min(distances)

        if (min_dist <= settings$fuzzy_distance) {
          best_match <- known_pathogens[which.min(distances)]
          data$pathogen[data$pathogen == orig_value] <- best_match
          match_info$standardized <- best_match
          match_info$match_type <- paste0("fuzzy_d", min_dist)
          match_info$confidence <- 100 - (min_dist * 10)
          matched <- TRUE
        }
      }
    }

    if (!matched) {
      match_info$standardized <- orig_value
      match_info$match_type <- "no_match"
      match_info$confidence <- 0
    }

    standardization_log[[orig_value]] <- match_info
  }

  report <- do.call(rbind, lapply(standardization_log, as.data.frame, stringsAsFactors = FALSE))
  report <- report[order(report$standardized, -report$count), ]

  return(list(data = data, report = report))
}

# --- Data Loading ---
cat("Loading raw MMWR data from:", args$mmwrFile, "\n")
mmwrdata <- haven::read_sas(args$mmwrFile) %>%
  as.data.frame()

mmwrdata <- mmwrdata %>% rename_all(tolower)

# Exclude COEX pre-2023; Colorado expanded to full state in 2023
mmwrdata <- mmwrdata %>%
  filter(!(siteid == "COEX" & year < 2023))

# --- Pathogen Standardization ---
standardization_result <- standardize_pathogens(mmwrdata, sensitivity = args$matching_sensitivity)
mmwrdata <- standardization_result$data

report_file <- sub("\\.csv$", "_preprocessing_report.csv", args$outputFile)
write.csv(standardization_result$report, file = report_file, row.names = FALSE)
cat("Pathogen standardization report saved to:", report_file, "\n")

# --- Serotype Recoding ---
serotype_config <- read_serotype_config(args$serotype_config)
if (!is.null(args$serotype_config)) {
  cat("Using serotype configuration from:", args$serotype_config, "\n")
} else {
  cat("Using default serotype configuration\n")
}

mmwrdata <- apply_serotype_config(mmwrdata, serotype_config)

mmwrdata$serotypesummary <- mmwrdata$sero2

# --- County Name Standardization ---
mmwrdata <- mmwrdata %>%
  mutate(
    county = if_else(county %in% c("ST. MARYS'S", "ST. MARYS"), "ST. MARY'S", county),
    county = if_else(county == "PRINCE GEORGES", "PRINCE GEORGE'S", county),
    county = if_else(county == "QUEEN ANNES", "QUEEN ANNE'S", county),
    county = if_else(county == "DE BACA", "DEBACA", county)
  )

# --- STEC Processing ---
if("STEC" %in% unique(mmwrdata$pathogen)) {
  if("stec_class" %in% names(mmwrdata)) {
    cat("STEC data found with stec_class information available for grouping.\n")
  } else {
    cat("Warning: STEC found but stec_class column not present. STEC grouping options will be limited.\n")
  }
}

# Listeria: keep only CSTE-reportable (invasive) cases
if("LISTERIA" %in% unique(mmwrdata$pathogen)) {
  if("cste" %in% names(mmwrdata)) {
    mmwrdata <- mmwrdata %>%
      filter(!(pathogen == "LISTERIA" & cste != "YES"))
    cat("Filtered Listeria cases to CSTE-reportable only.\n")
  } else {
    cat("Warning: LISTERIA found but cste column not present. Including all LISTERIA cases.\n")
  }
}

# --- Derived Columns ---
# CRYPTOSPORIDIUM and CYCLOSPORA are parasitic; all others bacterial
if(!"pathogentype" %in% names(mmwrdata)) {
  mmwrdata <- mmwrdata %>%
    mutate(pathogentype = ifelse(pathogen %in% c("CRYPTOSPORIDIUM", "CYCLOSPORA"), "Parasitic", "Bacterial"))
}

# --- Write Output ---
cat("Writing cleaned data to:", args$outputFile, "\n")
write.csv(mmwrdata, file = args$outputFile, row.names = FALSE)
cat("Data cleaning complete. Cleaned data saved to:", args$outputFile, "\n")
