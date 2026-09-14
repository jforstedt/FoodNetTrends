#!/usr/bin/env Rscript
# Read-only saved-fit inspection and posterior sampling. Never refits.
validate_classification_saved <- function(fit,d,cutoff,model) {
 x<-classification_data(d,cutoff);saved<-fit$.args$data
 spec<-attr(fit,'classification_spec')
 expected<-list(version='conditional_category_v1',cutoff=cutoff,model=model,target='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT',time_origin=2012,time_scale=4,intercept_mean=qlogis(.1),intercept_sd=1.5,slope_sd=1,site_sd_upper=1.5,cell_sd_upper=1,slope_sd_upper=1,pc_tail=.01)
 if(!isTRUE(all.equal(spec,expected,tolerance=0,check.attributes=FALSE)))stop('Saved model specification differs')
 for(k in c('state','year','success','trials','time_scaled','site','slope_site','cell')) {
  if(!k%in%names(saved)||!identical(as.character(saved[[k]]),as.character(x[[k]])))stop(paste('Saved data or masking differs:',k))
 }
 if(!identical(as.numeric(fit$.args$Ntrials),as.numeric(x$trials)))stop('Saved likelihood trials differ')
 fields<-c('site','cell',if(model=='site_slopes')'slope_site')
 if(!setequal(names(fit$summary.random),fields)||!all(fit$model.random=='IID model')||!identical(as.character(fit$.args$family),'binomial')||is.null(fit$misc$configs)||nrow(fit$summary.linear.predictor)!=nrow(x))stop('Saved likelihood or latent identity differs')
 if(!isTRUE(fit$ok)||as.numeric(fit$mode$mode.status)!=0)stop('Saved numerical fit gate failed')
 x
}
inspect_classification <- function(fit,x) {
 n<-nrow(x);cp<-fit$cpo
 if(any(vapply(cp[c('failure','cpo','pit')],length,integer(1))!=n))stop('CPO row identity unavailable')
 rows<-data.frame(state=x$state,year=x$year,observed=!is.na(x$success),cpo_failure=cp$failure,cpo=cp$cpo,pit=cp$pit)
 summary<-do.call(rbind,lapply(c(TRUE,FALSE),function(observed){i<-rows$observed==observed;data.frame(observed=observed,rows=sum(i),flagged=sum(rows$cpo_failure[i]>0,na.rm=TRUE),missing_failure=sum(is.na(rows$cpo_failure[i])),nonfinite_cpo=sum(!is.finite(rows$cpo[i])),nonpositive_cpo=sum(rows$cpo[i]<=0,na.rm=TRUE))}))
 list(row_diagnostics=rows,summary=summary)
}
run_saved_classification <- function(fitpath,input,out,cutoff,model,seed,mode,draws=2500L) {
 if(!mode%in%c('inspect','precision')||!model%in%c('shared','site_slopes')||(mode=='precision'&&cutoff!=2016L))stop('Unsupported diagnostic task')
 if(dir.exists(out))stop('Refusing existing output')
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 before<-tools::md5sum(c(fitpath,input));fit<-readRDS(fitpath);d<-read.csv(input,stringsAsFactors=FALSE);x<-validate_classification_saved(fit,d,cutoff,model)
 dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
 on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
 if(mode=='inspect') {
  reports<-inspect_classification(fit,x)
  for(n in names(reports))write.csv(reports[[n]],file.path(out,paste0(n,'.csv')),row.names=FALSE,na='NA')
  write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'));write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'))
  for(n in names(fit$summary.random))write.csv(fit$summary.random[[n]],file.path(out,paste0('latent_',n,'.csv')),row.names=FALSE)
 } else {
  reports<-classification_reports(fit,d,cutoff,seed,draws)
  for(n in c('predictions','stream_scores','annual'))write.csv(reports[[n]],file.path(out,paste0(n,'.csv')),row.names=FALSE)
 }
 write.csv(data.frame(cutoff=cutoff,model=model,seed=seed,mode=mode,rows=nrow(x),draws_per_stream=if(mode=='precision')draws else 0L,refitted=FALSE,accepted=FALSE),file.path(out,'identity.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(c(fitpath,input))))stop('Source inputs changed')
 writeLines('DIAGNOSTICS_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L) {
 script<-sub('^--file=','',grep('^--file=',commandArgs(FALSE),value=TRUE)[1]);source(file.path(dirname(normalizePath(script)),'fit_classification_trends.R'))
 a<-commandArgs(TRUE);if(length(a)!=7)stop('Usage FIT SUPPORT OUT CUTOFF MODEL SEED MODE')
 run_saved_classification(a[1],a[2],a[3],as.integer(a[4]),a[5],as.integer(a[6]),a[7])
}
