#!/usr/bin/env Rscript
################################################################################
# generate_dashboard.R - FoodNetTrends Results Dashboard Generator
#
# Purpose:
#   Reads all pipeline output files from a completed FoodNetTrends run, converts
#   CSV data to JSON and images to Base64, and assembles a single self-contained
#   HTML dashboard file.
#
# Usage:
#   Rscript generate_dashboard.R \
#     --output_dir output/20240115_143022/ \
#     --projID FNT-2024-0115 \
#     --output dashboard.html
#
# Dependencies: argparse, jsonlite, base64enc, dplyr, readr, tidyr
################################################################################

suppressPackageStartupMessages({
  library(argparse)
  library(jsonlite)
  library(base64enc)
  library(dplyr)
  library(readr)
  library(tidyr)
})

# --- Utility functions --------------------------------------------------------

msg <- function(...) {

  cat(paste0("[", format(Sys.time(), "%H:%M:%S"), "] ", ..., "\n"), file = stderr())
}

warn_missing <- function(path, label = NULL) {
 if (!file.exists(path)) {
    desc <- if (!is.null(label)) label else basename(path)
    msg("WARNING: ", desc, " not found: ", path)
    return(TRUE)
  }
  return(FALSE)
}

safe_read_csv <- function(path, label = NULL) {
  if (warn_missing(path, label)) return(NULL)
  tryCatch(
    read_csv(path, show_col_types = FALSE),
    error = function(e) {
      msg("WARNING: Error reading ", path, ": ", e$message)
      NULL
    }
  )
}

safe_readlines <- function(path, label = NULL) {
  if (warn_missing(path, label)) return(NULL)
  tryCatch(
    paste(readLines(path, warn = FALSE), collapse = "\n"),
    error = function(e) {
      msg("WARNING: Error reading ", path, ": ", e$message)
      NULL
    }
  )
}

encode_png_b64 <- function(path) {
  if (warn_missing(path)) return(NULL)
  tryCatch({
    raw_bytes <- readBin(path, "raw", file.info(path)$size)
    b64 <- base64encode(raw_bytes)
    paste0("data:image/png;base64,", b64)
  }, error = function(e) {
    msg("WARNING: Error encoding ", path, ": ", e$message)
    NULL
  })
}

# Escape text for safe JSON/HTML embedding
html_escape <- function(x) {
  if (is.null(x)) return("")
  x <- gsub("&", "&amp;", x)
  x <- gsub("<", "&lt;", x)
  x <- gsub(">", "&gt;", x)
  x
}

# --- FoodNet State Configuration ----------------------------------------------

STATE_INFO <- list(
  CA = list(name = "California",  joinYear = 1996),
  CO = list(name = "Colorado",    joinYear = 2001),
  CT = list(name = "Connecticut", joinYear = 1996),
  GA = list(name = "Georgia",     joinYear = 1996),
  MD = list(name = "Maryland",    joinYear = 1998),
  MN = list(name = "Minnesota",   joinYear = 1996),
  NM = list(name = "New Mexico",  joinYear = 2004),
  NY = list(name = "New York",    joinYear = 1998),
  OR = list(name = "Oregon",      joinYear = 1996),
  TN = list(name = "Tennessee",   joinYear = 2000)
)

# Pathogen display configuration with colors
PATHOGEN_COLORS <- list(
  CAMPYLOBACTER  = "#2e6da4",
  SALMONELLA     = "#c0392b",
  SHIGELLA       = "#8e44ad",
  STEC           = "#27ae60",
  VIBRIO         = "#3498db",
  YERSINIA       = "#f39c12",
  CYCLOSPORA     = "#1abc9c",
  CRYPTOSPORIDIUM = "#9b59b6",
  LISTERIA       = "#e67e22"
)

# Pathogens that may have subgroups
HIERARCHICAL_PATHOGENS <- c("SALMONELLA", "STEC")

# --- Argument parsing ---------------------------------------------------------

parser <- ArgumentParser(description = "Generate FoodNetTrends results dashboard")
parser$add_argument("--output_dir", type = "character", required = TRUE,
                    help = "Path to pipeline output directory")
parser$add_argument("--results_dir", default = NULL)
parser$add_argument("--preprocessed_dir", default = NULL)
parser$add_argument("--projID", type = "character", required = TRUE,
                    help = "Project ID string")
