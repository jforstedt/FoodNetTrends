source('scripts/fit_county_pilot.R');source('scripts/diagnose_saved_county_pilot.R');source('scripts/county_sensitivity.R')
a<-commandArgs(TRUE);if(length(a)!=1)stop('Supply saved synthetic fit directory')
b<-tempfile();dir.create(b);audit<-file.path(b,'audit');dir.create(audit)
d<-expand.grid(time=1:6,area=1:16);d$fips<-sprintf('%05d',d$area);d$year<-2003L+d$time;d$state<-ifelse(d$area<=8,'AA','BB');d$population<-10000+d$area*500
saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'));md5<-unname(tools::md5sum(file.path(audit,'county_panel_INTERNAL.rds')))
# Isolate the collector from production-size audit validation; no fitting calls.
validate_panel<-function(audit)list(data=d)
baseline<-file.path(b,'baseline');diag<-file.path(b,'diagnostics');dest<-file.path(b,'run');dir.create(dest);dir.create(file.path(diag,'reports'),recursive=TRUE)
checks<-data.frame(file=character(),md5=character())
for(v in c('spatial','iid')) {
 r<-file.path(baseline,v,'reports');dir.create(r,recursive=TRUE);write.csv(data.frame(md5=md5),file.path(r,'panel_checksum.csv'),row.names=FALSE)
 path<-file.path(baseline,v,'fit_INTERNAL.rds');file.copy(file.path(a[1],v,'fit_INTERNAL.rds'),path)
 checks<-rbind(checks,data.frame(file=path,md5=unname(tools::md5sum(path))))
 r<-file.path(diag,'reports',v);dir.create(r)
 for(n in c('zero_checks_INTERNAL.csv','zero_checks.pdf','model_diagnostics.csv'))writeLines('collector fixture',file.path(r,n))
 for(suffix in c('county_sd2','county_time')) {
  rr<-file.path(dest,paste(v,suffix,sep='_'),'reports');dir.create(rr,recursive=TRUE)
  writeLines('SENSITIVITY_FIT_COMPLETE',file.path(rr,'status.txt'));write.csv(data.frame(md5=md5),file.path(rr,'panel_checksum.csv'),row.names=FALSE)
  file.copy(path,file.path(dirname(rr),'fit_INTERNAL.rds'))
 }
}
write.csv(checks,file.path(diag,'reports/input_checksums.csv'),row.names=FALSE)
compare_sensitivities(audit,baseline,diag,dest)
z<-read.csv(file.path(dest,'comparison/paired_comparison.csv'));stopifnot(nrow(z)==4,all(z$waic_gain==0),all(z$naive_paired_se==0))
cat('PASS collector baseline checksums, reused reports and paired zero differences\n');unlink(b,recursive=TRUE)
