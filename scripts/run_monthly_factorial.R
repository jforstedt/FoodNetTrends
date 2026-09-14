#!/usr/bin/env Rscript
# Missing no-seasonality arms only; existing seasonal and RW1 controls are reused.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'run_monthly_comparison.R'));source(file.path(.here,'audit_saved_monthly.R'))
run_monthly_factorial <- function(candidate,audit,cutoff,out,seed,temporal,end_year,draws=2000L) {
 if(!temporal%in%c('rw1','ar1'))stop('Unsupported temporal family')
 if(dir.exists(out))stop('Refusing existing output')
 work<-dirname(out);fitpath<-file.path(work,'fit_INTERNAL.rds');truthpath<-file.path(work,'heldout_truth_INTERNAL.csv')
 if(file.exists(fitpath)||file.exists(truthpath))stop('Refusing existing checkpoint')
 inputpaths<-c(candidate,file.path(audit,'county_panel_INTERNAL.rds'));before<-tools::md5sum(inputpaths)
 d<-load_monthly_comparison(candidate,audit,cutoff,end_year);held<-d$year>cutoff;warnings<-character()
 fit<-withCallingHandlers(fit_monthly_model(d,cutoff*12+11L,FALSE,threads=4L,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002,trend_sd_upper=.5,temporal_model=temporal),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 writeLines(warnings,file.path(work,'fit_warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl("vb[.]correction['\"]?.*aborted",warnings,ignore.case=TRUE)))stop('New fit numerical gate failed')
 if('season'%in%names(fit$summary.random))stop('Unexpected seasonal effect in no-seasonality arm')
 saveRDS(fit,fitpath,version=2)
 truth<-d[held,c('fips','state','year','month')];truth$observed<-d$count[held];write.csv(truth,truthpath,row.names=FALSE)
 audit_monthly_saved(fitpath,truthpath,cutoff,FALSE,out,seed,draws=draws,expected_temporal=temporal)
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 write.csv(data.frame(new_fit=TRUE,temporal_model=temporal,end_year=end_year,seasonal=FALSE,rate_center=.0002,coverage_certified=FALSE,comparison='temporal_by_seasonality_factorial_v1'),file.path(out,'sensitivity_settings.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(inputpaths)))stop('Monthly inputs changed')
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=7L)stop('Usage CANDIDATE AUDIT CUTOFF OUT SEED TEMPORAL END_YEAR');run_monthly_factorial(a[1],a[2],as.integer(a[3]),a[4],as.integer(a[5]),a[6],as.integer(a[7]))}
