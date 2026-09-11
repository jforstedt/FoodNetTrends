#!/usr/bin/env Rscript
# Tab-separated count/value list for the launcher; base R only.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4) stop("Expected cleaned CSV, pathogen, rules CSV, source column")
script <- sub("--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
source(file.path(dirname(script), "classification.R"))
data <- read.csv(args[1], colClasses = "character", check.names = FALSE)
data <- classify_cases(data, read_classification_rules(args[3]), args[4])
values <- data$serotypesummary[canonical_value(data$pathogen) == canonical_value(args[2])]
values <- values[!is.na(values) & nzchar(values)]
counts <- sort(table(values), decreasing = TRUE)
for (value in names(counts)) {
  if (!grepl("[|~\t\r\n]", value)) cat(counts[[value]], value, sep = "\t", fill = FALSE) else next
  cat("\n")
}
