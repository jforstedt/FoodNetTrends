#!/usr/bin/env Rscript
# Refit an audited saved model with one sampler-control change. No new model/data.
same_sampler_refit_data <- function(before,after) {
  # update.brmsfit changes only this descriptive attribute when reusing data.
  attr(before,'data_name')<-NULL;attr(after,'data_name')<-NULL
  isTRUE(all.equal(before,after,tolerance=0,check.attributes=TRUE))
}

surveillance_sampler_plan <- function(sim,args) {
  scalar <- function(x) length(x)==1L && is.numeric(x) && is.finite(x) && x==floor(x)
  if (!all(vapply(sim[c('chains','iter','warmup','thin')],scalar,logical(1))) ||
      !all(c('chains','iter','warmup','thin') %in% names(sim)) ||
      sim$chains!=6L || sim$iter!=10001L || sim$warmup<0 || sim$warmup>=sim$iter || sim$thin<1L)
    stop('Source must have six chains, 10001 iterations, and valid saved warmup/thin')
  if (length(args)!=6L || any(vapply(args,function(a) is.null(a$control),logical(1))))
    stop('Source sampler controls are unavailable')
  control<-args[[1]]$control
  if (!all(vapply(args,function(a) identical(a$control,control),logical(1))) ||
      length(control$max_treedepth)!=1L || !is.finite(control$max_treedepth) || control$max_treedepth!=15L)
    stop('Source chain controls differ or maximum tree depth is not 15')
  seeds<-vapply(args,function(a) suppressWarnings(as.numeric(a$seed)),numeric(1))
  if (any(!is.finite(seeds)) || any(seeds!=123)) stop('Source sampler seed differs from the preserved seed 123')
  control$adapt_delta<-.9999
  list(chains=sim$chains,iter=sim$iter,warmup=sim$warmup,thin=sim$thin,seed=123L,cores=12L,control=control)
}

sampler_model_identity <- function(old,new,code_reader=function(x)brms::stancode(x)) {
  c(same_data=same_sampler_refit_data(old$data,new$data),
    same_priors=identical(old$prior,new$prior),
    same_stan_code=identical(code_reader(old),code_reader(new)))
}

save_sampler_checkpoint <- function(object,path) {
  if (file.exists(path)) stop('Refusing to overwrite an existing checkpoint')
  dir.create(dirname(path),recursive=TRUE,showWarnings=FALSE)
  temporary<-tempfile(paste0('.',basename(path),'.'),tmpdir=dirname(path))
  on.exit(unlink(temporary),add=TRUE)
  saveRDS(object,temporary)
  if (file.exists(path) || !file.rename(temporary,path)) stop('Cannot finalize new sampling checkpoint')
  invisible(path)
}

compare_sampler_exports <- function(before,after) {
  join<-intersect(c('year','state'),names(after))
  if (!'year' %in% join || !all(join %in% names(before)) ||
      anyDuplicated(before[join]) || anyDuplicated(after[join])) stop('Export comparison has missing/duplicate keys')
  merged<-merge(before,after,by=join,suffixes=c('_old','_new'))
  if (nrow(merged)!=nrow(before) || nrow(merged)!=nrow(after)) stop('Export state/year keys changed')
  for (field in intersect(c('population','raw_count','raw_ir','baseline_start','baseline_end'),names(after))) {
    if (!field %in% names(before) || !isTRUE(all.equal(merged[[paste0(field,'_old')]],
        merged[[paste0(field,'_new')]],tolerance=0))) stop('Observed data or baseline changed in export: ',field)
  }
  fields<-intersect(c('median_ir','lower_hdi_ir','upper_hdi_ir','relative_risk_est',
    'relative_risk_lower_hdi','relative_risk_upper_hdi','percent_change_est'),names(after))
  for (field in fields) {
    if (!field %in% names(before)) stop('Source comparison output lacks field: ',field)
    a<-merged[[paste0(field,'_old')]];b<-merged[[paste0(field,'_new')]]
    merged[[paste0(field,'_difference')]]<-b-a
    merged[[paste0(field,'_percent_difference')]]<-ifelse(a!=0,100*(b-a)/abs(a),NA_real_)
  }
  if ('relative_risk_lower_hdi' %in% names(after)) {
    category<-function(lo,hi)ifelse(lo>1,'increase',ifelse(hi<1,'decrease','includes_1'))
    merged$old_interval_category<-category(merged$relative_risk_lower_hdi_old,merged$relative_risk_upper_hdi_old)
    merged$new_interval_category<-category(merged$relative_risk_lower_hdi_new,merged$relative_risk_upper_hdi_new)
    merged$interval_category_changed<-merged$old_interval_category!=merged$new_interval_category
  }
  merged
}

