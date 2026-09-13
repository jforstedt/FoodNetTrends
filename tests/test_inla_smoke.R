source('scripts/inla_smoke.R')
x <- make_smoke_data()
stopifnot(identical(x, make_smoke_data()), nrow(x) == 136L,
          all(x$count >= 0), all(x$count == as.integer(x$count)),
          all(x$population > 0), !anyDuplicated(x[c('area', 'time')]))
path <- tempfile()
n <- write_smoke_graph(path)
stopifnot(length(n) == 17L, length(n[[17]]) == 0L,
          !any(n[[8]] == 9L), !any(n[[9]] == 8L))
for (i in seq_along(n)) for (j in n[[i]]) stopifnot(i %in% n[[j]])
# A stale successful report must not survive a new invocation.
d <- tempfile(); dir.create(d); writeLines('PASS', file.path(d, 'status.txt'))
tryCatch({run_smoke(d); stop('Should reject nonempty reports')}, error=function(e)
  stopifnot(grepl('new or empty', conditionMessage(e))))
stopifnot(readLines(file.path(d, 'status.txt')) == 'PASS')
unlink(c(d, path), recursive = TRUE)
cat('PASS deterministic synthetic fixture, disconnected/isolated graph, report overwrite guard\n')
# Owner-only execution must fail even when a root build's file.access succeeds.
b <- tempfile(); dir.create(b)
files <- file.path(b, c('inla.mkl.run', 'inla.mkl')); file.create(files)
Sys.chmod(files, '0744')
tryCatch({check_inla_permissions(b); stop('Should reject owner-only execution')},
         error=function(e) stopifnot(grepl('lacks execute permission', conditionMessage(e))))
Sys.chmod(files, '0755'); check_inla_permissions(b)
unlink(b, recursive=TRUE)
cat('PASS owner-only executable permissions rejected; shared execution accepted\n')
