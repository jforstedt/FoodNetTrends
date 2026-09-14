#!/usr/bin/env Rscript
# Additional leave-one-out computations; preserve original posterior and model.
cpo_comparison <- function(before,after,x) {
 a<-inspect_classification(before,x)$row_diagnostics;b<-inspect_classification(after,x)$row_diagnostics
 requested<-a$observed&!is.na(a$cpo_failure)&a$cpo_failure>0
 if(!any(requested))stop('No observed CPO flags to recompute')
 if(any(!a$observed&!is.na(a$cpo_failure)&a$cpo_failure>0))stop('Unexpected held-out CPO flag')
 for(k in c('failure','cpo','pit'))if(!identical(before$cpo[[k]][!requested],after$cpo[[k]][!requested]))stop('Untargeted CPO changed')
 invalid<-!is.finite(b$cpo)|b$cpo<=0|!is.finite(b$pit)|b$pit<0|b$pit>1|!is.finite(b$cpo_failure)
 flagged<-!is.na(b$cpo_failure)&b$cpo_failure>0
 list(comparison=data.frame(state=x$state,year=x$year,observed=a$observed,requested=requested,before_failure=a$cpo_failure,after_failure=b$cpo_failure,before_cpo=a$cpo,after_cpo=b$cpo,before_pit=a$pit,after_pit=b$pit),summary=data.frame(requested=sum(requested),remaining_flagged=sum(flagged&requested),invalid_requested=sum(invalid&requested),resolved=sum(requested&!invalid&!flagged)))
}
run_classification_cpo <- function(fitpath,input,flags,out,cutoff,model,cores=4L) {
 if(dir.exists(out))stop('Refusing existing output')
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 before_hash<-tools::md5sum(c(fitpath,input,flags));fit<-readRDS(fitpath);d<-read.csv(input,stringsAsFactors=FALSE);x<-validate_classification_saved(fit,d,cutoff,model)
 a<-inspect_classification(fit,x)$row_diagnostics;reported<-read.csv(flags,stringsAsFactors=FALSE)
 if(!isTRUE(all.equal(a,reported,tolerance=1e-12,check.attributes=FALSE)))stop('Saved CPO differs from reviewed flags')
 requested<-which(a$observed&!is.na(a$cpo_failure)&a$cpo_failure>0)
 if(!length(requested)||any(!a$observed&!is.na(a$cpo_failure)&a$cpo_failure>0))stop('Invalid CPO selection')
 dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'));warnings<-character()
 on.exit({writeLines(warnings,file.path(out,'warnings.txt'));writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt'))})
 original<-fit
 # inla.cpo uses the second thread count for each leave-one-out fit.
 fit$.args$num.threads<-'1:1'
 repaired<-withCallingHandlers(INLA::inla.cpo(fit,force=FALSE,mc.cores=cores,verbose=TRUE,recompute.mode=TRUE),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 repaired$.args$num.threads<-original$.args$num.threads
 # Only diagnostic values may change in the returned fit object.
 diagnostic_values<-repaired$cpo;repaired$cpo<-original$cpo
 if(!identical(repaired,original))stop('Original posterior or specification changed')
 repaired$cpo<-diagnostic_values
 result<-cpo_comparison(original,repaired,x)
 for(n in names(result))write.csv(result[[n]],file.path(out,paste0(n,'.csv')),row.names=FALSE,na='NA')
 saveRDS(repaired,file.path(out,'repaired_INTERNAL.rds'),version=2)
 if(!identical(before_hash,tools::md5sum(c(fitpath,input,flags))))stop('Original inputs changed')
 write.csv(data.frame(cutoff=cutoff,model=model,rows=nrow(x),requested=length(requested),original_preserved=TRUE,scientific_model_changed=FALSE,accepted=FALSE),file.path(out,'identity.csv'),row.names=FALSE)
 writeLines('CPO_RECOMPUTATION_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L) {
 script<-sub('^--file=','',grep('^--file=',commandArgs(FALSE),value=TRUE)[1]);base<-dirname(normalizePath(script))
 source(file.path(base,'fit_classification_trends.R'));source(file.path(base,'diagnose_classification_saved.R'))
 a<-commandArgs(TRUE);if(length(a)!=6)stop('Usage FIT SUPPORT FLAGS OUT CUTOFF MODEL')
 run_classification_cpo(a[1],a[2],a[3],a[4],as.integer(a[5]),a[6])
}
