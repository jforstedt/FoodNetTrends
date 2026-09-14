#!/usr/bin/env Rscript
# Deterministic, data-free basis export. Run locally with mgcv, not on the cluster.
source('scripts/county_spline_candidate.R')
source('scripts/monthly_spline_combination.R')
args<-commandArgs(TRUE)
if(length(args)!=1L||dir.exists(args[1]))stop('Supply a new basis directory')
dir.create(args[1],recursive=TRUE)
for(cutoff in c(2011L,2013L,2014L,2016L)) {
 serial<-seq(2004L*12L,(cutoff+3L)*12L+11L)
 b<-monthly_combination_basis(serial,cutoff*12L+11L)
 validate_monthly_combination_basis(b,serial,cutoff*12L+11L)
 write.csv(data.frame(serial=b$years,slope=b$slope,b$nonlinear),file.path(args[1],paste0(cutoff,'.csv')),row.names=FALSE)
}
writeLines(trimws(capture.output(sessionInfo()),which="right"),file.path(args[1],'generation_session.txt'))
