source('scripts/run_campylobacter_cx_model.R')
fails<-function(x)stopifnot(inherits(tryCatch({force(x);NULL},error=identity),'error'))
d<-data.frame(fips='13001',state='GA',year=c(2011L,2012L),month=1L,person_years=c(100,101),count=c(5,7))
for(local in c(FALSE,TRUE)) {
 task<-list(version='county_covariate_experiment_v1',task_id='original',pathogen='CAMPYLOBACTER',cutoff=2011L,temporal='rw1',local_seasonality=local,weather=FALSE,age=FALSE)
 old<-d;old$count[2]<-NA
 f<-list(.args=list(data=old));attr(f,'covariate_experiment_contract')<-task;attr(f,'covariate_experiment_masked_data')<-old
 validate_cx_reuse_training(f,d,2011L,local,task)
 x<-d;x$count[2]<-2;validate_cx_reuse_training(f,x,2011L,local,task) # new heldout target allowed
 x<-d;x$count[1]<-4;fails(validate_cx_reuse_training(f,x,2011L,local,task))
 x<-d;x$person_years[1]<-99;fails(validate_cx_reuse_training(f,x,2011L,local,task))
 fails(validate_cx_reuse_training(f,d,2013L,local,task))
}
# Explicit target version and source-record synchronization.
cx<-transform(d,record_count=count,candidate_person_years=person_years,population=1200)
p<-tempfile();saveRDS(cx,p);c<-transform(d,population=1200,record_count=count)
m<-list(version='campylobacter_cx_target_v1',status='CX_TARGET_PREPARATION_COMPLETE',target='recorded_CX_positive',combined_replay_verified=TRUE,raw_clean_cx_strata_verified=TRUE,pre2012_cx_equals_combined=TRUE,cx_candidate_md5=unname(tools::md5sum(p)))
z<-load_cx_monthly(p,c,m);stopifnot(identical(z$record_count,z$count))
m$version<-'bad';fails(load_cx_monthly(p,c,m));unlink(p)
cat('CX REUSE EXACT TRAINING/EXPOSURE/TARGET VERSION GUARDS PASS\n')
