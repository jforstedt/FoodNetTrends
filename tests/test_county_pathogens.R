source('scripts/county_matching.R');source('scripts/audit_county_pilot.R')
source('bin/classification.R');source('scripts/audit_county_pathogens.R')
d<-tempfile();dir.create(d);geo<-file.path(d,'geo');dir.create(geo)
write.csv(data.frame(fips=c('06001','06013'),state='CA',county=c('Alameda','Contra Costa')),
 file.path(geo,'counties.csv'),row.names=FALSE)
write.csv(data.frame(fips_a='06001',fips_b='06013'),file.path(geo,'edges.csv'),row.names=FALSE)
x<-data.frame(year=2004,state='CA',county='ALAMEDA',fips='06001',pathogen=pathogen_names,
 travelint='NO',cxcidt='CX+',cste='YES',serotypesummary='X')
x$cste[x$pathogen=='LISTERIA']<-'NO'
clean<-file.path(d,'clean.csv');write.csv(x,clean,row.names=FALSE)
p<-expand.grid(year=2004:2019,cofip=c(1,13));p$stfip<-6;p$state<-'CA'
p$county<-ifelse(p$cofip==1,'ALAMEDA','CONTRA COSTA');p$population<-10000
b<-file.path(d,'b.sas7bdat');pp<-file.path(d,'p.sas7bdat');haven::write_sas(p,b)
p$population<-20000;haven::write_sas(p,pp)
out<-file.path(d,'out');audit_pathogens(clean,b,pp,geo,'analysis_configs/classification_rules.csv',out)
s<-read.csv(file.path(out,'summary.csv'))
stopifnot(nrow(s)==9,sum(s$input_status=='INPUT_AUDIT_PASS')==8,
 !file.exists(file.path(out,'LISTERIA/county_panel_INTERNAL.rds')),
 all(readRDS(file.path(out,'CRYPTOSPORIDIUM/county_panel_INTERNAL.rds'))$population==20000),
 all(readRDS(file.path(out,'STEC/county_panel_INTERNAL.rds'))$population==10000),
 all(s$raw_reconciliation=='PENDING'))
stopifnot(inherits(try(check_pathogen_rules(data.frame(x=1),'LISTERIA'),silent=TRUE),'try-error'))
unlink(d,recursive=TRUE);cat('PASS nine-pathogen isolation, parasite denominator routing and CSTE gate\n')
