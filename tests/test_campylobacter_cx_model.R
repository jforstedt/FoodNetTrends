source('scripts/prepare_campylobacter_cx_target.R');source('scripts/run_campylobacter_cx_model.R');source('scripts/prepare_monthly_county.R')
fails<-function(x)stopifnot(inherits(tryCatch({force(x);NULL},error=identity),'error'))
p<-data.frame(state='GA',fips='13001',year=2011L,population=12000,count=3)
r<-data.frame(state='GA',fips='13001',year=2011L,month=c(1,1,2),dtspec=as.Date(c('2011-01-01','2011-01-02','2011-02-01')),cxcidt=c('CX+','CIDT+','CX+'))
combined<-monthly_inventory(r,p)$grid;z<-cx_subset_inventory(r,p,combined,monthly_inventory)
stopifnot(nrow(z$grid)==12L,sum(z$grid$record_count)==2L,sum(z$grid$candidate_person_years)==12000,all(z$grid$record_count<=combined$record_count),sum(z$grid$record_count==0)==10L)
bad<-r;bad$fips[1]<-'99999';fails(cx_subset_inventory(bad,p,combined,monthly_inventory))
bad<-r;bad$dtspec[1]<-as.Date(NA);fails(cx_subset_inventory(bad,p,combined,monthly_inventory))
bad<-combined;bad$record_count[1]<-0;fails(cx_subset_inventory(r,p,bad,monthly_inventory))
cat('CX COUNT/SUBSET/FULL-DOMAIN/EXPOSURE INVARIANTS PASS\n')
if('--inla'%in%commandArgs(TRUE)) {
 # Snapshot sources before the real test: live workspace edits cannot alter fixtures.
 stopifnot(requireNamespace('jsonlite',quietly=TRUE))
 td<-tempfile();dir.create(td);src<-file.path(td,'scripts');dir.create(src)
 frozen_source<-Sys.getenv('CX_FROZEN_SCRIPTS','scripts')
 file.copy(list.files(frozen_source,pattern='[.]R$',full.names=TRUE),src)
 d<-expand.grid(month=1:12,year=2010:2014,fips=c('13001','47001'),stringsAsFactors=FALSE)
 d$state<-ifelse(d$fips=='13001','GA','TN');d$population<-60000
 first<-as.Date(sprintf('%04d-%02d-01',d$year,d$month));nextm<-as.Date(sprintf('%04d-%02d-01',d$year+(d$month==12),d$month%%12+1))
 yd<-as.numeric(as.Date(paste0(d$year+1,'-01-01'))-as.Date(paste0(d$year,'-01-01')))
 d$person_years<-d$population*as.numeric(nextm-first)/yd;d$area<-d$fips;d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 set.seed(17221);d$count<-rnbinom(nrow(d),mu=d$person_years*.002,size=30)
 cx<-d;cx$record_count<-d$count;cx$record_count[cx$year>2011]<-rbinom(sum(cx$year>2011),d$count[d$year>2011],.8);cx$candidate_person_years<-cx$person_years
 candidate<-file.path(td,'cx.rds');saveRDS(cx,candidate);comb<-file.path(td,'combined.rds');saveRDS(d,comb)
 audit<-file.path(td,'audit');dir.create(audit);saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
 meta<-list(version='campylobacter_cx_target_v1',status='CX_TARGET_PREPARATION_COMPLETE',target='recorded_CX_positive',combined_replay_verified=TRUE,raw_clean_cx_strata_verified=TRUE,
  pre2012_cx_equals_combined=TRUE,combined_candidate=comb,audit=audit,cx_candidate_md5=unname(tools::md5sum(candidate)))
 mp<-file.path(td,'meta.json');jsonlite::write_json(meta,mp,auto_unbox=TRUE)
 # Only original full486 input-loader boundary is substituted. Actual fitter,
 # checkpoint, heldout adapter and 4x1000 posterior diagnostics remain unchanged.
 cat('\nload_monthly_comparison <- function(candidate,audit,cutoff,end_year)readRDS(candidate)\n',file=file.path(src,'run_monthly_comparison.R'),append=TRUE)
 task<-list(task_id='CAMPYLOBACTER_CX_2011_local1',candidate=candidate,combined_candidate=comb,audit=audit,source_scripts=src,
  cutoff=2011L,local_seasonality=TRUE,seed=450123L,output=file.path(td,'work'),preparation_metadata=mp)
 jp<-file.path(td,'task.json');jsonlite::write_json(task,jp,auto_unbox=TRUE)
 run_campylobacter_cx_model(jp)
 fit<-readRDS(file.path(task$output,'fit_INTERNAL.rds'))
 stopifnot(attr(fit,'diagnostic_era_specification')$target=='recorded_CX_positive',fit$mode$mode.status==0,
  readLines(file.path(task$output,'reports','status.txt'))=='CX_MODEL_COMPLETE',
  all(read.csv(file.path(task$output,'reports','stream_scores.csv'))$draws%in%c(1000,4000)))
 unlink(td,recursive=TRUE);cat('CX REAL RW1 LOCAL FIT/CHECKPOINT/FOUR POSTERIOR STREAMS PASS\n')
}
