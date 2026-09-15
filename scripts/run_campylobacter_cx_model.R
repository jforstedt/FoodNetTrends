#!/usr/bin/env Rscript
# Separate exploratory recorded-CX+ target. Baseline fitter is frozen and unchanged.
load_cx_monthly <- function(candidate,combined,metadata) {
 cx<-readRDS(candidate)
 cols<-c('state','fips','year','month','record_count','population','candidate_person_years')
 if(!all(cols%in%names(cx))||anyNA(cx[cols]))stop('Missing CX panel fields')
 key<-function(x)paste(x$state,x$fips,x$year,x$month,sep='|')
 if(anyDuplicated(key(cx))||!all(key(combined)%in%key(cx)))stop('CX panel domain differs')
 ix<-match(key(combined),key(cx));x<-cx[ix,]
 if(any(!is.finite(x$record_count)|x$record_count<0|x$record_count!=floor(x$record_count))||
    any(x$record_count>combined$count)||any(x$population!=combined$population)||any(x$candidate_person_years!=combined$person_years))stop('CX counts/exposure differ from original domain')
 if(is.null(metadata$version)||metadata$version!='campylobacter_cx_target_v1'||metadata$status!='CX_TARGET_PREPARATION_COMPLETE'||metadata$target!='recorded_CX_positive'||
    !isTRUE(metadata$combined_replay_verified)||!isTRUE(metadata$raw_clean_cx_strata_verified)||!isTRUE(metadata$pre2012_cx_equals_combined)||
    unname(tools::md5sum(candidate))!=metadata$cx_candidate_md5)stop('Unverified CX target')
 combined$count<-x$record_count;combined$record_count<-x$record_count;combined
}
validate_cx_reuse_training <- function(fit,d,cutoff,local,source_task) {
 c<-attr(fit,'covariate_experiment_contract')
 if(cutoff!=2011L||is.null(c)||c$version!='county_covariate_experiment_v1'||source_task$pathogen!='CAMPYLOBACTER'||source_task$temporal!='rw1'||c$pathogen!='CAMPYLOBACTER'||c$cutoff!=2011L||c$temporal!='rw1'||
    !identical(c$local_seasonality,local)||!identical(c$weather,FALSE)||!identical(c$age,FALSE)||
    c$task_id!=source_task$task_id||source_task$cutoff!=2011L||!identical(source_task$local_seasonality,local)||
    !identical(source_task$weather,FALSE)||!identical(source_task$age,FALSE))stop('Wrong reusable original fit identity')
 old<-if(local)attr(fit,'covariate_experiment_masked_data') else fit$.args$data
 k<-function(x)paste(x$fips,x$state,x$year,x$month,sep='|')
 held<-d$year>cutoff
 if(is.null(old)||!identical(k(old),k(d))||any(old$person_years!=d$person_years)||
    anyNA(old$count[!held])||any(old$count[!held]!=d$count[!held])||any(!is.na(old$count[held])))stop('Reusable fit training/masking/exposure differs from CX target')
 invisible(TRUE)
}

