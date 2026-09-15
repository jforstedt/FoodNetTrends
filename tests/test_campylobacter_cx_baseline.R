# Short actual-fit control adapter check; full extended worker covered separately.
source(file.path(Sys.getenv('CX_FROZEN_SCRIPTS','scripts'),'run_county_covariate_experiment.R'))
d<-expand.grid(month=1:12,year=2010:2014,fips=c('13001','47001'),stringsAsFactors=FALSE)
d$state<-ifelse(d$fips=='13001','GA','TN');d$area<-d$fips;d$person_years<-5000;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
set.seed(887);d$count<-rnbinom(nrow(d),mu=10,size=30)
f<-fit_monthly_local_seasonality(d,2011*12+11L,seasonal=TRUE,local_seasonality=FALSE,weather=FALSE,age=FALSE,
 temporal_model='rw1',rate_center=.0002,coverage='EXPLORATORY_ASSUMED_CONTINUOUS')
attr(f,'covariate_experiment_contract')<-list(version='county_covariate_experiment_v1',task_id='CX_baseline_synthetic',pathogen='CAMPYLOBACTER',cutoff=2011L,temporal='rw1',local_seasonality=FALSE,weather=FALSE,age=FALSE,weather_window='current')
attr(f,'diagnostic_era_specification')<-list(version='campylobacter_cx_model_v1',target='recorded_CX_positive')
t<-tempfile();saveRDS(f,t);f<-readRDS(t);unlink(t)
p<-d[d$year>2011,c('fips','state','year','month')];p$observed<-d$count[d$year>2011]
a<-validate_covariate_saved(f,p,2011L,TRUE)
stopifnot(length(a$indices)==72L,identical(attr(f,'diagnostic_era_specification')$target,'recorded_CX_positive'),f$mode$mode.status==0)
cat('CX BASELINE RW1 ACTUAL FIT AND ADAPTER ROUNDTRIP PASS\n')
source('scripts/run_campylobacter_cx_model.R')
source_task<-attr(f,'covariate_experiment_contract')
cx<-d;cx$count[cx$year>2011]<-pmax(0L,cx$count[cx$year>2011]-2L)
validate_cx_reuse_training(f,cx,2011L,FALSE,source_task)
p$observed<-cx$count[cx$year>2011]
reused<-validate_covariate_saved(f,p,2011L,TRUE)
stopifnot(identical(reused$truth,p$observed),length(reused$indices)==72L)
cat('ACTUAL SAVED 2011 BASELINE REUSE GUARD AND CHANGED-TARGET ADAPTER PASS\n')
