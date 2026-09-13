#!/usr/bin/env Rscript
# Read-only extension data audit. Never modifies eligibility or fits a model.
a<-commandArgs(TRUE);if(length(a)!=9L)stop('Expected kind, raw, censusB, censusP, clean, audit, pathogen, output, scripts')
kind<-a[1];out<-a[8];here<-a[9]
if(dir.exists(out))stop('Existing output directory')
dir.create(out,recursive=TRUE)
tryCatch({
  read_sas<-function(path) {
    x<-as.data.frame(haven::read_sas(path));names(x)<-tolower(names(x))
    if(anyDuplicated(names(x)))stop('Duplicate normalized source fields')
    x
  }
  if(kind=='diagnostics') {
    source(file.path(here,'audit_extension_diagnostics.R'))
    raw<-read_sas(a[2])
    clean<-readr::read_csv(a[5],col_types=readr::cols(.default=readr::col_character()),
      col_select=tidyselect::any_of(c('year','state','siteid','pathogen','cxcidt')),show_col_types=FALSE)
    if(nrow(readr::problems(clean)))stop('Parsing errors in selected clean fields')
    reports<-audit_extension_diagnostics(raw,as.data.frame(clean))
  } else if(kind=='seasonality') {
    source(file.path(here,'audit_extension_seasonality.R'))
    reports<-audit_extension_seasonality(read_sas(a[2]),read_sas(a[3]),read_sas(a[4]))
  } else if(kind=='counts') {
    source(file.path(here,'fit_county_pilot.R'));source(file.path(here,'audit_extension_count_models.R'))
    obj<-validate_panel(a[6],expected_production=FALSE)
    reports<-audit_extension_count_models(obj,a[7])
  } else stop('Unknown audit kind')
  if(!length(reports)||is.null(names(reports))||anyDuplicated(names(reports)))stop('Invalid report collection')
  manifest<-list()
  for(name in names(reports)) {
    if(!grepl('^[A-Za-z0-9_]+$',name)||!is.data.frame(reports[[name]]))stop('Invalid report table')
    x<-reports[[name]];rows<-nrow(x);cols<-ncol(x)
    if(!cols)x<-data.frame(note='No applicable source fields or records; no observations inferred.')
    path<-file.path(out,paste0(name,'.csv'));write.csv(x,path,row.names=FALSE,na='')
    manifest[[name]]<-data.frame(file=basename(path),source_rows=rows,source_columns=cols,md5=unname(tools::md5sum(path)))
  }
  write.csv(do.call(rbind,manifest),file.path(out,'report_manifest.csv'),row.names=FALSE)
  writeLines(c('EXTENSION_DATA_AUDIT_COMPLETE','Descriptive input audit only. Scientific readiness requires review; no model fitted.'),file.path(out,'status.txt'))
  writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt'))
},error=function(e){writeLines(c('FAILED',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
