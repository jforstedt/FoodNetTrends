source('scripts/rescore_covariate_expansion.R')
fails<-function(expr)stopifnot(inherits(tryCatch({force(expr);NULL},error=identity),'error'))
for(seed in c(1,1000000000))stopifnot(isTRUE(validate_covariate_recovery_seed(seed)))
for(seed in list(0,-1,1000000001,1001000000,NA_real_,Inf,1.5,NULL))fails(validate_covariate_recovery_seed(seed))
source('scripts/run_covariate_expansion.R')
tp<-tempfile(fileext='.json');jsonlite::write_json(list(seed=1001000000),tp,auto_unbox=TRUE)
# This must fail on the seed before trying to load missing task inputs or fit.
e<-tryCatch(run_covariate_expansion(tp),error=identity)
stopifnot(inherits(e,'error'),grepl('before fitting',conditionMessage(e),fixed=TRUE));unlink(tp)
cat('COVARIATE SEED BOUNDARY EARLY GUARD PASS\n')
if('--inla'%in%commandArgs(TRUE)) {
 load_covariate_expansion_helpers(list(source_scripts=normalizePath('scripts')))
 source('scripts/check_county_covariate_priors.R')
 td<-tempfile();dir.create(td);prior<-file.path(td,'prior.json');check_county_covariate_priors(prior)
 d<-expand.grid(month=1:12,year=2010:2014,fips=c('00001','00002'),stringsAsFactors=FALSE)
 d$state<-ifelse(d$fips=='00001','A','B');d$area<-d$fips;d$person_years<-20000
 d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 set.seed(1291);d$count<-rnbinom(nrow(d),mu=40,size=20)
 for(n in c('weather_tavg_z','weather_logprcp_z','age_under5_z','age65plus_z'))d[[n]]<-rnorm(nrow(d))
 feature<-file.path(td,'features.csv');write.csv(d[c('fips','year','month','weather_tavg_z','weather_logprcp_z','age_under5_z','age65plus_z')],feature,row.names=FALSE)
 # Round-trip exactly as the real worker does before saving its masked data.
 f<-read.csv(feature,colClasses=c(fips='character'))
 for(n in names(f))d[[n]]<-f[[n]]
 manifest<-list(version='covariate_factorial_transform_v1',weather_window='lag01',training_cutoff_year=2011L,mode='historical_conditional',outputs=setNames(list(digest::digest(file=feature,algo='sha256')),basename(feature)))
 mp<-file.path(td,'manifest.json');jsonlite::write_json(manifest,mp,auto_unbox=TRUE)
 candidate<-file.path(td,'candidate.rds');saveRDS(d,candidate);audit<-file.path(td,'audit');dir.create(audit);saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
 original<-file.path(td,'original');dir.create(original)
 task<-list(task_id='synthetic_recovery',pathogen='SALMONELLA',end_year=2019L,cutoff=2011L,temporal='ar1',expansion_version='county_covariate_expansion_v1',local_seasonality=TRUE,weather=TRUE,age=TRUE,weather_window='lag01',candidate=candidate,audit=audit,source_scripts=normalizePath('scripts'),weather_features=feature,weather_manifest=mp,prior_check=prior,seed=1001000000,threads=2L,output=original)
 fit<-fit_monthly_local_seasonality(d,2011*12+11L,temporal_model='ar1',local_seasonality=TRUE,weather=TRUE,age=TRUE,rate_center=.0002,threads=2L,coverage='EXPLORATORY_ASSUMED_CONTINUOUS')
 contract<-c(list(version='county_covariate_experiment_v1'),task[c('task_id','pathogen','cutoff','temporal','local_seasonality','weather','age','weather_window','expansion_version','end_year')],list(target='reported county incidence',weather_mode='historical_conditional',coverage_certified=FALSE))
 attr(fit,'covariate_experiment_contract')<-contract
 fp<-file.path(original,'fit_INTERNAL.rds');saveRDS(fit,fp)
 pred<-d[d$year>2011,c('fips','state','year','month')];pred$observed<-d$count[d$year>2011]
 truth<-file.path(original,'heldout_truth_INTERNAL.csv');write.csv(pred,truth,row.names=FALSE);writeLines(character(),file.path(original,'fit_warnings.txt'))
 # Reproduce the observed old failure after checkpointing, before sampling.
 fails(audit_monthly_saved(fp,truth,2011L,TRUE,file.path(original,'reports'),1001000000,draws=1000L,adapter=validate_covariate_saved,rng_protocol='explicit_config_v2'))
 stopifnot(grepl('Invalid sampling settings',readLines(file.path(original,'reports/status.txt'))[2],fixed=TRUE))
 validate_covariate_recovery_fit(fit,pred,task,d)
 bad<-pred;bad$observed[1]<-bad$observed[1]+1;fails(validate_covariate_recovery_fit(fit,bad,task,d))
 bad<-d;bad$person_years[1]<-bad$person_years[1]+1;fails(validate_covariate_recovery_fit(fit,pred,task,bad))
 badfit<-fit;attr(badfit,'covariate_experiment_contract')$pathogen<-'CAMPYLOBACTER';fails(validate_covariate_recovery_fit(badfit,pred,task,d))
 taskfile<-file.path(td,'source_task.json');jsonlite::write_json(task,taskfile,auto_unbox=TRUE)
 rec<-list(source_task=taskfile,fit=fp,truth=truth,seed=201000000,output=file.path(td,'recovered'),source_scripts=task$source_scripts)
 recfile<-file.path(td,'recovery.json');jsonlite::write_json(rec,recfile,auto_unbox=TRUE)
 load_covariate_expansion_helpers<-function(task)invisible(TRUE)
 load_monthly_comparison<-function(candidate,audit,cutoff,end_year)d
 before<-tools::md5sum(c(fp,truth))
 rescore_covariate_expansion(recfile)
 stopifnot(identical(before,tools::md5sum(c(fp,truth))),!file.exists(file.path(rec$output,'fit_INTERNAL.rds')),
  identical(unname(tools::md5sum(truth)),unname(tools::md5sum(file.path(rec$output,'heldout_truth_INTERNAL.csv')))))
 reports<-file.path(rec$output,'reports');settings<-jsonlite::read_json(file.path(reports,'experiment_settings.json'))
 stopifnot(!settings$new_fit,settings$seed==rec$seed,settings$original_seed==task$seed)
 scores<-read.csv(file.path(reports,'stream_scores.csv'));stopifnot(setequal(scores$stream,0:4),all(is.finite(scores$mean_log_score)))
 fails(rescore_covariate_expansion(recfile))
 unlink(td,recursive=TRUE)
 cat('POST-CHECKPOINT SEED FAILURE RECOVERY FOUR STREAMS PASS\n')
}
