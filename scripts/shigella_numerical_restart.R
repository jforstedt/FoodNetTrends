# One documented INLA optimizer restart. No model/prior or acceptance changes.
shigella_restart <- function(fit,work,rerun=INLA::inla.rerun) {
  saveRDS(fit,file.path(work,'initial_optimizer_fit_INTERNAL.rds'),version=2)
  metadata<-attributes(fit)[grepl('^monthly_',names(attributes(fit)))]
  original<-fit$.args
  writeLines(capture.output(str(list(ok=fit$ok,mode=fit$mode,control.inla=original$control.inla))),file.path(work,'initial_optimizer.txt'))
  # Verbose only exposes numerical diagnostics; no likelihood or prior change.
  fit$.args$verbose<-TRUE
  fresh<-rerun(fit)
  for(n in names(metadata))attr(fresh,n)<-metadata[[n]]
  for(n in c('formula','data','family','control.fixed','control.family','control.predictor','control.compute','num.threads','E','Ntrials','offset','weights','scale')) {
    a<-original[[n]];b<-fresh$.args[[n]]
    # inla.rerun explicitly sets this reporting switch to FALSE.
    if(n=='control.fixed'){a$correlation.matrix<-NULL;b$correlation.matrix<-NULL}
    if(!isTRUE(all.equal(a,b,check.attributes=TRUE)))stop(paste('Restart changed model argument',n))
  }
  saveRDS(fresh,file.path(work,'restarted_optimizer_fit_INTERNAL.rds'),version=2)
  writeLines(capture.output(str(list(ok=fresh$ok,mode=fresh$mode,control.inla=fresh$.args$control.inla))),file.path(work,'restarted_optimizer.txt'))
  write.csv(data.frame(initial_ok=isTRUE(fit$ok),initial_mode_status=paste(fit$mode$mode.status,collapse=';'),
    restart_ok=isTRUE(fresh$ok),restart_mode_status=paste(fresh$mode$mode.status,collapse=';'),
    fitting_threads='1:1',strategy='INLA_inla.rerun_once',model_changed=FALSE,quality_gate_relaxed=FALSE),
    file.path(work,'restart_numerics.csv'),row.names=FALSE)
  fresh
}
