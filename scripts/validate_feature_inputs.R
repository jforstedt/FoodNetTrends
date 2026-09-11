#!/usr/bin/env Rscript
# Existing-case membership and saved baseline checks. No model fitting.
args <- commandArgs(trailingOnly=TRUE)
if (length(args)!=1) stop('Expected completed project output directory')
root <- args[1]
suppressPackageStartupMessages({library(dplyr);library(tidyr)})
source('bin/classification.R')
clean <- file.path(root,'preprocessed','clean_mmwr.csv')
if (!file.exists(clean)) stop('Completed clean file unavailable: ',clean)
data <- read.csv(clean,stringsAsFactors=FALSE,check.names=FALSE)
rules <- read_classification_rules('analysis_configs/classification_rules.csv')
data <- classify_cases(data,rules)
stopifnot(identical(data,classify_cases(data,rules)))
data$validation_row <- seq_len(nrow(data))
cat('Real-data classification checks; counts precede model coverage/travel exclusions.\n')
partition <- function(pathogen,groups,selected=character()) {
  x <- select_analysis_cases(data,pathogen)
  parts <- lapply(groups,function(group) select_analysis_cases(data,pathogen,group,selected))
  ids <- unlist(lapply(parts,function(x) x$validation_row),use.names=FALSE)
  stopifnot(!anyDuplicated(ids),setequal(ids,x$validation_row))
  print(data.frame(pathogen=pathogen,group=groups,records=vapply(parts,nrow,integer(1))))
}
partition('STEC',c('O157','nonO157','NOT SEROGROUPED'))
partition('SALMONELLA',c('TYPHOIDAL','NONTYPHOIDAL','UNCLASSIFIED'))
named <- c('ENTERITIDIS','NEWPORT','TYPHIMURIUM','JAVIANA','I 4,[5],12:i:-')
partition('SALMONELLA',c(named,'OTHER SEROTYPES','NOT SEROTYPED'),named)
# The remaining-serotype category must adapt to a different user selection.
partition('SALMONELLA',c('ENTERITIDIS','OTHER SEROTYPES','NOT SEROTYPED'),'ENTERITIDIS')
for (pathogen in unique(data$pathogen)) {
  x <- select_analysis_cases(data,pathogen)
  values <- unique(x$serotypesummary[!is.na(x$serotypesummary) & nzchar(x$serotypesummary)])
  values <- setdiff(values,c('combined','OTHER SEROTYPES','TYPHOIDAL','NONTYPHOIDAL','UNCLASSIFIED','O157','nonO157','NOT SEROGROUPED'))
  for (value in values) {
    chosen <- select_analysis_cases(x,pathogen,value)
    stopifnot(nrow(chosen)==sum(canonical_value(x$serotypesummary)==canonical_value(value)))
  }
  cat('PASS exact subgroup membership:',pathogen,'values:',length(values),'\n')
}
files <- list.files(file.path(root,'spline_results'),pattern='_EstIRRCatch_[0-9]+_[0-9]+[.]csv$',full.names=TRUE)
if (!length(files)) stop('No completed baseline output tables found')
for (file in files) {
  x <- read.csv(file)
  start <- unique(x$baseline_start); end <- unique(x$baseline_end)
  stopifnot(length(start)==1,length(end)==1)
  b <- x[x$year>=start & x$year<=end,]
  stopifnot(setequal(b$year,seq.int(start,end)))
  crude <- sum(b$raw_count)/sum(b$population)*100000
  stopifnot(all(abs(x$baseline_raw_ir-crude)<1e-5),all(is.finite(x$baseline_median_ir)),
            all(is.finite(x$baseline_lower_hdi_ir)),all(is.finite(x$baseline_upper_hdi_ir)),
            all(x$baseline_lower_hdi_ir<=x$baseline_upper_hdi_ir))
  cat('PASS saved baseline:',basename(file),'crude incidence:',crude,'\n')
}
cat('\nSaved model diagnostics (warnings are not suppressed):\n')
for (file in list.files(file.path(root,'spline_results'),pattern='_convergence_diagnostics.csv$',full.names=TRUE)) print(read.csv(file))
cat('\nPASS feature-input and saved-baseline checks. This does not certify scientific definitions or subgroup-model convergence.\n')
