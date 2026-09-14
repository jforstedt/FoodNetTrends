source('scripts/audit_saved_monthly.R')
# Stable density arithmetic agrees with direct arithmetic, including chunking.
ld<-matrix(log(c(.1,.2,.3,.4,.5,.6)),2,3)
a<-density_moments(ld);b<-density_moments(ld[,3,drop=FALSE],density_moments(ld[,1:2]))
stopifnot(max(abs(summarize_density(a)$log_density-log(rowMeans(exp(ld)))))<1e-12,
 max(abs(summarize_density(a)$log_density-summarize_density(b)$log_density))<1e-12)
x<-matrix(c(rep(1,99),901),1);r<-tail_summary(x,x,1,data.frame(state='ALL',year=2012),1)
stopifnot(r$mean_expected==10,r$top_one_percent_mean_share==.901,r$median_expected==1)
x[1]<-Inf;stopifnot(inherits(try(tail_summary(x,x,1,data.frame(state='ALL',year=2012),1),silent=TRUE),'try-error'))
cat('Saved monthly density and tail tests PASS\n')
if('--fit'%in%commandArgs(TRUE)) {
 source('scripts/county_forecast_model.R');source('scripts/monthly_seasonal_model.R')
 set.seed(1981);d<-expand.grid(area=1:2,time0=0:59);d$fips<-sprintf('%05d',d$area);d$state<-ifelse(d$area==1,'AA','BB')
 d$year<-2004+d$time0%/%12;d$month<-d$time0%%12+1;d$person_years<-20000;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 d$count<-rnbinom(nrow(d),mu=4*exp(.5*cos(2*pi*d$month/12)),size=20)
 fit<-fit_monthly_model(d,2005*12+11L,TRUE,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002)
 pred<-d[d$year>2005,c('fips','state','year','month')];pred$observed<-d$count[d$year>2005]
 validate_monthly_saved(fit,pred,2005,TRUE)
 bad<-pred[nrow(pred):1,];stopifnot(inherits(try(validate_monthly_saved(fit,bad,2005,TRUE),silent=TRUE),'try-error'))
 stopifnot(inherits(try(validate_monthly_saved(fit,pred,2005,FALSE),silent=TRUE),'try-error'))
 fp<-tempfile(fileext='.rds');pp<-tempfile(fileext='.csv');saveRDS(fit,fp);write.csv(pred,pp,row.names=FALSE)
 before<-tools::md5sum(c(fp,pp));out<-tempfile('saved-monthly-check-')
 audit_monthly_saved(fp,pp,2005,TRUE,out,41000000L,draws=100L)
 stopifnot(identical(before,tools::md5sum(c(fp,pp))),readLines(file.path(out,'status.txt'))=='SAVED_MONTHLY_DIAGNOSTICS_COMPLETE')
 scores<-read.csv(file.path(out,'stream_scores.csv'));tails<-read.csv(file.path(out,'aggregate_tails.csv'))
 stopifnot(nrow(scores)==30,nrow(tails)==45,all(is.finite(scores$mean_log_score)),all(tails$top_one_percent_mean_share>=0&tails$top_one_percent_mean_share<=1))
 cat('Actual saved monthly sampling test PASS:',out,'\n')
}
