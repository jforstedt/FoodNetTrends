#!/usr/bin/env Rscript
args<-commandArgs(TRUE)
if(length(args)!=11L)stop('Expected frozen spatial task arguments')
here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(here,'run_monthly_spatial_factorial.R'))
original_spatial_fitter<-fit_monthly_spatial_combination
fit_monthly_spatial_combination<-function(...) {
 a<-list(...);a$threads<-1L
 fit<-do.call(original_spatial_fitter,a)
 write.csv(data.frame(fit_ok=isTRUE(fit$ok),mode_status=paste(fit$mode$mode.status,collapse=';'),
   fitting_threads='1:1',recovery='single_thread_same_model',quality_gate_relaxed=FALSE),
   file.path(dirname(args[4]),'recovery_numerics.csv'),row.names=FALSE)
 fit
}
run_monthly_spatial_factorial(args[1],args[2],as.integer(args[3]),args[4],as.integer(args[5]),args[6],args[7]=='TRUE',as.integer(args[8]),args[9],args[10],args[11])
