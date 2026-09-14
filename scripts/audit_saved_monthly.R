#!/usr/bin/env Rscript
# Saved posterior diagnostics only. This file never calls a model-fitting function.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'audit_saved_forecast_sampling.R'))

validate_monthly_saved <- function(fit,predictions,cutoff,seasonal,expected_trend_upper=.5) {
 spec<-attr(fit,'monthly_specification');d<-fit$.args$data
 if(is.null(spec)||spec$version!='monthly_rw1_cycle_v1'||spec$cutoff!=cutoff*12+11L||!identical(spec$seasonal,seasonal)||spec$coverage!='EXPLORATORY_ASSUMED_CONTINUOUS'||spec$rate_center!=.0002)stop('Saved model specification mismatch')
 if(length(expected_trend_upper)!=1||!is.finite(expected_trend_upper)||expected_trend_upper<=0||!isTRUE(all.equal(spec$trend_sd_bound*sqrt(spec$trend_scale),expected_trend_upper,tolerance=1e-10)))stop('Saved temporal prior differs')
 if(!is.data.frame(d)||!all(c('fips','state','year','month','count','person_years','time')%in%names(d)))stop('Saved model data missing')
 serial<-d$year*12+d$month-1;held<-d$year>cutoff
 if(!any(held)||max(d$year)!=cutoff+3||any(!is.na(d$count[held]))||any(!is.finite(d$count[!held]))||any(!is.finite(d$person_years)|d$person_years<=0))stop('Saved masking/exposure mismatch')
 key<-function(x)paste(x$fips,x$state,x$year,x$month,sep='|')
 if(nrow(predictions)!=sum(held)||anyDuplicated(key(predictions))||!identical(key(d[held,]),key(predictions)))stop('Prediction rows do not match saved predictor order')
 if(any(!is.finite(predictions$observed)|predictions$observed<0|predictions$observed!=floor(predictions$observed)))stop('Invalid heldout truth')
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||is.null(fit$misc$configs)||!identical(as.character(fit$.args$family),'nbinomial')||nrow(fit$summary.linear.predictor)!=nrow(d))stop('Saved fit/configuration not valid')
 if(!all(c('area','time')%in%names(fit$summary.random))||('season'%in%names(fit$summary.random))!=seasonal)stop('Random effect identity mismatch')
 A<-spec$trend_constraint$A
 if(ncol(A)!=length(unique(serial))||any(A[1,sort(unique(serial))>cutoff*12+11]!=0))stop('Future coefficients enter saved training constraint')
 list(data=d,indices=which(held),truth=predictions$observed)
}

tail_summary <- function(mu,predicted,truth,keys,stream) {
 if(!is.matrix(mu)||!identical(dim(mu),dim(predicted))||any(!is.finite(mu)|mu<0)||any(!is.finite(predicted)|predicted<0))stop('Invalid aggregate posterior draws')
 n<-ncol(mu);top<-max(1L,ceiling(.01*n));q<-t(apply(predicted,1,quantile,c(.025,.5,.975)))
 share<-apply(mu,1,function(x){s<-sum(x);if(s==0)0 else sum(sort(x,decreasing=TRUE)[seq_len(top)])/s})
 cbind(keys,stream=stream,draws=n,observed=truth,mean_expected=rowMeans(mu),median_expected=apply(mu,1,median),
   p975_expected=apply(mu,1,quantile,.975),max_expected=apply(mu,1,max),top_one_percent_mean_share=share,
   lower95=q[,1],median_predictive=q[,2],upper95=q[,3],prob_above_twice_observed=rowMeans(predicted>2*truth))
}

