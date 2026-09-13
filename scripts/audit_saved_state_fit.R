#!/usr/bin/env Rscript
# Read a completed state fit. Never call brm(), update(), sampling(), or stan().
state_fit_key <- function(d) paste(d$state, d$year, sep='|')

audit_state_data <- function(d) {
  required <- c('year','state','count','population')
  if (!is.data.frame(d) || !all(required %in% names(d)) || !nrow(d))
    stop('Saved model lacks nonempty state/year/count/population data')
  d <- d[required]
  if (!all(vapply(d[c('year','count','population')], is.numeric, logical(1))))
    stop('Saved year/count/population predictors must be numeric, not factors or strings')
  d$state <- as.character(d$state)
  if (anyNA(d) || any(!grepl('^[A-Z]{2}$',d$state)) ||
      any(!is.finite(d$year)) || any(d$year != floor(d$year)) ||
      any(!is.finite(d$count)) || any(d$count < 0 | d$count != floor(d$count)) ||
      any(!is.finite(d$population)) || any(d$population <= 0))
    stop('Invalid saved model count, population, state, or year')
  if (anyDuplicated(state_fit_key(d))) stop('Duplicate saved modeled state/year')
  d <- d[order(d$state,d$year),,drop=FALSE]; rownames(d) <- NULL
  d
}

audit_state_formula <- function(model) {
  if (!inherits(model,'brmsfit')) stop('Saved RDS is not a brmsfit')
  ff <- model$formula
  if (inherits(ff,'brmsformula')) {
    if (isTRUE(ff$nl) || length(ff$pforms) || length(ff$pfix)) stop('Unexpected nonlinear/distributional formula')
    ff <- ff$formula
  }
  if (!inherits(ff,'formula') || length(ff)!=3L || !identical(ff[[2]],quote(count)))
    stop('Unexpected state model response or formula')
  if (isTRUE(attr(ff,'nl')) || !is.null(attr(ff,'autocor')))
    stop('Unexpected nonlinear or autocorrelation formula attributes')
  flatten <- function(x) {
    if (is.call(x) && identical(x[[1]],as.name('+')) && length(x)==3L)
      c(Recall(x[[2]]),Recall(x[[3]]))
    else gsub('[[:space:]]','',paste(deparse(x),collapse=''))
  }
  actual <- flatten(ff[[3]])
  if (!identical(sort(actual),sort(c('s(year,by=state)','state','offset(log(population))'))))
    stop('Formula differs from count ~ s(year, by=state) + state + offset(log(population))')
  family <- model$family
  if (is.null(family)) family <- model$formula$family
  if (!identical(family$family,'negbinomial') || !identical(family$link,'log'))
    stop('Expected negative-binomial family with log link')
  list(formula=paste(deparse(ff),collapse=' '),family=family$family,link=family$link)
}

load_saved_catchment_functions <- function(path) {
  # Evaluate only these pure definitions: do not source package loading/model code.
  names <- c('read_catchment_config','validate_catchment_config','apply_catchment_filter')
  selected <- list()
  for (x in parse(path)) {
    if (is.call(x) && identical(x[[1]],as.name('<-')) && length(x)==3L &&
        is.symbol(x[[2]]) && as.character(x[[2]]) %in% names &&
        is.call(x[[3]]) && identical(x[[3]][[1]],as.name('function')))
      selected[[as.character(x[[2]])]] <- x
  }
  if (!setequal(names,names(selected))) stop('Snapshot lacks required catchment definitions')
  env <- new.env(parent=baseenv())
  for (x in selected) eval(x,env)
  env
}

