#!/usr/bin/env Rscript
# Fixed-truth simulation screening for the training-domain county forecast engine.
# This is not simulation-based calibration over the prior or proof of tail accuracy.
calibration_specification <- function() list(version='county-forecast-calibration-v1',
  densities=c('sparse','dense'),variants=c('spatial','iid'),counties=12L,
  training_years=8L,horizons=1:3,minimum_replicates=20L,minimum_draws=1000L,
  nominal_coverage=.95,gross_coverage_floor=.85,mean_log_rate=log(20/1e5),
  county_sd=.35,state_rw_sd=.12,county_rw_sd=.08,phi=.5,nb_size=8,
  reference='Known training latent effects and hyperparameters, with new joint RW innovations; not an exact posterior reference',
  approximation='INLA Gaussian joint latent sampling, skew.corr=FALSE; approximation-equivalence unverified')

calibration_truth <- function(density,variant,replicate,horizons=3L) {
  spec<-calibration_specification()
  if(!density%in%spec$densities||!variant%in%spec$variants||length(replicate)!=1||
     !is.finite(replicate)||replicate<1||replicate!=as.integer(replicate)||
     !horizons%in%1:3)stop('Invalid calibration scenario')
  seed<-as.integer(101000L+replicate*100L+match(variant,spec$variants)*10L)
  set.seed(seed);n<-spec$counties;nt<-spec$training_years;ns<-2L
  adj<-matrix(0,n,n)
  for(i in c(1:5,7:11)){adj[i,i+1]<-1;adj[i+1,i]<-1}
  spatial<-scaled_intrinsic(diag(rowSums(adj))-adj)
  county<-if(variant=='spatial')spec$county_sd*(sqrt(spec$phi)*as.vector(spatial$L%*%rnorm(ncol(spatial$L)))+
    sqrt(1-spec$phi)*rnorm(n)) else spec$county_sd*rnorm(n)
  q<-matrix(0,nt,nt);q[cbind(1:(nt-1),2:nt)]<-1;q<-q+t(q)
  # Exact constrained training covariance; avoid INLA's numerical diagonal jitter
  # changing the generator's scale relative to the forecast contract.
  eigen_q<-eigen(diag(rowSums(q))-q,symmetric=TRUE)
  positive<-eigen_q$values>max(eigen_q$values)*1e-10
  unscaled_L<-sweep(eigen_q$vectors[,positive,drop=FALSE],2,sqrt(eigen_q$values[positive]),'/')
  rw_scale<-exp(mean(log(rowSums(unscaled_L^2))))
  temporal<-list(L=unscaled_L/sqrt(rw_scale))
  if(!is.finite(rw_scale)||rw_scale<=0)stop('Invalid training RW scale')
  state_train<-temporal$L%*%matrix(rnorm(ncol(temporal$L)*ns),ncol(temporal$L),ns)*spec$state_rw_sd
  county_train<-temporal$L%*%matrix(rnorm(ncol(temporal$L)*n),ncol(temporal$L),n)*spec$county_rw_sd
  state_effect<-rbind(state_train,matrix(NA_real_,horizons,ns))
  county_effect<-rbind(county_train,matrix(NA_real_,horizons,n))
  for(h in seq_len(horizons)) {
    # Horizon-local seeds keep the common prefix exactly fixed when H changes.
    set.seed(seed+10000L+h)
    state_effect[nt+h,]<-state_effect[nt+h-1L,]+rnorm(ns,sd=spec$state_rw_sd/sqrt(rw_scale))
    county_effect[nt+h,]<-county_effect[nt+h-1L,]+rnorm(n,sd=spec$county_rw_sd/sqrt(rw_scale))
  }
  d<-expand.grid(area=seq_len(n),time=seq_len(nt+horizons),KEEP.OUT.ATTRS=FALSE);d<-d[order(d$area,d$time),]
  d$fips<-sprintf('%05d',d$area);d$year<-2003L+d$time
  d$state<-factor(ifelse(d$area<=6L,'AA','BB'));d$state_id<-as.integer(d$state)
  d$population<-if(density=='sparse')500 else 50000
  d$population<-d$population*(1+(d$area-1)/24)
  eta<-spec$mean_log_rate+county[d$area]+state_effect[cbind(d$time,d$state_id)]+county_effect[cbind(d$time,d$area)]
  d$true_mu<-d$population*exp(eta);d$count<-NA_integer_
  for(t in seq_len(nt+horizons)) {
    set.seed(seed+20000L+t+1000L*match(density,spec$densities));ix<-which(d$time==t)
    d$count[ix]<-rnbinom(length(ix),mu=d$true_mu[ix],size=spec$nb_size)
  }
  obj<-list(data=d[,setdiff(names(d),'true_mu')],adj=adj,ids=sort(unique(d$fips)),years=2004:(2003L+nt+horizons))
  list(obj=obj,truth=d,cutoff=2003L+nt,spec=spec,rw_scale=rw_scale,
    county=county,state_last=state_train[nt,],county_last=county_train[nt,],seed=seed)
}