parser$add_argument("--output", type = "character", default = "dashboard.html",
                    help = "Output HTML file path (default: dashboard.html)")
parser$add_argument("--cleanFile", type = "character", default = NULL,
                    help = "Path to the clean_mmwr.csv file (optional; used to locate preprocessing metadata when data comes from a different run directory)")
parser$add_argument("--pipeline_params", type = "character", default = NULL,
                    help = "Path to JSON file with pipeline run parameters (for re-run command)")

opts <- tryCatch(parser$parse_args(), error = function(e) {
  msg("FATAL: Argument parsing failed: ", e$message)
  quit(status = 1)
})

output_dir <- normalizePath(opts$output_dir, mustWork = FALSE)
projID     <- opts$projID
output_file <- opts$output
clean_file_arg <- opts$cleanFile

if (!dir.exists(output_dir) && is.null(opts$results_dir)) {
  msg("FATAL: Output directory does not exist: ", output_dir)
  quit(status = 1)
}

msg("Starting dashboard generation for project: ", projID)
msg("Output directory: ", output_dir)

# --- File discovery -----------------------------------------------------------

msg("Discovering pipeline output files...")

preprocessed_dir <- if (is.null(opts$preprocessed_dir)) file.path(output_dir, "preprocessed") else opts$preprocessed_dir
spline_dir <- if (is.null(opts$results_dir)) file.path(output_dir, "spline_results") else opts$results_dir
pipeline_info_dir <- file.path(output_dir, "pipeline_info")

# Determine the source directory for preprocessing metadata.
# When --cleanFile is provided and points to a different run directory,
# fall back to the cleanFile's parent directory for metadata files.
alt_preprocessed_dir <- NULL
if (!is.null(clean_file_arg)) {
  alt_preprocessed_dir <- normalizePath(dirname(clean_file_arg), mustWork = FALSE)
  if (alt_preprocessed_dir == normalizePath(preprocessed_dir, mustWork = FALSE)) {
    alt_preprocessed_dir <- NULL
  } else {
    msg("Alternative preprocessed dir (from --cleanFile): ", alt_preprocessed_dir)
  }
}

# Helper: resolve a preprocessed file path, falling back to alt_preprocessed_dir
resolve_preproc_file <- function(filename) {
  primary <- file.path(preprocessed_dir, filename)
  if (file.exists(primary)) return(primary)
  if (!is.null(alt_preprocessed_dir)) {
    alt <- file.path(alt_preprocessed_dir, filename)
    if (file.exists(alt)) {
      msg("  Using fallback for ", filename, ": ", alt)
      return(alt)
    }
  }
  return(primary)  # Return primary (even if missing) so warn_missing reports it
}

# Preprocessed files
clean_mmwr_path <- if (!is.null(clean_file_arg)) clean_file_arg else resolve_preproc_file("clean_mmwr.csv")
preprocess_report_path <- resolve_preproc_file("clean_mmwr_preprocessing_report.csv")
resource_profile_path  <- resolve_preproc_file("resource_profile.csv")
resource_profile_subgroups_path <- resolve_preproc_file("resource_profile_subgroups.csv")
metadata_states_path   <- resolve_preproc_file("metadata_states.csv")
metadata_cidt_path     <- resolve_preproc_file("metadata_cidt.csv")
metadata_travel_path   <- resolve_preproc_file("metadata_travel.csv")

# Spline result files (glob)
ircatch_files <- if (dir.exists(spline_dir)) {
  f <- Sys.glob(file.path(spline_dir, "*_IRCatch.csv"))
  f[!grepl("_(domestic|travel)_IRCatch\\.csv$", f)]
} else character(0)

irsite_files <- if (dir.exists(spline_dir)) {
  f <- Sys.glob(file.path(spline_dir, "*_IRSite.csv"))
  f[!grepl("_(domestic|travel)_IRSite\\.csv$", f)]
} else character(0)

estirr_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_EstIRRCatch_*.csv"))
} else character(0)

summary_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_summary.txt"))
} else character(0)

error_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_error.txt"))
} else character(0)

overall_trend_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_overall_trend.png"))
} else character(0)

site_trends_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_site_trends.png"))
} else character(0)

