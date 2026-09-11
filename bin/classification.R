# Shared, package-free case classification for preprocessing, menus and models.
canonical_value <- function(x) {
  x <- toupper(trimws(as.character(x)))
  x[is.na(x)] <- ""
  x
}

read_classification_rules <- function(path) {
  rules <- read.csv(path, colClasses = "character", na.strings = NULL,
                    check.names = FALSE)
  if (!all(c("classification", "match_type", "value") %in% names(rules)))
    stop("Classification rules require classification, match_type and value columns")
  if (any(!rules$classification %in% c("not_serotyped", "typhoidal", "nontyphoidal", "unclassified")) ||
      any(!rules$match_type %in% c("exact", "contains")))
    stop("Invalid classification or match_type in classification rules")
  if (any(rules$match_type == "contains" & !nzchar(rules$value)))
    stop("A contains rule cannot have an empty value")
  rules
}

classify_cases <- function(data, rules, source = "auto") {
  if (!"pathogen" %in% names(data)) stop("Missing pathogen column")
  if (source == "auto") {
    candidates <- c("serotypesummary2", "serotypesummary_original", "serotypesummary", "sero1")
    source <- candidates[candidates %in% names(data)][1]
  }
  if (is.na(source)) {
    raw <- rep(NA_character_, nrow(data))
    source <- "unavailable"
  } else {
    if (!source %in% names(data)) stop("Serotype source column not found: ", source)
    raw <- data[[source]]
  }
  # Never fall back per row: a blank in the chosen source means not serotyped.
  data$serotypesummary_original <- raw
  if (source != "serotypesummary_original") data$serotype_source <- source
  values <- canonical_value(raw)
  matches <- function(category) {
    found <- rep(FALSE, length(values))
    subset <- rules[rules$classification == category, , drop = FALSE]
    for (i in seq_len(nrow(subset))) {
      value <- canonical_value(subset$value[i])
      found <- found | if (subset$match_type[i] == "exact") values == value else
        grepl(value, values, fixed = TRUE)
    }
    found
  }
  salmonella <- canonical_value(data$pathogen) == "SALMONELLA"
  missing <- matches("not_serotyped") | !nzchar(values)
  data$serotypesummary <- trimws(as.character(raw))
  data$serotypesummary[salmonella & missing] <- "NOT SEROTYPED"
  data$salmonella_type <- NA_character_
  data$salmonella_type[salmonella] <- "NONTYPHOIDAL"
  data$salmonella_type[salmonella & matches("unclassified")] <- "UNCLASSIFIED"
  data$salmonella_type[salmonella & matches("nontyphoidal")] <- "NONTYPHOIDAL"
  data$salmonella_type[salmonella & matches("typhoidal")] <- "TYPHOIDAL"
  data$salmonella_type[salmonella & missing] <- "UNCLASSIFIED"
  if (!"stec_class_original" %in% names(data)) {
    data$stec_class_original <- if ("stec_class" %in% names(data))
      as.character(data$stec_class) else rep(NA_character_, nrow(data))
  }
  stec <- canonical_value(data$pathogen) == "STEC"
  stec_class <- canonical_value(data$stec_class_original)
  if ("dx0157" %in% names(data)) {
    dx <- canonical_value(data$dx0157)
    stec_class[stec & dx == "POSITIVE"] <- "STEC O157"
    stec_class[stec & dx == "NEGATIVE"] <- "STEC NONO157"
  }
  data$stec_class <- ifelse(stec, stec_class, as.character(data$stec_class_original))
  data$stec_group <- NA_character_
  data$stec_group[stec] <- "NOT SEROGROUPED"
  data$stec_group[stec & stec_class == "STEC O157"] <- "O157"
  data$stec_group[stec & stec_class == "STEC NONO157"] <- "nonO157"
  data
}

select_analysis_cases <- function(data, pathogen, subgroup = "combined", selected = character()) {
  data <- data[canonical_value(data$pathogen) == canonical_value(pathogen), , drop = FALSE]
  if (subgroup == "combined") return(data)
  if (pathogen == "STEC" && subgroup %in% c("O157", "nonO157", "NOT SEROGROUPED")) {
    keep <- data$stec_group == subgroup
  } else if (pathogen == "SALMONELLA" && subgroup %in% c("TYPHOIDAL", "NONTYPHOIDAL", "UNCLASSIFIED")) {
    keep <- data$salmonella_type == subgroup
  } else if (pathogen == "SALMONELLA" && subgroup == "OTHER SEROTYPES") {
    values <- canonical_value(data$serotypesummary)
    keep <- nzchar(values) & !values %in% c("NOT SEROTYPED", canonical_value(selected))
  } else {
    if (!"serotypesummary" %in% names(data)) stop("Missing serotypesummary column")
    keep <- canonical_value(data$serotypesummary) == canonical_value(subgroup)
  }
  data[!is.na(keep) & keep, , drop = FALSE]
}

classification_counts <- function(data) {
  fields <- c("pathogen", "serotype_source", "serotypesummary_original", "serotypesummary",
              "salmonella_type", "stec_class_original", "stec_class", "stec_group")
  x <- as.data.frame(data[fields], stringsAsFactors = FALSE)
  x[] <- lapply(x, function(v) ifelse(is.na(v), "", as.character(v)))
  if (!nrow(x)) { x$count <- integer(); return(x) }
  aggregate(list(count = rep(1L, nrow(x))), x, sum)
}
