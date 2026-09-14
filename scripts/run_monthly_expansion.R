#!/usr/bin/env Rscript
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'run_monthly_comparison.R'));source(file.path(.here,'audit_saved_monthly.R'))
run_monthly_expansion <- function(candidate,audit,cutoff,out,seed,temporal='rw1',end_year=2019L,draws=2000L) {
 if(dir.exists(out))stop('Refusing existing output')
 work<-dirname(out);fitpath<-file.path(work,'fit_INTERNAL.rds');predpath<-file.path(work,'heldout_truth_INTERNAL.csv')
 if(file.exists(fitpath)||file.exists(predpath))stop('Refusing existing checkpoint')
 d<-load_monthly_comparison(candidate,audit,cutoff,end_year);held<-d$year>cutoff
 warnings<-character()
 fit<-withCallingHandlers(fit_monthly_model(d,cutoff*12+11L,TRUE,threads=4L,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002,temporal_model=temporal),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 writeLines(warnings,file.path(work,'fit_warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl('vb.correction.*aborted',warnings,ignore.case=TRUE)))stop('New fit numerical gate failed')
 saveRDS(fit,fitpath,version=2)
 pred<-d[held,c('fips','state','year','month')];pred$observed<-d$count[held]
 write.csv(pred,predpath,row.names=FALSE)
 audit_monthly_saved(fitpath,predpath,cutoff,TRUE,out,seed,draws=draws,expected_temporal=temporal)
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 write.csv(fit$summary.random$season,file.path(out,'seasonal_effect.csv'),row.names=FALSE)
 write.csv(data.frame(new_fit=TRUE,temporal_model=temporal,end_year=end_year,seasonal=TRUE,rate_center=.0002,coverage_certified=FALSE),file.path(out,'sensitivity_settings.csv'),row.names=FALSE)
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=7L)stop('Usage: CANDIDATE AUDIT CUTOFF OUT SEED TEMPORAL END_YEAR');run_monthly_expansion(a[1],a[2],as.integer(a[3]),a[4],as.integer(a[5]),a[6],as.integer(a[7]))}
