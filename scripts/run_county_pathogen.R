#!/usr/bin/env Rscript
# One array task. Reconciliation and fit run in their respective existing images.
a<-commandArgs(TRUE)
here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
for(f in c('county_matching.R','reconcile_raw_county.R','fit_county_pilot.R',
 'diagnose_saved_county_pilot.R','county_sensitivity.R'))source(file.path(here,f))
if(length(a)<4)stop('Expected mode, pathogen, audit, output, mode arguments')
mode<-a[1];pathogen<-a[2];audit<-a[3];out<-a[4]
if(!pathogen%in%c('CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA','SHIGELLA','STEC','VIBRIO','YERSINIA'))stop('Unsupported new pathogen')
if(readLines(file.path(audit,'status.txt'))[1]!='INPUT_AUDIT_PASS')stop('Pathogen rule audit did not pass')
if(mode=='reconcile' && length(a)==7) {
 raw_review(a[5],a[6],a[7],audit,out,pathogen)
 if(readLines(file.path(out,'status.txt'))[1]!='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH')stop('Reconciliation requires review')
} else if(mode=='fit' && length(a)==6) {
 reconciliation<-a[5];name<-a[6]
 if(!name%in%c('spatial_county_time','iid_county_time'))stop('Unexpected model')
 if(readLines(file.path(reconciliation,'status.txt'))[1]!='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH')stop('Reconciliation has not passed')
 checks<-read.csv(file.path(reconciliation,'input_checksums.csv'),stringsAsFactors=FALSE)
 if(anyNA(tools::md5sum(checks$file))||any(unname(tools::md5sum(checks$file))!=checks$md5))stop('Reconciled inputs changed')
 d<-readRDS(file.path(audit,'county_panel_INTERNAL.rds'))
 if(nrow(d)!=7776||length(unique(d$fips))!=486||!setequal(d$year,2004:2019)||sum(d$count)<=0)stop('Unexpected extension scope')
 run_sensitivity(audit,out,name,threads=8L,draws=2000L,expected_production=FALSE)
} else stop('Invalid task arguments')
