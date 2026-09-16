#!/usr/bin/env Rscript
# All-pathogen expansion: preserve the established fitting/scoring machinery.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'prepare_covariate_expansion.R'))

run_covariate_expansion <- function(taskpath) {
 task<-jsonlite::read_json(taskpath,simplifyVector=TRUE)
 # Check the frozen sampler's actual bound before doing any fitting work.
 if(!is.numeric(task$seed)||length(task$seed)!=1L||!is.finite(task$seed)||task$seed<1||task$seed>1e9||task$seed!=floor(task$seed))stop('Sampling seed must be an integer in 1..1000000000 before fitting')
 load_covariate_expansion_helpers(task)
 if(is.null(task$age))task$age<-FALSE
 if(is.null(task$weather_window))task$weather_window<-'current'
 fields<-c('task_id','pathogen','cutoff','temporal','local_seasonality','weather','candidate','audit','weather_features','weather_manifest','output','seed','prior_check')
 if(!all(fields%in%names(task)))stop('Missing task fields')
 validate_covariate_expansion_task(task)
 for(name in c('local_seasonality','weather','age'))if(!is.logical(task[[name]])||length(task[[name]])!=1L||is.na(task[[name]]))stop('Invalid arm flag')
 draws<-if(is.null(task$draws_per_stream))1000L else task$draws_per_stream
 threads<-if(is.null(task$threads))4L else task$threads
 if(draws!=1000L||threads<1||threads!=floor(threads))stop('Wrong resource/sampling contract')

 prior<-jsonlite::read_json(task$prior_check,simplifyVector=TRUE)
 if(prior$status!='PRIOR_CHECK_PASS'||prior$version!='county_covariate_prior_v1'||!identical(prior$outcome_data_used,FALSE)||
    prior$weather_mean!=0||prior$weather_sd!=.25||prior$age_sd!=.25||prior$local_sd_upper!=.5||prior$local_sd_tail!=.01)stop('Prior check mismatch')
 for(path in names(prior$sources))if(!identical(unname(tools::md5sum(path)),unname(prior$sources[[path]])))stop('Prior-checked source changed')
 work<-task$output;dir.create(work,recursive=TRUE,showWarnings=FALSE)
 fitpath<-file.path(work,'fit_INTERNAL.rds');truthpath<-file.path(work,'heldout_truth_INTERNAL.csv');out<-file.path(work,'reports')
 if(file.exists(fitpath)||file.exists(truthpath)||dir.exists(out))stop('Refusing existing task artifacts')
 inputs<-c(taskpath,task$candidate,file.path(task$audit,'county_panel_INTERNAL.rds'),task$weather_features,task$weather_manifest,task$prior_check)
 before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing experiment input')
 manifest<-jsonlite::read_json(task$weather_manifest,simplifyVector=TRUE)
 # SHA256 public transform digest is independently checked even for weather-off controls.
 if(!requireNamespace('digest',quietly=TRUE))stop('digest required for transform SHA256')
 expected<-manifest$outputs[[basename(task$weather_features)]]
 if(is.null(expected)||digest::digest(file=task$weather_features,algo='sha256')!=expected)stop('Weather transform hash differs')
 if(task$weather_window!='current'&&task$weather_window!='lag01')stop('Unknown weather window')
 if(!is.null(manifest$weather_window)&&manifest$weather_window!=task$weather_window)stop('Weather window mismatch')
 if((task$age||task$weather_window=='lag01')&&manifest$version!='covariate_factorial_transform_v1')stop('Factorial transform required')
 d<-load_monthly_comparison(task$candidate,task$audit,task$cutoff,task$end_year)
 d<-covariate_experiment_data(d,read.csv(task$weather_features,colClasses=c(fips='character')),manifest,task$cutoff)
 warnings<-character()
 fit<-withCallingHandlers(fit_monthly_local_seasonality(d,task$cutoff*12+11L,seasonal=TRUE,
    threads=threads,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002,
    temporal_model=task$temporal,local_seasonality=task$local_seasonality,weather=task$weather,age=task$age),
    warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 writeLines(warnings,file.path(work,'fit_warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl('vb[.]correction.*aborted',warnings,ignore.case=TRUE)))stop('Numerical gate failed')
 contract<-list(version='county_covariate_experiment_v1',task_id=task$task_id,pathogen=task$pathogen,
   cutoff=task$cutoff,temporal=task$temporal,local_seasonality=task$local_seasonality,weather=task$weather,age=task$age,weather_window=task$weather_window,
   expansion_version='county_covariate_expansion_v1',end_year=task$end_year,
   target='reported county incidence',weather_mode='historical_conditional',coverage_certified=FALSE)
 attr(fit,'covariate_experiment_contract')<-contract
 saveRDS(fit,fitpath,version=2)
 truth<-d[d$year>task$cutoff,c('fips','state','year','month')];truth$observed<-d$count[d$year>task$cutoff]
 write.csv(truth,truthpath,row.names=FALSE)
 audit_monthly_saved(fitpath,truthpath,task$cutoff,TRUE,out,task$seed,draws=draws,
    adapter=validate_covariate_saved,rng_protocol='explicit_config_v2')
 if(!file.rename(file.path(out,'pooled_cell_scores.csv'),file.path(out,'pooled_cell_scores_INTERNAL.csv')))stop('Could not mark county scores INTERNAL')
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'),row.names=TRUE)
 jsonlite::write_json(c(contract,list(streams=4L,draws_per_stream=draws,threads=threads,
   seed=task$seed,weather_prior_sd=.25,age_prior_sd=.25,local_prior_sd_upper=.5,local_prior_tail=.01,
   new_fit=TRUE,scientific_acceptance=FALSE)),file.path(out,'experiment_settings.json'),auto_unbox=TRUE,pretty=TRUE)
 if(!identical(before,tools::md5sum(inputs)))stop('Experiment input changed during execution')
 write.csv(data.frame(file=inputs,md5=unname(before)),file.path(out,'experiment_input_checksums.csv'),row.names=FALSE)
 writeLines('COUNTY_COVARIATE_EXPERIMENT_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage TASK_JSON');run_covariate_expansion(a[1])}
