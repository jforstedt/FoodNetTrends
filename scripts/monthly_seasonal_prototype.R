#!/usr/bin/env Rscript
# Preserve the synthetic-only entry point; real inputs use a separate audited loader.
.monthly_source<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.monthly_here<-if(is.null(.monthly_source))'scripts' else dirname(.monthly_source)
source(file.path(.monthly_here,'monthly_seasonal_model.R'))
monthly_prototype_data <- function(d,cutoff) monthly_model_data(d,cutoff,'SYNTHETIC_COMPLETE')
fit_monthly_prototype <- function(d,cutoff,seasonal=TRUE,threads=2L)
  fit_monthly_model(d,cutoff,seasonal,threads,coverage='SYNTHETIC_COMPLETE',rate_center=.002)