# Travel-stratified result files
domestic_ircatch_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_domestic_IRCatch.csv"))
} else character(0)

travel_ircatch_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_travel_IRCatch.csv"))
} else character(0)

domestic_irsite_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_domestic_IRSite.csv"))
} else character(0)

travel_irsite_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_travel_IRSite.csv"))
} else character(0)

travel_comparison_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_travel_comparison.png"))
} else character(0)

travel_comparison_site_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_travel_comparison_site.png"))
} else character(0)

travel_fraction_files <- if (dir.exists(spline_dir)) {
  Sys.glob(file.path(spline_dir, "*_travel_fraction.png"))
} else character(0)

# Per-state individual trend plots (exclude overall_trend and site_trends)
state_trend_files <- if (dir.exists(spline_dir)) {
  all_trend_pngs <- Sys.glob(file.path(spline_dir, "*_trend.png"))
  all_trend_pngs[!grepl("_(overall_trend|site_trends)\\.png$", all_trend_pngs)]
} else character(0)

# Pipeline info files
execution_reports <- if (dir.exists(pipeline_info_dir)) {
  Sys.glob(file.path(pipeline_info_dir, "execution_*.html"))
} else character(0)

execution_traces <- if (dir.exists(pipeline_info_dir)) {
  Sys.glob(file.path(pipeline_info_dir, "execution_trace_*.txt"))
} else character(0)

pipeline_dags <- if (dir.exists(pipeline_info_dir)) {
  Sys.glob(file.path(pipeline_info_dir, "pipeline_dag_*.html"))
} else character(0)

has_travel_strat <- length(domestic_ircatch_files) > 0 && length(travel_ircatch_files) > 0

msg("Found: ", length(ircatch_files), " IRCatch, ",
    length(irsite_files), " IRSite, ",
    length(estirr_files), " EstIRR, ",
    length(overall_trend_files), " trend plots, ",
    length(error_files), " error files",
    if (has_travel_strat) paste0(", travel strat: ",
      length(domestic_ircatch_files), " domestic + ",
      length(travel_ircatch_files), " travel") else "")

# --- Pathogen/subgroup discovery ----------------------------------------------

msg("Identifying analysis units...")

# Use resource_profile.csv pathogen list as ground truth if available
resource_profile <- safe_read_csv(resource_profile_path, "resource_profile.csv")
resource_profile_subgroups <- safe_read_csv(resource_profile_subgroups_path, "resource_profile_subgroups.csv")
known_pathogens <- if (!is.null(resource_profile)) {
  unique(resource_profile$pathogen)
} else {
  # Fallback: derive from filenames
  NULL
}

# Parse analysis unit ID from filename
# Examples:
#   CAMPYLOBACTER_combined_IRCatch.csv -> pathogen=CAMPYLOBACTER, subgroup=combined
#   SALMONELLA_Enteritidis_IRCatch.csv -> pathogen=SALMONELLA, subgroup=Enteritidis
#   STEC_nonO157_IRCatch.csv -> pathogen=STEC, subgroup=nonO157
#   I_4__5__12_i_-_combined_IRCatch.csv -> pathogen=I_4__5__12_i_-, subgroup=combined
parse_analysis_id <- function(filename, suffix_pattern, known_pathogens = NULL) {
  # Remove directory and suffix
  base <- basename(filename)
  base <- sub(suffix_pattern, "", base)

  if (!is.null(known_pathogens)) {
    # Try matching against known pathogens (longest match first)
    sorted_pathogens <- known_pathogens[order(-nchar(known_pathogens))]
    for (p in sorted_pathogens) {
      prefix <- paste0(p, "_")
      if (startsWith(base, prefix)) {
        subgroup <- substring(base, nchar(prefix) + 1)
        if (nchar(subgroup) == 0) subgroup <- "combined"
        return(list(pathogen = p, subgroup = subgroup, id = paste0(p, "_", subgroup)))
      }
    }
  }

  # Fallback: try common pathogen names
  common_pathogens <- c("CAMPYLOBACTER", "SALMONELLA", "SHIGELLA", "STEC",
                         "VIBRIO", "YERSINIA", "CYCLOSPORA", "CRYPTOSPORIDIUM",
                         "LISTERIA")
  sorted_common <- common_pathogens[order(-nchar(common_pathogens))]
  for (p in sorted_common) {
    prefix <- paste0(p, "_")
    if (startsWith(base, prefix)) {
      subgroup <- substring(base, nchar(prefix) + 1)
      if (nchar(subgroup) == 0) subgroup <- "combined"
      return(list(pathogen = p, subgroup = subgroup, id = paste0(p, "_", subgroup)))
    }
  }

  # Last resort: split at first underscore
  parts <- strsplit(base, "_", fixed = TRUE)[[1]]
  if (length(parts) >= 2) {
    return(list(pathogen = parts[1], subgroup = paste(parts[-1], collapse = "_"),
                id = base))
  }
  return(list(pathogen = base, subgroup = "combined", id = paste0(base, "_combined")))
}

