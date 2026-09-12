#!/usr/bin/env Rscript
same_refit_data <- function(before, after) {
  # brms::update rewrites the descriptive data_name attribute. It is not data.
  attr(before, "data_name") <- NULL
  attr(after, "data_name") <- NULL
  isTRUE(all.equal(before, after, tolerance=0, check.attributes=TRUE))
}
args <- commandArgs(TRUE)
stopifnot(length(args)==3L)
source_dir <- args[1]; destination <- args[2]; key <- args[3]
source(file.path(destination, 'functions.R'))
results <- file.path(destination, 'spline_results')
old_path <- file.path(source_dir, 'spline_results', paste0(key, '_brm.Rds'))
new_path <- file.path(results, paste0(key, '_brm.Rds'))
if(file.exists(new_path)) stop('Comparison fit already exists; refusing overwrite')
old <- readRDS(old_path)
stopifnot(inherits(old$fit, 'stanfit'))
sim <- old$fit@sim
control <- old$fit@stan_args[[1]]$control
stopifnot(sim$chains==6, sim$iter==10001, control$max_treedepth==15)
control$adapt_delta <- 0.999
cat('Refitting saved model:', key, '\nOnly requested sampler change: adapt_delta=0.999\n')
checkpoint_dir <- file.path(destination, 'checkpoints')
dir.create(checkpoint_dir, showWarnings=FALSE)
checkpoint <- file.path(checkpoint_dir, paste0(key, '.rds'))
if (file.exists(checkpoint)) {
  cat('Using saved sampling checkpoint; no new sampling\n')
  new <- readRDS(checkpoint)
} else {
  if (identical(Sys.getenv("FOODNET_CHECKPOINT_ONLY"), "1")) stop("Required checkpoint missing; sampling is disabled")
  new <- update(old, recompile=FALSE, chains=sim$chains, iter=sim$iter,
                warmup=sim$warmup, thin=sim$thin, seed=123, cores=12, control=control)
  saveRDS(new, paste0(checkpoint, '.tmp'))
  if (!file.rename(paste0(checkpoint, '.tmp'), checkpoint)) stop('Cannot finalize checkpoint')
}
checks <- c(same_data=same_refit_data(old$data,new$data),
            same_priors=identical(old$prior,new$prior),
            same_stan_code=identical(brms::stancode(old),brms::stancode(new)))
writeLines(c(capture.output(print(checks)),
             'Full data comparison (including descriptive attributes):',
             capture.output(print(all.equal(old$data,new$data,tolerance=0)))),
           file.path(destination,paste0(key,'_identity_check.txt')))
if (!all(checks)) stop('Model identity check failed; completed sampling checkpoint preserved. See identity_check.txt')
saveRDS(new, new_path)
CHECK_CONVERGENCE(new, key, results)
settings_path <- file.path(source_dir, 'spline_results', paste0(key, '_analysis_settings.csv'))
settings <- read.csv(settings_path, stringsAsFactors=FALSE)
file.copy(settings_path, file.path(results, basename(settings_path)), overwrite=FALSE)
write.csv(data.frame(adapt_delta=0.999, chains=sim$chains, iterations=sim$iter,
                     warmup=sim$warmup, seed=123, same_data=TRUE, same_priors=TRUE,
                     same_stan_code=TRUE), file.path(results,paste0(key,'_refit_settings.csv')),row.names=FALSE)
draws <- LINPREAD_DRAW_FN(new$data, new)
catch <- CATCHMENT(draws)
write.csv(LINPRED_TO_CATCHIR(catch),file.path(results,paste0(key,'_IRCatch.csv')),row.names=FALSE)
write.csv(LINPRED_TO_SITEIR(draws),file.path(results,paste0(key,'_IRSite.csv')),row.names=FALSE)
irr_suffix <- paste0('_EstIRRCatch_',settings$baseline_start,'_',settings$baseline_end,'.csv')
IR_COMP_CATCH(catch,settings$baseline_start,settings$baseline_end,file.path(results,paste0(key,irr_suffix)))
# Compare published numerical results by year (and state for site estimates).
for(suffix in c('_IRCatch.csv','_IRSite.csv',irr_suffix)) {
  before <- read.csv(file.path(source_dir,'spline_results',paste0(key,suffix)))
  after <- read.csv(file.path(results,paste0(key,suffix)))
  join <- intersect(c('year','state'),names(after))
  stopifnot(!anyDuplicated(before[join]),!anyDuplicated(after[join]))
  m <- merge(before,after,by=join,suffixes=c('_old','_new'))
  stopifnot(nrow(m)==nrow(before),nrow(m)==nrow(after))
  for(field in intersect(c('population','raw_count','raw_ir'),names(after)))
    stopifnot(isTRUE(all.equal(m[[paste0(field,'_old')]],m[[paste0(field,'_new')]])))
  fields <- intersect(c('median_ir','lower_hdi_ir','upper_hdi_ir','relative_risk_est',
                        'relative_risk_lower_hdi','relative_risk_upper_hdi','percent_change_est'),names(after))
  for(field in fields) {
    a <- m[[paste0(field,'_old')]]; b <- m[[paste0(field,'_new')]]
    m[[paste0(field,'_difference')]] <- b-a
    m[[paste0(field,'_percent_difference')]] <- ifelse(a!=0,100*(b-a)/abs(a),NA_real_)
  }
  if('relative_risk_lower_hdi'%in%names(after)) {
    category <- function(lo,hi) ifelse(lo>1,'increase',ifelse(hi<1,'decrease','includes_1'))
    m$old_interval_category <- category(m$relative_risk_lower_hdi_old,m$relative_risk_upper_hdi_old)
    m$new_interval_category <- category(m$relative_risk_lower_hdi_new,m$relative_risk_upper_hdi_new)
    m$interval_category_changed <- m$old_interval_category != m$new_interval_category
  }
  write.csv(m,file.path(destination,'comparisons',paste0(key,suffix)),row.names=FALSE)
}
writeLines('SUCCESS',file.path(destination,paste0(key,'.status')))
