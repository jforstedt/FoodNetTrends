#!/usr/bin/env Rscript
verify_reconciled <- function(audit,reconciliation) {
 if(readLines(file.path(audit,'status.txt'))[1]!='INPUT_AUDIT_PASS')stop('Rule audit not passed')
 if(readLines(file.path(reconciliation,'status.txt'))[1]!='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH')stop('Reconciliation not passed')
 checks<-read.csv(file.path(reconciliation,'input_checksums.csv'),stringsAsFactors=FALSE)
 actual<-unname(tools::md5sum(checks$file))
 if(anyNA(actual)||any(actual!=checks$md5))stop('Reconciled source changed')
 d<-readRDS(file.path(audit,'county_panel_INTERNAL.rds'))
 end_year<-if(basename(audit)=='CRYPTOSPORIDIUM')2017L else 2019L
 if(nrow(d)!=486*(end_year-2004+1)||length(unique(d$fips))!=486||!setequal(d$year,2004:end_year))stop('Unexpected scope')
 invisible(TRUE)
}
repair_cpo <- function(audit,original,dest,recompute=NULL) {
 if(is.null(recompute))recompute<-function(fit)INLA::inla.cpo(fit,force=FALSE,mc.cores=1L,verbose=TRUE)
 if(dir.exists(dest))stop('Existing output')
 out<-file.path(dest,'reports');dir.create(out,recursive=TRUE)
 writeLines('RUNNING',file.path(out,'status.txt'))
 tryCatch({
  obj<-validate_panel(audit,FALSE);d<-obj$data
  checkpoint<-file.path(original,'fit_INTERNAL.rds');before<-tools::md5sum(checkpoint)
  chk<-read.csv(file.path(original,'reports/panel_checksum.csv'),stringsAsFactors=FALSE)
  if(nrow(chk)!=1||chk$md5!=unname(tools::md5sum(file.path(audit,'county_panel_INTERNAL.rds'))))stop('Saved fit panel mismatch')
  fit<-readRDS(checkpoint);n<-nrow(d)
  if(length(fit$cpo$failure)!=n||length(fit$cpo$cpo)!=n)stop('CPO dimension mismatch')
  bad<-which(!is.finite(fit$cpo$failure)|fit$cpo$failure!=0|!is.finite(fit$cpo$cpo)|fit$cpo$cpo<=0)
  old<-fit$cpo;fit$cpo$failure[bad]<-1
  repaired<-recompute(fit)
  # Manual CPO calculations must not replace the original full-data posterior.
  for(field in c('summary.fixed','summary.hyperpar','summary.fitted.values'))
   if(!identical(fit[[field]],repaired[[field]]))stop('CPO repair altered posterior summaries')
  z<-d[bad,c('fips','state','year','count')]
  z$cpo_before<-old$cpo[bad];z$cpo_after<-repaired$cpo$cpo[bad]
  z$failure_before<-old$failure[bad];z$failure_after<-repaired$cpo$failure[bad]
  write.csv(z,file.path(out,'recomputed_cells_INTERNAL.csv'),row.names=FALSE)
  saveRDS(repaired,file.path(dest,'fit_cpo_repaired_INTERNAL.rds'))
  valid<-is.finite(repaired$cpo$cpo)&repaired$cpo$cpo>0&is.finite(repaired$cpo$failure)&repaired$cpo$failure==0
  write.csv(data.frame(cells=n,recomputed=length(bad),remaining_failures=sum(!valid),
   sum_log_cpo=if(all(valid))sum(log(repaired$cpo$cpo)) else NA),file.path(out,'cpo_summary.csv'),row.names=FALSE)
  if(!identical(before,tools::md5sum(checkpoint)))stop('Original fit changed')
  write.csv(data.frame(file=checkpoint,md5=unname(before)),file.path(out,'original_checksum.csv'),row.names=FALSE)
  writeLines(if(all(valid))'CPO_REPAIR_COMPLETE' else 'CPO_REVIEW_REQUIRED',file.path(out,'status.txt'))
 },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L) {
 a<-commandArgs(TRUE);if(length(a)!=6)stop('MODE AUDIT RECONCILIATION ORIGINAL DEST MODEL')
 here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
 for(f in c('fit_county_pilot.R','diagnose_saved_county_pilot.R','county_sensitivity.R','county_forecast_check.R'))source(file.path(here,f))
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected pinned INLA')
 verify_reconciled(a[2],a[3])
 if(a[1]=='forecast')run_forecast(a[2],a[5],a[6],threads=8L,expected_production=FALSE)
 else if(a[1]=='retry')run_sensitivity(a[2],a[5],a[6],threads=1L,expected_production=FALSE,verbose=TRUE)
 else if(a[1]=='cpo')repair_cpo(a[2],a[4],a[5])
 else stop('Unknown mode')
}