calibration_oracle <- function(sim,draws) {
  d<-sim$truth[sim$truth$year>sim$cutoff,];s<-sim$spec
  mu<-predictive<-matrix(NA_real_,nrow(d),draws)
  state<-matrix(rep(sim$state_last,draws),2,draws)
  county<-matrix(rep(sim$county_last,draws),s$counties,draws)
  for(h in sort(unique(d$year-sim$cutoff))) {
    set.seed(sim$seed+30000L+h)
    state<-state+matrix(rnorm(length(state),sd=s$state_rw_sd/sqrt(sim$rw_scale)),nrow(state))
    county<-county+matrix(rnorm(length(county),sd=s$county_rw_sd/sqrt(sim$rw_scale)),nrow(county))
    ix<-which(d$year-sim$cutoff==h)
    m<-d$population[ix]*exp(s$mean_log_rate+sim$county[d$area[ix]]+
       state[d$state_id[ix],,drop=FALSE]+county[d$area[ix],,drop=FALSE])
    mu[ix,]<-m
    set.seed(sim$seed+40000L+h)
    predictive[ix,]<-matrix(rnbinom(length(m),mu=as.vector(m),size=s$nb_size),length(ix))
  }
  list(mu=mu,predictive=predictive)
}

calibration_metrics <- function(truth,predictive,mu,method,replicate,density,variant,cutoff) {
  if(!identical(dim(predictive),dim(mu))||nrow(predictive)!=nrow(truth)||
     any(!is.finite(predictive))||any(!is.finite(mu)))stop('Invalid calibration draws')
  results<-list()
  for(h in sort(unique(truth$year-cutoff))) {
    ix<-which(truth$year-cutoff==h)
    for(unit in c('cell','total','zero_total')) {
      draws<-switch(unit,cell=predictive[ix,,drop=FALSE],total=matrix(colSums(predictive[ix,,drop=FALSE]),1),
        zero_total=matrix(colSums(predictive[ix,,drop=FALSE]==0),1))
      observed<-switch(unit,cell=truth$count[ix],total=sum(truth$count[ix]),zero_total=sum(truth$count[ix]==0))
      q<-t(apply(draws,1,quantile,c(.025,.975),names=FALSE));covered<-observed>=q[,1]&observed<=q[,2]
      results[[length(results)+1L]]<-data.frame(density=density,variant=variant,replicate=replicate,
        method=method,horizon=h,unit=unit,observations=length(observed),coverage=mean(covered),
        mean_width=mean(q[,2]-q[,1]),mean_absolute_error=mean(abs(rowMeans(draws)-observed)),
        draws=ncol(draws),mean_predictive_mcse=mean(apply(draws,1,sd)/sqrt(ncol(draws))))
    }
  }
  do.call(rbind,results)
}

calibration_interval <- function(x) {
  # Independent simulation replicates are the sampling units, not correlated counties.
  n<-length(x);m<-mean(x)
  if(n<2)return(c(mean=m,lower=NA_real_,upper=NA_real_,mcse=NA_real_))
  se<-sd(x)/sqrt(n)
  if(all(x%in%c(0,1))) {
    ci<-binom.test(sum(x),n)$conf.int
  } else ci<-pmax(0,pmin(1,m+c(-1,1)*qt(.975,n-1)*se))
  c(mean=m,lower=ci[1],upper=ci[2],mcse=se)
}