audit_expected_state_grid <- function(job,settings,population,catchment) {
  if (nzchar(as.character(settings$catchment_config %||% '')) ||
      nzchar(as.character(job$settings$catchment_config %||% '')))
    stop('Custom catchment needs a separate explicit audit specification')
  first <- as.numeric(job$first_year); last <- as.numeric(job$last_year)
  if (length(first)!=1L || length(last)!=1L || !is.finite(first) || !is.finite(last) ||
      first!=floor(first) || last!=floor(last) || first>last) stop('Invalid declared analysis window')
  declared <- trimws(as.character(job$settings$states %||% ''))
  all_states <- c('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
  states <- if (declared %in% c('','all','ALL')) all_states else trimws(strsplit(declared,',',fixed=TRUE)[[1]])
  if (!length(states) || anyDuplicated(states) || any(!states %in% all_states)) stop('Invalid declared state selection')
  expected <- expand.grid(year=seq.int(first,last),state=states,stringsAsFactors=FALSE)
  kind <- if (job$settings$pathogen %in% c('CRYPTOSPORIDIUM','CYCLOSPORA')) 'parasitic' else 'bacterial'
  config <- catchment$validate_catchment_config(catchment$read_catchment_config())
  expected <- catchment$apply_catchment_filter(expected,config,kind)
  if (!nrow(expected)) stop('Declared eligibility grid is empty')
  expected <- expected[order(expected$state,expected$year),,drop=FALSE];rownames(expected)<-NULL
  required <- c('year','state','population')
  if (!all(required %in% names(population))) stop('Population artifact lacks required fields')
  if ('pathogentype' %in% names(population) &&
      any(tolower(as.character(population$pathogentype))!=kind)) stop('Population pathogen type differs')
  p <- population[required];p$count <- 0
  p <- audit_state_data(p)
  if (any(!p$state %in% states) || any(p$year<first | p$year>last))
    stop('Population artifact extends outside declared years/states')
  p <- catchment$apply_catchment_filter(p,config,kind)
  if (!setequal(state_fit_key(p),state_fit_key(expected)))
    stop('Population artifact is incomplete for independently declared eligible state/year grid')
  bs <- as.numeric(settings$baseline_start); be <- as.numeric(settings$baseline_end)
  if (length(bs)!=1L || length(be)!=1L || any(!is.finite(c(bs,be))) ||
      any(c(bs,be)!=floor(c(bs,be))) || bs>be ||
      !all(seq.int(bs,be) %in% expected$year)) stop('Saved baseline lies outside eligible observed years')
  for (name in c('pathogen','subgroup','baseline_start','baseline_end','states','travel','cidt',
                 'colorado_coverage','parasite_end_year','serotype_source','selected_serotypes')) {
    if (is.null(settings[[name]]) || is.null(job$settings[[name]]) ||
        !identical(as.character(settings[[name]]),as.character(job$settings[[name]])))
      stop('Saved setting differs from declared job: ',name)
  }
  if (as.numeric(settings$analysis_start_year)!=first || as.numeric(settings$analysis_end_year)!=last)
    stop('Saved settings coverage differs from declared job')
  list(expected_keys=expected,population=p,baseline=c(bs,be),states=states)
}

`%||%` <- function(x,y) if (is.null(x)) y else x

audit_state_diagnostic_values <- function(parameter_summary,chain_summary,post_draws) {
  issues <- character()
  required <- c('rhat','ess_bulk','ess_tail')
  if (!is.data.frame(parameter_summary) || !nrow(parameter_summary) ||
      !all(required %in% names(parameter_summary)) ||
      any(!is.finite(as.matrix(parameter_summary[required]))))
    stop('Rank R-hat or bulk/tail ESS unavailable/nonfinite for one or more parameters')
  chain_required <- c('draws','divergences','treedepth_hits','ebfmi','depth_limit')
  if (!is.data.frame(chain_summary) || nrow(chain_summary)<2L ||
      !all(chain_required %in% names(chain_summary)) ||
      any(!is.finite(as.matrix(chain_summary[chain_required]))) ||
      length(post_draws)!=1L || !is.finite(post_draws) || post_draws<4L ||
      any(chain_summary$draws!=post_draws)) stop('Sampler diagnostics missing, nonfinite, or inconsistent with posterior draws')
  threshold <- max(400,100*nrow(chain_summary))
  d <- list(max_rhat=max(parameter_summary$rhat),min_ess_bulk=min(parameter_summary$ess_bulk),
    min_ess_tail=min(parameter_summary$ess_tail),min_ess=min(as.matrix(parameter_summary[c('ess_bulk','ess_tail')])),
    n_divergent=sum(chain_summary$divergences),n_treedepth_hits=sum(chain_summary$treedepth_hits),
    min_ebfmi=min(chain_summary$ebfmi),chains=nrow(chain_summary),post_warmup_draws_per_chain=post_draws,
    ess_threshold=threshold,chain_diagnostics=chain_summary)
  if (d$max_rhat>1.01) issues<-c(issues,'Rank-normalized R-hat exceeds 1.01')
  if (d$min_ess_bulk<threshold || d$min_ess_tail<threshold) issues<-c(issues,paste('Bulk/tail ESS below',threshold))
  if (d$n_divergent!=0) issues<-c(issues,'Divergent transitions present')
  if (d$n_treedepth_hits!=0) issues<-c(issues,'Maximum tree depth reached')
  if (d$min_ebfmi<.3) issues<-c(issues,'At least one chain has E-BFMI below 0.3')
  d$converged <- !length(issues);d$warnings <- as.list(issues)
  list(diagnostics=d,issues=issues)
}

audit_rstan_diagnostics <- function(model) {
  if (!inherits(model$fit,'stanfit')) stop('Saved posterior is not an rstan stanfit; backend needs an explicit reviewer')
  for (pkg in c('rstan','posterior')) if (!requireNamespace(pkg,quietly=TRUE)) stop('Required diagnostic package unavailable: ',pkg)
  draws <- rstan::extract(model$fit,permuted=FALSE,inc_warmup=FALSE)
  if (length(dim(draws))!=3L || dim(draws)[1]<4L || dim(draws)[2]<2L ||
      dim(draws)[3]<1L || any(!is.finite(draws))) stop('Saved posterior draws are missing, nonfinite, or dimensionally invalid')
  parameters <- as.data.frame(posterior::summarise_draws(posterior::as_draws_array(draws),'rhat','ess_bulk','ess_tail'))
  np <- rstan::get_sampler_params(model$fit,inc_warmup=FALSE)
  args <- model$fit@stan_args
  if (length(np)!=dim(draws)[2] || length(args)!=dim(draws)[2]) stop('Sampler/chain metadata dimensions differ from posterior')
  chain <- do.call(rbind,lapply(seq_along(np),function(i) {
    x<-np[[i]]
    if (!is.matrix(x) || !all(c('divergent__','treedepth__','energy__') %in% colnames(x)) ||
        any(!is.finite(x[,c('divergent__','treedepth__','energy__'),drop=FALSE]))) stop('Sampler transition diagnostics unavailable/nonfinite')
    limit<-args[[i]]$control$max_treedepth %||% 10L
    if (length(limit)!=1L || !is.finite(limit) || limit<1) stop('Invalid stored maximum tree depth')
    energy<-x[,'energy__']
    data.frame(chain=i,draws=nrow(x),divergences=sum(x[,'divergent__']),
      treedepth_hits=sum(x[,'treedepth__']>=limit),depth_limit=limit,
      ebfmi=mean(diff(energy)^2)/var(energy))
  }))
  audit_state_diagnostic_values(parameters,chain,dim(draws)[1])
}

audit_saved_state_fit <- function(task_dir,output_json) {
  if (!requireNamespace('jsonlite',quietly=TRUE) || !requireNamespace('digest',quietly=TRUE))
    stop('jsonlite and digest are required for a machine-readable saved-fit audit')
  if (file.exists(output_json)) stop('Refusing to overwrite an existing saved-fit proof')
  result <- list(schema_version=1L,status='REVIEW_REQUIRED',issues=list(),fit_sha256=NULL,
    model_data_sha256=NULL,model_data=data.frame(),expected_keys=data.frame(),eligibility_status='REVIEW_REQUIRED',
    diagnostics=list(converged=FALSE,warnings=list('Saved diagnostics not yet verified')),
    note=paste('Read-only audit of a saved fit against its declared snapshot and input artifacts.',
      'PASS is a structural/numerical gate, not proof of historical catchment accuracy, case ascertainment, or forecast calibration.',
      'No fitting performed. Priors fingerprinted without asserting unchanged data-dependent numeric defaults.'))
  issues <- character()
  tryCatch({
    task_dir <- normalizePath(task_dir,mustWork=TRUE);result$task_dir<-task_dir
    manifest_path<-file.path(dirname(task_dir),'manifest.json')
    manifest<-jsonlite::fromJSON(manifest_path,simplifyVector=FALSE)
    jobs<-Filter(function(x) identical(x$task,basename(task_dir)),manifest$jobs)
    if (length(jobs)!=1L) stop('Task must match exactly one declared job in its parent manifest')
    job<-jobs[[1]];prefix<-job$prefix;result$prefix<-prefix
    out<-file.path(task_dir,'spline_results')
    fits<-list.files(out,pattern='_brm\\.[Rr][Dd][Ss]$',full.names=TRUE)
    fit_path<-file.path(out,paste0(prefix,'_brm.Rds'))
    if (length(fits)!=1L || !identical(normalizePath(fits,mustWork=TRUE),normalizePath(fit_path,mustWork=TRUE)))
      stop('Task must contain exactly its declared saved fit')
    result$fit_sha256<-digest::digest(file=fit_path,algo='sha256');result$fit_file<-fit_path
    settings<-read.csv(file.path(out,paste0(prefix,'_analysis_settings.csv')),stringsAsFactors=FALSE,check.names=FALSE,
      colClasses='character',na.strings=character())
    if (nrow(settings)!=1L) stop('Expected exactly one saved settings row')
    settings<-as.list(settings[1,,drop=FALSE]);result$settings<-settings
    snapshot<-file.path(dirname(task_dir),'scripts','functions.R')
    snapshot_hash<-digest::digest(file=snapshot,algo='sha256')
    if (!identical(snapshot_hash,manifest$source_sha256[['functions.R']])) stop('Catchment function snapshot hash differs from manifest')
    result$catchment_snapshot_sha256<-snapshot_hash
    pop_path<-file.path(out,paste0(prefix,'_population_used.csv'))
    population<-read.csv(pop_path,stringsAsFactors=FALSE,check.names=FALSE)
    result$population_artifact_sha256<-digest::digest(file=pop_path,algo='sha256')
    grid<-audit_expected_state_grid(job,settings,population,load_saved_catchment_functions(snapshot))
    result$expected_keys<-grid$expected_keys
    model<-readRDS(fit_path)
    signature<-audit_state_formula(model)
    result$formula<-signature$formula;result$family<-signature$family;result$link<-signature$link
    result$prior_sha256<-digest::digest(model$prior,algo='sha256')
    data<-audit_state_data(model$data);result$model_data<-data
    result$model_data_sha256<-digest::digest(as.character(jsonlite::toJSON(data,dataframe='rows',digits=17,auto_unbox=TRUE)),algo='sha256',serialize=FALSE)
    if (!setequal(state_fit_key(data),state_fit_key(grid$expected_keys))) stop('Saved fitted data omit or add eligible state/year rows')
    p<-grid$population[match(state_fit_key(data),state_fit_key(grid$population)),,drop=FALSE]
    if (any(data$population!=p$population)) stop('Saved model populations differ from the recorded population artifact')
    result$eligibility_status<-'PASS'
    diagnostic<-audit_rstan_diagnostics(model)
    result$diagnostics<-diagnostic$diagnostics;issues<-c(issues,diagnostic$issues)
    if (!identical(result$fit_sha256,digest::digest(file=fit_path,algo='sha256'))) stop('Saved fit changed during audit')
  },error=function(e) {issues<<-c(issues,conditionMessage(e))})
  result$issues<-as.list(unique(issues))
  result$status<-if (!length(issues) && identical(result$eligibility_status,'PASS') && isTRUE(result$diagnostics$converged)) 'PASS' else 'REVIEW_REQUIRED'
  dir.create(dirname(output_json),recursive=TRUE,showWarnings=FALSE)
  jsonlite::write_json(result,output_json,pretty=TRUE,auto_unbox=TRUE,dataframe='rows',digits=17,na='null',null='null')
  cat('Saved-fit audit:',result$status,'\nProof:',normalizePath(output_json),'\n')
  if(length(issues))cat(paste(issues,collapse='\n'),'\n')
  invisible(result)
}

if (sys.nframe()==0L) {
  args<-commandArgs(TRUE)
  if (length(args)!=2L) stop('Usage: audit_saved_state_fit.R TASK_DIR OUTPUT_JSON')
  result<-audit_saved_state_fit(args[1],args[2])
  quit(status=if(identical(result$status,'PASS'))0L else 1L)
}
