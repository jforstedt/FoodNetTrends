#!/usr/bin/env Rscript
# Singleton CV versus explicit omission, fixed and re-estimated hyperparameters.
masked_classification <- function(x,index) {
 if(length(index)!=1L||is.na(index)||index<1||index>nrow(x)||is.na(x$success[index]))stop('Target must be one observed response')
 x$success[index]<-NA_real_;x
}
explicit_classification <- function(original,x,index,method) {
 stopifnot(method%in%c('full','eb'));masked<-masked_classification(x,index)
 f<-INLA::f;formula<-original$.args$formula;environment(formula)<-environment()
 args<-list(formula=formula,data=masked,family='binomial',Ntrials=masked$trials,num.threads='4:1',control.fixed=original$.args$control.fixed,control.predictor=list(compute=TRUE,link=1),control.compute=list(config=TRUE,cpo=FALSE,waic=FALSE))
 if(method=='eb'){args$control.mode<-list(theta=original$mode$theta,fixed=TRUE);args$control.inla<-list(int.strategy='eb')}
 fit<-do.call(INLA::inla,args)
 if(method=='eb'&&(!isTRUE(fit$.args$control.mode$fixed)||!isTRUE(all.equal(as.numeric(fit$.args$control.mode$theta),as.numeric(original$mode$theta),tolerance=0))))stop('Fixed hyperparameters changed')
 if(!isTRUE(fit$ok)||as.numeric(fit$mode$mode.status)!=0)stop('Explicit numerical fit failed')
 for(k in c('state','year','success','trials','time_scaled','site','slope_site','cell'))if(!identical(as.character(fit$.args$data[[k]]),as.character(masked[[k]])))stop('Explicit fit data or mask mismatch')
 if(!identical(as.numeric(fit$.args$Ntrials),as.numeric(masked$trials)))stop('Explicit likelihood trials mismatch')
 fit
}
score_omitted <- function(fit,index,y,n,seed,draws=1000L) {
 logdens<-matrix(NA_real_,4,draws)
 for(k in 1:4) {
  samples<-INLA::inla.posterior.sample(draws,fit,selection=list(Predictor=index),seed=as.integer(seed+k*10000L),num.threads='1:1',skew.corr=FALSE)
  for(j in seq_len(draws)) {
   latent<-samples[[j]]$latent
   if(nrow(latent)!=1L||rownames(latent)[1]!=paste0('Predictor:',index))stop('Sample predictor mismatch')
   logdens[k,j]<-dbinom(y,n,plogis(latent[1,1]),log=TRUE)
  }
 }
 summarize<-function(v){a<-max(v);if(!is.finite(a))stop('Nonfinite density');z<-exp(v-a);c(log_score=a+log(mean(z)),relative_mcse=sd(z)/sqrt(length(z))/mean(z))}
 streams<-as.data.frame(t(apply(logdens,1,summarize)));streams$stream<-1:4;streams$draws<-draws
 list(pooled=summarize(as.vector(logdens)),streams=streams)
}
run_classification_crosscheck <- function(fitpath,input,flags,out,state,year,seed,draws=1000L) {
 if(dir.exists(out))stop('Refusing existing output');if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 before<-tools::md5sum(c(fitpath,input,flags));original<-readRDS(fitpath);d<-read.csv(input,stringsAsFactors=FALSE);x<-validate_classification_saved(original,d,2016L,'shared')
 reported<-read.csv(flags,stringsAsFactors=FALSE)
 if(!isTRUE(all.equal(inspect_classification(original,x)$row_diagnostics,reported,tolerance=1e-12,check.attributes=FALSE)))stop('Source flags differ')
 index<-which(x$state==state&x$year==year);masked_classification(x,index)
 dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'));warnings<-character()
 on.exit({writeLines(warnings,file.path(out,'warnings.txt'));writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt'))})
 results<-withCallingHandlers({
  copy<-original;copy$.args$num.threads<-'4:1'
  g<-INLA::inla.group.cv(copy,groups=lapply(seq_len(nrow(x)),function(i)i),type.cv='single')
  if(length(g$groups)!=nrow(x)||length(g$cv)!=nrow(x)||!all(vapply(seq_len(nrow(x)),function(i)identical(as.integer(g$groups[[i]]$idx),as.integer(i)),logical(1))))stop('CV singleton identity differs')
  scores<-list();numerical<-list()
  for(method in c('full','eb')) {
   fit<-explicit_classification(original,x,index,method)
   scores[[method]]<-score_omitted(fit,index,x$success[index],x$trials[index],seed+if(method=='eb')100000L else 0L,draws)
   numerical[[method]]<-data.frame(method=method,fit_ok=fit$ok,mode_status=fit$mode$mode.status)
   saveRDS(fit,file.path(out,if(method=='full')'explicit_INTERNAL.rds' else 'eb_INTERNAL.rds'),version=2)
  }
  list(g=g,scores=scores,numerical=numerical)
 },warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 scores<-results$scores;g<-results$g
 write.csv(data.frame(state=state,year=year,original_cpo=original$cpo$cpo[index],original_failure=original$cpo$failure[index],group_cv=g$cv[index],explicit_log_score=scores$full$pooled['log_score'],explicit_relative_mcse=scores$full$pooled['relative_mcse'],eb_log_score=scores$eb$pooled['log_score'],eb_relative_mcse=scores$eb$pooled['relative_mcse']),file.path(out,'comparison.csv'),row.names=FALSE)
 streams<-do.call(rbind,lapply(names(scores),function(m)data.frame(method=m,scores[[m]]$streams)));write.csv(streams,file.path(out,'stream_scores.csv'),row.names=FALSE)
 write.csv(do.call(rbind,results$numerical),file.path(out,'numerical.csv'),row.names=FALSE)
 write.csv(data.frame(state=state,year=year,seed=seed,row_id=index,observed_cidt=x$success[index],trials=x$trials[index],original_preserved=TRUE,accepted=FALSE),file.path(out,'identity.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(c(fitpath,input,flags))))stop('Original inputs changed')
 writeLines('CROSSCHECK_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L) {
 script<-sub('^--file=','',grep('^--file=',commandArgs(FALSE),value=TRUE)[1]);base<-dirname(normalizePath(script))
 source(file.path(base,'fit_classification_trends.R'));source(file.path(base,'diagnose_classification_saved.R'))
 a<-commandArgs(TRUE);if(length(a)!=7)stop('Usage FIT SUPPORT FLAGS OUT STATE YEAR SEED')
 run_classification_crosscheck(a[1],a[2],a[3],a[4],a[5],as.integer(a[6]),as.integer(a[7]))
}
