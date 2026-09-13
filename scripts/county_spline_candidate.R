#!/usr/bin/env Rscript
# Experimental county thin-plate candidate; does not modify the accepted state fit.
county_spline_basis <- function(years,cutoff,k=6L) {
  years<-sort(unique(as.numeric(years)));train<-years[years<=cutoff]
  if(length(train)<5L || !identical(years,as.numeric(seq(min(years),max(years)))) ||
     !cutoff%in%years || !any(years>cutoff)) stop('Invalid spline year domain')
  if(!requireNamespace('mgcv',quietly=TRUE)) stop('mgcv required to construct training-only basis; supply obj$spline_basis prepared with mgcv')
  k<-min(as.integer(k),length(train));if(k<4L)stop('Spline rank must be at least four')
  sm<-mgcv::smoothCon(mgcv::s(year,bs='tp',k=k),data=data.frame(year=train),absorb.cons=FALSE)[[1]]
  ee<-eigen(sm$S[[1]],symmetric=TRUE);positive<-ee$values>max(ee$values)*1e-9
  transform<-sweep(ee$vectors[,positive,drop=FALSE],2,sqrt(ee$values[positive]),'/')
  center<-mean(train);span<-max(train)-min(train)
  line<-cbind(1,(years-center)/span);trainline<-line[years<=cutoff,,drop=FALSE]
  raw<-mgcv::PredictMat(sm,data.frame(year=years))%*%transform
  projection<-qr.solve(trainline,raw[years<=cutoff,,drop=FALSE])
  nonlinear<-raw-line%*%projection
  scale<-sqrt(exp(mean(log(rowSums(nonlinear[years<=cutoff,,drop=FALSE]^2)))))
  if(!is.finite(scale)||scale<=0)stop('Invalid spline scale')
  list(years=years,cutoff=cutoff,k=k,nonlinear=nonlinear/scale,slope=line[,2],
    training_center=center,training_span=span,scale=scale,mgcv_version=as.character(utils::packageVersion('mgcv')),
    version='training_only_thin_plate_v1')
}
county_spline_design <- function(basis,d,group) {
  year_index<-match(d$year,basis$years);groups<-as.integer(group)
  if(anyNA(year_index)||anyNA(groups)||any(groups<1L)||!setequal(groups,seq_len(max(groups))))stop('Invalid spline design indices')
  n<-nrow(d);q<-ncol(basis$nonlinear)
  Z<-Matrix::sparseMatrix(i=rep(seq_len(n),each=q),
    j=rep((groups-1L)*q,each=q)+rep(seq_len(q),n),
    x=as.vector(t(basis$nonlinear[year_index,,drop=FALSE])),dims=c(n,max(groups)*q))
  L<-Matrix::sparseMatrix(i=seq_len(n),j=groups,x=basis$slope[year_index],dims=c(n,max(groups)))
  list(nonlinear=Z,slope=L)
}
prepare_county_spline_basis <- county_spline_basis
fit_county_spline <- function(obj,variant,cutoff,basis=NULL,threads=4L,verbose=FALSE) {
  if(!variant%in%c('spatial','iid'))stop('Invalid spline county variant')
  if(length(threads)!=1L||!is.finite(threads)||threads<1L||threads!=floor(threads))stop('Invalid spline threads')
  d<-obj$data;required<-c('year','state','state_id','area','population','count')
  if(!all(required%in%names(d))||any(!is.finite(d$population))||any(d$population<=0)||
    any(!is.finite(d$count[d$year<=cutoff]))||any(d$count[d$year<=cutoff]<0)||
    any(d$count[d$year<=cutoff]!=floor(d$count[d$year<=cutoff])))stop('Invalid spline data')
  if(is.null(basis))basis<-obj$spline_basis
  if(is.null(basis))basis<-county_spline_basis(d$year,cutoff)
  if(!identical(as.numeric(basis$years),sort(unique(as.numeric(d$year))))||basis$cutoff!=cutoff||
     basis$version!='training_only_thin_plate_v1')stop('Prepared spline basis domain mismatch')
  if(!is.matrix(basis$nonlinear)||nrow(basis$nonlinear)!=length(basis$years)||
     ncol(basis$nonlinear)!=basis$k-2L||length(basis$slope)!=length(basis$years)||
     any(!is.finite(basis$nonlinear))||any(!is.finite(basis$slope)))stop('Invalid prepared spline basis')
  d$count[d$year>cutoff]<-NA_real_
  zs<-county_spline_design(basis,d,d$state_id);zc<-county_spline_design(basis,d,d$area)
  stack<-INLA::inla.stack(data=list(count=d$count,population=d$population),
    A=list(1,zs$nonlinear,zc$nonlinear,zs$slope,zc$slope),
    effects=list(data.frame(state=d$state,area=d$area),
      list(state_smooth=seq_len(ncol(zs$nonlinear))),list(county_smooth=seq_len(ncol(zc$nonlinear))),
      list(state_slope=seq_len(ncol(zs$slope))),list(county_slope=seq_len(ncol(zc$slope)))),
    tag='all',compress=FALSE,remove.unused=FALSE)
  f<-INLA::f
  pc<-list(prec=list(prior='pc.prec',param=c(.5,.01)))
  slope_prior<-list(prec=list(initial=log(4),fixed=TRUE))
  formula<-count~0+state+
    f(state_smooth,model='iid',hyper=pc)+f(county_smooth,model='iid',hyper=pc)+
    f(state_slope,model='iid',hyper=slope_prior)+f(county_slope,model='iid',hyper=slope_prior)
  if(variant=='iid')formula<-update(formula,.~.+f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))) else {
    graph<-INLA::inla.read.graph(Matrix::Matrix(diag(rowSums(obj$adj))-obj$adj,sparse=TRUE))
    formula<-update(formula,.~.+f(area,model='bym2',graph=graph,scale.model=TRUE,constr=TRUE,adjust.for.con.comp=TRUE,
      hyper=list(prec=list(prior='pc.prec',param=c(1,.01)),phi=list(prior='pc',param=c(.5,.5)))))
  }
  fit<-INLA::inla(formula,data=INLA::inla.stack.data(stack),family='nbinomial',num.threads=paste0(threads,':1'),
    E=d$population,control.fixed=list(mean=log(20/1e5),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(log(12),1),initial=log(12)))),
    verbose=verbose,control.predictor=list(A=INLA::inla.stack.A(stack),compute=TRUE,link=1),
    control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  # INLA A-matrix fits have APredictor (observation scale), not Predictor entries.
  attr(fit,'county_spline_observation_indices')<-seq_len(nrow(d))
  attr(fit,'county_spline_population')<-d$population
  attr(fit,'sensitivity_formula')<-deparse(formula)
  attr(fit,'forecast_specification')<-list(version=basis$version,training_start=min(d$year),training_end=cutoff,
    prediction_end=max(d$year),k=basis$k,mgcv_version=basis$mgcv_version,penalized_sd_upper=.5,
    sd_tail_probability=.01,slope_sd=.5,training_center=basis$training_center,training_span=basis$training_span)
  fit
}

