source('scripts/county_matching.R');source('scripts/review_county_histories.R')
b<-tempfile();dir.create(b);a<-file.path(b,'audit');dir.create(file.path(a,'reports'),recursive=TRUE)
n<-read.csv('analysis_configs/county_pilot/counties.csv',colClasses='character')
p<-merge(n,data.frame(year=2004:2019),by=NULL);p$count<-15L;p$count[seq_len(5384)]<-16L;p$population<-10000
saveRDS(p,file.path(a,'county_panel_INTERNAL.rds'));writeLines('INPUT_AUDIT_PASS',file.path(a,'reports/status.txt'))
write.csv(n,file.path(a,'reports/graph_nodes.csv'),row.names=FALSE);file.copy('analysis_configs/county_pilot/edges.csv',file.path(a,'reports/graph_edges.csv'))
x<-p[rep(seq_len(nrow(p)),p$count),c('year','state','county','fips')];x$pathogen<-'SALMONELLA';x$travelint<-'NO';x$cxcidt<-'CX+'
clean<-file.path(b,'clean.csv');write.csv(x,clean,row.names=FALSE)
write.csv(data.frame(file=clean,md5=unname(tools::md5sum(clean))),file.path(a,'reports/input_checksums.csv'),row.names=FALSE)
f<-file.path(b,'fits')
for(v in c('spatial','iid')){d<-file.path(f,v,'reports');dir.create(d,recursive=TRUE);writeLines('EXPLORATORY_FIT_COMPLETE',file.path(d,'status.txt'));write.csv(data.frame(md5=unname(tools::md5sum(file.path(a,'county_panel_INTERNAL.rds')))),file.path(d,'panel_checksum.csv'),row.names=FALSE);r<-p[c('fips','year')];r$mean<-r$median<-150;r$lower<-100;r$upper<-200;write.csv(r,file.path(d,'county_incidence_INTERNAL.csv'),row.names=FALSE)}
out<-file.path(b,'review');review_histories(a,f,clean,out)
stopifnot(readLines(file.path(out,'status.txt'))[1]=='COUNTY_HISTORY_REVIEW_COMPLETE',nrow(read.csv(file.path(out,'target_summary_INTERNAL.csv')))==15)
cat('PASS end-to-end 7776-cell synthetic history review, clean-file reconstruction and plots\n');unlink(b,recursive=TRUE)
