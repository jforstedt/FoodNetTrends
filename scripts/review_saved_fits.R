#!/usr/bin/env Rscript
# Read saved feature fits; never call brm/update or overwrite analysis outputs.
args <- commandArgs(TRUE)
if (length(args) != 2L) stop('Usage: review_saved_fits.R PROJECT_DIRECTORY REVIEW_DIRECTORY')
source_dir <- args[1]; review_dir <- args[2]
if (dir.exists(review_dir)) stop('Review directory already exists')
dir.create(review_dir, recursive=TRUE)
suppressPackageStartupMessages(library(brms))
keys <- c('STEC_nonO157', 'SALMONELLA_NONTYPHOIDAL', 'SALMONELLA_OTHER_SEROTYPES',
          'STEC_O157', 'STEC_NOT_SEROGROUPED', 'SALMONELLA_I_4_5_12_i_-')
report <- file.path(review_dir, 'review.txt')
sink(report, split=TRUE)
cat('READ-ONLY SAVED-FIT REVIEW\nSource:', normalizePath(source_dir), '\n')
failed <- character()
for (key in keys) {
  cat('\n==========', key, '==========\n')
  tryCatch({
    path <- file.path(source_dir, 'spline_results', paste0(key, '_brm.Rds'))
    cat('Model:', path, '\n')
    model <- readRDS(path)
    if (!inherits(model$fit, 'stanfit')) stop('This reviewer requires a saved rstan fit')
    fit <- model$fit
    np <- rstan::get_sampler_params(fit, inc_warmup=FALSE)
    depth_limit <- fit@stan_args[[1]]$control$max_treedepth
    if (is.null(depth_limit)) depth_limit <- 10L
    cat('Saved formula:\n'); print(model$formula)
    cat('Saved priors:\n'); print(model$prior)
    cat('Saved maximum tree depth:', depth_limit, '\n')
    chain <- do.call(rbind, lapply(seq_along(np), function(i) {
      x <- np[[i]]; energy <- x[, 'energy__']
      data.frame(chain=i, draws=nrow(x), divergences=sum(x[, 'divergent__']),
                 treedepth_hits=sum(x[, 'treedepth__'] >= depth_limit),
                 max_depth=max(x[, 'treedepth__']),
                 ebfmi=mean(diff(energy)^2)/var(energy),
                 mean_accept=mean(x[, 'accept_stat__']))
    }))
    print(chain, row.names=FALSE)
    write.csv(chain, file.path(review_dir, paste0(key, '_chains.csv')), row.names=FALSE)
    draws <- as.array(fit)
    # posterior supplies rank-normalized Rhat and separate bulk/tail ESS.
    if (requireNamespace('posterior', quietly=TRUE)) {
      diag <- posterior::summarise_draws(posterior::as_draws_array(draws),
                                       'rhat', 'ess_bulk', 'ess_tail')
      write.csv(as.data.frame(diag), file.path(review_dir, paste0(key, '_parameters.csv')), row.names=FALSE)
      finite_range <- function(x, fun) if (any(is.finite(x))) fun(x[is.finite(x)]) else NA_real_
      cat('Rank Rhat max:', finite_range(diag$rhat, max),
          ' Bulk ESS min:', finite_range(diag$ess_bulk, min),
          ' Tail ESS min:', finite_range(diag$ess_tail, min), '\n')
      cat('Nonfinite diagnostic counts:', sum(!is.finite(diag$rhat)),
          sum(!is.finite(diag$ess_bulk)), sum(!is.finite(diag$ess_tail)), '\n')
      print(as.data.frame(diag[order(diag$rhat, decreasing=TRUE), ])[1:min(10,nrow(diag)), ], row.names=FALSE)
    } else stop('posterior package unavailable; full diagnostics incomplete')
    # Flatten in the same chain-major order as sampler diagnostics.
    mat <- do.call(rbind, lapply(seq_len(dim(draws)[2]), function(i) draws[,i,]))
    divergent <- unlist(lapply(np, function(x) x[, 'divergent__'] == 1), use.names=FALSE)
    candidates <- grep('^(b_|sd_|sds_|shape$)', colnames(mat), value=TRUE)
    if (!length(candidates)) stop('No structural parameters found for divergence plots')
    loc <- do.call(rbind, lapply(candidates, function(p) {
      x <- mat[,p]; d <- x[divergent]; spread <- sd(x)
      data.frame(parameter=p, mean_shift_sd=if(length(d) && spread>0) (mean(d)-mean(x))/spread else NA_real_,
                 divergent_min_percentile=if(length(d)) mean(x <= min(d)) else NA_real_,
                 divergent_max_percentile=if(length(d)) mean(x <= max(d)) else NA_real_)
    }))
    loc <- loc[order(abs(loc$mean_shift_sd), decreasing=TRUE, na.last=TRUE), ]
    cat('Divergence locations (descriptive only; small counts do not establish cause):\n')
    print(head(loc, 12), row.names=FALSE)
    write.csv(loc, file.path(review_dir, paste0(key, '_divergence_locations.csv')), row.names=FALSE)
    chosen <- head(loc$parameter, 6)
    pdf(file.path(review_dir, paste0(key, '_diagnostic_plots.pdf')), width=11, height=8.5)
    tryCatch({
      par(mfrow=c(2,3))
      for (p in chosen) {
        matplot(draws[,,p], type='l', lty=1, main=p, xlab='Post-warmup iteration', ylab='Value')
        for (i in seq_along(np)) {
          idx <- which(np[[i]][,'divergent__'] == 1)
          points(idx, draws[idx,i,p], col='red', pch=4)
        }
      }
      par(mfrow=c(1,1))
      # Keep every divergent draw and a deterministic background sample.
      idx <- sort(unique(c(which(divergent), seq(1,nrow(mat),length.out=min(3000,nrow(mat))))))
      idx <- as.integer(idx)
      pairs(mat[idx,chosen,drop=FALSE], col=ifelse(divergent[idx], 'red', '#55555540'),
            pch=ifelse(divergent[idx], 4, 16), cex=.4, main=paste(key, ': red = divergent'))
    }, finally=dev.off())
    rm(model, fit, draws, mat); gc()
  }, error=function(e) { failed <<- c(failed, key); cat('REVIEW ERROR:', conditionMessage(e), '\n') })
}
cat('\nReview failures:', if(length(failed)) paste(failed,collapse=', ') else 'none', '\n')
cat('No models fitted or source files modified.\n')
sink()
if(length(failed)) quit(status=1)
