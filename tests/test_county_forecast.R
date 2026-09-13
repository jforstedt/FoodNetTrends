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
short<-restrict_forecast_horizon(obj,cutoff,1L)
stopifnot(max(short$data$year)==2008,max(obj$data$year)==2009,identical(short$years,2004:2008),
 inherits(try(restrict_forecast_horizon(obj,cutoff,3L),silent=TRUE),'try-error'))
b<-tempfile();dir.create(b);INLA::inla.setOption(num.threads='2:1')
for(v in c('spatial','iid'))for(time in c(FALSE,TRUE)) {
 out<-file.path(b,paste(v,time));dir.create(out)
 fit<-fit_county_forecast(obj,v,cutoff,county_time=time,threads=2)
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
# Exercise the full reporting path with an explicitly bounded horizon. The
# production audit is replaced only by this already constructed synthetic panel.
audit<-file.path(b,'audit');dir.create(audit);saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
original_validator<-validate_panel
validate_panel<-function(...)list(data=d,adj=adj,ids=sort(unique(d$fips)),years=2004:2009)
run_forecast(audit,file.path(b,'bounded_run'),'iid_county_time',threads=2,draws=100L,
  cutoff=cutoff,expected_production=FALSE,horizon=1L)
validate_panel<-original_validator
report<-file.path(b,'bounded_run','reports')
split<-read.csv(file.path(report,'split.csv'));cells<-read.csv(file.path(report,'heldout_cells_INTERNAL.csv'))
spec<-read.csv(file.path(report,'forecast_specification.csv'));weights<-read.csv(file.path(report,'temporal_constraint.csv'))
stopifnot(split$test_end==2008,split$audited_source_end==2009,split$evaluation_horizon==1,
 all(cells$year==2008),spec$version=='training_origin_rw1_v1',
 all(weights$centering_weight[weights$year>cutoff]==0))
cat('PASS full forecast reporting, one-year horizon restriction and origin-prior provenance\n')
unlink(b,recursive=TRUE)
