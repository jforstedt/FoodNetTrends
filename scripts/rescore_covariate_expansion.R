#!/usr/bin/env Rscript
# Recover posterior diagnostics from an existing fit. Never refit a model.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'prepare_covariate_expansion.R'))

validate_covariate_recovery_seed <- function(seed) {
 if(!is.numeric(seed)||length(seed)!=1L||!is.finite(seed)||seed<1||seed>1e9||seed!=floor(seed))stop('Recovery seed must be an integer in 1..1000000000')
 invisible(TRUE)
}

validate_covariate_recovery_fit <- function(fit,pred,task,source_data) {
 validate_covariate_expansion_task(task)
 contract<-attr(fit,'covariate_experiment_contract')
 fields<-c('task_id','pathogen','cutoff','temporal','local_seasonality','weather','age','weather_window','expansion_version','end_year')
 for(n in fields)if(is.null(contract[[n]])||!isTRUE(all.equal(contract[[n]],task[[n]],check.attributes=FALSE)))stop(paste('Saved fit/task contract differs:',n))
 if(!identical(contract$version,'county_covariate_experiment_v1')||!identical(contract$target,'reported county incidence')||!identical(contract$weather_mode,'historical_conditional')||!identical(contract$coverage_certified,FALSE))stop('Saved outcome/coverage contract differs')
 obj<-validate_covariate_saved(fit,pred,task$cutoff,TRUE)
 expected<-monthly_model_data(source_data,task$cutoff*12+11L,'EXPLORATORY_ASSUMED_CONTINUOUS')$data
 cols<-c('fips','state','year','month','area','state_id','time','season','count','person_years','weather_tavg_z','weather_logprcp_z','age_under5_z','age65plus_z')
 saved<-obj$data
 if(nrow(saved)!=nrow(expected)||!all(cols%in%names(saved)))stop('Saved/source model data domain differs')
 for(n in cols) {
  a<-saved[[n]];b<-expected[[n]]
  if(n%in%c('fips','state')){a<-as.character(a);b<-as.character(b)}
  if(!isTRUE(all.equal(a,b,tolerance=0,check.attributes=FALSE)))stop(paste('Saved/source model data differs:',n))
 }
 held<-source_data$year>task$cutoff
 if(!isTRUE(all.equal(as.numeric(pred$observed),as.numeric(source_data$count[held]),tolerance=0)))stop('Saved heldout truth differs from audited source')
 spec<-attr(fit,'monthly_specification')
 equal<-function(x,y)isTRUE(all.equal(x,y,tolerance=1e-12,check.attributes=FALSE))
 if(!equal(spec$seasonal_sd_bound,.5)||!equal(spec$pc_tail,.01)||!equal(spec$nb_log_size_mean,log(20))||!equal(spec$nb_log_size_sd,1))stop('Saved common prior contract differs')
 if(task$temporal=='ar1') {
  if(!equal(spec$ar1_marginal_sd_upper,1)||!equal(spec$ar1_rho_internal_mean,log(19))||!equal(spec$ar1_rho_internal_sd,1.5)||!is.null(spec$trend_constraint))stop('Saved AR1 prior differs')
 } else {
  target<-monthly_model_data(source_data,task$cutoff*12+11L,'EXPLORATORY_ASSUMED_CONTINUOUS')$spec
  for(n in c('trend_constraint','trend_scale','trend_sd_bound','trend_sd_upper'))if(!equal(spec[[n]],target[[n]]))stop(paste('Saved RW1 prior differs:',n))
 }
 features<-c(if(task$weather)c('weather_tavg_z','weather_logprcp_z'),if(task$age)c('age_under5_z','age65plus_z'))
 for(n in features)if(!equal(fit$.args$control.fixed$mean[[n]],0)||!equal(fit$.args$control.fixed$prec[[n]],16))stop('Saved coefficient prior differs')
 if(length(features)&&(!equal(fit$.args$control.fixed$mean$default,log(.0002))||!equal(fit$.args$control.fixed$prec$default,1)))stop('Saved intercept prior differs')
 if(!length(features)&&(!equal(fit$.args$control.fixed$mean,log(.0002))||!equal(fit$.args$control.fixed$prec,1)))stop('Saved intercept prior differs')
 obj
}

