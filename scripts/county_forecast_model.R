#!/usr/bin/env Rscript
# County forecast model with prior scale and centering defined at the origin.
# Historical sensitivity models and the published state spline are untouched.
rw1_training_scale <- function(n_training) {
  if (length(n_training)!=1L || !is.finite(n_training) ||
      n_training!=as.integer(n_training) || n_training<3L) stop('At least three consecutive training years required')
  n<-as.integer(n_training)
  difference<-matrix(0,n-1L,n)
  difference[cbind(seq_len(n-1L),seq_len(n-1L))]<- -1
  difference[cbind(seq_len(n-1L),2:n)]<-1
  eig<-eigen(crossprod(difference),symmetric=TRUE)
  positive<-eig$values>max(eig$values)*1e-10
  covariance_factor<-sweep(eig$vectors[,positive,drop=FALSE],2,sqrt(eig$values[positive]),'/')
  # This is the multiplier of Q used to give the constrained training RW1 a
  # geometric-mean marginal variance of one at unit standardized precision.
  exp(mean(log(rowSums(covariance_factor^2))))
}

county_forecast_specification <- function(years,cutoff) {
  years<-sort(unique(as.numeric(years)))
  if (!length(years) || any(!is.finite(years)) || any(years!=floor(years)) ||
      !identical(years,as.numeric(seq.int(min(years),max(years)))) ||
      length(cutoff)!=1L || !is.finite(cutoff) || cutoff!=floor(cutoff) ||
      !cutoff %in% years || !any(years>cutoff)) stop('Invalid forecast year domain or cutoff')
  n_training<-sum(years<=cutoff);scale<-rw1_training_scale(n_training)
  # Every replicated RW1 receives this same constraint, using only training
  # coefficients. Future coefficients are unconstrained random-walk continuations.
  A<-matrix(as.numeric(years<=cutoff)/n_training,nrow=1L)
  list(version='training_origin_rw1_v1',training_start=min(years),training_end=cutoff,
    prediction_end=max(years),training_years=n_training,domain_years=length(years),
    training_precision_scale=scale,standardized_sd_upper=.5,sd_tail_probability=.01,
    innovation_sd_upper=.5/sqrt(scale),constraint=list(A=A,e=0),
    centering='Mean over training years is zero; future coefficients are not included in centering',
    precision='Unscaled RW1 precision; PC SD bound is 0.5/sqrt(training_precision_scale)')
}

fit_county_forecast <- function(obj,variant,cutoff,county_time=TRUE,threads=4L,verbose=FALSE) {
  if (!variant %in% c('spatial','iid')) stop('Invalid county forecast variant')
  if (length(threads)!=1L || !is.finite(threads) || threads<1L || threads!=as.integer(threads)) stop('Invalid thread count')
  d<-obj$data
  required<-c('year','state','state_id','area','population','count')
  if (!all(required %in% names(d))) stop('Forecast data lack model fields')
  spec<-county_forecast_specification(d$year,cutoff)
  if (any(!is.finite(d$population)) || any(d$population<=0) ||
      any(!is.finite(d$count[d$year<=cutoff])) || any(d$count[d$year<=cutoff]<0) ||
      any(d$count[d$year<=cutoff]!=floor(d$count[d$year<=cutoff]))) stop('Invalid training outcomes or forecast populations')
  # Mask internally as well as in the caller: later counts can never enter this fit.
  d$count[d$year>cutoff]<-NA_real_
  d$time<-match(d$year,sort(unique(d$year)));d$county_time<-d$time
  nt<-spec$domain_years;constraint<-spec$constraint
  temporal_hyper<-list(prec=list(prior='pc.prec',param=c(spec$innovation_sd_upper,.01)))
  f<-INLA::f
  graph<-INLA::inla.read.graph(Matrix::Matrix(diag(rowSums(obj$adj))-obj$adj,sparse=TRUE))
  if (variant=='spatial') {
    formula<-count~0+state+offset(log(population))+
      f(area,model='bym2',graph=graph,scale.model=TRUE,constr=TRUE,adjust.for.con.comp=TRUE,
        hyper=list(prec=list(prior='pc.prec',param=c(1,.01)),phi=list(prior='pc',param=c(.5,.5))))+
      f(time,model='rw1',n=nt,replicate=state_id,scale.model=FALSE,constr=FALSE,
        extraconstr=constraint,rankdef=1,hyper=temporal_hyper)
  } else {
    formula<-count~0+state+offset(log(population))+
      f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
      f(time,model='rw1',n=nt,replicate=state_id,scale.model=FALSE,constr=FALSE,
        extraconstr=constraint,rankdef=1,hyper=temporal_hyper)
  }
  if (county_time) formula<-update(formula,.~.+f(county_time,model='rw1',n=nt,replicate=area,
    scale.model=FALSE,constr=FALSE,extraconstr=constraint,rankdef=1,hyper=temporal_hyper))
  fit<-INLA::inla(formula,data=d,family='nbinomial',num.threads=paste0(threads,':1'),
    control.fixed=list(mean=log(20/1e5),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(log(12),1),initial=log(12)))),
    verbose=verbose,control.predictor=list(compute=TRUE,link=1),
    control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  attr(fit,'sensitivity_formula')<-deparse(formula)
  attr(fit,'forecast_specification')<-spec
  fit
}

sample_county_forecast <- function(fit,indices,draws=4000L,seed=20260916L,batch_size=100L) {
  if (!length(indices) || anyNA(indices) || anyDuplicated(indices) ||
      any(indices<1 | indices!=floor(indices)) || length(draws)!=1L ||
      !is.finite(draws) || draws<1 || draws!=floor(draws) ||
      length(batch_size)!=1L || !is.finite(batch_size) || batch_size<1 || batch_size!=floor(batch_size))
    stop('Invalid posterior sampling request')
  n<-length(indices);mu<-replicated<-matrix(NA_real_,n,draws);sizes<-numeric(draws)
  for (start in seq.int(1L,draws,by=as.integer(batch_size))) {
    jj<-start:min(start+batch_size-1L,draws)
    samples<-INLA::inla.posterior.sample(length(jj),fit,selection=list(Predictor=indices),
      seed=as.integer(seed+start),num.threads='1:1',skew.corr=FALSE)
    set.seed(as.integer(seed+10000L+start))
    for (k in seq_along(samples)) {
      s<-samples[[k]];ids<-as.integer(sub('^Predictor:','',rownames(s$latent)))
      if (anyNA(ids) || length(ids)!=n || anyDuplicated(ids) || !setequal(ids,indices))
        stop('Unexpected forecast predictor indexing')
      m<-exp(as.numeric(s$latent[match(indices,ids),1]))
      ix<-grep('size for',names(s$hyperpar),fixed=TRUE)
      if (length(ix)!=1L) stop('Missing negative-binomial size')
      size<-as.numeric(s$hyperpar[ix])
      if (any(!is.finite(m)) || !is.finite(size) || size<=0) stop('Invalid forecast parameters')
      j<-jj[k];mu[,j]<-m;sizes[j]<-size;replicated[,j]<-rnbinom(n,mu=m,size=size)
    }
  }
  if (any(!is.finite(replicated))) stop('Nonfinite predictive draw')
  list(mu=mu,replicated=replicated,size=sizes,indices=indices,
    approximation='INLA joint posterior sampling with skew.corr=FALSE')
}
