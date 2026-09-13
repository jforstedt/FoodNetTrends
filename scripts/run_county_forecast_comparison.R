#!/usr/bin/env Rscript
args<-commandArgs(TRUE)
if(length(args)!=7L)stop('AUDIT RECONCILIATION DEST MODEL THREADS ORIGIN HORIZON')
here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
for(n in c('fit_county_pilot.R','diagnose_saved_county_pilot.R','county_sensitivity.R',
 'county_forecast_model.R','county_forecast_check.R','county_forecast_historical_reference.R'))source(file.path(here,n))
audit<-args[1];reconciliation<-args[2];dest<-args[3];model<-args[4]
threads<-as.integer(args[5]);origin<-as.integer(args[6]);horizon<-as.integer(args[7])
if(readLines(file.path(reconciliation,'status.txt'))[1]!='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH')stop('Raw reconciliation not passed')
checks<-read.csv(file.path(reconciliation,'input_checksums.csv'),stringsAsFactors=FALSE)
if(anyNA(tools::md5sum(checks$file))||any(unname(tools::md5sum(checks$file))!=checks$md5))stop('Reconciled inputs changed')
run_forecast(audit,dest,model,threads=threads,draws=4000L,cutoff=origin,expected_production=FALSE,horizon=horizon)
d<-readRDS(file.path(audit,'county_panel_INTERNAL.rds'));d<-d[d$year<=origin+horizon,]
county_historical_reference(d,origin,file.path(dest,'reports'))
cat('Paired forecast and historical reference complete; scientific review pending.\n')
