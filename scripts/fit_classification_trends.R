#!/usr/bin/env Rscript
# Conditional classification among eligible CX+/CIDT+ cases, never incidence.
classification_data <- function(d,cutoff) {
 needed<-c('state','year','cx_classified','cidt_classified','parasitic_classified','classification_denominator')
 if(!all(needed%in%names(d)))stop('Missing classification fields')
 d<-d[d$year>=2012&d$year<=2019,,drop=FALSE];d<-d[order(d$state,d$year),]
 if(!cutoff%in%c(2016L,2019L)||anyDuplicated(paste(d$state,d$year))||!setequal(d$year,2012:2019)||nrow(d)!=length(unique(d$state))*8)stop('Invalid classification domain')
 for(n in needed[-1])if(any(!is.finite(d[[n]])|d[[n]]!=floor(d[[n]])))stop('Invalid integer field')
 if(any(d$classification_denominator<=0|d$cx_classified<0|d$cidt_classified<0|d$parasitic_classified!=0|d$cx_classified+d$cidt_classified!=d$classification_denominator))stop('Unsupported category denominator')
 d$success<-d$cidt_classified;d$trials<-d$classification_denominator;d$success[d$year>cutoff]<-NA_real_
 d$time_scaled<-(d$year-2012)/4;d$site<-match(d$state,sort(unique(d$state)));d$slope_site<-d$site;d$cell<-seq_len(nrow(d));d
}
fit_classification <- function(d,cutoff,model,threads=4L) {
 if(!model%in%c('shared','site_slopes'))stop('Unknown classification model')
 x<-classification_data(d,cutoff)
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 f<-INLA::f
 formula<-success~1+time_scaled+
  f(site,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1.5,.01)) ))+
  f(cell,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))
 if(model=='site_slopes')formula<-update(formula,.~.+f(slope_site,time_scaled,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01)))))
 fit<-INLA::inla(formula,data=x,family='binomial',Ntrials=x$trials,num.threads=paste0(threads,':1'),control.fixed=list(mean=0,prec=1,mean.intercept=qlogis(.1),prec.intercept=1/1.5^2),control.predictor=list(compute=TRUE,link=1),control.compute=list(config=TRUE,cpo=TRUE,waic=TRUE))
 attr(fit,'classification_spec')<-list(version='conditional_category_v1',cutoff=cutoff,model=model,target='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT',time_origin=2012,time_scale=4,intercept_mean=qlogis(.1),intercept_sd=1.5,slope_sd=1,site_sd_upper=1.5,cell_sd_upper=1,slope_sd_upper=1,pc_tail=.01)
 fit
}
classification_reports <- function(fit,d,cutoff,seed,draws=500L) {
 d<-classification_data(d,cutoff);n<-nrow(d);prob<-sim<-matrix(NA_real_,n,4L*draws);streams<-list()
 if(!all(is.na(fit$.args$data$success[d$year>cutoff]))||!identical(as.integer(fit$.args$data$trials),as.integer(d$trials)))stop('Saved masking/denominator mismatch')
 for(k in 1:4) {
  samples<-INLA::inla.posterior.sample(draws,fit,selection=list(Predictor=seq_len(n)),seed=as.integer(seed+k*10000L),num.threads='1:1',skew.corr=FALSE)
  set.seed(seed+k*10000L+5000L)
  for(j in seq_len(draws)) {
   ids<-as.integer(sub('^Predictor:','',rownames(samples[[j]]$latent)))
   if(anyNA(ids)||anyDuplicated(ids)||!setequal(ids,seq_len(n)))stop('Predictor identity mismatch')
   col<-(k-1L)*draws+j;prob[,col]<-plogis(samples[[j]]$latent[match(seq_len(n),ids),1]);sim[,col]<-rbinom(n,d$trials,prob[,col])
  }
 }
 density<-dbinom(matrix(d$cidt_classified,n,ncol(prob)),size=d$trials,prob=prob,log=TRUE)
 summarize<-function(cols) {
  a<-density[,cols,drop=FALSE];mx<-apply(a,1,max);z<-exp(a-mx)
  if(any(!is.finite(mx)))stop('Predictive density underflow')
  data.frame(state=d$state,year=d$year,stream=if(length(cols)==4*draws)0L else ceiling(max(cols)/draws),draws=length(cols),log_score=mx+log(rowMeans(z)),density_relative_mcse=apply(z,1,sd)/sqrt(ncol(z))/rowMeans(z))
 }
 for(k in 1:4)streams[[k]]<-summarize(((k-1L)*draws+1L):(k*draws));streams[[5]]<-summarize(seq_len(4L*draws))
 q<-t(apply(prob,1,quantile,c(.025,.5,.975)));pred<-t(apply(sim,1,quantile,c(.025,.5,.975)))
 report<-data.frame(state=d$state,year=d$year,observed_cidt=d$cidt_classified,trials=d$trials,observed_share=d$cidt_classified/d$trials,mean_probability=rowMeans(prob),lower_probability=q[,1],median_probability=q[,2],upper_probability=q[,3],lower_predictive=pred[,1],median_predictive=pred[,2],upper_predictive=pred[,3],evaluation=ifelse(d$year>cutoff,'CONDITIONAL_HINDCAST','IN_SAMPLE_DESCRIPTION'))
 aggregate_counts<-rowsum(sim,d$year);aq<-t(apply(aggregate_counts,1,quantile,c(.025,.5,.975)))
 annual<-aggregate(cbind(observed_cidt=d$cidt_classified,trials=d$trials),list(year=d$year),sum)
 annual$mean_predicted_cidt<-rowMeans(rowsum(prob*d$trials,d$year));annual$lower_predictive<-aq[,1];annual$median_predictive<-aq[,2];annual$upper_predictive<-aq[,3]
 list(predictions=report,stream_scores=do.call(rbind,streams),annual=annual,draws=list(probability=prob,predictive=sim))
}
run_classification <- function(input,out,cutoff,model,seed,draws=500L) {
 if(dir.exists(out))stop('Refusing existing result');dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
 before<-tools::md5sum(input);d<-read.csv(input,stringsAsFactors=FALSE);warnings<-character()
 fit<-withCallingHandlers(fit_classification(d,cutoff,model),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 writeLines(warnings,file.path(out,'warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl('vb.correction.*aborted',warnings,ignore.case=TRUE)))stop('Numerical fit gate failed')
 write.csv(data.frame(fit_ok=isTRUE(fit$ok),mode_status=as.numeric(fit$mode$mode.status),cpo_failures=sum(fit$cpo$failure>0,na.rm=TRUE),waic=fit$waic$waic),file.path(out,'numerical.csv'),row.names=FALSE)
 result<-classification_reports(fit,d,cutoff,seed,draws)
 for(n in c('predictions','stream_scores','annual'))write.csv(result[[n]],file.path(out,paste0(n,'.csv')),row.names=FALSE)
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE);write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'),row.names=TRUE)
 write.csv(classification_data(d,cutoff)[c('state','year','cidt_classified','trials')],file.path(out,'scoring_input.csv'),row.names=FALSE)
 saveRDS(fit,file.path(out,'fit_INTERNAL.rds'),version=2);saveRDS(result$draws,file.path(out,'draws_INTERNAL.rds'),version=2)
 if(!identical(before,tools::md5sum(input)))stop('Input changed')
 write.csv(data.frame(cutoff=cutoff,model=model,seed=seed,streams=4,draws_per_stream=draws,classification_target=TRUE,incidence_adjustment=FALSE,independent_validation=FALSE),file.path(out,'settings.csv'),row.names=FALSE)
 writeLines('CLASSIFICATION_FIT_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=5)stop('Usage SUPPORT OUT CUTOFF MODEL SEED');run_classification(a[1],a[2],as.integer(a[3]),a[4],as.integer(a[5]))}
