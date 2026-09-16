#!/usr/bin/env Rscript
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'run_monthly_comparison.R'))
source(file.path(.here,'audit_saved_monthly.R'))
source(file.path(.here,'monthly_local_seasonality.R'))

covariate_experiment_data <- function(d,features,manifest,cutoff) {
 if(!manifest$version%in%c('weather_experiment_transform_v1','covariate_factorial_transform_v1')||manifest$training_cutoff_year!=cutoff||manifest$mode!='historical_conditional')stop('Wrong weather training/vintage contract')
 required<-c('fips','year','month','weather_tavg_z','weather_logprcp_z')
 if(!all(required%in%names(features)))stop('Missing weather columns')
 key<-function(x)paste(x$fips,x$year,x$month,sep='|')
 if(anyDuplicated(key(features))||anyDuplicated(key(d)))stop('Duplicate model/weather key')
 j<-match(key(d),key(features));if(anyNA(j))stop('Missing county weather rows')
 feature_names<-c('weather_tavg_z','weather_logprcp_z',if(manifest$version=='covariate_factorial_transform_v1')c('age_under5_z','age65plus_z'))
 if(!all(feature_names%in%names(features)))stop('Missing covariate columns')
 for(name in feature_names) {
  if(!is.numeric(features[[name]])||any(!is.finite(features[[name]][j])))stop('Invalid standardized weather')
  d[[name]]<-features[[name]][j]
 }
 d
}

validate_covariate_saved <- function(fit,predictions,cutoff,seasonal) {
 contract<-attr(fit,'covariate_experiment_contract')
 if(is.null(contract)||contract$version!='county_covariate_experiment_v1'||!isTRUE(seasonal)||contract$cutoff!=cutoff)stop('Invalid experiment contract')
 if(!contract$local_seasonality&&!contract$weather&&!isTRUE(contract$age))return(validate_monthly_saved(fit,predictions,cutoff,TRUE,expected_temporal=contract$temporal))
 d<-attr(fit,'covariate_experiment_masked_data');spec<-attr(fit,'monthly_specification')
 if(is.null(d)||spec$version!='monthly_local_seasonality_fit_v1'||spec$reference_version!=paste0('monthly_',contract$temporal,'_cycle_v1')||spec$cutoff!=cutoff*12+11L||spec$rate_center!=.0002||!isTRUE(spec$seasonal))stop('Wrong extension fit specification')
 if(!isTRUE(fit$ok)||fit$mode$mode.status!=0||is.null(fit$misc$configs)||fit$.args$family!='nbinomial')stop('Fit numerical/config gate')
 if(('local_season'%in%names(fit$summary.random))!=contract$local_seasonality)stop('Local effect identity differs')
 if(!identical(attr(fit,'weather_specification')$enabled,contract$weather))stop('Weather identity differs')
 names_weather<-c('weather_tavg_z','weather_logprcp_z')
 if(any(names_weather%in%rownames(fit$summary.fixed))!=contract$weather||
   (contract$weather&&!all(names_weather%in%rownames(fit$summary.fixed))))stop('Weather coefficient identity differs')
 if(!identical(attr(fit,'age_specification')$enabled,isTRUE(contract$age)))stop('Age identity differs')
 age_names<-c('age_under5_z','age65plus_z')
 if(any(age_names%in%rownames(fit$summary.fixed))!=isTRUE(contract$age)||(isTRUE(contract$age)&&!all(age_names%in%rownames(fit$summary.fixed))))stop('Age coefficient identity differs')
 held<-d$year>cutoff;key<-function(x)paste(x$fips,x$state,x$year,x$month,sep='|')
 if(max(d$year)!=cutoff+3L||any(!is.na(d$count[held]))||any(!is.finite(d$count[!held]))||
    !identical(key(d[held,]),key(predictions))||anyDuplicated(key(predictions))||
    any(!is.finite(predictions$observed)|predictions$observed<0|predictions$observed!=floor(predictions$observed)))stop('Masking/heldout keys differ')
 local_seasonality_count_mean(fit,which(held))
 mapping<-attr(fit,'local_seasonality_prediction_indices')
 if(!identical(as.integer(mapping),seq_len(nrow(d))))stop('Unsupported nonidentity observation mapping')
 list(data=d,indices=which(held),truth=predictions$observed,predictor='APredictor',exposure=d$person_years[held])
}

run_county_covariate_experiment <- function(taskpath) {
 task<-jsonlite::read_json(taskpath,simplifyVector=TRUE)
 if(is.null(task$age))task$age<-FALSE
 if(is.null(task$weather_window))task$weather_window<-'current'
 fields<-c('task_id','pathogen','cutoff','temporal','local_seasonality','weather','candidate','audit','weather_features','weather_manifest','output','seed','prior_check')
 if(!all(fields%in%names(task)))stop('Missing task fields')
 if(!task$pathogen%in%c('SALMONELLA','CAMPYLOBACTER')||!task$cutoff%in%c(2011L,2013L,2016L)||
    task$temporal!=if(task$pathogen=='SALMONELLA')'ar1' else 'rw1')stop('Task outside frozen matrix')
 for(name in c('local_seasonality','weather','age'))if(!is.logical(task[[name]])||length(task[[name]])!=1L||is.na(task[[name]]))stop('Invalid arm flag')
 draws<-if(is.null(task$draws_per_stream))1000L else task$draws_per_stream
 threads<-if(is.null(task$threads))4L else task$threads
 if(draws!=1000L||threads<1||threads!=floor(threads))stop('Wrong resource/sampling contract')
 if(!is.null(task$end_year)&&task$end_year!=2019L)stop('Wrong end year')
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
 d<-load_monthly_comparison(task$candidate,task$audit,task$cutoff,2019L)
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
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage TASK_JSON');run_county_covariate_experiment(a[1])}