# Discover all analysis units from IRCatch and error files
all_analysis_files <- c(ircatch_files, error_files)
analysis_ids <- list()

for (f in all_analysis_files) {
  suffix <- if (grepl("_IRCatch\\.csv$", f)) {
    "_IRCatch\\.csv$"
  } else if (grepl("_error\\.txt$", f)) {
    "_error\\.txt$"
  } else next

  parsed <- parse_analysis_id(f, suffix, known_pathogens)
  if (!parsed$id %in% names(analysis_ids)) {
    analysis_ids[[parsed$id]] <- parsed
  }
}

msg("Identified ", length(analysis_ids), " analysis units: ",
    paste(names(analysis_ids), collapse = ", "))

# --- Data ingestion -----------------------------------------------------------

msg("Reading preprocessed data...")

preprocess_report  <- safe_read_csv(preprocess_report_path, "preprocessing report")
metadata_states    <- safe_read_csv(metadata_states_path, "state metadata")
metadata_cidt      <- safe_read_csv(metadata_cidt_path, "CIDT metadata")
metadata_travel    <- safe_read_csv(metadata_travel_path, "travel metadata")

# --- clean_mmwr summary (do NOT embed the full file) -------------------------

msg("Summarizing clean_mmwr.csv...")

clean_mmwr_summary <- list(
  total_rows = 0,
  year_range = c(NA, NA),
  by_pathogen = NULL,
  by_state = NULL,
  crosstab = NULL,
  file_exists = FALSE
)

if (!warn_missing(clean_mmwr_path, "clean_mmwr.csv")) {
  tryCatch({
    # Read in chunks if very large; for summary we need all rows
    clean_data <- read_csv(clean_mmwr_path, show_col_types = FALSE)
    names(clean_data) <- tolower(names(clean_data))

    clean_mmwr_summary$total_rows <- nrow(clean_data)
    clean_mmwr_summary$file_exists <- TRUE

    if ("year" %in% names(clean_data)) {
      clean_mmwr_summary$year_range <- range(clean_data$year, na.rm = TRUE)
    }

    if ("pathogen" %in% names(clean_data)) {
      clean_mmwr_summary$by_pathogen <- clean_data %>%
        count(pathogen) %>%
        arrange(desc(n)) %>%
        as.data.frame()
    }

    if ("state" %in% names(clean_data)) {
      clean_mmwr_summary$by_state <- clean_data %>%
        count(state) %>%
        arrange(desc(n)) %>%
        as.data.frame()
    }

    if (all(c("pathogen", "year") %in% names(clean_data))) {
      clean_mmwr_summary$crosstab <- clean_data %>%
        count(pathogen, year) %>%
        pivot_wider(names_from = year, values_from = n, values_fill = 0) %>%
        as.data.frame()
    }

    rm(clean_data)
    gc(verbose = FALSE)
    msg("clean_mmwr summary: ", clean_mmwr_summary$total_rows, " rows, years ",
        clean_mmwr_summary$year_range[1], "-", clean_mmwr_summary$year_range[2])
  }, error = function(e) {
    msg("WARNING: Error summarizing clean_mmwr.csv: ", e$message)
  })
}

# --- Per-analysis data ingestion ----------------------------------------------

msg("Reading per-analysis spline results...")

analyses_data <- list()

