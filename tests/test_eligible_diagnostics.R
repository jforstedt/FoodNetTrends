source('scripts/county_matching.R');source('scripts/audit_eligible_diagnostics.R')
p<-data.frame(state=c('AA','AA','AA'),fips=c('01001','01001','01001'),year=2015:2017,population=1000,count=c(2,1,0))
d<-data.frame(state='AA',fips='01001',year=c(2015,2015,2016),county='TEST',pathogen='LISTERIA',travelint='NO',cxcidt=c('CX+','CIDT+','CX+'),cste='YES')
x<-eligible_category_tables(d,p,'LISTERIA');stopifnot(sum(x$categories$records)==3,x$support$cidt_classification_share[1]==.5,is.na(x$support$cidt_classification_share[3]))
bad<-d;bad$cste[1]<-'NO';stopifnot(inherits(try(eligible_category_tables(bad,p,'LISTERIA'),silent=TRUE),'try-error'))
bad<-d;bad$fips[1]<-'01003';stopifnot(inherits(try(eligible_category_tables(bad,p,'LISTERIA'),silent=TRUE),'try-error'))
d$pathogen<-'CRYPTOSPORIDIUM';d$cxcidt<-'PARASITIC';extra<-d[1,];extra$year<-2018
x<-eligible_category_tables(rbind(d,extra),p,'CRYPTOSPORIDIUM');stopifnot(sum(x$categories$records)==3,all(x$support$classification_denominator==0),all(is.na(x$support$cidt_classification_share)))
p$count[1]<-3;stopifnot(inherits(try(eligible_category_tables(d,p,'CRYPTOSPORIDIUM'),silent=TRUE),'try-error'))
cat('Eligible category reconciliation, CSTE, Crypto cutoff and missing-share tests PASS\n')
# Exercise actual CSV ingestion and the production report writer on a synthetic full domain.
work<-tempfile();dir.create(work);audit<-file.path(work,'audit');dir.create(audit);dir.create(file.path(audit,'reports'))
panel<-expand.grid(fips=sprintf('%05d',1001:1486),year=2004:2017,stringsAsFactors=FALSE);panel$state<-'AA';panel$population<-10000;panel$count<-1L
validate_panel<-function(...)list(data=panel)
clean<-panel[c('fips','state','year')];clean$county<-'TEST';clean$pathogen<-'CRYPTOSPORIDIUM';clean$travelint<-'NO';clean$cxcidt<-'PARASITIC'
cp<-file.path(work,'clean.csv');write.csv(clean,cp,row.names=FALSE);saveRDS(panel,file.path(audit,'county_panel_INTERNAL.rds'))
write.csv(data.frame(file=cp,md5=unname(tools::md5sum(cp))),file.path(audit,'reports/input_checksums.csv'),row.names=FALSE)
out<-file.path(work,'result');run_audit(cp,audit,out,'CRYPTOSPORIDIUM')
stopifnot(readLines(file.path(out,'status.txt'))=='ELIGIBLE_DIAGNOSTICS_COMPLETE',sum(read.csv(file.path(out,'categories.csv'))$records)==6804)
cat('Actual eligible CSV/report integration PASS\n')
