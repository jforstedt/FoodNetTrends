#!/usr/bin/env Rscript
# Opt-in projected state-by-calendar-month seasonality. No default fitter mutation.
local_seasonality_component <- function(data, states=NULL, sd_upper=.5, sd_tail=.01) {
  if(!is.data.frame(data)||!all(c('state','month')%in%names(data))||nrow(data)==0L)stop('State/month data required')
  state<-as.character(data$state);month<-data$month
  if(anyNA(state)||any(!nzchar(state))||!is.numeric(month)||anyNA(month)||any(!is.finite(month)|month!=floor(month)|month<1|month>12))stop('Invalid state/month')
  if(is.null(states))states<-sort(unique(state))
  if(!is.character(states)||anyNA(states)||any(!nzchar(states))||anyDuplicated(states)||length(states)<2L||!all(state%in%states))stop('At least two unique declared states required')
  if(length(sd_upper)!=1L||!is.finite(sd_upper)||sd_upper<=0||length(sd_tail)!=1L||!is.finite(sd_tail)||sd_tail<=0||sd_tail>=1)stop('Invalid PC prior')
  # Orthonormal columns span the zero-sum state and calendar-month spaces.
  contrast<-function(n) { H<-contr.helmert(n);sweep(H,2,sqrt(colSums(H^2)),'/') }
  S<-length(states);Hs<-contrast(S);Hm<-contrast(12L)
  B<-kronecker(Hs,Hm) # state-major, month-minor rows
  D<-diag(12L);D[cbind(seq_len(12L),c(2:12,1))]<- -1
  Qcycle<-crossprod(D)
  Q<-kronecker(diag(S-1L),crossprod(Hm,Qcycle%*%Hm))
  variance<-diag(B%*%solve(Q,t(B)))
  scale<-exp(mean(log(variance)))
  Q<-Q*scale # all state-month marginal variances now one at precision one
  rows<-(match(state,states)-1L)*12L+as.integer(month)
  k<-ncol(B)
  list(A=B[rows,,drop=FALSE],Q=Q,basis=B,effects=list(local_season=seq_len(k)),
    states=states,row_index=rows,
    specification=list(version='monthly_local_seasonality_v1',states=states,
      n_coefficients=k,cycle_months=12L,scale=scale,sd_upper=sd_upper,sd_tail=sd_tail,
      constraints='unweighted state sum each month; month sum each state',
      prior='P(marginal state-month deviation SD > sd_upper) = sd_tail',
      forecast_rule='repeat calendar cycle; state domain fixed from training'))
}

local_seasonality_formula <- function(formula,component) {
  if(!inherits(formula,'formula')||!is.list(component)||is.null(component$Q)||is.null(component$specification))stop('Formula/component required')
  if('local_season'%in%all.vars(formula))stop('Local seasonality already present')
  spec<-component$specification
  env<-list2env(list(.local_season_Q=component$Q,
    .local_season_prior=list(prec=list(prior='pc.prec',param=c(spec$sd_upper,spec$sd_tail)))),
    parent=environment(formula))
  term<-quote(f(local_season,model='generic0',Cmatrix=.local_season_Q,
    constr=FALSE,rankdef=0,hyper=.local_season_prior))
  formula[[3L]]<-call('+',formula[[3L]],term);environment(formula)<-env
  formula
}

