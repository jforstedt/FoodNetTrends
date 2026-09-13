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
