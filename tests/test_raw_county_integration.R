source('scripts/county_matching.R');source('scripts/reconcile_raw_county.R')
b<-tempfile();dir.create(b);audit<-file.path(b,'audit');dir.create(file.path(audit,'reports'),recursive=TRUE)
nodes<-read.csv('analysis_configs/county_pilot/counties.csv',colClasses='character')
p<-merge(nodes,data.frame(year=2004:2019),by=NULL);p$count<-15L;p$count[seq_len(5384)]<-16L
saveRDS(p,file.path(audit,'county_panel_INTERNAL.rds'));write.csv(nodes,file.path(audit,'reports/graph_nodes.csv'),row.names=FALSE)
x<-p[rep(seq_len(nrow(p)),p$count),c('year','state','county','fips')];x$pathogen<-'SALMONELLA';x$travelint<-'NO';x$cxcidt<-'CX+';x$siteid<-x$state
clean<-file.path(b,'clean.csv');write.csv(x,clean,row.names=FALSE)
write.csv(data.frame(file=clean,md5=unname(tools::md5sum(clean))),file.path(audit,'reports/input_checksums.csv'),row.names=FALSE)
report<-file.path(b,'mapping.csv');write.csv(data.frame(original='SALMONELLA',standardized='SALMONELLA'),report,row.names=FALSE)
extra<-x[1:3,];extra$county<-c('UNKNOWN','OUT OF STATE','VALID');extra$siteid[3]<-'COEX'
raw<-file.path(b,'raw.sas7bdat');haven::write_sas(rbind(x,extra),raw)
out<-file.path(b,'reports');raw_review(raw,clean,report,audit,out)
s<-read.csv(file.path(out,'summary.csv'));stopifnot(s$raw_mapped_records==122027,s$clean_records==122024,s$unexplained_cells==0)
stopifnot(readLines(file.path(out,'status.txt'))[1]=='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH')
cat('PASS full SAS-to-CSV reconciliation with 3 known exclusions and 7776 panel cells\n')
unlink(b,recursive=TRUE)
