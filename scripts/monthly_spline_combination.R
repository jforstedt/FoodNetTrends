#!/usr/bin/env Rscript
# Source county_forecast_model.R, county_spline_candidate.R and monthly_seasonal_model.R first.
# Controlled monthly candidate: state temporal effects, county IID intercept only.
monthly_combination_basis <- function(serial,cutoff,k=6L) {
  b<-county_spline_basis(serial,cutoff,k)
  train<-b$years<=cutoff
  # Orthogonalize using TRAINING rows only. The same deterministic transform is
  # applied to prediction rows; the spline cannot substitute for month effects.
  phase<-factor(b$years%%12,levels=0:11)
  nuisance<-cbind(1,b$slope,model.matrix(~phase)[,-1,drop=FALSE])
  projection<-qr.solve(nuisance[train,,drop=FALSE],b$nonlinear[train,,drop=FALSE])
  z<-b$nonlinear-nuisance%*%projection
  if(qr(z[train,,drop=FALSE])$rank!=ncol(z))stop('Monthly spline lost nonlinear rank')
  scale<-sqrt(exp(mean(log(rowSums(z[train,,drop=FALSE]^2)))))
  if(!is.finite(scale)||scale<=0)stop('Invalid monthly spline scale')
  b$nonlinear<-z/scale;b$phase_projection<-projection;b$phase_scale<-scale
  b$version<-'monthly_training_phase_orthogonal_thin_plate_v1'
  b
}

fit_monthly_combination <- function(d,cutoff,temporal='rw1',seasonal=TRUE,threads=4L,
  coverage='SYNTHETIC_COMPLETE',basis=NULL) {
  if(length(temporal)!=1||!temporal%in%c('rw1','spline')||length(seasonal)!=1||is.na(seasonal)||!is.logical(seasonal)||
     length(threads)!=1||!is.finite(threads)||threads<1||threads!=floor(threads))stop('Invalid combination options')
  if(temporal=='rw1')return(fit_monthly_model(d,cutoff,seasonal=seasonal,threads=threads,coverage=coverage,rate_center=.0002))
  obj<-monthly_model_data(d,cutoff,coverage);d<-obj$data;spec<-obj$spec
  serial<-12*d$year+d$month-1L
  if(is.null(basis))basis<-monthly_combination_basis(serial,cutoff)
  if(!identical(as.numeric(basis$years),sort(unique(as.numeric(serial))))||basis$cutoff!=cutoff||
     basis$version!='monthly_training_phase_orthogonal_thin_plate_v1'||!is.matrix(basis$nonlinear)||
     nrow(basis$nonlinear)!=length(basis$years)||ncol(basis$nonlinear)!=basis$k-2||
     length(basis$slope)!=length(basis$years)||any(!is.finite(basis$nonlinear))||any(!is.finite(basis$slope)))stop('Invalid prepared monthly basis')
  if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
  design_data<-d;design_data$year<-serial
  z<-county_spline_design(basis,design_data,d$state_id)
  stack<-INLA::inla.stack(data=list(count=d$count),A=list(1,z$nonlinear,z$slope),
    effects=list(data.frame(state=d$state,area=d$area,season=d$season),
      list(state_smooth=seq_len(ncol(z$nonlinear))),list(state_slope=seq_len(ncol(z$slope)))),
    tag='all',compress=FALSE,remove.unused=FALSE)
  f<-INLA::f
  pc<-list(prec=list(prior='pc.prec',param=c(.5,.01)))
  slope_prior<-list(prec=list(initial=log(4),fixed=TRUE))
  formula<-count~0+state+f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
    f(state_smooth,model='iid',hyper=pc)+f(state_slope,model='iid',hyper=slope_prior)
  cycle<-monthly_cycle_scale()
  seasonal_prior<-list(prec=list(prior='pc.prec',param=c(.5/sqrt(cycle$scale),.01)))
  if(seasonal)formula<-update(formula,.~.+f(season,model='rw1',n=12,cyclic=TRUE,constr=FALSE,
    scale.model=FALSE,extraconstr=list(A=matrix(1/12,1,12),e=0),rankdef=1,hyper=seasonal_prior))
  fit<-INLA::inla(formula,data=INLA::inla.stack.data(stack),family='nbinomial',E=d$person_years,
    num.threads=paste0(threads,':1'),control.fixed=list(mean=log(.0002),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(log(20),1),initial=log(20)))),
    control.predictor=list(A=INLA::inla.stack.A(stack),compute=TRUE,link=1),
    control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  attr(fit,'monthly_combination_indices')<-seq_len(nrow(d))
  attr(fit,'monthly_combination_exposure')<-d$person_years
  attr(fit,'monthly_combination_basis')<-basis
  spec$version<-basis$version;spec$trend_constraint<-NULL;spec$trend_scale<-NULL;spec$trend_sd_bound<-NULL
  attr(fit,'monthly_specification')<-c(spec,list(temporal='spline',seasonal=seasonal,cycle_scale=cycle$scale,
    rate_center=.0002,k=basis$k,slope_sd=.5,nonlinear_sd_upper=.5,county_temporal=FALSE,
    phase_projection='training intercept, linear time and 11 month contrasts'))
  fit
}

sample_monthly_combination <- function(fit,indices,draws=4000L,seed=20260916L,batch_size=100L) {
  if(is.null(attr(fit,'monthly_combination_indices')))return(sample_county_forecast(fit,indices,draws,seed,batch_size))
  # Reuse the tested APredictor sampler with its required explicit exposure.
  attr(fit,'county_spline_observation_indices')<-attr(fit,'monthly_combination_indices')
  attr(fit,'county_spline_population')<-attr(fit,'monthly_combination_exposure')
  sample_county_spline(fit,indices,draws,seed,batch_size)
}
