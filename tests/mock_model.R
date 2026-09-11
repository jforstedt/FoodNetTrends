#!/usr/bin/env Rscript
# Integration fixture: run the actual trendy.R flow with deterministic fake model draws.
# These outputs are NOT scientific estimates. Only Stan fitting/prediction and its
# diagnostics are replaced; CLI parsing, filtering, aggregation and exports are real.
suppressPackageStartupMessages({library(dplyr);library(tidyr);library(HDInterval)})
script <- sub('--file=', '', grep('^--file=', commandArgs(), value=TRUE)[1])
root <- dirname(dirname(normalizePath(script)))
model_env <- new.env(parent = globalenv())
model_env$LOAD_PACKAGES <- function(...) invisible(NULL)
model_env$source <- function(file, ...) {
  if (basename(file) %in% c('classification.R','input_validation.R')) {
    sys.source(file.path(root,'bin',basename(file)), envir=model_env)
  } else if (basename(file) == 'functions.R') {
    for (expr in parse(file.path(root,'bin/functions.R'))) {
      if (is.call(expr) && identical(expr[[1]], as.name('<-')) &&
          is.call(expr[[3]]) && identical(expr[[3]][[1]], as.name('function')))
        eval(expr, envir=model_env)
    }
    model_env$PROPOSED_BM <- function(data, ...) {
      data$year <- as.numeric(as.character(data$year))
      list(data=as.data.frame(data))
    }
    model_env$LINPREAD_DRAW_FN <- function(data, model) {
      crossing(as.data.frame(data), .draw=1:100) %>%
        mutate(.epred=(count+0.5)*(.draw/100+0.5))
    }
    model_env$CHECK_CONVERGENCE <- function(model, pathogen_name, output_dir) {
      diagnostics <- list(converged=FALSE, warnings='Integration fixture: intentionally not converged',
                          max_rhat=1.2, min_ess=50)
      write.csv(as.data.frame(diagnostics),
                file.path(output_dir,paste0(pathogen_name,'_convergence_diagnostics.csv')),row.names=FALSE)
      diagnostics
    }
    # Avoid plotting dependencies in the fixture environment.
    for (name in c('PLOT_TRAVEL_COMPARISON','PLOT_TRAVEL_COMPARISON_SITE','PLOT_TRAVEL_FRACTION'))
      model_env[[name]] <- function(...) invisible(NULL)
  } else stop('Unexpected source in integration fixture: ',file)
}
for (expr in parse(file.path(root,'bin/trendy.R'))) {
  if (is.call(expr) && identical(expr[[1]], as.name('<-')) &&
      identical(expr[[2]], as.name('LOAD_PACKAGES'))) next
  eval(expr, envir=model_env)
}
