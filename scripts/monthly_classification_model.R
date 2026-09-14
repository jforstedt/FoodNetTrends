# Conditional CIDT/(CIDT+CX) models. Outcomes after cutoff never enter fit design.
monthly_classification_scale <- function(n,cyclic=FALSE) {
 D<-matrix(0,if(cyclic)n else n-1L,n)
 j<-seq_len(nrow(D));D[cbind(j,j)]<- -1;D[cbind(j,if(cyclic)c(2:n,1) else 2:n)]<-1
 ee<-eigen(crossprod(D),symmetric=TRUE);keep<-ee$values>max(ee$values)*1e-10
 V<-sweep(ee$vectors[,keep,drop=FALSE],2,sqrt(ee$values[keep]),'/')
 list(scale=exp(mean(log(rowSums(V^2)))),factor=V)
}
prepare_monthly_classification <- function(data,cutoff,level=c('site','county')) {
 level<-match.arg(level);d<-data
 if(length(cutoff)!=1||!cutoff%in%c(2015L,2016L))stop('Cutoff must be 2015 or 2016')
 needed<-c('state','year','month','cidt_classified','cx_classified','classification_denominator')
 if(level=='county')needed<-c(needed,'fips')
 if(!all(needed%in%names(d)))stop('Missing conditional classification fields')
 if(anyNA(d[c('state','year','month')])||any(!is.finite(d$year)|d$year!=floor(d$year)|!is.finite(d$month)|d$month!=floor(d$month)|d$month<1|d$month>12))stop('Invalid monthly domain')
 d<-d[d$year>=2012&d$year<=cutoff+3,needed,drop=FALSE]
 if(!nrow(d))stop('Empty classification data')
 nums<-c('cidt_classified','cx_classified','classification_denominator')
 if(any(!is.finite(d$classification_denominator)|d$classification_denominator<0|d$classification_denominator!=floor(d$classification_denominator)))stop('Invalid conditioning denominator')
 train<-d$year<=cutoff
 for(n in nums)if(any(!is.finite(d[[n]][train])|d[[n]][train]<0|d[[n]][train]!=floor(d[[n]][train])))stop('Invalid training classified counts')
 if(any(d$cidt_classified[train]+d$cx_classified[train]!=d$classification_denominator[train]))stop('Literal category denominator mismatch')
 d$cidt_classified[!train]<-NA_real_;d$cx_classified[!train]<-NA_real_
 d$state<-as.character(d$state)
 if(any(!nzchar(d$state)))stop('Empty site identity')
 if(level=='county') {
  d$fips<-as.character(d$fips)
  if(anyNA(d$fips)||any(!nzchar(d$fips))||any(vapply(split(d$state,d$fips),function(x)length(unique(x))!=1L,logical(1))))stop('Invalid county mapping')
  d<-d[order(d$state,d$fips,d$year,d$month),,drop=FALSE];unit<-d$fips
 } else {d<-d[order(d$state,d$year,d$month),,drop=FALSE];unit<-d$state}
 rownames(d)<-NULL;serial<-12*d$year+d$month-1L
 times<-seq(2012*12,(cutoff+4)*12-1L)
 if(!setequal(unique(serial),times)||anyDuplicated(paste(unit,serial))||nrow(d)!=length(unique(unit))*length(times))stop('Incomplete or duplicate monthly classification grid')
 d$row_key<-paste(unit,d$year,sprintf('%02d',d$month),sep='|');d$row_id<-seq_len(nrow(d))
 d$state_id<-match(d$state,sort(unique(d$state)));d$time_id<-match(serial,times);d$month_id<-d$month;d$cell_id<-seq_len(nrow(d))
 d$area<-if(level=='county')match(d$fips,sort(unique(d$fips))) else d$state_id
 d$area_id<-d$area
 d$Ntrials<-d$classification_denominator;d$y<-d$cidt_classified
 d$y[d$year>cutoff|d$Ntrials==0]<-NA_real_
 d$training<-d$year<=cutoff;d$likelihood_eligible<-d$training&d$Ntrials>0
 if(!any(d$likelihood_eligible))stop('No training binomial information')
 nt<-(cutoff-2012+1L)*12L;sc<-monthly_classification_scale(nt)$scale;cycle<-monthly_classification_scale(12,TRUE)$scale
 spec<-list(version='monthly_conditional_classification_v1',target='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT',cutoff=as.integer(cutoff),level=level,
  start_year=2012L,train_start=2012L,link='logit',horizon=36L,horizon_months=36L,n_training=nt,n_time=length(times),intercept_mean=qlogis(.1),intercept_sd=1.5,
  site_sd_upper=1.5,cell_sd_upper=1,spatial_sd_upper=1,pc_tail=.01,trend_sd_upper=1,trend_scale=sc,trend_sd_bound=1/sqrt(sc),
  seasonal_sd_upper=1,seasonal_scale=cycle,seasonal_sd_bound=1/sqrt(cycle),ar1_marginal_sd_upper=1,ar1_rho_internal_mean=log(19),ar1_rho_internal_sd=1.5,
  phi_u=.5,phi_probability=.5,conditional_future_denominators=TRUE,incidence_adjustment=FALSE,
  trend_constraint=list(A=matrix(as.numeric(times<=(cutoff*12+11L))/nt,nrow=1),e=0))
 list(data=d,spec=spec)
}
fit_monthly_classification <- function(data,cutoff,level='site',temporal='rw1',seasonal=FALSE,spatial='none',nodes=NULL,edges=NULL,threads=4L) {
 if(!temporal%in%c('rw1','ar1')||length(temporal)!=1)stop('RW1/AR1 only; spline gate pending')
 if(length(seasonal)!=1||!is.logical(seasonal)||is.na(seasonal)||length(threads)!=1||!is.finite(threads)||threads<1||threads!=floor(threads))stop('Invalid fit options')
 if((level=='site'&&spatial!='none')||(level=='county'&&!spatial%in%c('iid','bym2')))stop('Invalid level/spatial combination')
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 obj<-prepare_monthly_classification(data,cutoff,level);d<-obj$data;s<-obj$spec;f<-INLA::f
 formula<-y~1+f(state_id,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1.5,.01))))+
  f(cell_id,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))
 if(level=='county')formula<-update(formula,.~.+f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01)))))
 graph<-NULL
 if(level=='county') {
  if(!exists('monthly_spatial_graph',mode='function')||!exists('monthly_bym2_effect',mode='function'))stop('Source monthly_spatial_combination.R first')
  graph<-monthly_spatial_graph(data.frame(area=d$fips,state=d$state),nodes,edges)
  if(spatial=='bym2')formula<-monthly_bym2_effect(graph)(formula,d)
 }
 nt<-s$n_time;constraint<-s$trend_constraint;bound<-s$trend_sd_bound;cyclebound<-s$seasonal_sd_bound
 if(temporal=='rw1')formula<-update(formula,.~.+f(time_id,model='rw1',n=nt,constr=FALSE,scale.model=FALSE,extraconstr=constraint,rankdef=1,hyper=list(prec=list(prior='pc.prec',param=c(bound,.01)))))
 else formula<-update(formula,.~.+f(time_id,model='ar1',n=nt,constr=FALSE,hyper=list(prec=list(prior='pc.prec',param=c(1,.01)),rho=list(prior='normal',param=c(log(19),1/1.5^2)))))
 if(seasonal)formula<-update(formula,.~.+f(month_id,model='rw1',n=12,cyclic=TRUE,constr=FALSE,scale.model=FALSE,extraconstr=list(A=matrix(1/12,1,12),e=0),rankdef=1,hyper=list(prec=list(prior='pc.prec',param=c(cyclebound,.01)))))
 fit<-INLA::inla(formula,data=d,family='binomial',Ntrials=d$Ntrials,num.threads=paste0(threads,':1'),
  control.fixed=list(mean=0,prec=1,mean.intercept=s$intercept_mean,prec.intercept=1/s$intercept_sd^2),
  control.family=list(link='logit'),control.predictor=list(compute=TRUE,link=1),control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
 s$temporal<-temporal;s$seasonal<-seasonal;s$spatial<-spatial;s$county_temporal<-FALSE
 if(!is.null(graph))s$graph<-c(graph$specification,list(ids=graph$ids,n_components=graph$n_components,n_edges=graph$n_edges))
 attr(fit,'monthly_classification_data')<-d;attr(fit,'monthly_classification_specification')<-s
 fit
}
