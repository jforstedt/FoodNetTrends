source('scripts/run_monthly_temporal_sensitivity.R')
d<-expand.grid(area=1:4,time0=0:95);d$fips<-sprintf('%05d',d$area);d$state<-ifelse(d$area<=2,'AA','BB')
d$year<-2004+d$time0%/%12;d$month<-d$time0%%12+1;d$person_years<-20000;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
set.seed(197);d$count<-rnbinom(nrow(d),mu=4*exp(.5*cos(2*pi*d$month/12)),size=20)
cutoff<-2008*12+11L
old<-monthly_model_data(d,cutoff,'EXPLORATORY_ASSUMED_CONTINUOUS',.5)
new<-monthly_model_data(d,cutoff,'EXPLORATORY_ASSUMED_CONTINUOUS',.25)
stopifnot(identical(old$data,new$data),new$spec$trend_sd_bound==old$spec$trend_sd_bound/2,
 identical(old$spec$trend_constraint,new$spec$trend_constraint),identical(old$spec$seasonal_sd_bound,new$spec$seasonal_sd_bound),identical(old$spec$nb_log_size_mean,new$spec$nb_log_size_mean))
keep<-setdiff(names(old$spec),c('trend_sd_upper','trend_sd_bound'))
stopifnot(identical(old$spec[keep],new$spec[keep]))
for(v in c(0,-1,NA,Inf))stopifnot(inherits(try(monthly_model_data(d,cutoff,'EXPLORATORY_ASSUMED_CONTINUOUS',v),silent=TRUE),'try-error'))
ext<-d[d$year==2011,];ext$year<-2012;ext$count<-Inf
long<-monthly_model_data(rbind(d,ext),cutoff,'EXPLORATORY_ASSUMED_CONTINUOUS',.25)
stopifnot(new$spec$trend_sd_bound==long$spec$trend_sd_bound,all(long$spec$trend_constraint$A[1,61:108]==0))
cat('Temporal-prior isolation and future-masking tests PASS\n')
if('--fit'%in%commandArgs(TRUE)) {
 load_monthly_comparison<-function(...)d
 work<-tempfile('temporal-sensitivity-test-');dir.create(work)
 run_temporal_sensitivity('unused','unused',2008,file.path(work,'result'),47000000L,draws=100L)
 fit<-readRDS(file.path(work,'fit_INTERNAL.rds'));pred<-read.csv(file.path(work,'heldout_truth_INTERNAL.csv'),colClasses=c(fips='character'))
 validate_monthly_saved(fit,pred,2008,TRUE,.25)
 stopifnot(inherits(try(validate_monthly_saved(fit,pred,2008,TRUE,.5),silent=TRUE),'try-error'),attr(fit,'monthly_specification')$trend_sd_upper==.25)
 r<-read.csv(file.path(work,'result/sensitivity_settings.csv'));stopifnot(r$new_fit,r$trend_sd_upper==.25)
 cat('New temporal fit plus saved-sampling integration PASS:',work,'\n')
}
