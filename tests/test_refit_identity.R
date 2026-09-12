# Load only the pure comparison helper, without invoking the refit entry point.
code <- parse('scripts/refit_saved_feature.R')
eval(code[[1]])
a <- data.frame(year=2019:2020,state=factor(c('CA','CO')),count=c(1L,0L),population=c(100,200))
attr(a,'data_name') <- 'current_data'
b <- a;attr(b,'data_name') <- 'old$data'
stopifnot(!identical(a,b),same_refit_data(a,b))
b$count[1] <- 2L;stopifnot(!same_refit_data(a,b))
b <- a;b$population[1] <- 101;stopifnot(!same_refit_data(a,b))
b <- a[2:1,];stopifnot(!same_refit_data(a,b))
b <- a;attr(b,'unrecognized_metadata') <- TRUE;stopifnot(!same_refit_data(a,b))
# The checkpoint must be written before any identity validation runs.
text <- readLines('scripts/refit_saved_feature.R')
stopifnot(grep('saveRDS(new, paste0',text,fixed=TRUE)<grep('checks <-',text,fixed=TRUE))
cat('PASS data-name metadata accepted; changed values, row order and other attributes rejected; checkpoint precedes validation\n')

b <- a;b$population[1] <- b$population[1]+1e-10
stopifnot(!same_refit_data(a,b))
# Formula environments may differ in identity while containing equivalent metadata.
b <- a
attr(a,'terms_fixture') <- as.formula('~year',env=new.env(parent=baseenv()))
attr(b,'terms_fixture') <- as.formula('~year',env=new.env(parent=baseenv()))
stopifnot(!identical(a,b),same_refit_data(a,b))
cat('PASS zero tolerance rejects small numeric changes and accepts equivalent formula environments\n')