for (aid in names(analysis_ids)) {
  info <- analysis_ids[[aid]]
  prefix <- file.path(spline_dir, paste0(info$pathogen, "_", info$subgroup))

  entry <- list(
    pathogen = info$pathogen,
    subgroup = info$subgroup,
    id = aid,
    status = "unknown",
    diagnostics = list(),
    convergence_status = "Not assessed",
    settings = NULL,
    color = ifelse(info$pathogen %in% names(PATHOGEN_COLORS),
                   PATHOGEN_COLORS[[info$pathogen]], "#666666"),
    has_subgroups = info$pathogen %in% HIERARCHICAL_PATHOGENS,
    ircatch = NULL,
    irsite = NULL,
    domestic_ircatch = NULL,
    travel_ircatch = NULL,
    domestic_irsite = NULL,
    travel_irsite = NULL,
    irr = list(),
    summary_txt = NULL,
    error_txt = NULL,
    overall_trend_b64 = NULL,
    site_trends_b64 = NULL,
    travel_comparison_b64 = NULL,
    travel_comparison_site_b64 = NULL,
    travel_fraction_b64 = NULL,
    state_plots = list()
  )

  # Check for error file
  error_path <- paste0(prefix, "_error.txt")
  if (file.exists(error_path)) {
    entry$error_txt <- safe_readlines(error_path)
    entry$status <- "failed"
  }

  # Read IRCatch
  ircatch_path <- paste0(prefix, "_IRCatch.csv")
  if (file.exists(ircatch_path)) {
    entry$ircatch <- safe_read_csv(ircatch_path)
    if (is.null(entry$error_txt) && !is.null(entry$ircatch)) entry$status <- "success"
  }

  for (stratum in c("all", "domestic", "travel")) {
    diag_path <- paste0(prefix, if (stratum == "all") "" else paste0("_", stratum), "_convergence_diagnostics.csv")
    if (file.exists(diag_path)) entry$diagnostics[[stratum]] <- safe_read_csv(diag_path)
  }
  diag <- entry$diagnostics$all
  if (!is.null(diag) && nrow(diag)) {
    entry$convergence_status <- if (!isTRUE(diag$converged[1])) "Not converged" else
      if (!is.na(diag$warnings[1]) && nzchar(diag$warnings[1])) "Review diagnostics" else "Converged"
  }
  settings_path <- paste0(prefix, "_analysis_settings.csv")
  if (file.exists(settings_path)) {
    entry$settings <- safe_read_csv(settings_path)
    if (!is.null(entry$settings) && "subgroup" %in% names(entry$settings) && nrow(entry$settings))
      entry$subgroup <- entry$settings$subgroup[1]
  }

  # Read IRSite
  irsite_path <- paste0(prefix, "_IRSite.csv")
  if (file.exists(irsite_path)) {
    entry$irsite <- safe_read_csv(irsite_path)
  }

  # Read travel-stratified IR files
  domestic_ircatch_path <- paste0(prefix, "_domestic_IRCatch.csv")
  if (file.exists(domestic_ircatch_path)) {
    entry$domestic_ircatch <- safe_read_csv(domestic_ircatch_path)
  }

  travel_ircatch_path <- paste0(prefix, "_travel_IRCatch.csv")
  if (file.exists(travel_ircatch_path)) {
    entry$travel_ircatch <- safe_read_csv(travel_ircatch_path)
  }

  domestic_irsite_path <- paste0(prefix, "_domestic_IRSite.csv")
  if (file.exists(domestic_irsite_path)) {
    entry$domestic_irsite <- safe_read_csv(domestic_irsite_path)
  }

  travel_irsite_path <- paste0(prefix, "_travel_IRSite.csv")
  if (file.exists(travel_irsite_path)) {
    entry$travel_irsite <- safe_read_csv(travel_irsite_path)
  }

  # Read EstIRRCatch files (may be multiple comparison periods)
  irr_pattern <- paste0(prefix, "_EstIRRCatch_")
  matching_irr <- estirr_files[startsWith(estirr_files, irr_pattern)]
  for (irr_file in matching_irr) {
    # Extract comparison period from filename, e.g., _EstIRRCatch_2016_2018.csv
    period <- sub(".*_EstIRRCatch_", "", basename(irr_file))
    period <- sub("\\.csv$", "", period)
    entry$irr[[period]] <- safe_read_csv(irr_file)
  }

  # Read summary.txt
  summary_path <- paste0(prefix, "_summary.txt")
  if (file.exists(summary_path)) {
    entry$summary_txt <- safe_readlines(summary_path)
  }

  # Encode trend PNGs
  overall_png <- paste0(prefix, "_overall_trend.png")
  if (file.exists(overall_png)) {
    entry$overall_trend_b64 <- encode_png_b64(overall_png)
  }

  site_png <- paste0(prefix, "_site_trends.png")
  if (file.exists(site_png)) {
    entry$site_trends_b64 <- encode_png_b64(site_png)
  }

  # Encode travel comparison PNGs
  travel_comp_png <- paste0(prefix, "_travel_comparison.png")
  if (file.exists(travel_comp_png)) {
    entry$travel_comparison_b64 <- encode_png_b64(travel_comp_png)
  }

  travel_comp_site_png <- paste0(prefix, "_travel_comparison_site.png")
  if (file.exists(travel_comp_site_png)) {
    entry$travel_comparison_site_b64 <- encode_png_b64(travel_comp_site_png)
  }

  travel_frac_png <- paste0(prefix, "_travel_fraction.png")
  if (file.exists(travel_frac_png)) {
    entry$travel_fraction_b64 <- encode_png_b64(travel_frac_png)
  }

  # Encode per-state trend PNGs
  state_plot_prefix <- paste0(prefix, "_")
  matching_state_pngs <- state_trend_files[startsWith(state_trend_files, state_plot_prefix)]
  for (sp_file in matching_state_pngs) {
    sp_base <- sub("_trend\\.png$", "", basename(sp_file))
    state_code <- sub(paste0(".*", info$pathogen, "_", info$subgroup, "_"), "", sp_base)
    if (nchar(state_code) > 0 && nchar(state_code) <= 3) {
      entry$state_plots[[state_code]] <- encode_png_b64(sp_file)
    }
  }

  # Set status if we only have error
  if (entry$status == "unknown") {
    entry$status <- "no_data"
  }

  analyses_data[[aid]] <- entry
  msg("  ", aid, ": status=", entry$status,
      if (!is.null(entry$ircatch)) paste0(", ", nrow(entry$ircatch), " IRCatch rows") else "",
      if (!is.null(entry$irsite)) paste0(", ", nrow(entry$irsite), " IRSite rows") else "")
}

