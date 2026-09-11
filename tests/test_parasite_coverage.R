#!/usr/bin/env Rscript
suppressPackageStartupMessages({library(dplyr); library(tidyr)})
# Exercise the real input aggregation without requiring Stan or plotting packages.
for (expr in parse('bin/functions.R')) {
  if (is.call(expr) && identical(expr[[1]], as.name('<-')) &&
      is.call(expr[[3]]) && identical(expr[[3]][[1]], as.name('function'))) eval(expr)
}
grid <- expand.grid(year=1997:1999, state=c('CA','GA'), stringsAsFactors=FALSE)
population <- transform(grid, population=100000, pathogentype='Parasitic')
population <- subset(population, !(state=='GA' & year==1997))
for (pathogen in c('CRYPTOSPORIDIUM','CYCLOSPORA')) {
  cases <- data.frame(year=c(1997,1999), state=c('CA','GA'), pathogen=pathogen)
  result <- PATH_ANALYSIS(cases, population, surveillance=grid)
  stopifnot(nrow(result)==5, sum(result$count)==2,
            !any(result$state=='GA' & result$year==1997),
            result$count[result$state=='GA' & result$year==1998]==0,
            all(result$population==100000))
  # An absent population during covered surveillance must still fail.
  broken <- subset(population, !(state=='GA' & year==1998))
  failure <- tryCatch(PATH_ANALYSIS(cases, broken, surveillance=grid), error=identity)
  stopifnot(inherits(failure,'error'), grepl('Missing or invalid population',conditionMessage(failure)))
}
# Bacterial Georgia observations remain included in 1997.
bacterial <- transform(grid, population=100000, pathogentype='Bacterial')
cases <- data.frame(year=1997, state='GA', pathogen='SALMONELLA')
result <- PATH_ANALYSIS(cases,bacterial,surveillance=grid)
stopifnot(nrow(result)==6, result$count[result$state=='GA' & result$year==1997]==1)
# Explicit user catchment definitions continue to control coverage.
custom <- data.frame(state='GA',start_year=1999,end_year=9999,pathogen_type='parasitic')
result <- PATH_ANALYSIS(transform(cases,year=1999,pathogen='CYCLOSPORA'),population,custom,grid)
stopifnot(nrow(result)==1,result$year==1999,result$count==1)
cat('Parasite coverage, zero counts, missing denominators, bacterial coverage and custom windows passed.\n')
