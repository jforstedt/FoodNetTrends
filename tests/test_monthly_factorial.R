source('scripts/run_monthly_factorial.R')
if('--fit'%in%commandArgs(TRUE)) {
 d<-expand.grid(fips=c('01001','02001'),year=2004:2010,month=1:12,stringsAsFactors=FALSE);d<-d[order(d$fips,d$year,d$month),]
 d$state<-ifelse(d$fips=='01001','AA','BB');d$area<-d$fips;d$person_years<-1000;d$count<-rep(c(0,1,2,1),length.out=nrow(d));d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 candidate<-tempfile();saveRDS(d,candidate);audit<-tempfile();dir.create(audit);saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
 # Isolate only the production-only 486-county input loader. Fitting and scoring are real.
 load_monthly_comparison<-function(...)d
 for(temporal in c('rw1','ar1')) {
  work<-tempfile();dir.create(work);out<-file.path(work,'result')
  run_monthly_factorial(candidate,audit,2007L,out,700000000L,temporal,2019L,draws=100L)
  f<-readRDS(file.path(work,'fit_INTERNAL.rds'));stopifnot(!('season'%in%names(f$summary.random)),all(is.na(f$.args$data$count[f$.args$data$year>2007])),all(is.finite(read.csv(file.path(out,'stream_scores.csv'))$mean_log_score)))
  s<-read.csv(file.path(out,'sensitivity_settings.csv'));stopifnot(!s$seasonal,s$temporal_model==temporal)
 }
}
cat('Monthly factorial no-seasonality runner PASS\n')
