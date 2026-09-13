#!/usr/bin/env Rscript
# Recompute tables from an existing posterior in a new destination; never sample.
reexport_saved_state_tables <- function(source_results,dest_results,key) {
  if(length(key)!=1L || !grepl('^[A-Za-z0-9_-]+$',key))stop('Invalid analysis key')
  if(dir.exists(dest_results))stop('Use a new destination; original outputs are preserved')
  source_results<-normalizePath(source_results,mustWork=TRUE)
  oldfit<-file.path(source_results,paste0(key,'_brm.Rds'))
  before<-digest::digest(file=oldfit,algo='sha256')
  model<-readRDS(oldfit)
  if(!inherits(model,'brmsfit'))stop('Expected saved brms posterior')
  settings<-read.csv(file.path(source_results,paste0(key,'_analysis_settings.csv')),stringsAsFactors=FALSE)
  if(nrow(settings)!=1L)stop('Expected one settings row')
  bs<-settings$baseline_start;be<-settings$baseline_end
  if(length(bs)!=1L||length(be)!=1L||any(!is.finite(c(bs,be)))||any(c(bs,be)!=floor(c(bs,be)))||bs>be)
    stop('Invalid baseline settings')
  required<-paste0(key,c('_analysis_settings.csv','_population_used.csv','_classification_rules.csv'))
  if(any(!file.exists(file.path(source_results,required))))stop('Required source metadata missing')
  dir.create(dest_results,recursive=TRUE)
  for(name in required)if(!file.copy(file.path(source_results,name),file.path(dest_results,name)))stop('Cannot copy metadata')
  targetfit<-file.path(dest_results,paste0(key,'_brm.Rds'))
  if(!file.copy(oldfit,targetfit))stop('Cannot preserve saved posterior')
  set.seed(123)
  draws<-LINPREAD_DRAW_FN(model$data,model);catch<-CATCHMENT(draws)
  site<-LINPRED_TO_SITEIR(draws);overall<-LINPRED_TO_CATCHIR(catch)
  for(pair in list(list(value=site,suffix='_IRSite.csv'),list(value=overall,suffix='_IRCatch.csv'))) {
    value<-pair$value;original<-read.csv(file.path(source_results,paste0(key,pair$suffix)),stringsAsFactors=FALSE)
    join<-intersect(c('year','state'),names(value));k<-function(d)do.call(paste,c(d[join],sep='|'))
    if(anyDuplicated(k(original))||anyDuplicated(k(value))||!setequal(k(original),k(value)))stop('Source/export keys differ')
    for(label in intersect(c('pathogen','travel','culture'),names(original)))value[[label]]<-original[[label]][match(k(value),k(original))]
    write.csv(value,file.path(dest_results,paste0(key,pair$suffix)),row.names=FALSE)
  }
  IR_COMP_CATCH(catch,bs,be,file.path(dest_results,paste0(key,'_EstIRRCatch_',bs,'_',be,'.csv')))
  CHECK_CONVERGENCE(model,key,dest_results)
  if(!identical(before,digest::digest(file=oldfit,algo='sha256'))||
     !identical(before,digest::digest(file=targetfit,algo='sha256')))stop('Source/checkpoint identity changed')
  WRITE_STATE_EXPORT_MANIFEST(targetfit,dest_results,key,bs,be)
  cat('SAVED POSTERIOR RE-EXPORTED: no sampling; independent saved-fit review still required.\n')
}
if(sys.nframe()==0L){
  a<-commandArgs(TRUE);if(length(a)!=3L)stop('Usage: SOURCE_RESULTS NEW_DEST_RESULTS KEY')
  here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
  source(file.path(dirname(here),'bin','functions.R'))
  reexport_saved_state_tables(a[1],a[2],a[3])
}