# Isolated opt-in wrapper. Baseline formula/priors retained explicitly.
fit_monthly_local_seasonality <- function(d,cutoff,seasonal=TRUE,threads=2L,coverage='SYNTHETIC_COMPLETE',rate_center=.002,trend_sd_upper=.5,temporal_model='rw1',area_effect=NULL,local_seasonality=TRUE,local_sd_upper=.5,local_sd_tail=.01,weather=FALSE,age=FALSE) {
  if(length(local_seasonality)!=1L||is.na(local_seasonality)||!is.logical(local_seasonality))stop('Invalid local seasonality option')
  if(length(weather)!=1L||is.na(weather)||!is.logical(weather))stop('Invalid weather option')
  if(length(age)!=1L||is.na(age)||!is.logical(age))stop('Invalid age option')
  required<-if(local_seasonality||weather||age)c('monthly_model_data','monthly_cycle_scale','rw1_training_scale') else 'fit_monthly_model'
  if(any(!vapply(required,exists,logical(1),mode='function',inherits=TRUE)))stop('Source county_forecast_model.R and monthly_seasonal_model.R first')
  if(!local_seasonality&&!weather&&!age)return(fit_monthly_model(d,cutoff,seasonal,threads,coverage,rate_center,trend_sd_upper,temporal_model,area_effect))
  if(!isTRUE(seasonal))stop('Extensions require the common seasonal reference')
  weather_names<-c('weather_tavg_z','weather_logprcp_z')
  if(weather&&(!all(weather_names%in%names(d))||any(!vapply(d[weather_names],is.numeric,logical(1)))||any(!is.finite(as.matrix(d[weather_names])))))stop('Missing/nonfinite weather features')
  age_names<-c('age_under5_z','age65plus_z')
  if(age&&(!all(age_names%in%names(d))||any(!vapply(d[age_names],is.numeric,logical(1)))||any(!is.finite(as.matrix(d[age_names])))))stop('Missing/nonfinite age features')
  if(length(seasonal)!=1||is.na(seasonal)||!is.logical(seasonal)||length(threads)!=1||!is.finite(threads)||threads<1||threads!=floor(threads))stop('Invalid fit options')
  if(length(rate_center)!=1||!is.finite(rate_center)||rate_center<=0)stop('Invalid prior rate')
  if(!temporal_model%in%c('rw1','ar1'))stop('Invalid temporal model')
  obj<-monthly_model_data(d,cutoff,coverage,trend_sd_upper);d<-obj$data;spec<-obj$spec
  if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
  f<-INLA::f;nt<-spec$n_time;constraint<-spec$trend_constraint
  temporal<-list(prec=list(prior='pc.prec',param=c(spec$trend_sd_bound,spec$pc_tail)))
  cycle<-monthly_cycle_scale()
  seasonal_prior<-list(prec=list(prior='pc.prec',param=c(spec$seasonal_sd_bound/sqrt(cycle$scale),spec$pc_tail)))
  formula<-count~0+state+
    f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
    f(time,model='rw1',n=nt,replicate=state_id,constr=FALSE,scale.model=FALSE,
      extraconstr=constraint,rankdef=1,hyper=temporal)
  if(temporal_model=='ar1') {
    # Proper stationary AR1: prec is MARGINAL precision, not innovation precision.
    spec$version<-'monthly_ar1_cycle_v1';spec$trend_constraint<-NULL
    spec$trend_scale<-NULL;spec$trend_sd_bound<-NULL;spec$trend_sd_upper<-NULL
    spec$ar1_marginal_sd_upper<-1;spec$ar1_rho_internal_mean<-log(19);spec$ar1_rho_internal_sd<-1.5
    ar_prior<-list(prec=list(prior='pc.prec',param=c(1,.01)),rho=list(prior='normal',param=c(log(19),1/1.5^2)))
    formula<-count~0+state+
      f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
      f(time,model='ar1',n=nt,replicate=state_id,constr=FALSE,hyper=ar_prior)
  }
  if(seasonal)formula<-update(formula,.~.+f(season,model='rw1',n=12,cyclic=TRUE,
    constr=FALSE,scale.model=FALSE,extraconstr=list(A=matrix(1/12,1,12),e=0),rankdef=1,hyper=seasonal_prior))
  if(!is.null(area_effect))formula<-area_effect(formula,d)
  component<-if(local_seasonality)local_seasonality_component(d,sd_upper=local_sd_upper,sd_tail=local_sd_tail) else NULL
  if(local_seasonality)formula<-local_seasonality_formula(formula,component)
  fixed<-list(mean=log(rate_center),prec=1)
  feature_names<-c(if(weather)weather_names,if(age)age_names)
  if(length(feature_names)) {
    for(name in feature_names)formula<-update(formula,paste('.~.+',name))
    fixed<-list(mean=c(list(default=log(rate_center)),setNames(as.list(rep(0,length(feature_names))),feature_names)),
      prec=c(list(default=1),setNames(as.list(rep(16,length(feature_names))),feature_names)))
  }
  effects<-d;effects$count<-NULL;effects$person_years<-NULL
  matrices<-list(1);effect_list<-list(effects)
  if(local_seasonality){matrices<-c(matrices,list(component$A));effect_list<-c(effect_list,list(component$effects))}
  stack<-INLA::inla.stack(data=list(count=d$count),A=matrices,effects=effect_list,tag='monthly')
  fit<-INLA::inla(formula,data=INLA::inla.stack.data(stack),family='nbinomial',E=d$person_years,num.threads=paste0(threads,':1'),
    control.fixed=fixed,
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(spec$nb_log_size_mean,1/spec$nb_log_size_sd^2),initial=spec$nb_log_size_mean))),
    control.predictor=list(A=INLA::inla.stack.A(stack),compute=TRUE,link=1),control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  if(!isTRUE(fit$ok)||length(fit$mode$mode.status)!=1L||is.na(fit$mode$mode.status)||fit$mode$mode.status!=0)stop('Local seasonal fit failed numerical gate')
  spec$reference_version<-spec$version;spec$version<-'monthly_local_seasonality_fit_v1'
  attr(fit,'monthly_specification')<-c(spec,list(seasonal=seasonal,cycle_scale=cycle$scale,rate_center=rate_center))
  attr(fit,'local_seasonality_specification')<-if(local_seasonality)component$specification else list(version='local_seasonality_disabled')
  attr(fit,'weather_specification')<-list(enabled=weather,features=if(weather)weather_names else character(),coefficient_mean=0,coefficient_sd=.25,future_features='historical_conditional')
  attr(fit,'age_specification')<-list(enabled=age,features=if(age)age_names else character(),coefficient_mean=0,coefficient_sd=.25,interpretation='ecological population composition')
  attr(fit,'covariate_experiment_masked_data')<-d
  attr(fit,'local_seasonality_prediction_indices')<-INLA::inla.stack.index(stack,'monthly')$data
  attr(fit,'local_seasonality_predictor_prefix')<-'APredictor'
  attr(fit,'local_seasonality_exposure')<-d$person_years
  attr(fit,'local_seasonality_prediction_scale')<-'APredictor log rate; fitted.values rate; multiply person-years once for count'
  fit
}

