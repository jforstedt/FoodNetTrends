source('scripts/audit_monthly_combination_priors.R')
a<-prior_monthly_components(2011L,draws=300L,seed=111L)
stopifnot(a$nt==96L,length(a$serial)==132L,all(vapply(a$trend,function(x)identical(dim(x),c(132L,300L)),logical(1))),max(abs(colSums(a$season)))<1e-8,max(abs(colMeans(a$trend$rw1[1:96,])))<1e-9)
# Anchoring the random walk affects only its level, not innovation differences.
stopifnot(all(is.finite(a$trend$spline)),all(is.finite(a$trend$ar1)),all(a$size>0))
stopifnot(inherits(try(prior_monthly_components(2010L),silent=TRUE),'try-error'))
cat('Joint monthly prior constraints and domain PASS\n')