calibration_write_json <- function(value,path) {
  # The minimal INLA image does not require jsonlite. This serializer only handles
  # the scalar/vector/list types used by the fixed task manifest.
  encode <- function(x) {
    if(is.null(x))return('null')
    if(is.list(x)) {
      named<-!is.null(names(x)) && all(nzchar(names(x)))
      parts<-vapply(x,encode,character(1))
      if(named)parts<-paste0(encodeString(names(x),quote='"'),':',parts)
      return(paste0(if(named)'{' else '[',paste(parts,collapse=','),if(named)'}' else ']'))
    }
    if(length(x)!=1L)return(paste0('[',paste(vapply(as.list(x),encode,character(1)),collapse=','),']'))
    if(is.na(x))return('null')
    if(is.character(x))return(encodeString(x,quote='"'))
    if(is.logical(x))return(if(x)'true' else 'false')
    if(is.numeric(x)&&is.finite(x))return(format(x,digits=17,trim=TRUE,scientific=FALSE))
    stop('Unsupported calibration manifest value')
  }
  writeLines(encode(value),path)
}

run_calibration_task <- function(out,density,variant,replicate,draws=1000L,threads=2L) {
  if(dir.exists(out))stop('Existing calibration task output; refusing overwrite')
  spec<-calibration_specification()
  if(draws<spec$minimum_draws||draws!=as.integer(draws))stop('Calibration requires at least 1000 draws')
  dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
  tryCatch({
    if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected pinned INLA 26.08.07')
    sim<-calibration_truth(density,variant,replicate)
    engine_scale<-rw1_training_scale(spec$training_years)
    if(abs(sim$rw_scale-engine_scale)>1e-8)stop('Generator/engine training scale mismatch')
    fit<-fit_county_forecast(sim$obj,variant,sim$cutoff,county_time=TRUE,threads=threads)
    ix<-which(sim$truth$year>sim$cutoff);n<-length(ix)
    sampled<-sample_county_forecast(fit,ix,draws=draws,seed=as.integer(sim$seed+50000L))
    mu<-sampled$mu;predictive<-sampled$replicated
    oracle<-calibration_oracle(sim,draws)
    metrics<-rbind(calibration_metrics(sim$truth[ix,],predictive,mu,'INLA_GAUSSIAN',replicate,density,variant,sim$cutoff),
      calibration_metrics(sim$truth[ix,],oracle$predictive,oracle$mu,'KNOWN_PARAMETER_ORACLE',replicate,density,variant,sim$cutoff))
    write.csv(metrics,file.path(out,'metrics.csv'),row.names=FALSE)
    write.csv(sim$truth,file.path(out,'simulation_truth.csv'),row.names=FALSE)
    saveRDS(fit,file.path(out,'fit_INTERNAL.rds'))
    summary<-list(status='TASK_COMPLETE',density=density,variant=variant,replicate=replicate,draws=draws,
      seed=sim$seed,training_rw_scale=sim$rw_scale,training_center_only=TRUE,independent_future_rw_innovations=TRUE,
      specification=spec,scientific_status='REVIEW_REQUIRED',
      higher_accuracy_posterior_reference='UNAVAILABLE: oracle conditions on known latent training effects and parameters; it is not an exact posterior comparator')
    calibration_write_json(summary,file.path(out,'task_summary.json'))
    writeLines('TASK_COMPLETE: simulation screening only; approximation-equivalence review remains required',file.path(out,'status.txt'))
    invisible(metrics)
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}

if(sys.nframe()==0L) {
  a<-commandArgs(TRUE);here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
  source(file.path(here,'fit_county_pilot.R'));source(file.path(here,'county_forecast_model.R'))
  if(length(a)!=7L||a[1]!='task')stop('Usage: task OUT DENSITY VARIANT REPLICATE DRAWS THREADS')
  run_calibration_task(a[2],a[3],a[4],as.integer(a[5]),as.integer(a[6]),as.integer(a[7]))
}