preserve_sampler_labels <- function(value,original) {
  join<-intersect(c('year','state'),names(value))
  key<-function(x)do.call(paste,c(x[join],sep='|'))
  if (!'year' %in% join || anyDuplicated(key(value)) || anyDuplicated(key(original)) ||
      !setequal(key(value),key(original))) stop('Cannot preserve source labels on changed export keys')
  ix<-match(key(value),key(original))
  for (name in intersect(c('pathogen','travel','culture'),names(original))) value[[name]]<-original[[name]][ix]
  value
}

run_surveillance_sampler_refit <- function(source_task,dest_task,key) {
  if (length(key)!=1L || !grepl('^[A-Za-z0-9_-]+$',key)) stop('Invalid model key')
  source_task<-normalizePath(source_task,mustWork=TRUE);dest_task<-normalizePath(dest_task,mustWork=TRUE)
  if (identical(source_task,dest_task) || startsWith(dest_task,paste0(source_task,'/')))
    stop('Destination must be separate from the original task')
  lock<-file.path(dest_task,'.sampler_refit_lock')
  if (!dir.create(lock,showWarnings=FALSE)) stop('Another refit/export process holds this task lock')
  on.exit(unlink(lock,recursive=TRUE),add=TRUE)
  status_path<-file.path(dest_task,paste0(key,'.status'));writeLines('RUNNING',status_path)
  tryCatch({
    if (!requireNamespace('digest',quietly=TRUE) || !requireNamespace('jsonlite',quietly=TRUE)) stop('digest/jsonlite required')
    sha<-function(path)digest::digest(file=path,algo='sha256')
    source_results<-file.path(source_task,'spline_results');results<-file.path(dest_task,'spline_results')
    dir.create(results,recursive=TRUE,showWarnings=FALSE);dir.create(file.path(dest_task,'comparisons'),showWarnings=FALSE)
    old_path<-file.path(source_results,paste0(key,'_brm.Rds'))
    expected<-trimws(readLines(file.path(dest_task,'source_fit_sha256.txt'),warn=FALSE))
    if (length(expected)!=1L || !grepl('^[0-9a-f]{64}$',expected)) stop('Invalid expected source fit SHA256')
    before<-sha(old_path)
    if (!identical(before,expected)) stop('Source fit differs from the audited SHA256')
    source(file.path(dest_task,'functions.R'),local=environment())
    old<-readRDS(old_path)
    if (!inherits(old,'brmsfit') || !inherits(old$fit,'stanfit')) stop('Expected saved brms/rstan model')
    plan<-surveillance_sampler_plan(old$fit@sim,old$fit@stan_args)
    settings_path<-file.path(source_results,paste0(key,'_analysis_settings.csv'))
    settings<-read.csv(settings_path,stringsAsFactors=FALSE,check.names=FALSE)
    if (nrow(settings)!=1L || !all(c('baseline_start','baseline_end') %in% names(settings))) stop('Invalid source analysis settings')
    bs<-settings$baseline_start;be<-settings$baseline_end
    if (any(!is.finite(c(bs,be))) || any(c(bs,be)!=floor(c(bs,be))) || bs>be) stop('Invalid saved baseline')
    suffixes<-c('_IRCatch.csv','_IRSite.csv',paste0('_EstIRRCatch_',bs,'_',be,'.csv'))
    for (suffix in c('_analysis_settings.csv','_population_used.csv','_classification_rules.csv',suffixes))
      if (!file.exists(file.path(source_results,paste0(key,suffix)))) stop('Required source artifact missing: ',suffix)
    checkpoint<-file.path(dest_task,'checkpoints',paste0(key,'.rds'))
    if (file.exists(checkpoint)) {
      cat('Reusing completed checkpoint; no new sampling\n');new<-readRDS(checkpoint)
    } else {
      if (identical(Sys.getenv('FOODNET_CHECKPOINT_ONLY'),'1')) stop('Required checkpoint missing; sampling disabled')
      cat('Refitting',key,'with saved data, priors and compiled Stan code\n',
        'Only sampler control change: adapt_delta=0.9999; maximum tree depth remains 15\n')
      new<-stats::update(old,recompile=FALSE,chains=plan$chains,iter=plan$iter,warmup=plan$warmup,
        thin=plan$thin,seed=plan$seed,cores=plan$cores,control=plan$control)
      # Preserve expensive completed sampling even if any following assertion/export fails.
      save_sampler_checkpoint(new,checkpoint)
    }
    checks<-sampler_model_identity(old,new)
    if (!inherits(new,'brmsfit') || !inherits(new$fit,'stanfit')) stop('Checkpoint is not a saved brms/rstan fit')
    newsim<-new$fit@sim;newargs<-new$fit@stan_args
    checks<-c(checks,same_sampler_schedule=all(vapply(c('chains','iter','warmup','thin'),
      function(n)identical(as.numeric(old$fit@sim[[n]]),as.numeric(newsim[[n]])),logical(1))),
      requested_controls=length(newargs)==6L && all(vapply(newargs,function(a)
        identical(a$control,plan$control) && isTRUE(as.numeric(a$seed)==plan$seed),logical(1))),
      source_fit_unchanged=identical(before,sha(old_path)))
    identity<-list(status=if(all(checks))'IDENTITY_PASS' else 'REVIEW_REQUIRED',checks=as.list(checks),
      source_fit_sha256=before,source_fit_sha256_after=sha(old_path),checkpoint_sha256=sha(checkpoint),
      functions_sha256=sha(file.path(dest_task,'functions.R')),adapt_delta=.9999,max_treedepth=15,
      chains=plan$chains,iterations=plan$iter,warmup=plan$warmup,thin=plan$thin,seed=plan$seed,cores=plan$cores,
      note='Only descriptive data_name attribute is ignored in the exact data comparison. Scientific identity does not certify sampler convergence.')
    jsonlite::write_json(identity,file.path(dest_task,paste0(key,'_identity_check.json')),pretty=TRUE,auto_unbox=TRUE)
    write.csv(data.frame(check=names(checks),passed=unname(checks)),file.path(dest_task,paste0(key,'_identity_check.csv')),row.names=FALSE)
    if (!all(checks)) stop('Saved model identity/control check failed; checkpoint preserved, replacement exports blocked')
    new_path<-file.path(results,paste0(key,'_brm.Rds'))
    if (file.exists(new_path)) {
      if (!identical(sha(new_path),sha(checkpoint))) stop('Existing replacement fit differs from the completed checkpoint')
    } else {
      temp<-tempfile(paste0('.',key,'.'),tmpdir=results)
      if (!file.copy(checkpoint,temp) || !file.rename(temp,new_path)) {unlink(temp);stop('Cannot publish completed checkpoint')}
    }
    provenance<-c('_analysis_settings.csv','_population_used.csv','_classification_rules.csv',
      '_classification_report.csv','_input_exclusions.csv','_observation_policy.csv')
    for (suffix in provenance) {
      from<-file.path(source_results,paste0(key,suffix));to<-file.path(results,paste0(key,suffix))
      if (!file.exists(from)) next
      if (file.exists(to)) {
        if (!identical(sha(from),sha(to))) stop('Existing copied provenance differs: ',suffix)
      } else if (!file.copy(from,to)) stop('Cannot preserve source provenance: ',suffix)
    }
    CHECK_CONVERGENCE(new,key,results)
    write.csv(data.frame(adapt_delta=.9999,max_treedepth=15,chains=plan$chains,iterations=plan$iter,
      warmup=plan$warmup,thin=plan$thin,seed=123,cores=12,same_data=TRUE,same_priors=TRUE,same_stan_code=TRUE,
      source_fit_sha256=before),file.path(results,paste0(key,'_refit_settings.csv')),row.names=FALSE)
    set.seed(123)
    draws<-LINPREAD_DRAW_FN(new$data,new);catch<-CATCHMENT(draws)
    catch_ir<-preserve_sampler_labels(LINPRED_TO_CATCHIR(catch),read.csv(file.path(source_results,paste0(key,suffixes[1])),stringsAsFactors=FALSE))
    site_ir<-preserve_sampler_labels(LINPRED_TO_SITEIR(draws),read.csv(file.path(source_results,paste0(key,suffixes[2])),stringsAsFactors=FALSE))
    write.csv(catch_ir,file.path(results,paste0(key,suffixes[1])),row.names=FALSE)
    write.csv(site_ir,file.path(results,paste0(key,suffixes[2])),row.names=FALSE)
    IR_COMP_CATCH(catch,bs,be,file.path(results,paste0(key,suffixes[3])))
    for (suffix in suffixes) {
      old_csv<-read.csv(file.path(source_results,paste0(key,suffix)),stringsAsFactors=FALSE)
      new_csv<-read.csv(file.path(results,paste0(key,suffix)),stringsAsFactors=FALSE)
      comparison<-compare_sampler_exports(old_csv,new_csv)
      write.csv(comparison,file.path(dest_task,'comparisons',paste0(key,suffix)),row.names=FALSE)
    }
    if (!identical(before,sha(old_path))) stop('Source fit changed during export')
    writeLines(c('SUCCESS','Saved model identity preserved; independent post-run diagnostics still required.'),status_path)
    cat('SAMPLER REFIT EXPORT COMPLETE:',key,'\n')
    invisible(identity)
  },error=function(e) {writeLines(c('FAIL',conditionMessage(e)),status_path);stop(e)})
}

if (sys.nframe()==0L) {
  args<-commandArgs(TRUE)
  if (length(args)!=3L) stop('Usage: refit_surveillance_sampler.R SOURCE_TASK DEST_TASK KEY')
  run_surveillance_sampler_refit(args[1],args[2],args[3])
}
