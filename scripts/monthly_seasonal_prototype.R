#!/usr/bin/env Rscript
# Synthetic-only monthly reference and cyclic-seasonal prototype.
# Source county_forecast_model.R first for training-origin RW1 scaling.
monthly_prototype_data <- function(d,cutoff) {
  needed<-c('area','state','year','month','person_years','count','observation_status')
  if(!all(needed%in%names(d))||!isTRUE(attr(d,'synthetic')))stop('Synthetic data marker and monthly fields required; production inputs are gated')
  if(anyNA(d[c('area','state','year','month','person_years','observation_status')])||any(!is.finite(d$year)|d$year!=floor(d$year))||any(!is.finite(d$month)|d$month!=floor(d$month)|d$month<1|d$month>12)||any(!is.finite(d$person_years)|d$person_years<=0)||any(d$observation_status!='SYNTHETIC_COMPLETE'))stop('Invalid synthetic monthly domain/exposure')
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
  list(data=d,training=train,spec=list(version='synthetic_monthly_rw1_cycle_v1',cutoff=cutoff,
    n_training=nt,n_time=length(times),trend_scale=scale,trend_sd_bound=.5/sqrt(scale),
    trend_constraint=list(A=matrix(as.numeric(times<=cutoff)/nt,nrow=1),e=0),
    seasonal_sd_bound=.5,pc_tail=.01,nb_log_size_mean=log(20),nb_log_size_sd=1,
    status='SYNTHETIC_ONLY_NOT_PRODUCTION_PRIORS'))
}

monthly_cycle_scale <- function() {
  D<-diag(12);D[cbind(1:12,c(2:12,1))]<- -1
  Q<-crossprod(D);ee<-eigen(Q,symmetric=TRUE);positive<-ee$values>1e-10
  cov<-tcrossprod(sweep(ee$vectors[,positive,drop=FALSE],2,sqrt(ee$values[positive]),'/'))
  list(Q=Q,scale=exp(mean(log(diag(cov)))))
}

fit_monthly_prototype <- function(d,cutoff,seasonal=TRUE,threads=2L) {
  if(length(seasonal)!=1||is.na(seasonal)||!is.logical(seasonal)||length(threads)!=1||!is.finite(threads)||threads<1||threads!=floor(threads))stop('Invalid fit options')
  obj<-monthly_prototype_data(d,cutoff);d<-obj$data;spec<-obj$spec
  if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
  f<-INLA::f;nt<-spec$n_time;constraint<-spec$trend_constraint
  temporal<-list(prec=list(prior='pc.prec',param=c(spec$trend_sd_bound,spec$pc_tail)))
  cycle<-monthly_cycle_scale()
  seasonal_prior<-list(prec=list(prior='pc.prec',param=c(spec$seasonal_sd_bound/sqrt(cycle$scale),spec$pc_tail)))
  formula<-count~0+state+offset(log(person_years))+
    f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
    f(time,model='rw1',n=nt,replicate=state_id,constr=FALSE,scale.model=FALSE,
      extraconstr=constraint,rankdef=1,hyper=temporal)
  if(seasonal)formula<-update(formula,.~.+f(season,model='rw1',n=12,cyclic=TRUE,
    constr=FALSE,scale.model=FALSE,extraconstr=list(A=matrix(1/12,1,12),e=0),rankdef=1,hyper=seasonal_prior))
  fit<-INLA::inla(formula,data=d,family='nbinomial',num.threads=paste0(threads,':1'),
    control.fixed=list(mean=log(.002),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(spec$nb_log_size_mean,1/spec$nb_log_size_sd^2),initial=spec$nb_log_size_mean))),
    control.predictor=list(compute=TRUE,link=1),control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  attr(fit,'monthly_specification')<-c(spec,list(seasonal=seasonal,cycle_scale=cycle$scale))
  fit
}
