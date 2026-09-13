source('scripts/county_forecast_model.R')
source('scripts/audit_saved_forecast_sampling.R')
set.seed(42)
x<-matrix(rnorm(120,-500,8),12,10)
a<-density_moments(x);b<-density_moments(x[,1:4]);b<-density_moments(x[,5:10],b)
stopifnot(max(abs(summarize_density(a)$log_density-summarize_density(b)$log_density))<1e-12,
 max(abs(summarize_density(a)$relative_mcse-summarize_density(b)$relative_mcse))<1e-12)
reference<-log(rowMeans(exp(x+500)))-500
stopifnot(max(abs(reference-summarize_density(a)$log_density))<1e-12)
stopifnot(inherits(try(density_moments(matrix(-Inf,2,2)),silent=TRUE),'try-error'))
d<-data.frame(fips=rep('00001',5),state=factor(rep('AA',5)),year=2001:2005,population=100,area=1L,state_id=1L,count=1:5)
f<-list(.args=list(data=d,family='nbinomial'),misc=list(configs=list(test=TRUE)),summary.linear.predictor=data.frame(mean=rep(0,5)))
f$.args$data$count[4:5]<-NA;attr(f,'forecast_specification')<-county_forecast_specification(d$year,2003)
validate_saved_forecast(f,d,2003,2)
f$summary.random<-list(area=NULL,time=NULL,county_time=NULL);f$model.random<-c("IID model","RW1 model","RW1 model")
validate_saved_forecast(f,d,2003,2,"iid_county_time")
stopifnot(inherits(try(validate_saved_forecast(f,d,2003,2,"spatial_county_time"),silent=TRUE),"try-error"))
g<-f;g$.args$data$count[4]<-4;stopifnot(inherits(try(validate_saved_forecast(g,d,2003,2),silent=TRUE),'try-error'))
g<-f;g$.args$data$population[1]<-101;stopifnot(inherits(try(validate_saved_forecast(g,d,2003,2),silent=TRUE),'try-error'))
g<-f;attr(g,'forecast_specification')$prediction_end<-2006;stopifnot(inherits(try(validate_saved_forecast(g,d,2003,2),silent=TRUE),'try-error'))
# Optional existing synthetic INLA checkpoint: sampling only, no fit created.
a<-commandArgs(TRUE)
if(length(a)) {
  f<-readRDS(a[1]);d<-f$.args$data;cutoff<-attr(f,'forecast_specification')$training_end
  d$count[d$year>cutoff]<-0
  validate_saved_forecast(f,d,cutoff,max(d$year)-cutoff,"iid_county_time")
  z<-sample_saved_density(f,d,cutoff,draws=200L,seed=91001L)
  stopifnot(nrow(z$cells)==sum(d$year>cutoff),all(is.finite(z$cells$log_predictive_density)),all(z$cells$density_relative_mcse>=0),nrow(z$batches)==2*nrow(z$scores))
}
cat('Saved forecast sampling tests PASS\n')