local_seasonality_count_mean <- function(fit,indices=seq_along(attr(fit,'local_seasonality_exposure'))) {
  exposure<-attr(fit,'local_seasonality_exposure');mapping<-attr(fit,'local_seasonality_prediction_indices')
  if(!identical(attr(fit,'local_seasonality_predictor_prefix'),'APredictor')||!length(exposure)||
    length(mapping)!=length(exposure)||anyNA(mapping)||anyDuplicated(mapping)||
    any(!is.finite(mapping)|mapping!=floor(mapping)|mapping<1|mapping>nrow(fit$summary.fitted.values))||
    any(!is.finite(exposure)|exposure<=0)||
    !length(indices)||anyNA(indices)||anyDuplicated(indices)||any(indices!=floor(indices)|indices<1|indices>length(exposure)))stop('Invalid local seasonal prediction metadata/indices')
  result<-fit$summary.fitted.values$mean[mapping[indices]]*exposure[indices]
  if(any(!is.finite(result)|result<0))stop('Invalid fitted count means')
  result
}

sample_monthly_local_seasonality <- function(fit,indices,draws=4000L,seed=20260916L,batch_size=100L) {
  local_seasonality_count_mean(fit,indices) # metadata/index gate, no sampling side effects
  integer_scalar<-function(x)length(x)==1L&&is.finite(x)&&x==floor(x)&&x>=1&&x<.Machine$integer.max-10001L
  if(!integer_scalar(draws)||!integer_scalar(seed)||!integer_scalar(batch_size)||seed+draws+10001L>=.Machine$integer.max)stop('Invalid sampling request')
  exposure<-attr(fit,'local_seasonality_exposure')[indices]
  predictors<-attr(fit,'local_seasonality_prediction_indices')[indices]
  mu<-replicated<-matrix(NA_real_,length(indices),draws);sizes<-numeric(draws)
  for(start in seq.int(1L,draws,by=as.integer(batch_size))) {
    jj<-start:min(start+batch_size-1L,draws)
    samples<-INLA::inla.posterior.sample(length(jj),fit,selection=list(APredictor=predictors),
      seed=as.integer(seed+start),num.threads='1:1',skew.corr=FALSE)
    set.seed(as.integer(seed+10000L+start))
    for(k in seq_along(samples)) {
      sample<-samples[[k]];ids<-as.integer(sub('^APredictor:','',rownames(sample$latent)))
      if(anyNA(ids)||length(ids)!=length(predictors)||anyDuplicated(ids)||!setequal(ids,predictors))stop('Invalid local APredictor indexing')
      rate<-exp(as.numeric(sample$latent[match(predictors,ids),1]));m<-rate*exposure
      ix<-grep('size for',names(sample$hyperpar),fixed=TRUE)
      if(length(ix)!=1L)stop('Missing negative-binomial size')
      size<-as.numeric(sample$hyperpar[ix])
      if(any(!is.finite(m)|m<0)||!is.finite(size)||size<=0)stop('Invalid local forecast parameter')
      j<-jj[k];mu[,j]<-m;sizes[j]<-size;replicated[,j]<-rnbinom(length(indices),mu=m,size=size)
    }
  }
  if(any(!is.finite(replicated)))stop('Nonfinite predictive counts')
  list(mu=mu,replicated=replicated,size=sizes,indices=indices,exposure=exposure,
    scale='counts',approximation='INLA joint posterior skew.corr=FALSE; APredictor log rate times person-years')
}
