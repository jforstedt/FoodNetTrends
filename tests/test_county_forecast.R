source('scripts/fit_county_pilot.R');source('scripts/diagnose_saved_county_pilot.R');source('scripts/county_sensitivity.R');source('scripts/county_forecast_check.R')
set.seed(25);n<-16L;adj<-matrix(0,n,n)
for(i in c(1:7,9:15)){adj[i,i+1]<-1;adj[i+1,i]<-1}
d<-expand.grid(area=1:n,time=1:6);d<-d[order(d$area,d$time),]
d$fips<-sprintf('%05d',d$area);d$year<-2003L+d$time;d$state<-factor(ifelse(d$area<=8,'AA','BB'));d$state_id<-as.integer(d$state)
d$population<-10000+d$area*500;d$count<-rnbinom(nrow(d),mu=d$population*exp(log(.0002)+.05*d$time),size=12)
cutoff<-2007L;mask<-d$year>cutoff;mutated<-d;mutated$count[mask]<-999999L
stopifnot(identical(training_panel(d,cutoff),training_panel(mutated,cutoff)),
 identical(forecast_groups(d,which(mask),cutoff),forecast_groups(mutated,which(mask),cutoff)))
stopifnot(abs(log_average(log(c(.1,.2,.3)))-log(.2))<1e-12)
obj<-list(data=training_panel(d,cutoff),adj=adj,ids=sort(unique(d$fips)),years=2004:2009)
b<-tempfile();dir.create(b);INLA::inla.setOption(num.threads='2:1')
for(v in c('spatial','iid'))for(time in c(FALSE,TRUE)) {
 out<-file.path(b,paste(v,time));dir.create(out)
 fit<-sensitivity_fit(obj,v,county_time=time,threads=2,predictor_link=1)
 z<-forecast_diagnostics(fit,d,out,cutoff,draws=100)
 stopifnot(nrow(z)==sum(mask),all(z$year>cutoff),all(is.finite(z$log_predictive_density)),
   all(z$randomized_pit>=0&z$randomized_pit<=1),all(z$predicted_zero_probability>=0&z$predicted_zero_probability<=1),
   all(z$lower95<=z$median&z$median<=z$upper95))
 # Response-scale summaries for NA outcomes must use the NB log link.
 analytic<-fit$summary.fitted.values$mean[mask]
 stopifnot(sum(z$mean_expected)/sum(analytic)>.7,sum(z$mean_expected)/sum(analytic)<1.3)
 a<-read.csv(file.path(out,'heldout_aggregate_checks_INTERNAL.csv'))
 for(kind in unique(a$grouping)){r<-a[a$grouping==kind,];stopifnot(sum(r$cells)==sum(mask),sum(r$observed_total)==sum(d$count[mask]))}
 cat('PASS actual held-out',v,'county_time=',time,'fit, no future outcome leakage, log link and scoring\n')
}
unlink(b,recursive=TRUE)