audit_monthly_saved <- function(fitpath,predpath,cutoff,seasonal,out,seed,draws=2000L,expected_trend_upper=.5) {
 if(dir.exists(out))stop('Refusing existing diagnostic result');dir.create(out,recursive=TRUE)
 writeLines('RUNNING',file.path(out,'status.txt'))
 inputs<-c(fitpath,predpath);before<-tools::md5sum(inputs)
 tryCatch({
  if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
  if(length(draws)!=1||!is.finite(draws)||draws<100||draws>4000||draws!=floor(draws)||length(seed)!=1||!is.finite(seed)||seed<1||seed>1e9||seed!=floor(seed))stop('Invalid sampling settings')
  fit<-readRDS(fitpath);pred<-read.csv(predpath,colClasses=c(fips='character'))
  obj<-validate_monthly_saved(fit,pred,cutoff,seasonal,expected_trend_upper);ix<-obj$indices;truth<-obj$truth;d<-obj$data[ix,]
  cell_group<-paste(d$state,d$year,sep='|');levels<-unique(cell_group);first<-match(levels,cell_group)
  keys<-data.frame(state=as.character(d$state[first]),year=d$year[first]);catchyears<-sort(unique(d$year))
  aggregate_keys<-rbind(keys,data.frame(state='ALL',year=catchyears))
  agg<-function(x)rbind(rowsum(x,cell_group,reorder=FALSE),rowsum(x,d$year,reorder=TRUE))
  aggregate_truth<-as.numeric(agg(truth));allmoments<-NULL;all_mu<-all_y<-NULL;scores<-tails<-hyper<-list()
  for(stream in 1:4) {
   # Stream blocks are 50,000 apart; tasks receive disjoint 1,000,000 blocks.
   stream_seed<-seed+(stream-1L)*50000L;moments<-NULL;total_mu<-total_y<-NULL;sizes<-numeric()
   for(start in seq.int(1L,draws,by=100L)) {
    n<-min(100L,draws-start+1L)
    ss<-INLA::inla.posterior.sample(n,fit,selection=list(Predictor=ix),seed=as.integer(stream_seed+start),num.threads='1:1',skew.corr=FALSE)
    mu<-ld<-replicated<-matrix(NA_real_,length(ix),n);size<-numeric(n)
    # Separate predictive simulation RNG from INLA sampling seeds.
    set.seed(as.integer(stream_seed+10000L+start))
    for(j in seq_len(n)) {
     s<-ss[[j]];ids<-as.integer(sub('^Predictor:','',rownames(s$latent)));si<-grep('size for',names(s$hyperpar),fixed=TRUE)
     if(anyNA(ids)||anyDuplicated(ids)||!setequal(ids,ix)||length(si)!=1L)stop('Unexpected sampled predictor/shape identity')
     mu[,j]<-exp(as.numeric(s$latent[match(ix,ids),1]));size[j]<-as.numeric(s$hyperpar[si])
     if(any(!is.finite(mu[,j]))||!is.finite(size[j])||size[j]<=0)stop('Invalid sampled mean/shape')
     ld[,j]<-dnbinom(truth,mu=mu[,j],size=size[j],log=TRUE)
     replicated[,j]<-rnbinom(length(ix),mu=mu[,j],size=size[j])
    }
    moments<-density_moments(ld,moments);allmoments<-density_moments(ld,allmoments)
    total_mu<-cbind(total_mu,agg(mu));total_y<-cbind(total_y,agg(replicated));sizes<-c(sizes,size)
   }
   z<-summarize_density(moments)
   scores[[stream]]<-data.frame(keys,stream=stream,draws=draws,mean_log_score=as.numeric(rowsum(z$log_density,cell_group,reorder=FALSE))/as.numeric(table(factor(cell_group,levels))),
    max_cell_density_relative_mcse=as.numeric(tapply(z$relative_mcse,factor(cell_group,levels),max)))
   tails[[stream]]<-tail_summary(total_mu,total_y,aggregate_truth,aggregate_keys,stream)
   hyper[[stream]]<-data.frame(stream=stream,size_median=median(sizes),size_p025=unname(quantile(sizes,.025)),size_p975=unname(quantile(sizes,.975)))
   all_mu<-cbind(all_mu,total_mu);all_y<-cbind(all_y,total_y)
  }
  z<-summarize_density(allmoments)
  scores[[5]]<-data.frame(keys,stream=0,draws=4L*draws,mean_log_score=as.numeric(rowsum(z$log_density,cell_group,reorder=FALSE))/as.numeric(table(factor(cell_group,levels))),
   max_cell_density_relative_mcse=as.numeric(tapply(z$relative_mcse,factor(cell_group,levels),max)))
  tails[[5]]<-tail_summary(all_mu,all_y,aggregate_truth,aggregate_keys,0)
  latent<-data.frame(state=d$state,year=d$year,log_predictor_sd=fit$summary.linear.predictor$sd[ix])
  write.csv(aggregate(latent['log_predictor_sd'],latent[c('state','year')],mean),file.path(out,'latent_sd_by_site_year.csv'),row.names=FALSE)
  write.csv(do.call(rbind,scores),file.path(out,'stream_scores.csv'),row.names=FALSE)
  write.csv(do.call(rbind,tails),file.path(out,'aggregate_tails.csv'),row.names=FALSE)
  write.csv(do.call(rbind,hyper),file.path(out,'shape_streams.csv'),row.names=FALSE)
  write.csv(data.frame(fips=d$fips,state=d$state,year=d$year,month=d$month,log_score=z$log_density,density_relative_mcse=z$relative_mcse),file.path(out,'pooled_cell_scores.csv'),row.names=FALSE)
  saveRDS(list(keys=aggregate_keys,expected=all_mu,predictive=all_y,draws_per_stream=draws,base_seed=seed),file.path(out,'aggregate_draws_INTERNAL.rds'),version=2)
  if(!identical(before,tools::md5sum(inputs)))stop('Saved inputs changed during diagnostics')
  write.csv(data.frame(file=inputs,md5=unname(before)),file.path(out,'input_checksums.csv'),row.names=FALSE)
  write.csv(data.frame(cutoff=cutoff,seasonal=seasonal,streams=4,draws_per_stream=draws,base_seed=seed,refitted=FALSE,coverage_certified=FALSE),file.path(out,'settings.csv'),row.names=FALSE)
  writeLines('SAVED_MONTHLY_DIAGNOSTICS_COMPLETE',file.path(out,'status.txt'))
 },error=function(e){writeLines(c('FAILED',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=6L)stop('Usage: FIT PREDICTIONS CUTOFF SEASONAL OUT SEED');audit_monthly_saved(a[1],a[2],as.integer(a[3]),a[4]=='TRUE',a[5],as.integer(a[6]))}
