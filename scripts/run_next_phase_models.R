#!/usr/bin/env Rscript
args<-commandArgs(TRUE);kind<-args[1];here<-args[2]
source(file.path(here,'fit_county_pilot.R'));source(file.path(here,'diagnose_saved_county_pilot.R'));source(file.path(here,'county_forecast_check.R'))
if(kind=='basis') {
  out<-args[3];if(dir.exists(out))stop('Existing basis output');dir.create(out,recursive=TRUE)
  source(file.path(here,'county_spline_candidate.R'))
  for(origin in c(2011L,2013L,2016L))saveRDS(prepare_county_spline_basis(seq.int(2004L,origin+3L),origin),file.path(out,paste0('basis_',origin,'.rds')),version=2)
  writeLines('SPLINE_BATCH_BASIS_COMPLETE',file.path(out,'status.txt'))
} else if(kind=='definitions') {
  source(file.path(here,'audit_extension_definitions.R'));raw<-as.data.frame(haven::read_sas(args[3]));names(raw)<-tolower(names(raw));out<-args[4]
  if(dir.exists(out))stop('Existing definition output');dir.create(out,recursive=TRUE)
  tables<-audit_extension_definitions(raw)
  for(n in names(tables)){x<-tables[[n]];if(!ncol(x))x<-data.frame(note='No applicable source fields');write.csv(x,file.path(out,paste0(n,'.csv')),row.names=FALSE,na='')}
  writeLines('EXTENSION_DEFINITIONS_COMPLETE',file.path(out,'status.txt'))
} else if(kind=='cyclospora') {
  audit<-args[3];out<-args[4];threads<-as.integer(args[5]);if(dir.exists(out))stop('Existing diagnostic output');dir.create(out,recursive=TRUE)
  obj<-restrict_forecast_horizon(validate_panel(audit,expected_production=FALSE),2011L,3L)
  write.csv(aggregate(obj$data$count,list(state=obj$data$state,year=obj$data$year),sum),file.path(out,'state_year_counts_INTERNAL.csv'),row.names=FALSE)
  writeLines(c('Diagnostic fit of the failed candidate; no tuning or automatic adoption.',paste('threads',threads)),file.path(out,'diagnostic_specification.txt'))
  fit<-fit_county_forecast(obj,'spatial',2011L,county_time=TRUE,threads=threads,verbose=TRUE)
  saveRDS(fit,file.path(out,'diagnostic_fit_INTERNAL.rds'))
  writeLines('CYCLOSPORA_DIAGNOSTIC_COMPLETE',file.path(out,'status.txt'))
} else if(kind=='spline') {
  audit<-args[3];origin<-as.integer(args[4]);variant<-args[5];basispath<-args[6];out<-args[7]
  if(dir.exists(out))stop('Existing spline output');dir.create(out,recursive=TRUE)
  source(file.path(here,'county_spline_candidate.R'))
  obj<-restrict_forecast_horizon(validate_panel(audit,expected_production=FALSE),origin,3L)
  fit<-fit_county_spline(obj,variant,origin,basis=readRDS(basispath),threads=8L)
  saveRDS(fit,file.path(out,'fit_INTERNAL.rds'))
  # Inject the stack-aware sampler into this copy of diagnostics only.
  diagnostics<-forecast_diagnostics;e<-new.env(parent=environment(diagnostics));e$sample_county_forecast<-sample_county_spline;environment(diagnostics)<-e
  diagnostics(fit,obj$data,out,cutoff=origin,draws=4000L)
  write.csv(as.data.frame(attr(fit,'forecast_specification')),file.path(out,'spline_specification.csv'),row.names=FALSE)
  write.csv(data.frame(train_start=min(obj$data$year),train_end=origin,test_start=origin+1L,test_end=origin+3L,variant=variant,heldout_counts_masked=TRUE),file.path(out,'split.csv'),row.names=FALSE)
  write.csv(data.frame(file=c(basispath,file.path(audit,'county_panel_INTERNAL.rds')),md5=unname(tools::md5sum(c(basispath,file.path(audit,'county_panel_INTERNAL.rds'))))),file.path(out,'input_checksums.csv'),row.names=FALSE)
  writeLines(c('COUNTY_SPLINE_PILOT_COMPLETE','Experimental candidate with explicit proper slope and spline priors; not an equivalent fit of the published state model.'),file.path(out,'status.txt'))
} else stop('Unknown mode')
