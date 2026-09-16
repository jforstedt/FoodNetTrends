#!/usr/bin/env Rscript
# Validate previously reconciled monthly inventories; no raw records are reread.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
load_covariate_expansion_helpers <- function(task) {
 if(!is.character(task$source_scripts)||length(task$source_scripts)!=1L||!dir.exists(task$source_scripts))stop('Missing frozen source scripts')
 path<-file.path(task$source_scripts,'run_county_covariate_experiment.R')
 # Frozen helpers locate sibling scripts through sys.frame(1)$ofile. When
 # sourced from a function, expose that same source location for the duration
 # of loading, then restore the caller frame exactly.
 frame<-sys.frame(1);had<-exists('ofile',envir=frame,inherits=FALSE)
 if(had)previous<-get('ofile',envir=frame,inherits=FALSE)
 assign('ofile',path,envir=frame)
 on.exit(if(had)assign('ofile',previous,envir=frame) else rm('ofile',envir=frame),add=TRUE)
 source(path,local=.GlobalEnv)
}

validate_covariate_expansion_task <- function(task) {
 pathogens<-c('SALMONELLA','CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA','SHIGELLA','STEC','VIBRIO','YERSINIA')
 scalar_integer<-function(x) is.numeric(x)&&length(x)==1L&&!is.na(x)&&is.finite(x)&&x==floor(x)
 if(!is.character(task$pathogen)||length(task$pathogen)!=1L||is.na(task$pathogen)||!task$pathogen%in%pathogens)stop('Unsupported expansion pathogen')
 if(!identical(task$expansion_version,'county_covariate_expansion_v1'))stop('Wrong expansion contract')
 end<-if(task$pathogen=='CRYPTOSPORIDIUM')2017L else 2019L
 cutoffs<-if(end==2017L)c(2011L,2013L,2014L) else c(2011L,2013L,2016L)
 if(!scalar_integer(task$end_year)||task$end_year!=end||!scalar_integer(task$cutoff)||!task$cutoff%in%cutoffs||task$cutoff+3L>end)stop('Pathogen surveillance/evaluation window differs')
 if(!is.character(task$temporal)||length(task$temporal)!=1L||is.na(task$temporal)||!task$temporal%in%c('rw1','ar1'))stop('Unsupported temporal model')
 allowed<-switch(task$pathogen,SALMONELLA='ar1',CAMPYLOBACTER='rw1',CRYPTOSPORIDIUM='ar1',SHIGELLA='ar1',LISTERIA='ar1',CYCLOSPORA='ar1',STEC='rw1',VIBRIO='rw1',YERSINIA=c('rw1','ar1'))
 if(!task$temporal%in%allowed)stop('Temporal model outside frozen pathogen comparison')
 for(n in c('local_seasonality','weather','age'))if(!is.logical(task[[n]])||length(task[[n]])!=1L||is.na(task[[n]]))stop('Invalid expansion arm flag')
 if(!is.character(task$weather_window)||length(task$weather_window)!=1L||is.na(task$weather_window)||!task$weather_window%in%c('current','lag01'))stop('Unknown weather window')
 # Weather-off arms have exactly one representation, preventing duplicate fits.
 if(!task$weather&&task$weather_window!='current')stop('Weather-off control must use current-window manifest')
 invisible(TRUE)
}

prepare_covariate_expansion <- function(taskpath,reportpath) {
 obj<-jsonlite::read_json(taskpath,simplifyVector=FALSE)
 tasks<-if(!is.null(obj$tasks))obj$tasks else if(!is.null(obj$pathogen))list(obj) else obj
 if(!is.list(tasks)||!length(tasks))stop('Empty preparation task list')
 invisible(lapply(tasks,validate_covariate_expansion_task))
 task<-tasks[[1L]]
 shared<-c('pathogen','end_year','candidate','audit','source_scripts')
 for(t in tasks)for(n in shared)if(!identical(t[[n]],task[[n]]))stop('Mixed pathogen/input preparation task list')
 load_covariate_expansion_helpers(task)
 inputs<-unique(c(taskpath,task$candidate,file.path(task$audit,'county_panel_INTERNAL.rds'),
   unlist(lapply(tasks,function(t)c(t$weather_features,t$weather_manifest)),use.names=FALSE)))
 before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing expansion input')
 datasets<-list();seen<-list();checks<-list()
 for(t in tasks) {
  k<-paste(t$cutoff,t$weather_window,sep='|');paths<-c(t$weather_features,t$weather_manifest)
  if(!is.null(seen[[k]])) {
   if(!identical(seen[[k]],paths))stop('Transform differs between paired arms')
   next
  }
  seen[[k]]<-paths;yr<-as.character(t$cutoff)
  if(is.null(datasets[[yr]]))datasets[[yr]]<-load_monthly_comparison(t$candidate,t$audit,t$cutoff,t$end_year)
  manifest<-jsonlite::read_json(t$weather_manifest,simplifyVector=TRUE)
  if(manifest$version!='covariate_factorial_transform_v1'||manifest$weather_window!=t$weather_window)stop('Wrong factorial transform')
  expected<-manifest$outputs[[basename(t$weather_features)]]
  if(is.null(expected)||digest::digest(file=t$weather_features,algo='sha256')!=expected)stop('Public transform hash differs')
  d<-covariate_experiment_data(datasets[[yr]],read.csv(t$weather_features,colClasses=c(fips='character')),manifest,t$cutoff)
  checks[[k]]<-list(cutoff=t$cutoff,weather_window=t$weather_window,rows=nrow(d),training_rows=sum(d$year<=t$cutoff),heldout_rows=sum(d$year>t$cutoff))
 }
 if(!identical(before,tools::md5sum(inputs)))stop('Expansion input changed during validation')
 if(file.exists(reportpath))stop('Refusing existing preparation report')
 jsonlite::write_json(list(status='COVARIATE_EXPANSION_INPUT_PASS',pathogen=task$pathogen,
   cutoffs=sort(unique(vapply(tasks,function(t)t$cutoff,numeric(1)))),end_year=task$end_year,
   tasks=length(tasks),checks=checks,
   interpretation='Exploratory historical conditional comparison; annual/within-year coverage is not externally certified',
   coverage_certified=FALSE,prospective_validation=FALSE,scientific_acceptance=FALSE,
   input_md5=as.list(setNames(unname(before),inputs))),reportpath,auto_unbox=TRUE,pretty=TRUE)
 invisible(checks)
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=2L)stop('Usage TASK_LIST_JSON REPORT_JSON');prepare_covariate_expansion(a[1],a[2])}
