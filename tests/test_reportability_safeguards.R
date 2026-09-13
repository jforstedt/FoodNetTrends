# Test input safeguards directly without running a fit or reading surveillance data.
load_functions <- function(path) {
  for (expr in parse(path)) {
    if (is.call(expr) && identical(expr[[1]], as.name('<-')) &&
        is.call(expr[[3]]) && identical(expr[[3]][[1]], as.name('function'))) {
      eval(expr, envir = .GlobalEnv)
    }
  }
}
load_functions('bin/preprocess.R')
load_functions('bin/functions.R')
must_fail <- function(expr, text) {
  result <- tryCatch(force(expr), error = identity)
  stopifnot(inherits(result, 'error'), grepl(text, conditionMessage(result), fixed = TRUE))
}
rules <- data.frame(rule_type='pathogen_filter', match_column='pathogen', match_value='LISTERIA',
                    replacement=NA_character_, condition="cste == 'YES'", notes='CSTE')
data <- data.frame(id=1:5, pathogen=c('LISTERIA','LISTERIA','LISTERIA','SALMONELLA','SALMONELLA'),
                   cste=c('YES','NO',NA,NA,'NO'))
require_listeria_reportability(data)
filtered <- apply_data_rules(data, rules)
stopifnot(identical(filtered$id, c(1L,4L,5L)), !anyNA(filtered$id))
# Missing CSTE fails both the pipeline-wide check and configured-rule path.
missing <- data[c('id','pathogen')]
must_fail(require_listeria_reportability(missing), 'requires the cste')
must_fail(apply_data_rules(missing, rules), 'required column')
# Data without Listeria never require an irrelevant reportability field.
other <- missing[missing$pathogen != 'LISTERIA', ]
require_listeria_reportability(other)
stopifnot(identical(apply_data_rules(other, rules), other))
# The published example must be equivalent to the built-in catchment defaults.
defaults <- read_catchment_config()
example <- read_catchment_config('analysis_configs/examples/catchment_config.csv')
grid <- expand.grid(state=unique(defaults$state), year=1996:2004, stringsAsFactors=FALSE)
for (kind in c('bacterial','parasitic')) {
  stopifnot(identical(apply_catchment_filter(grid, defaults, kind),
                      apply_catchment_filter(grid, example, kind)))
}
cat('Reportability and example catchment safeguards passed.\n')
# Empty/custom optional rules cannot bypass the mandatory final filter.
empty_rules <- rules[FALSE,]
stopifnot(identical(filter_listeria_reportability(apply_data_rules(data,empty_rules))$id,c(1L,4L,5L)))
permissive_rules <- rules; permissive_rules$condition <- "cste == 'NO'"
stopifnot(!any(filter_listeria_reportability(apply_data_rules(data,permissive_rules))$pathogen=='LISTERIA'))
must_fail(filter_listeria_reportability(missing),'requires the cste')
stopifnot(identical(filter_listeria_reportability(other),other))
# Reused clean files must pass the same eligibility requirement at model entry.
source('bin/input_validation.R')
pop <- data.frame(year=2019L,state='CA',population=10000)
cases <- transform(data,year=2019L,state='CA')
r <- prepare_analysis_inputs(cases,pop,pop,'LISTERIA')
stopifnot(identical(r$cases$id,1L),sum(r$excluded$records)==2L,
          all(grepl('CSTE-reportable',r$excluded$reason)))
must_fail(prepare_analysis_inputs(cases[,setdiff(names(cases),'cste')],pop,pop,'LISTERIA'),'requires the cste')
# No reportability field is needed for another pathogen or excluded Listeria years.
stopifnot(nrow(prepare_analysis_inputs(cases[,setdiff(names(cases),'cste')],pop,pop,'SALMONELLA')$cases)==2)
old <- cases[,setdiff(names(cases),'cste')];old$year<-2018L
stopifnot(nrow(prepare_analysis_inputs(old,pop,pop,'LISTERIA',observation_years=2019L)$cases)==0)
# Confirm the zero grid counts only the single eligible case.
suppressPackageStartupMessages({library(dplyr);library(tidyr)})
model_data <- PATH_ANALYSIS(r$cases,r$census,surveillance=data.frame(year=2019L,state='CA'))
stopifnot(model_data$count==1L)
cat('Mandatory custom-rule and preprocessed Listeria eligibility passed.\n')
