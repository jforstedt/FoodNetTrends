source('scripts/audit_campylobacter_regional_history.R')
fails<-function(x)stopifnot(inherits(tryCatch({force(x);NULL},error=identity),'error'))
d<-expand.grid(month=1:12,year=2010:2014,fips=c('01001','47001'),stringsAsFactors=FALSE)
d$state<-ifelse(d$fips=='01001','GA','TN');d$population<-ifelse(d$state=='GA',1200,2400)
d$person_years<-d$population/12;d$count<-ifelse(d$state=='GA',10,20)
t<-campylobacter_history_tables(d)
stopifnot(nrow(t$month)==120,nrow(t$year)==10,nrow(t$phases)==30,
 all(t$year$count[t$year$state=='GA']==120),all(t$year$person_years[t$year$state=='TN']==2400),
 all(t$domain$entered_counties[!is.na(t$domain$entered_counties)]==0),
 all(t$phases$phase[t$phases$cutoff==2011&t$phases$year==2012]=='heldout'),
 all(t$phases$phase[t$phases$cutoff==2011&t$phases$year==2010]=='training'))
fails(campylobacter_history_tables(d[-1,]));fails(campylobacter_history_tables(rbind(d,d[1,])))
bad<-d;bad$person_years[1]<-1;fails(campylobacter_history_tables(bad))
bad<-d;bad$count[1]<--1;fails(campylobacter_history_tables(bad))
bad<-d;bad$year[1]<-2010.5;fails(campylobacter_history_tables(bad))
bad<-d;bad$state[bad$fips=='01001'&bad$year==2011]<-'TN';fails(campylobacter_history_tables(bad))
# Domain changes must be reported, not silently hidden by aggregation.
x<-d[!(d$fips=='01001'&d$year==2014),];new<-d[d$fips=='01001'&d$year==2014,];new$fips<-'01003';x<-rbind(x,new)
a<-campylobacter_history_tables(x)$domain
stopifnot(a$entered_counties[a$state=='GA'&a$year==2014]==1,a$departed_counties[a$state=='GA'&a$year==2014]==1)
clean<-data.frame(pathogen=c('CAMPYLOBACTER','CAMPYLOBACTER','SALMONELLA','CAMPYLOBACTER'),year=c('2012','2012','2012','2020'),state='GA',cxcidt=c('UNKNOWN',NA,'CX+','CX+'),travelint=c('YES','','NO','NO'),stringsAsFactors=FALSE)
z<-campylobacter_clean_strata(clean)
stopifnot(z$records==2L,identical(z$unavailable,'siteid'),
 sum(z$rows$records[z$rows$field=='cxcidt'])==2,
 all(c('UNKNOWN','[MISSING]')%in%z$rows$value), '[BLANK]'%in%z$rows$value)
bad<-clean;bad$year[1]<-'bad';fails(campylobacter_clean_strata(bad))
cat('REGIONAL HISTORY CONSERVATION, DOMAIN, CUTOFF AND UNKNOWN-LABEL TESTS PASS\n')
if(requireNamespace('jsonlite',quietly=TRUE)) {
 td<-tempfile();dir.create(td);run<-file.path(td,'run');dir.create(run)
 src<-file.path(run,'bundle','scripts');dir.create(src,recursive=TRUE)
 audit<-file.path(td,'audit');dir.create(file.path(audit,'reports'),recursive=TRUE)
 d<-expand.grid(month=1:12,year=2004:2019,fips=sprintf('%05d',1:10),stringsAsFactors=FALSE)
 d$state<-c('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')[match(d$fips,sprintf('%05d',1:10))]
 d$count<-1L;d$population<-1200;d$person_years<-100
 a<-campylobacter_history_tables(d)$year
 write.csv(data.frame(state=a$state,year=a$year,assigned_records=a$count,annual_records=a$count,unassigned_records=0,population=a$person_years,candidate_person_years=a$person_years),file.path(td,'annual_reconciliation.csv'),row.names=FALSE)
 candidate<-file.path(td,'candidate.rds');saveRDS(d,candidate);saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
 cleanpath<-file.path(td,'clean_mmwr.csv');write.csv(clean,cleanpath,row.names=FALSE,na='')
 write.csv(data.frame(file=cleanpath,md5=unname(tools::md5sum(cleanpath))),file.path(td,'input_checksums.csv'),row.names=FALSE)
 write.csv(data.frame(file=candidate,md5=unname(tools::md5sum(candidate))),file.path(audit,'reports','input_checksums.csv'),row.names=FALSE)
 # Inject only frozen loader boundary; exercise actual discovery, source binding,
 # read-only checks, stratification, report serialization and completion handling.
 writeLines('load_monthly_comparison <- function(candidate,audit,cutoff,end_year)readRDS(candidate)',file.path(src,'run_monthly_comparison.R'))
 for(i in 1:36)jsonlite::write_json(list(pathogen='CAMPYLOBACTER',cutoff=c(2011,2013,2016)[(i-1)%%3+1],candidate=candidate,audit=audit),file.path(run,paste0('CAMPYLOBACTER_',i,'.json')),auto_unbox=TRUE)
 task<-list(source_run=run,output=file.path(td,'reports'));jp<-file.path(td,'task.json');jsonlite::write_json(task,jp,auto_unbox=TRUE)
 audit_campylobacter_regional_history(jp)
 meta<-jsonlite::read_json(file.path(task$output,'audit_metadata.json'))
 stopifnot(meta$original_annual_reconciliation=='VERIFIED_AGAINST_FROZEN_PANEL',identical(meta$scientific_acceptance,FALSE),identical(meta$refitted,FALSE),meta$clean_inventory$status=='DESCRIPTIVE_INVENTORY_COMPLETE',
   nrow(read.csv(file.path(task$output,'state_month_history.csv')))==1920,
   readLines(file.path(task$output,'status.txt'))=='CAMPYLOBACTER_REGIONAL_HISTORY_COMPLETE',
   file.exists(file.path(task$output,'county_year_INTERNAL.csv')))
 fails(audit_campylobacter_regional_history(jp));unlink(td,recursive=TRUE)
 cat('READ-ONLY HISTORY ORCHESTRATION SYNTHETIC PASS\n')
}