run_campylobacter_cx_model <- function(taskpath) {
 task<-jsonlite::read_json(taskpath,simplifyVector=TRUE)
 fields<-c('task_id','candidate','combined_candidate','audit','source_scripts','cutoff','local_seasonality','seed','output','preparation_metadata')
 if(!all(fields%in%names(task))||!task$cutoff%in%c(2011L,2013L,2016L)||!is.logical(task$local_seasonality)||length(task$local_seasonality)!=1||is.na(task$local_seasonality)||dir.exists(task$output))stop('Invalid CX model task')
 src<-task$source_scripts;frame<-sys.frame(1);had<-exists('ofile',frame,inherits=FALSE);old<-if(had)get('ofile',frame) else NULL
 assign('ofile',file.path(src,'run_county_covariate_experiment.R'),frame)
 tryCatch(source(file.path(src,'run_county_covariate_experiment.R'),local=globalenv()),finally={if(had)assign('ofile',old,frame) else rm('ofile',envir=frame)})
 reuse<-!is.null(task$reuse_fit)
 if(reuse&&is.null(task$reuse_task))stop('Missing reusable source task')
 inputs<-unique(c(if(reuse)task$reuse_fit,taskpath,task$candidate,task$combined_candidate,task$preparation_metadata,file.path(task$audit,'county_panel_INTERNAL.rds'),list.files(src,pattern='[.]R$',full.names=TRUE)))
 before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing CX fit input')
 meta<-jsonlite::read_json(task$preparation_metadata,simplifyVector=TRUE)
 if(meta$combined_candidate!=task$combined_candidate||meta$audit!=task$audit)stop('Target source identity differs')
 d<-load_monthly_comparison(task$combined_candidate,task$audit,task$cutoff,2019L)
 d<-load_cx_monthly(task$candidate,d,meta)
 dir.create(task$output,recursive=TRUE);complete<-FALSE;on.exit(if(!complete)writeLines('FAILED',file.path(task$output,'status.txt')),add=TRUE)
 warnings<-character()
 if(reuse){
  fit<-readRDS(task$reuse_fit);validate_cx_reuse_training(fit,d,task$cutoff,task$local_seasonality,task$reuse_task)
  pred<-d[d$year>task$cutoff,c('fips','state','year','month')];pred$observed<-d$count[d$year>task$cutoff]
  validate_covariate_saved(fit,pred,task$cutoff,TRUE)
 } else fit<-withCallingHandlers(fit_monthly_local_seasonality(d,task$cutoff*12+11L,seasonal=TRUE,threads=4L,
   coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002,temporal_model='rw1',
   local_seasonality=task$local_seasonality,weather=FALSE,age=FALSE),warning=function(w)warnings<<-c(warnings,conditionMessage(w)))
 writeLines(warnings,file.path(task$output,'fit_warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl('vb[.]correction.*aborted',warnings,ignore.case=TRUE)))stop('CX numerical fit gate failed')
 # Existing adapter checks structural indices, offset and held-out masking only.
 # Target provenance is separate and mandatory; these are NOT combined-incidence fits.
 contract<-list(version='county_covariate_experiment_v1',task_id=task$task_id,pathogen='CAMPYLOBACTER',cutoff=task$cutoff,
  temporal='rw1',local_seasonality=task$local_seasonality,weather=FALSE,age=FALSE,weather_window='current')
 attr(fit,'covariate_experiment_contract')<-contract
 era<-list(version='campylobacter_cx_model_v1',target='recorded_CX_positive',preparation=meta,
  cutoff=task$cutoff,local_seasonality=task$local_seasonality,source_scripts=src,models_fitted=!reuse,reused_fit=if(reuse)task$reuse_fit else NULL,
  rate_center=.0002,prior_policy='Unchanged frozen RW1/count priors; no CX-target tuning; smaller-count prior predictive behavior not independently certified',
  interpretation='Separate recorded culture-positive target, potentially including reflex confirmation; not adjusted total infection incidence')
 attr(fit,'diagnostic_era_specification')<-era
 fp<-file.path(task$output,'fit_INTERNAL.rds');saveRDS(fit,fp,version=2)
 truth<-d[d$year>task$cutoff,c('fips','state','year','month')];truth$observed<-d$count[d$year>task$cutoff]
 tp<-file.path(task$output,'truth_INTERNAL.csv');write.csv(truth,tp,row.names=FALSE)
 adapter<-function(fit,pred,cutoff,seasonal){e<-attr(fit,'diagnostic_era_specification')
  if(is.null(e)||e$target!='recorded_CX_positive'||e$cutoff!=cutoff)stop('CX fit target identity mismatch')
  validate_covariate_saved(fit,pred,cutoff,seasonal)}
 out<-file.path(task$output,'reports')
 audit_monthly_saved(fp,tp,task$cutoff,TRUE,out,task$seed,draws=1000L,adapter=adapter,rng_protocol='explicit_config_v2')
 if(!file.rename(file.path(out,'pooled_cell_scores.csv'),file.path(out,'pooled_cell_scores_INTERNAL.csv')))stop('Cannot mark internal county scores')
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 jsonlite::write_json(c(era,list(status='CX_MODEL_COMPLETE',pathogen='CAMPYLOBACTER',task_id=task$task_id,refitted=!reuse,
  streams=4L,draws_per_stream=1000L,seed=task$seed,weather=FALSE,age=FALSE,scientific_acceptance=FALSE,coverage_certified=FALSE)),file.path(out,'cx_model_metadata.json'),auto_unbox=TRUE,pretty=TRUE)
 if(!identical(before,tools::md5sum(inputs)))stop('CX fit inputs changed')
 write.csv(data.frame(file=inputs,md5=unname(before)),file.path(out,'input_checksums.csv'),row.names=FALSE)
 writeLines('CX_MODEL_COMPLETE',file.path(out,'status.txt'));writeLines('CX_MODEL_COMPLETE',file.path(task$output,'status.txt'));complete<-TRUE
}
if(sys.nframe()==0L){if(!requireNamespace('jsonlite',quietly=TRUE))stop('jsonlite required');a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage TASK_JSON');run_campylobacter_cx_model(a[1])}
