#!/usr/bin/env Rscript
args<-commandArgs(TRUE);if(length(args)!=6)stop('MODE DEST CLEAN CENSUS RAW MAPPING')
here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
for(f in c('county_matching.R','audit_county_pilot.R','reconcile_raw_county.R','fit_county_pilot.R',
 'diagnose_saved_county_pilot.R','county_sensitivity.R','county_forecast_check.R'))source(file.path(here,f))
mode<-args[1];dest<-args[2];audit<-file.path(dest,'CRYPTOSPORIDIUM')
if(mode=='prepare') {
 audit_pilot(args[3],args[4],file.path(here,'geography'),file.path(audit,'reports'),'CRYPTOSPORIDIUM')
 if(readLines(file.path(audit,'reports/status.txt'))[1]!='INPUT_AUDIT_PASS')stop('Corrected audit failed')
 raw_review(args[5],args[3],args[6],audit,file.path(dest,'reconciliation'),'CRYPTOSPORIDIUM')
 if(readLines(file.path(dest,'reconciliation/status.txt'))[1]!='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH')stop('Corrected reconciliation failed')
 writeLines('CORRECTED_INPUTS_READY',file.path(dest,'preparation_status.txt'))
} else {
 if(readLines(file.path(dest,'preparation_status.txt'))[1]!='CORRECTED_INPUTS_READY')stop('Preparation incomplete')
 checks<-read.csv(file.path(dest,'reconciliation/input_checksums.csv'),stringsAsFactors=FALSE)
 h<-unname(tools::md5sum(checks$file));if(anyNA(h)||any(h!=checks$md5))stop('Reconciled inputs changed')
 d<-readRDS(file.path(audit,'county_panel_INTERNAL.rds'))
 if(nrow(d)!=6804||!setequal(d$year,2004:2017))stop('Invalid corrected window')
 name<-if(grepl('spatial',mode,fixed=TRUE))'spatial_county_time' else 'iid_county_time'
 out<-file.path(dest,mode)
 if(startsWith(mode,'full_'))run_sensitivity(audit,out,name,threads=8,expected_production=FALSE)
 else if(startsWith(mode,'forecast_'))run_forecast(audit,out,name,threads=8,cutoff=2014L,expected_production=FALSE)
 else stop('Unknown task')
}
