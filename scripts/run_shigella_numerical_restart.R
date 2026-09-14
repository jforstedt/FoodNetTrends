#!/usr/bin/env Rscript
args<-commandArgs(TRUE)
if(length(args)!=11L||args[3]!='2011'||args[6]!='ar1'||args[7]!='TRUE'||!grepl('SHIGELLA',args[4],fixed=TRUE))stop('Expected frozen Shigella 2011 seasonal AR1 spatial task')
here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(here,'run_monthly_spatial_factorial.R'))
source(file.path(here,'shigella_numerical_restart.R'))
original_spatial_fitter<-fit_monthly_spatial_combination
fit_monthly_spatial_combination<-function(...) {
 a<-list(...);a$threads<-1L
 fit<-do.call(original_spatial_fitter,a)
 shigella_restart(fit,dirname(args[4]))
}
run_monthly_spatial_factorial(args[1],args[2],as.integer(args[3]),args[4],as.integer(args[5]),args[6],args[7]=='TRUE',as.integer(args[8]),args[9],args[10],args[11])
