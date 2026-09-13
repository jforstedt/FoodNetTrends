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
if('--fit'%in%commandArgs(TRUE)) {
 # Real shared model and full scoring path, with a synthetic small loader substitute.
 set.seed(894);small<-expand.grid(area=1:4,serial=0:95)
 small$fips<-sprintf('%05d',small$area);small$state<-ifelse(small$area<=2,'AA','BB');small$year<-2004+small$serial%/%12;small$month<-small$serial%%12+1
 small$person_years<-20000;small$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 small$count<-rnbinom(nrow(small),mu=small$person_years*.0002*exp(.5*cos(2*pi*small$month/12)),size=20)
 load_monthly_comparison<-function(...)small
 out<-tempfile('monthly-real-synthetic-')
 run_monthly_comparison('unused','unused',2008,TRUE,out,5400000L)
 stopifnot(readLines(file.path(out,'status.txt'))=='EXPLORATORY_FIT_COMPLETE')
 county<-read.csv(file.path(out,'county_month_predictions.csv'));catchment<-read.csv(file.path(out,'catchment_year_predictions.csv'))
 stopifnot(nrow(county)==144,nrow(catchment)==3,sum(county$observed)==sum(catchment$observed),all(is.finite(county$log_score)))
 cat('Monthly fitting and joint aggregation test PASS:',out,'\n')
}
