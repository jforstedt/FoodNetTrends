#!/usr/bin/env Rscript
# Shared monthly reference and cyclic-seasonal implementation.
# Coverage is an explicit analysis contract, not certification of ascertainment.
# Source county_forecast_model.R first for training-origin RW1 scaling.
monthly_model_data <- function(d,cutoff,coverage='SYNTHETIC_COMPLETE',trend_sd_upper=.5) {
  if(length(trend_sd_upper)!=1||!is.finite(trend_sd_upper)||trend_sd_upper<=0)stop('Invalid temporal SD prior bound')
  needed<-c('area','state','year','month','person_years','count','observation_status')
  if(!coverage%in%c('SYNTHETIC_COMPLETE','EXPLORATORY_ASSUMED_CONTINUOUS')||!all(needed%in%names(d)))stop('Invalid coverage contract or monthly fields')
  if(coverage=='SYNTHETIC_COMPLETE'&&!isTRUE(attr(d,'synthetic')))stop('Synthetic marker required')
  if(anyNA(d[c('area','state','year','month','person_years','observation_status')])||any(!is.finite(d$year)|d$year!=floor(d$year))||any(!is.finite(d$month)|d$month!=floor(d$month)|d$month<1|d$month>12)||any(!is.finite(d$person_years)|d$person_years<=0)||any(d$observation_status!=coverage))stop('Invalid synthetic monthly domain/exposure')
  serial<-12*d$year+d$month-1L
  if(length(cutoff)!=1L||!is.finite(cutoff)||cutoff!=floor(cutoff)||!cutoff%in%serial)stop('Invalid cutoff; use year*12+month-1')
  times<-sort(unique(serial));areas<-sort(unique(as.character(d$area)))
  if(!identical(as.numeric(times),as.numeric(seq(min(times),max(times))))||sum(times<=cutoff)<24||!any(times>cutoff))stop('Consecutive domain, two training years and future months required')
  key<-paste(d$area,serial)
  if(anyDuplicated(key)||nrow(d)!=length(times)*length(areas))stop('Incomplete or duplicate county/month grid')
  if(any(vapply(split(as.character(d$state),d$area),function(x)length(unique(x))!=1,logical(1))))stop('County changes state')
  train<-serial<=cutoff
  if(any(!is.finite(d$count[train])|d$count[train]<0|d$count[train]!=floor(d$count[train])))stop('Invalid training counts')
  d$count[!train]<-NA_real_ # do not even validate held-out outcomes as training inputs
  d$area<-match(as.character(d$area),areas);d$state<-factor(d$state)
  d$state_id<-as.integer(d$state);d$time<-match(serial,times);d$season<-d$month
  nt<-sum(times<=cutoff);scale<-rw1_training_scale(nt)
  list(data=d,training=train,spec=list(version='monthly_rw1_cycle_v1',cutoff=cutoff,
    n_training=nt,n_time=length(times),trend_scale=scale,trend_sd_upper=trend_sd_upper,trend_sd_bound=trend_sd_upper/sqrt(scale),
    trend_constraint=list(A=matrix(as.numeric(times<=cutoff)/nt,nrow=1),e=0),
    seasonal_sd_bound=.5,pc_tail=.01,nb_log_size_mean=log(20),nb_log_size_sd=1,
    coverage=coverage))
}

monthly_cycle_scale <- function() {
  D<-diag(12);D[cbind(1:12,c(2:12,1))]<- -1
  Q<-crossprod(D);ee<-eigen(Q,symmetric=TRUE);positive<-ee$values>1e-10
  cov<-tcrossprod(sweep(ee$vectors[,positive,drop=FALSE],2,sqrt(ee$values[positive]),'/'))
  list(Q=Q,scale=exp(mean(log(diag(cov)))))
}

fit_monthly_model <- function(d,cutoff,seasonal=TRUE,threads=2L,coverage='SYNTHETIC_COMPLETE',rate_center=.002,trend_sd_upper=.5,temporal_model='rw1') {
  if(length(seasonal)!=1||is.na(seasonal)||!is.logical(seasonal)||length(threads)!=1||!is.finite(threads)||threads<1||threads!=floor(threads))stop('Invalid fit options')
  if(length(rate_center)!=1||!is.finite(rate_center)||rate_center<=0)stop('Invalid prior rate')
  if(!temporal_model%in%c('rw1','ar1'))stop('Invalid temporal model')
  obj<-monthly_model_data(d,cutoff,coverage,trend_sd_upper);d<-obj$data;spec<-obj$spec
  if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
  f<-INLA::f;nt<-spec$n_time;constraint<-spec$trend_constraint
  temporal<-list(prec=list(prior='pc.prec',param=c(spec$trend_sd_bound,spec$pc_tail)))
  cycle<-monthly_cycle_scale()
  seasonal_prior<-list(prec=list(prior='pc.prec',param=c(spec$seasonal_sd_bound/sqrt(cycle$scale),spec$pc_tail)))
  formula<-count~0+state+offset(log(person_years))+
    f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
    f(time,model='rw1',n=nt,replicate=state_id,constr=FALSE,scale.model=FALSE,
      extraconstr=constraint,rankdef=1,hyper=temporal)
  if(temporal_model=='ar1') {
    # Proper stationary AR1: prec is MARGINAL precision, not innovation precision.
    spec$version<-'monthly_ar1_cycle_v1';spec$trend_constraint<-NULL
    spec$trend_scale<-NULL;spec$trend_sd_bound<-NULL;spec$trend_sd_upper<-NULL
    spec$ar1_marginal_sd_upper<-1;spec$ar1_rho_internal_mean<-log(19);spec$ar1_rho_internal_sd<-1.5
    ar_prior<-list(prec=list(prior='pc.prec',param=c(1,.01)),rho=list(prior='normal',param=c(log(19),1/1.5^2)))
    formula<-count~0+state+offset(log(person_years))+
      f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
      f(time,model='ar1',n=nt,replicate=state_id,constr=FALSE,hyper=ar_prior)
  }
  if(seasonal)formula<-update(formula,.~.+f(season,model='rw1',n=12,cyclic=TRUE,
    constr=FALSE,scale.model=FALSE,extraconstr=list(A=matrix(1/12,1,12),e=0),rankdef=1,hyper=seasonal_prior))
  fit<-INLA::inla(formula,data=d,family='nbinomial',num.threads=paste0(threads,':1'),
    control.fixed=list(mean=log(rate_center),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(spec$nb_log_size_mean,1/spec$nb_log_size_sd^2),initial=spec$nb_log_size_mean))),
    control.predictor=list(compute=TRUE,link=1),control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  attr(fit,'monthly_specification')<-c(spec,list(seasonal=seasonal,cycle_scale=cycle$scale,rate_center=rate_center))
  fit
}
