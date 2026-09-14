source('scripts/prepare_monthly_county.R');source('scripts/county_matching.R');source('scripts/reconcile_raw_county.R')
work<-tempfile();dir.create(work)
for(pathogen in c('LISTERIA','CRYPTOSPORIDIUM')) {
 end<-if(pathogen=='CRYPTOSPORIDIUM')2017L else 2019L
 panel<-expand.grid(fips=sprintf('%05d',1001:1486),year=2004:end,stringsAsFactors=FALSE);panel$state<-'AA';panel$population<-10000;panel$count<-1L
 validate_panel<-function(...)list(data=panel)
 audit<-file.path(work,pathogen);dir.create(audit);dir.create(file.path(audit,'reports'));saveRDS(panel,file.path(audit,'county_panel_INTERNAL.rds'))
 clean<-panel[c('fips','year','state')];clean$county<-'TEST';clean$pathogen<-pathogen;clean$travelint<-'NO';clean$cxcidt<-'CX+';clean$siteid<-'AA';clean$cste<-'YES'
 raw<-clean;raw$dtspec<-as.Date(paste0(raw$year,'-02-01'));raw$month<-2L
 if(pathogen=='LISTERIA'){bad<-raw[1,];bad$cste<-'NO';raw<-rbind(raw,bad)}
 if(pathogen=='CRYPTOSPORIDIUM'){bad<-raw[1,];bad$year<-2018L;bad$dtspec<-as.Date('2018-02-01');raw<-rbind(raw,bad)}
 rp<-file.path(audit,'raw.sas7bdat');cp<-file.path(audit,'clean.csv');mp<-file.path(audit,'mapping.csv')
 haven::write_sas(raw,rp);write.csv(clean,cp,row.names=FALSE);write.csv(data.frame(original=pathogen,standardized=pathogen),mp,row.names=FALSE)
 write.csv(data.frame(file=cp,md5=unname(tools::md5sum(cp))),file.path(audit,'reports/input_checksums.csv'),row.names=FALSE)
 out<-file.path(audit,'monthly');prepare_monthly_county(rp,cp,mp,audit,out,pathogen)
 d<-readRDS(file.path(out,'candidate_monthly_INTERNAL.rds'));stopifnot(max(d$year)==end,sum(d$record_count)==nrow(panel))
 if(pathogen=='LISTERIA') {
  clean$cste[1]<-'NO';write.csv(clean,cp,row.names=FALSE);write.csv(data.frame(file=cp,md5=unname(tools::md5sum(cp))),file.path(audit,'reports/input_checksums.csv'),row.names=FALSE)
  stopifnot(inherits(try(prepare_monthly_county(rp,cp,mp,audit,file.path(audit,'bad'),pathogen),silent=TRUE),'try-error'))
 }
}
cat('Actual SAS preparation: Listeria CSTE and Crypto cutoff PASS\n')