rescore_covariate_expansion <- function(taskpath) {
 recovery<-jsonlite::read_json(taskpath,simplifyVector=TRUE)
 required<-c('source_task','fit','truth','seed','output','source_scripts')
 if(!all(required%in%names(recovery)))stop('Missing recovery task fields')
 validate_covariate_recovery_seed(recovery$seed)
 task<-jsonlite::read_json(recovery$source_task,simplifyVector=TRUE)
 if(!identical(recovery$source_scripts,task$source_scripts))stop('Recovery source scripts differ from original task')
 if(!identical(normalizePath(recovery$fit,mustWork=TRUE),normalizePath(file.path(task$output,'fit_INTERNAL.rds'),mustWork=TRUE))||
    !identical(normalizePath(recovery$truth,mustWork=TRUE),normalizePath(file.path(task$output,'heldout_truth_INTERNAL.csv'),mustWork=TRUE)))stop('Recovery checkpoints differ from original task output')
 load_covariate_expansion_helpers(task)
 validate_covariate_expansion_task(task)
 # Fail before creating reports if any original numerical warning invalidated the fit.
 warningpath<-file.path(dirname(recovery$fit),'fit_warnings.txt')
 if(!file.exists(warningpath)||any(grepl('vb[.]correction.*aborted',readLines(warningpath,warn=FALSE),ignore.case=TRUE)))stop('Missing/failed original numerical warning gate')
 inputs<-c(taskpath,recovery$source_task,recovery$fit,recovery$truth,warningpath,task$candidate,file.path(task$audit,'county_panel_INTERNAL.rds'),task$weather_features,task$weather_manifest,task$prior_check)
 before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing recovery/source input')
 prior<-jsonlite::read_json(task$prior_check,simplifyVector=TRUE)
 if(prior$status!='PRIOR_CHECK_PASS'||prior$version!='county_covariate_prior_v1'||!identical(prior$outcome_data_used,FALSE)||prior$weather_mean!=0||prior$weather_sd!=.25||prior$age_sd!=.25||prior$local_sd_upper!=.5||prior$local_sd_tail!=.01)stop('Original prior check differs')
 for(path in names(prior$sources))if(!identical(unname(tools::md5sum(path)),unname(prior$sources[[path]])))stop('Original prior-checked source changed')
 manifest<-jsonlite::read_json(task$weather_manifest,simplifyVector=TRUE)
 if(manifest$version!='covariate_factorial_transform_v1'||manifest$weather_window!=task$weather_window)stop('Original transform contract differs')
 hash<-manifest$outputs[[basename(task$weather_features)]]
 if(is.null(hash)||digest::digest(file=task$weather_features,algo='sha256')!=hash)stop('Original feature hash differs')
 d<-load_monthly_comparison(task$candidate,task$audit,task$cutoff,task$end_year)
 d<-covariate_experiment_data(d,read.csv(task$weather_features,colClasses=c(fips='character')),manifest,task$cutoff)
 fit<-readRDS(recovery$fit);pred<-read.csv(recovery$truth,colClasses=c(fips='character'))
 validate_covariate_recovery_fit(fit,pred,task,d)
 out<-file.path(recovery$output,'reports')
 copiedtruth<-file.path(recovery$output,'heldout_truth_INTERNAL.csv')
 if(dir.exists(out)||file.exists(out)||file.exists(copiedtruth))stop('Refusing existing recovery reports/truth')
 dir.create(recovery$output,recursive=TRUE,showWarnings=FALSE)
 if(!file.copy(recovery$truth,copiedtruth,overwrite=FALSE)||!identical(unname(tools::md5sum(recovery$truth)),unname(tools::md5sum(copiedtruth))))stop('Could not copy exact heldout truth')
 audit_monthly_saved(recovery$fit,recovery$truth,task$cutoff,TRUE,out,recovery$seed,draws=1000L,
  adapter=validate_covariate_saved,rng_protocol='explicit_config_v2')
 if(!file.rename(file.path(out,'pooled_cell_scores.csv'),file.path(out,'pooled_cell_scores_INTERNAL.csv')))stop('Could not mark county scores INTERNAL')
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'),row.names=TRUE)
 contract<-attr(fit,'covariate_experiment_contract')
 jsonlite::write_json(c(contract,list(streams=4L,draws_per_stream=1000L,threads=task$threads,
  seed=recovery$seed,original_seed=task$seed,weather_prior_sd=.25,age_prior_sd=.25,local_prior_sd_upper=.5,local_prior_tail=.01,
  new_fit=FALSE,scientific_acceptance=FALSE)),file.path(out,'experiment_settings.json'),auto_unbox=TRUE,pretty=TRUE)
 jsonlite::write_json(list(version='county_covariate_rescore_v1',source_task=task,source_task_path=recovery$source_task,
  original_seed=task$seed,new_seed=recovery$seed,refitted=FALSE,original_fit_unchanged=TRUE,
  source_fit=recovery$fit,source_truth=recovery$truth,input_md5=as.list(setNames(unname(before),inputs)),
  validation=list(full_task_contract=TRUE,source_panel=TRUE,masked_training_counts=TRUE,heldout_truth=TRUE,
   exposure=TRUE,covariates=TRUE,temporal_priors=TRUE,coefficient_priors=TRUE,predictor_mapping=TRUE),
  status='COVARIATE_EXPANSION_RESCORE_COMPLETE'),file.path(out,'sampling_recovery.json'),auto_unbox=TRUE,pretty=TRUE)
 if(!identical(before,tools::md5sum(inputs)))stop('Original inputs changed during recovery')
 if(!identical(unname(tools::md5sum(recovery$truth)),unname(tools::md5sum(copiedtruth))))stop('Copied recovery truth changed during scoring')
 write.csv(data.frame(file=inputs,md5=unname(before)),file.path(out,'experiment_input_checksums.csv'),row.names=FALSE)
 writeLines('COUNTY_COVARIATE_EXPERIMENT_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage TASK_JSON');rescore_covariate_expansion(a[1])}
