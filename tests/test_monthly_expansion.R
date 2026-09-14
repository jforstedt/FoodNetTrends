source('scripts/run_monthly_comparison.R')
# Validate the full loader footprint without reading private inputs.
annual<-expand.grid(fips=sprintf('%05d',1:486),year=2004:2019,stringsAsFactors=FALSE)
annual$state<-'AA';annual$count<-12L;annual$population<-36600
validate_panel<-function(...)list(data=annual)
d<-annual[rep(seq_len(nrow(annual)),each=12),];d$month<-rep(1:12,nrow(annual))
d$record_count<-1L;d$modeled_count<-NA_integer_;d$observation_status<-'UNVERIFIED';d$exposure_status<-'UNVALIDATED_ANNUAL_POPULATION_DAY_FRACTION'
a<-as.Date(sprintf('%04d-%02d-01',d$year,d$month));b<-as.Date(sprintf('%04d-%02d-01',d$year+(d$month==12),d$month%%12+1))
d$candidate_person_years<-d$population*as.numeric(b-a)/as.numeric(as.Date(paste0(d$year+1,'-01-01'))-as.Date(paste0(d$year,'-01-01')))
p<-tempfile(fileext='.rds');on.exit<-NULL;saveRDS(d,p)
x<-load_monthly_comparison(p,'unused',2011)
stopifnot(max(x$year)==2014,nrow(x)==486*11*12,all(x$observation_status=='EXPLORATORY_ASSUMED_CONTINUOUS'))
z<-d;z$record_count[1]<-2;saveRDS(z,p);stopifnot(inherits(try(load_monthly_comparison(p,'unused',2011),silent=TRUE),'try-error'))
z<-d;z$candidate_person_years[1]<-1;saveRDS(z,p);stopifnot(inherits(try(load_monthly_comparison(p,'unused',2011),silent=TRUE),'try-error'))
unlink(p)
cat('Monthly real-data loader tests PASS\n')

# The corrected parasite panel must stop in 2017; a later horizon is refused.
annual<-annual[annual$year<=2017,];d<-d[d$year<=2017,];p<-tempfile(fileext='.rds');saveRDS(d,p)
x<-load_monthly_comparison(p,'unused',2014,2017L)
stopifnot(max(x$year)==2017,nrow(x)==486*14*12)
stopifnot(inherits(try(load_monthly_comparison(p,'unused',2016,2017L),silent=TRUE),'try-error'))
unlink(p)
if('--integration'%in%commandArgs(TRUE)) {
 source('scripts/run_monthly_expansion.R')
 set.seed(197);d<-expand.grid(area=1:4,time0=0:95);d$fips<-sprintf('%05d',d$area);d$state<-ifelse(d$area<=2,'AA','BB');d$year<-2004+d$time0%/%12;d$month<-d$time0%%12+1
 d$person_years<-20000;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS';d$count<-rnbinom(nrow(d),mu=4,size=20)
 load_monthly_comparison<-function(...)d
 for(model in c('rw1','ar1')) {
  work<-tempfile();dir.create(work)
  run_monthly_expansion('unused','unused',2008,file.path(work,'result'),160000000L,model,2019L,draws=100L)
  stopifnot(readLines(file.path(work,'result/status.txt'))=='SAVED_MONTHLY_DIAGNOSTICS_COMPLETE')
  settings<-read.csv(file.path(work,'result/sensitivity_settings.csv'));stopifnot(settings$temporal_model==model)
 }
}
cat('Expansion cutoff and runner tests PASS\n')