# --- Build state view data ----------------------------------------------------

msg("Building state view aggregations...")

# Collect all states from IRSite data across all analyses
all_states <- character(0)
for (aid in names(analyses_data)) {
  if (!is.null(analyses_data[[aid]]$irsite) && "state" %in% names(analyses_data[[aid]]$irsite)) {
    all_states <- union(all_states, unique(analyses_data[[aid]]$irsite$state))
  }
}
all_states <- sort(all_states)

states_data <- list()
for (st in all_states) {
  si <- if (st %in% names(STATE_INFO)) STATE_INFO[[st]] else list(name = st, joinYear = NA)

  # Aggregate IRSite data for this state from all analysis units
  state_irsite <- list()
  for (aid in names(analyses_data)) {
    entry <- analyses_data[[aid]]
    if (!is.null(entry$irsite) && "state" %in% names(entry$irsite)) {
      rows <- entry$irsite %>% filter(state == st)
      if (nrow(rows) > 0) {
        state_irsite[[aid]] <- rows %>% as.data.frame()
      }
    }
  }

  # Collect per-state trend plots for this state
  state_trend_plots <- list()
  for (aid in names(analyses_data)) {
    e <- analyses_data[[aid]]
    if (length(e$state_plots) > 0 && st %in% names(e$state_plots)) {
      state_trend_plots[[aid]] <- e$state_plots[[st]]
    }
  }

  states_data[[st]] <- list(
    code = st,
    name = si$name,
    joinYear = si$joinYear,
    irsite_by_analysis = state_irsite,
    state_trend_plots = state_trend_plots
  )
}

msg("Built state views for ", length(states_data), " states: ",
    paste(names(states_data), collapse = ", "))

# --- Pipeline info discovery --------------------------------------------------

msg("Collecting pipeline info...")

pipeline_info <- list(
  execution_reports = basename(execution_reports),
  execution_traces = basename(execution_traces),
  pipeline_dags = basename(pipeline_dags),
  trace_data = NULL
)

