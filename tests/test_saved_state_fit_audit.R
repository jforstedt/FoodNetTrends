source('scripts/audit_saved_state_fit.R')
expect_error <- function(expr,pattern) {
  message<-tryCatch({force(expr);NULL},error=function(e)conditionMessage(e))
  stopifnot(!is.null(message),grepl(pattern,message,fixed=TRUE))
}
states<-c('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
d<-expand.grid(year=2004:2006,state=states,stringsAsFactors=FALSE)
d$count<-seq_len(nrow(d));d$population<-100000
valid<-audit_state_data(transform(d,state=factor(state)))
stopifnot(nrow(valid)==30L,!anyDuplicated(state_fit_key(valid)))
expect_error(audit_state_data(rbind(d,d[1,])),'Duplicate')
expect_error(audit_state_data(transform(d,count=count+.5)),'Invalid saved')
expect_error(audit_state_data(transform(d,population=Inf)),'Invalid saved')
expect_error(audit_state_data(transform(d,year=factor(year))),'must be numeric')
fake<-structure(list(formula=count~s(year,by=state)+state+offset(log(population)),
  family=list(family='negbinomial',link='log'),data=d,prior=data.frame(prior='inv_gamma(0.4,0.3)')),class='brmsfit')
stopifnot(audit_state_formula(fake)$family=='negbinomial')
wrapped<-fake;wrapped$formula<-structure(list(formula=fake$formula,pforms=list(),pfix=list()),class='brmsformula')
stopifnot(audit_state_formula(wrapped)$family=='negbinomial')
bad<-wrapped;bad$formula$pfix<-list(shape=1)
expect_error(audit_state_formula(bad),'distributional formula')
bad<-wrapped;attr(bad$formula$formula,'nl')<-TRUE
expect_error(audit_state_formula(bad),'formula attributes')
bad<-fake;bad$formula<-count~s(year)+state+offset(log(population))
expect_error(audit_state_formula(bad),'Formula differs')
bad<-fake;bad$family$link<-'identity';expect_error(audit_state_formula(bad),'log link')
expect_error(audit_state_formula(unclass(fake)),'not a brmsfit')

b<-tempfile('saved-state-audit-');dir.create(b)
snapshot<-file.path(b,'functions.R')
writeLines(c('stop("UNRELATED TOP LEVEL MUST NOT RUN")',readLines('bin/functions.R')),snapshot)
catchment<-load_saved_catchment_functions(snapshot)
s<-list(pathogen='YERSINIA',subgroup='combined',states='',baseline_start='2004',baseline_end='2005',
  analysis_start_year='2004',analysis_end_year='2006',travel='NO,UNKNOWN,YES',cidt='CIDT+,CX+,PARASITIC',
  colorado_coverage='historical',parasite_end_year='2024',serotype_source='auto',selected_serotypes='',catchment_config='')
job<-list(task='task_01',prefix='YERSINIA_combined',first_year=2004,last_year=2006,settings=s)
pop<-transform(d[c('year','state','population')],pathogentype='Bacterial')
grid<-audit_expected_state_grid(job,s,pop,catchment)
stopifnot(nrow(grid$expected_keys)==30L,setequal(grid$expected_keys$state,states))
expect_error(audit_expected_state_grid(job,s,pop[pop$state!='NM',],catchment),'independently declared')
bad<-s;bad$baseline_end<-'2007';expect_error(audit_expected_state_grid(job,bad,pop,catchment),'baseline')
bad<-s;bad$catchment_config<-'custom.csv';expect_error(audit_expected_state_grid(job,bad,pop,catchment),'Custom catchment')
badjob<-job;badjob$settings$states<-'CA,CO';expect_error(audit_expected_state_grid(badjob,s,pop,catchment),'outside declared')

parameters<-data.frame(rhat=c(1,1.002),ess_bulk=c(900,1000),ess_tail=c(800,950))
chains<-data.frame(chain=1:6,draws=5001,divergences=0,treedepth_hits=0,ebfmi=.8,depth_limit=15)
good<-audit_state_diagnostic_values(parameters,chains,5001)
stopifnot(good$diagnostics$converged,good$diagnostics$ess_threshold==600,good$diagnostics$min_ess==800)
bad<-parameters;bad$ess_tail[1]<-500
stopifnot(!audit_state_diagnostic_values(bad,chains,5001)$diagnostics$converged)
for (name in c('rhat','ess_bulk','ess_tail')) {
  bad<-parameters;bad[[name]][1]<-NA_real_
  expect_error(audit_state_diagnostic_values(bad,chains,5001),'unavailable/nonfinite')
}
for (name in c('divergences','treedepth_hits','ebfmi')) {
  bad<-chains;bad[[name]][1]<-if(name=='ebfmi').1 else 1
  stopifnot(!audit_state_diagnostic_values(parameters,bad,5001)$diagnostics$converged)
}
bad<-chains;bad$draws[1]<-4000
expect_error(audit_state_diagnostic_values(parameters,bad,5001),'inconsistent')
cat('PASS structural formula/data checks, independent expected grid, missing-state rejection, diagnostic fail-closed thresholds\n')

if (!requireNamespace('jsonlite',quietly=TRUE) || !requireNamespace('digest',quietly=TRUE))
  stop('jsonlite/digest required to exercise proof generation')
dir.create(file.path(b,'scripts'));file.copy(snapshot,file.path(b,'scripts','functions.R'))
task<-file.path(b,'task_01');dir.create(file.path(task,'spline_results'),recursive=TRUE)
manifest<-list(jobs=list(job),source_sha256=setNames(list(digest::digest(file=snapshot,algo='sha256')),'functions.R'))
jsonlite::write_json(manifest,file.path(b,'manifest.json'),auto_unbox=TRUE)
out<-file.path(task,'spline_results');prefix<-job$prefix
write.csv(as.data.frame(s),file.path(out,paste0(prefix,'_analysis_settings.csv')),row.names=FALSE)
write.csv(pop,file.path(out,paste0(prefix,'_population_used.csv')),row.names=FALSE)
fitfile<-file.path(out,paste0(prefix,'_brm.Rds'))
saveRDS(list(arbitrary='This is not a fitted model'),fitfile)
proof<-audit_saved_state_fit(task,file.path(b,'plain_rds.json'))
stopifnot(proof$status=='REVIEW_REQUIRED',any(grepl('not a brmsfit',unlist(proof$issues))),nchar(proof$fit_sha256)==64)
saveRDS(fake,fitfile)
proof<-audit_saved_state_fit(task,file.path(b,'fake_brms.json'))
stopifnot(proof$status=='REVIEW_REQUIRED',proof$eligibility_status=='PASS',
  any(grepl('not an rstan stanfit',unlist(proof$issues))),nrow(proof$model_data)==30)
bad<-fake;bad$data<-bad$data[bad$data$state!='NM',];saveRDS(bad,fitfile)
proof<-audit_saved_state_fit(task,file.path(b,'missing_model_state.json'))
stopifnot(proof$status=='REVIEW_REQUIRED',proof$eligibility_status=='REVIEW_REQUIRED',
  any(grepl('omit or add',unlist(proof$issues))))
saveRDS(fake,fitfile);write.csv(pop[pop$state!='NM',],file.path(out,paste0(prefix,'_population_used.csv')),row.names=FALSE)
proof<-audit_saved_state_fit(task,file.path(b,'missing_population_state.json'))
stopifnot(proof$status=='REVIEW_REQUIRED',any(grepl('independently declared',unlist(proof$issues))))
expect_error(audit_saved_state_fit(task,file.path(b,'plain_rds.json')),'overwrite')
unlink(b,recursive=TRUE)
cat('PASS proof emission rejects arbitrary RDS, fake posterior, missing modeled state, missing population state; existing proofs preserved\n')