# Same output contract as sample_county_forecast, with the stack observation scale.
sample_county_spline <- function(fit,indices,draws=4000L,seed=20260916L,batch_size=100L) {
  if(!length(indices)||anyNA(indices)||anyDuplicated(indices)||any(indices<1|indices!=floor(indices))||
     any(!indices%in%attr(fit,'county_spline_observation_indices'))||length(draws)!=1L||!is.finite(draws)||
     draws<1||draws!=floor(draws)||length(batch_size)!=1L||!is.finite(batch_size)||batch_size<1||batch_size!=floor(batch_size))stop('Invalid spline sampling request')
  n<-length(indices);mu<-replicated<-matrix(NA_real_,n,draws);sizes<-numeric(draws)
  for(start in seq.int(1L,draws,by=as.integer(batch_size))) {
    jj<-start:min(start+batch_size-1L,draws)
    ss<-INLA::inla.posterior.sample(length(jj),fit,selection=list(APredictor=indices),seed=as.integer(seed+start),num.threads='1:1',skew.corr=FALSE)
    set.seed(as.integer(seed+10000L+start))
    for(k in seq_along(ss)) {
      s<-ss[[k]];ids<-as.integer(sub('^APredictor:','',rownames(s$latent)))
      if(anyNA(ids)||!setequal(ids,indices)||anyDuplicated(ids))stop('Invalid spline APredictor indexing')
      m<-exp(as.numeric(s$latent[match(indices,ids),1]))*attr(fit,'county_spline_population')[indices];ix<-grep('size for',names(s$hyperpar),fixed=TRUE)
      if(length(ix)!=1L)stop('Missing spline negative-binomial size')
      size<-as.numeric(s$hyperpar[ix]);j<-jj[k]
      if(any(!is.finite(m))||!is.finite(size)||size<=0)stop('Invalid spline forecast parameters')
      mu[,j]<-m;sizes[j]<-size;replicated[,j]<-rnbinom(n,mu=m,size=size)
    }
  }
  list(mu=mu,replicated=replicated,size=sizes,indices=indices,approximation='INLA joint posterior sampling with skew.corr=FALSE; APredictor')
}
