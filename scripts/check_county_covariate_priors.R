#!/usr/bin/env Rscript
.prior_source<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.prior_here<-dirname(normalizePath(if(!is.null(.prior_source)).prior_source else sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1])))
check_county_covariate_priors <- function(output) {
 if(file.exists(output))stop('Refusing existing prior check')
 if(!requireNamespace('jsonlite',quietly=TRUE))stop('jsonlite required')
 # Fixed scientific-scale gates, chosen before real outcomes. One standardized
 # predictor can plausibly change rate by roughly a factor 1.6, not orders of magnitude.
 set.seed(73119);n<-50000L;beta<-matrix(rnorm(4*n,0,.25),n,4)
 one<-exp(beta[,1]);both<-exp(rowSums(beta));rr95<-quantile(one,c(.025,.975))
 stopifnot(rr95[1]>.55,rr95[2]<1.85,mean(both>4)<.004,all(is.finite(both)))
 source(file.path(.prior_here,'monthly_local_seasonality.R'))
 grid<-expand.grid(month=1:12,state=c('A','B','C'),stringsAsFactors=FALSE)
 component<-local_seasonality_component(grid,sd_upper=.5,sd_tail=.01)
 stopifnot(min(eigen(component$Q,symmetric=TRUE,only.values=TRUE)$values)>0,
   max(abs(diag(component$basis%*%solve(component$Q,t(component$basis)))-1))<1e-10)
 out<-list(status='PRIOR_CHECK_PASS',version='county_covariate_prior_v1',outcome_data_used=FALSE,
   seed=73119,draws=n,weather_mean=0,weather_sd=.25,age_sd=.25,local_sd_upper=.5,local_sd_tail=.01,
   local_constraints='state and cycle zero sums',weather_rr95=as.numeric(rr95),joint_feature_count=4L,joint_rr95=as.numeric(quantile(both,c(.025,.975))),joint_probability_rr_above4=mean(both>4),
   sources=as.list(tools::md5sum(file.path(.prior_here,c('monthly_local_seasonality.R','monthly_seasonal_model.R','check_county_covariate_priors.R','run_county_covariate_experiment.R')))))
 jsonlite::write_json(out,output,auto_unbox=TRUE,pretty=TRUE)
 cat('PRIOR_CHECK_PASS\n')
}
if(sys.nframe()==0L){args<-commandArgs(TRUE);if(length(args)!=1L)stop('Usage OUTPUT_JSON');check_county_covariate_priors(args[1])}
