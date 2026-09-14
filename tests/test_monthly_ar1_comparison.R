source('scripts/run_monthly_ar1_comparison.R')
# Stationary AR1 marginal covariance is independent of appended forecast nodes.
rho<-.9;covariance<-function(n)rho^abs(outer(seq_len(n),seq_len(n),'-'))
stopifnot(identical(covariance(60),covariance(96)[1:60,1:60]))
h<-1:120;v<-1-rho^(2*h);stopifnot(all(v>=0&v<=1),rho^120<.001)
d<-expand.grid(area=1:4,time0=0:95);d$fips<-sprintf('%05d',d$area);d$state<-ifelse(d$area<=2,'AA','BB')
d$year<-2004+d$time0%/%12;d$month<-d$time0%%12+1;d$person_years<-20000;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
set.seed(197);d$count<-rnbinom(nrow(d),mu=4*exp(.5*cos(2*pi*d$month/12)),size=20)
obj<-monthly_model_data(d,2008*12+11L,'EXPLORATORY_ASSUMED_CONTINUOUS')
stopifnot(all(is.na(obj$data$count[d$year>2008])))
if('--fit'%in%commandArgs(TRUE)) {
 load_monthly_comparison<-function(...)d
 work<-tempfile('ar1-test-');dir.create(work)
 run_ar1_comparison('unused','unused',2008,file.path(work,'result'),67000000L,draws=100L)
 fit<-readRDS(file.path(work,'fit_INTERNAL.rds'));pred<-read.csv(file.path(work,'heldout_truth_INTERNAL.csv'),colClasses=c(fips='character'))
 validate_monthly_saved(fit,pred,2008,TRUE,expected_temporal='ar1')
 stopifnot(inherits(try(validate_monthly_saved(fit,pred,2008,TRUE),silent=TRUE),'try-error'))
 spec<-attr(fit,'monthly_specification');stopifnot(is.null(spec$trend_constraint),spec$ar1_marginal_sd_upper==1)
 bad<-fit;attr(bad,'monthly_specification')$ar1_rho_internal_sd<-2
 stopifnot(inherits(try(validate_monthly_saved(bad,pred,2008,TRUE,expected_temporal='ar1'),silent=TRUE),'try-error'))
 ext<-d[d$year==2011,];ext$year<-2012;ext$count<-Inf
 longer<-fit_monthly_model(rbind(d,ext),2008*12+11L,TRUE,threads=2L,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002,temporal_model='ar1')
 delta<-abs(fit$summary.linear.predictor$mean-longer$summary.linear.predictor$mean[seq_len(nrow(d))])
 stopifnot(max(delta/fit$summary.linear.predictor$sd)<.05)
 cat('AR1 fit, horizon invariance and posterior sampling PASS:',work,'\n')
}
cat('AR1 checks PASS\n')