# Read execution trace if available
if (length(execution_traces) > 0) {
  tryCatch({
    trace_df <- read.delim(execution_traces[1], sep = "\t", stringsAsFactors = FALSE,
                           check.names = FALSE)
    # Keep only key columns for display
    keep_cols <- intersect(names(trace_df),
                           c("task_id", "name", "status", "cpus", "memory",
                             "realtime", "%cpu", "peak_rss", "hash"))
    if (length(keep_cols) > 0) {
      pipeline_info$trace_data <- trace_df[, keep_cols, drop = FALSE] %>% as.data.frame()
    }
  }, error = function(e) {
    msg("WARNING: Error reading execution trace: ", e$message)
  })
}

# --- JSON serialization -------------------------------------------------------

msg("Building dashboard data object...")

# Helper to convert data frame to JSON-safe list
df_to_list <- function(df) {
  if (is.null(df)) return(NULL)
  as.data.frame(df)
}

# Compute summary statistics
n_analyses <- length(analyses_data)
if (n_analyses == 0) {
  stop("No analysis results found in ", file.path(output_dir, "spline_results"),
       ". Check that TRENDY outputs are published to the expected directory.")
}
n_success  <- sum(vapply(analyses_data, function(x) x$status == "success", logical(1)))
n_failed   <- sum(vapply(analyses_data, function(x) x$status == "failed", logical(1)))
unique_pathogens <- unique(vapply(analyses_data, function(x) x$pathogen, character(1)))

# Determine year range from IRCatch data
all_years <- c()
for (aid in names(analyses_data)) {
  if (!is.null(analyses_data[[aid]]$ircatch) && "year" %in% names(analyses_data[[aid]]$ircatch)) {
    all_years <- c(all_years, analyses_data[[aid]]$ircatch$year)
  }
}
year_range <- if (length(all_years) > 0) range(all_years, na.rm = TRUE) else c(NA, NA)

# Build the main data object
dashboard_data <- list(
  metadata = c(list(
    projID = projID,
    generated = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
    output_dir = output_dir,
    n_analyses = n_analyses,
    n_success = n_success,
    n_failed = n_failed,
    n_pathogens = length(unique_pathogens),
    n_states = length(all_states),
    year_range = year_range,
    pathogens = unique_pathogens
  ), if (!is.null(opts$pipeline_params) && file.exists(opts$pipeline_params)) {
    tryCatch(fromJSON(opts$pipeline_params), error = function(e) list())
  } else list()),

  preprocessing = list(
    report = df_to_list(preprocess_report),
    resource_profile = df_to_list(resource_profile),
    resource_profile_subgroups = df_to_list(resource_profile_subgroups),
    metadata_states = df_to_list(metadata_states),
    metadata_cidt = df_to_list(metadata_cidt),
    metadata_travel = df_to_list(metadata_travel)
  ),

  clean_mmwr_summary = list(
    total_rows = clean_mmwr_summary$total_rows,
    year_range = clean_mmwr_summary$year_range,
    by_pathogen = df_to_list(clean_mmwr_summary$by_pathogen),
    by_state = df_to_list(clean_mmwr_summary$by_state),
    crosstab = df_to_list(clean_mmwr_summary$crosstab),
    file_exists = clean_mmwr_summary$file_exists
  ),

  analyses = lapply(analyses_data, function(entry) {
    list(
      pathogen = entry$pathogen,
      subgroup = entry$subgroup,
      id = entry$id,
      status = entry$status,
      convergence_status = entry$convergence_status,
      diagnostics = lapply(entry$diagnostics, df_to_list),
      settings = df_to_list(entry$settings),
      color = entry$color,
      has_subgroups = entry$has_subgroups,
      ircatch = df_to_list(entry$ircatch),
      irsite = df_to_list(entry$irsite),
      domestic_ircatch = df_to_list(entry$domestic_ircatch),
      travel_ircatch = df_to_list(entry$travel_ircatch),
      domestic_irsite = df_to_list(entry$domestic_irsite),
      travel_irsite = df_to_list(entry$travel_irsite),
      irr = lapply(entry$irr, df_to_list),
      summary_txt = entry$summary_txt,
      error_txt = entry$error_txt,
      overall_trend_b64 = entry$overall_trend_b64,
      site_trends_b64 = entry$site_trends_b64,
      travel_comparison_b64 = entry$travel_comparison_b64,
      travel_comparison_site_b64 = entry$travel_comparison_site_b64,
      travel_fraction_b64 = entry$travel_fraction_b64,
      state_plots = entry$state_plots
    )
  }),

  states = lapply(states_data, function(s) {
    list(
      code = s$code,
      name = s$name,
      joinYear = s$joinYear,
      irsite_by_analysis = lapply(s$irsite_by_analysis, df_to_list),
      state_trend_plots = s$state_trend_plots
    )
  }),

  state_info = lapply(STATE_INFO, function(si) {
    list(name = si$name, joinYear = si$joinYear)
  }),

  has_travel_strat = has_travel_strat,
  pathogen_colors = PATHOGEN_COLORS,
  hierarchical_pathogens = HIERARCHICAL_PATHOGENS,

  pipeline_info = list(
    execution_reports = pipeline_info$execution_reports,
    execution_traces = pipeline_info$execution_traces,
    pipeline_dags = pipeline_info$pipeline_dags,
    trace_data = df_to_list(pipeline_info$trace_data)
  )
)

