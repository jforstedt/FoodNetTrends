source('scripts/prepare_covariate_expansion.R')
fails<-function(expr)stopifnot(inherits(tryCatch({force(expr);NULL},error=identity),'error'))
base<-list(pathogen='CRYPTOSPORIDIUM',end_year=2017L,cutoff=2014L,temporal='ar1',
 expansion_version='county_covariate_expansion_v1',local_seasonality=TRUE,weather=TRUE,age=TRUE,weather_window='lag01')
stopifnot(isTRUE(validate_covariate_expansion_task(base)))
bad<-base;bad$cutoff<-2016L;fails(validate_covariate_expansion_task(bad))
bad<-base;bad$end_year<-2019L;fails(validate_covariate_expansion_task(bad))
bad<-base;bad$temporal<-'rw1';fails(validate_covariate_expansion_task(bad))
bad<-base;bad$weather<-FALSE;fails(validate_covariate_expansion_task(bad))
bad<-base;bad$age<-1L;fails(validate_covariate_expansion_task(bad))
bad<-base;bad$expansion_version<-NULL;fails(validate_covariate_expansion_task(bad))
for(p in c('SALMONELLA','CAMPYLOBACTER','CYCLOSPORA','LISTERIA','SHIGELLA','STEC','VIBRIO','YERSINIA')) {
 t<-base;t$pathogen<-p;t$end_year<-2019L;t$cutoff<-2016L
 t$temporal<-if(p%in%c('CAMPYLOBACTER','STEC','VIBRIO'))'rw1' else 'ar1'
 stopifnot(isTRUE(validate_covariate_expansion_task(t)))
 if(p=='YERSINIA'){t$temporal<-'rw1';stopifnot(isTRUE(validate_covariate_expansion_task(t)))}
}
# Exercise preparation deduplication and fail-closed joining without private data.
td<-tempfile();dir.create(td)
load_covariate_expansion_helpers(list(source_scripts=normalizePath('scripts')))
wrapper<-function()load_covariate_expansion_helpers(list(source_scripts=normalizePath('scripts')))
wrapper()
stopifnot(is.function(fit_monthly_local_seasonality),is.function(validate_covariate_saved))
d<-expand.grid(fips=c('00001','00002'),year=2011:2017,month=1:12,stringsAsFactors=FALSE)
d$state<-ifelse(d$fips=='00001','A','B')
f<-d[c('fips','year','month')]
for(n in c('weather_tavg_z','weather_logprcp_z','age_under5_z','age65plus_z'))f[[n]]<-seq_len(nrow(f))/100
feature<-file.path(td,'features.csv');write.csv(f,feature,row.names=FALSE)
manifest<-list(version='covariate_factorial_transform_v1',weather_window='lag01',training_cutoff_year=2014L,mode='historical_conditional',outputs=setNames(list(digest::digest(file=feature,algo='sha256')),basename(feature)))
mp<-file.path(td,'manifest.json');jsonlite::write_json(manifest,mp,auto_unbox=TRUE)
candidate<-file.path(td,'candidate.rds');saveRDS(d,candidate)
audit<-file.path(td,'audit');dir.create(audit);saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
base$candidate<-candidate;base$audit<-audit;base$source_scripts<-normalizePath('scripts');base$weather_features<-feature;base$weather_manifest<-mp
calls<-0L
load_covariate_expansion_helpers<-function(task)invisible(TRUE)
load_monthly_comparison<-function(candidate,audit,cutoff,end_year){calls<<-calls+1L;d}
tp<-file.path(td,'tasks.json');jsonlite::write_json(list(tasks=list(base,base)),tp,auto_unbox=TRUE)
report<-file.path(td,'report.json');prepare_covariate_expansion(tp,report)
r<-jsonlite::read_json(report,simplifyVector=TRUE)
stopifnot(calls==1L,r$status=='COVARIATE_EXPANSION_INPUT_PASS',r$end_year==2017L,r$tasks==2L,length(r$checks)==1L)
fails(prepare_covariate_expansion(tp,report))
write.csv(f[-1,],feature,row.names=FALSE)
fails(prepare_covariate_expansion(tp,file.path(td,'changed.json')))
manifest$outputs[[basename(feature)]]<-digest::digest(file=feature,algo='sha256');jsonlite::write_json(manifest,mp,auto_unbox=TRUE)
fails(prepare_covariate_expansion(tp,file.path(td,'missing.json')))
cat('COVARIATE EXPANSION DOMAIN/PREFLIGHT PASS\n')
if('--inla'%in%commandArgs(TRUE)) {
 source('scripts/run_covariate_expansion.R')
 source('scripts/check_county_covariate_priors.R')
 prior<-file.path(td,'prior.json');check_county_covariate_priors(prior)
 # Inject only the data-loading boundary; execute actual NB fitting and scoring.
 load_covariate_expansion_helpers<-function(task)invisible(TRUE)
 d$area<-d$fips;d$person_years<-20000;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 set.seed(9881);d$count<-rnbinom(nrow(d),mu=40,size=20)
 load_monthly_comparison<-function(candidate,audit,cutoff,end_year){stopifnot(cutoff==2014L,end_year==2017L);d}
 write.csv(f,feature,row.names=FALSE)
 manifest$outputs[[basename(feature)]]<-digest::digest(file=feature,algo='sha256');jsonlite::write_json(manifest,mp,auto_unbox=TRUE)
 base$task_id<-'synthetic_crypto_expansion';base$output<-file.path(td,'fit');base$seed<-551331L
 base$threads<-2L;base$draws_per_stream<-1000L;base$prior_check<-prior
 jsonlite::write_json(base,tp,auto_unbox=TRUE)
 run_covariate_expansion(tp)
 reports<-file.path(base$output,'reports')
 settings<-jsonlite::read_json(file.path(reports,'experiment_settings.json'),simplifyVector=TRUE)
 stopifnot(settings$end_year==2017L,settings$cutoff==2014L,settings$expansion_version=='county_covariate_expansion_v1',
  file.exists(file.path(reports,'pooled_cell_scores_INTERNAL.csv')))
 scores<-read.csv(file.path(reports,'stream_scores.csv'))
 stopifnot(setequal(scores$stream,0:4),all(is.finite(scores$mean_log_score)),all(scores$draws[scores$stream==0]==4000L))
 cat('CRYPTO 2014 EXPANSION ACTUAL FIT AND FOUR STREAMS PASS\n')
}
unlink(td,recursive=TRUE)
