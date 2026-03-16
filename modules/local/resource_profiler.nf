process RESOURCE_PROFILER {
    tag "Profiling resources for pathogen analysis"
    label 'process_low'
    shell "/bin/bash"
    container 'foodnet.sif'

    publishDir "${params.outdir}/${params.projID}/preprocessed", mode: 'copy'

    input:
    path cleanFile

    output:
    path "resource_profile.csv", emit: profile
    path "resource_profile_subgroups.csv", emit: subgroup_profile
    path "metadata_states.csv", emit: states_metadata
    path "metadata_cidt.csv", emit: cidt_metadata
    path "metadata_travel.csv", emit: travel_metadata

    script:
    """
    #!/usr/bin/env Rscript
    suppressPackageStartupMessages({
        library(dplyr)
        library(readr)
        library(tidyr)
    })

    # Read the cleaned data
    data <- read_csv("${cleanFile}", show_col_types = FALSE)
    
    # Ensure column names are lowercase (matching preprocess.R output)
    names(data) <- tolower(names(data))
    
    # Debug: Print column names and first few rows
    cat("\\nColumn names:", paste(names(data), collapse=", "), "\\n")
    cat("Number of rows:", nrow(data), "\\n")
    if (nrow(data) > 0) {
        cat("First few pathogens:", paste(head(unique(data\$pathogen), 10), collapse=", "), "\\n")
    }
    
    # Calculate metrics for each pathogen
    pathogen_metrics <- data %>%
        filter(!is.na(pathogen)) %>%  # Filter out NA values only
        group_by(pathogen) %>%
        summarise(
            rows = n(),
            sites = n_distinct(state),
            years = n_distinct(year),
            .groups = 'drop'
        ) %>%
        mutate(
            # Complexity score: rows * sites * years
            complexity = rows * sites * years,
            # Data size category for logging
            size_category = case_when(
                rows > 50000 ~ "extra_large",
                rows > 20000 ~ "large",
                rows > 10000 ~ "medium",
                rows > 5000 ~ "small",
                TRUE ~ "tiny"
            )
        )

    # Aggregate to state x year level for posterior difficulty metrics.
    # These capture properties that drive MCMC convergence difficulty:
    # sparsity, overdispersion, and cross-state variation.
    state_year_counts <- data %>%
        filter(!is.na(pathogen)) %>%
        group_by(pathogen, state, year) %>%
        summarise(count = n(), .groups = 'drop')

    difficulty_metrics <- state_year_counts %>%
        group_by(pathogen) %>%
        summarise(
            zero_frac = sum(count == 0) / n(),
            sparse_cells = sum(count < 5) / n(),
            overdispersion = ifelse(mean(count) > 0, var(count) / mean(count), 0),
            state_cv = ifelse(
                mean(count) > 0,
                sd(tapply(count, state, mean)) / mean(count),
                0
            ),
            .groups = 'drop'
        ) %>%
        mutate(
            difficulty = 2.0 * zero_frac +
                         1.5 * sparse_cells +
                         1.0 * pmin(overdispersion / 100, 2) +
                         0.5 * pmin(state_cv, 2),
            difficulty_category = case_when(
                difficulty >= 4.5 ~ "very_hard",
                difficulty >= 3.0 ~ "hard",
                difficulty >= 1.5 ~ "moderate",
                TRUE ~ "easy"
            )
        )

    pathogen_metrics <- pathogen_metrics %>%
        left_join(difficulty_metrics, by = "pathogen")

    # Check if we have any valid pathogens
    if (nrow(pathogen_metrics) == 0) {
        stop("No valid pathogens found in the data. Check if the pathogen column contains proper pathogen names.")
    }

    # ---- Subgroup-level profiling ----
    # Compute difficulty metrics at the serotype and STEC class level so that
    # downstream resource allocation can use real data instead of estimates.

    has_serotype <- "serotypesummary" %in% names(data)
    has_stec_class <- "stec_class" %in% names(data)

    compute_subgroup_metrics <- function(df, group_col) {
        # Compute the same metrics used at pathogen level, grouped by
        # pathogen + the specified subgroup column.
        base <- df %>%
            filter(!is.na(.data[[group_col]]) &
                   .data[[group_col]] != "" &
                   .data[[group_col]] != "Missing") %>%
            group_by(pathogen, subgroup = .data[[group_col]]) %>%
            summarise(
                rows = n(),
                sites = n_distinct(state),
                years = n_distinct(year),
                .groups = 'drop'
            ) %>%
            mutate(
                complexity = rows * sites * years,
                size_category = case_when(
                    rows > 50000 ~ "extra_large",
                    rows > 20000 ~ "large",
                    rows > 10000 ~ "medium",
                    rows > 5000  ~ "small",
                    TRUE ~ "tiny"
                )
            )

        sy <- df %>%
            filter(!is.na(.data[[group_col]]) &
                   .data[[group_col]] != "" &
                   .data[[group_col]] != "Missing") %>%
            group_by(pathogen, subgroup = .data[[group_col]], state, year) %>%
            summarise(count = n(), .groups = 'drop')

        diff <- sy %>%
            group_by(pathogen, subgroup) %>%
            summarise(
                zero_frac = sum(count == 0) / n(),
                sparse_cells = sum(count < 5) / n(),
                overdispersion = ifelse(mean(count) > 0, var(count) / mean(count), 0),
                state_cv = ifelse(
                    mean(count) > 0,
                    sd(tapply(count, state, mean)) / mean(count),
                    0
                ),
                .groups = 'drop'
            ) %>%
            mutate(
                difficulty = 2.0 * zero_frac +
                             1.5 * sparse_cells +
                             1.0 * pmin(overdispersion / 100, 2) +
                             0.5 * pmin(state_cv, 2),
                difficulty_category = case_when(
                    difficulty >= 4.5 ~ "very_hard",
                    difficulty >= 3.0 ~ "hard",
                    difficulty >= 1.5 ~ "moderate",
                    TRUE ~ "easy"
                )
            )

        base %>% left_join(diff, by = c("pathogen", "subgroup"))
    }

    subgroup_parts <- list()

    if (has_serotype) {
        sero <- compute_subgroup_metrics(data, "serotypesummary")
        if (nrow(sero) > 0) {
            subgroup_parts <- c(subgroup_parts, list(sero))
        }
    }

    if (has_stec_class) {
        stec <- data %>% filter(pathogen == "STEC")
        if (nrow(stec) > 0) {
            stec_sub <- compute_subgroup_metrics(stec, "stec_class")
            if (nrow(stec_sub) > 0) {
                subgroup_parts <- c(subgroup_parts, list(stec_sub))
            }
        }
    }

    if (length(subgroup_parts) > 0) {
        subgroup_metrics <- bind_rows(subgroup_parts) %>%
            distinct(pathogen, subgroup, .keep_all = TRUE)
    } else {
        # Empty frame with correct schema
        subgroup_metrics <- tibble(
            pathogen = character(),
            subgroup = character(),
            rows = integer(),
            sites = integer(),
            years = integer(),
            complexity = double(),
            size_category = character(),
            zero_frac = double(),
            sparse_cells = double(),
            overdispersion = double(),
            state_cv = double(),
            difficulty = double(),
            difficulty_category = character()
        )
    }

    # Extract state metadata
    state_metrics <- data %>%
        filter(!is.na(state)) %>%
        group_by(state) %>%
        summarise(
            first_year = min(year, na.rm = TRUE),
            last_year = max(year, na.rm = TRUE),
            total_cases = n(),
            n_pathogens = n_distinct(pathogen),
            .groups = 'drop'
        ) %>%
        arrange(state)
    
    # Extract CIDT metadata
    cidt_metrics <- data %>%
        filter(!is.na(cxcidt)) %>%
        group_by(cxcidt) %>%
        summarise(
            count = n(),
            first_year = min(year, na.rm = TRUE),
            last_year = max(year, na.rm = TRUE),
            percentage = round(n() / nrow(data) * 100, 1),
            .groups = 'drop'
        ) %>%
        arrange(desc(count))
    
    # Extract travel metadata
    travel_metrics <- data %>%
        filter(!is.na(travelint)) %>%
        group_by(travelint) %>%
        summarise(
            count = n(),
            percentage = round(n() / nrow(data) * 100, 1),
            .groups = 'drop'
        ) %>%
        arrange(desc(count))
    
    # Write all CSV files
    write_csv(pathogen_metrics, "resource_profile.csv")
    write_csv(subgroup_metrics, "resource_profile_subgroups.csv")
    write_csv(state_metrics, "metadata_states.csv")
    write_csv(cidt_metrics, "metadata_cidt.csv")
    write_csv(travel_metrics, "metadata_travel.csv")
    
    # Print summary for logging
    cat("\\nResource Profile Summary:\\n")
    cat("========================\\n")
    for (i in 1:nrow(pathogen_metrics)) {
        cat(sprintf("%-15s: %6d rows, %2d sites, %2d years (complexity: %d, size: %s, difficulty: %.2f [%s])\\n",
                    pathogen_metrics\$pathogen[i],
                    pathogen_metrics\$rows[i],
                    pathogen_metrics\$sites[i],
                    pathogen_metrics\$years[i],
                    pathogen_metrics\$complexity[i],
                    pathogen_metrics\$size_category[i],
                    pathogen_metrics\$difficulty[i],
                    pathogen_metrics\$difficulty_category[i]))
    }

    if (nrow(subgroup_metrics) > 0) {
        cat("\\n\\nSubgroup Profile Summary:\\n")
        cat("========================\\n")
        for (i in 1:nrow(subgroup_metrics)) {
            cat(sprintf("%-15s | %-20s: %6d rows, %2d sites, %2d years (difficulty: %.2f [%s])\\n",
                        subgroup_metrics\$pathogen[i],
                        subgroup_metrics\$subgroup[i],
                        subgroup_metrics\$rows[i],
                        subgroup_metrics\$sites[i],
                        subgroup_metrics\$years[i],
                        subgroup_metrics\$difficulty[i],
                        subgroup_metrics\$difficulty_category[i]))
        }
    }

    # Print state summary
    cat("\\n\\nState Summary:\\n")
    cat("==============\\n")
    for (i in 1:nrow(state_metrics)) {
        cat(sprintf("%-2s: %4d-%4d, %6d cases\\n", 
                    state_metrics\$state[i], 
                    state_metrics\$first_year[i], 
                    state_metrics\$last_year[i], 
                    state_metrics\$total_cases[i]))
    }
    
    # Print CIDT summary
    cat("\\n\\nDiagnostic Method Summary:\\n")
    cat("=========================\\n")
    for (i in 1:nrow(cidt_metrics)) {
        cat(sprintf("%-10s: %6d cases (%.1f%%)\\n", 
                    cidt_metrics\$cxcidt[i], 
                    cidt_metrics\$count[i], 
                    cidt_metrics\$percentage[i]))
    }
    
    # Print travel summary
    cat("\\n\\nTravel Status Summary:\\n")
    cat("=====================\\n")
    for (i in 1:nrow(travel_metrics)) {
        cat(sprintf("%-7s: %6d cases (%.1f%%)\\n", 
                    travel_metrics\$travelint[i], 
                    travel_metrics\$count[i], 
                    travel_metrics\$percentage[i]))
    }
    """
}