# Serialize to JSON
msg("Serializing to JSON...")
json_str <- toJSON(dashboard_data, auto_unbox = TRUE, pretty = FALSE,
                   na = "null", null = "null", digits = 6)
# JSON strings can contain HTML closing tags; keep them inert inside the script element.
json_str <- gsub("<", "\\u003c", json_str, fixed = TRUE)
msg("JSON size: ", format(nchar(json_str), big.mark = ","), " characters")

# --- Template assembly --------------------------------------------------------

msg("Assembling dashboard HTML...")

# Locate template
script_dir <- tryCatch({
  script_path <- commandArgs(trailingOnly = FALSE)
  script_path <- sub("--file=", "", script_path[grep("--file=", script_path)])
  dirname(script_path)
}, error = function(e) {
  "."
})

# Try to find template.html
template_paths <- c(
  file.path(script_dir, "template.html"),
  file.path(dirname(output_dir), "dashboard", "template.html"),
  file.path(getwd(), "dashboard", "template.html"),
  file.path(getwd(), "template.html")
)

template_path <- NULL
for (tp in template_paths) {
  if (file.exists(tp)) {
    template_path <- tp
    break
  }
}

if (is.null(template_path)) {
  msg("FATAL: Cannot find template.html. Searched: ", paste(template_paths, collapse = ", "))
  quit(status = 1)
}

msg("Using template: ", template_path)
template <- paste(readLines(template_path, warn = FALSE), collapse = "\n")

# Try to load vendored JS/CSS libraries
lib_dir <- file.path(dirname(template_path), "lib")

load_vendored <- function(filename) {
  path <- file.path(lib_dir, filename)
  if (file.exists(path)) {
    msg("  Inlining vendored: ", filename)
    paste(readLines(path, warn = FALSE), collapse = "\n")
  } else {
    msg("  Vendored file not found: ", filename, " (using fallback)")
    ""
  }
}

tabulator_js  <- load_vendored("tabulator.min.js")
tabulator_css <- load_vendored("tabulator.min.css")
medium_zoom_js <- load_vendored("medium-zoom.min.js")

# Perform token substitution
template <- gsub("{{DASHBOARD_DATA_JSON}}", json_str, template, fixed = TRUE)
template <- gsub("{{PROJ_ID}}", projID, template, fixed = TRUE)
template <- gsub("{{GENERATED_TIMESTAMP}}", format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), template, fixed = TRUE)
template <- gsub("{{TABULATOR_JS}}", tabulator_js, template, fixed = TRUE)
template <- gsub("{{TABULATOR_CSS}}", tabulator_css, template, fixed = TRUE)
template <- gsub("{{MEDIUM_ZOOM_JS}}", medium_zoom_js, template, fixed = TRUE)

# --- Write output -------------------------------------------------------------

msg("Writing dashboard to: ", output_file)
writeLines(template, output_file, useBytes = TRUE)

final_size <- file.info(output_file)$size
msg("Dashboard generated successfully!")
msg("  File: ", output_file)
msg("  Size: ", format(final_size, big.mark = ","), " bytes (",
    round(final_size / 1024 / 1024, 1), " MB)")
msg("  Analyses: ", n_analyses, " (", n_success, " success, ", n_failed, " failed)")
msg("  States: ", length(all_states))
