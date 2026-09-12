#!/usr/bin/env Rscript
# Synthetic executable/offset/spatial smoke checks, not Daniel's model or a
# validated county analysis. Reads no FoodNet input data and never calls Stan.

make_smoke_data <- function(seed = 20260912L) {
  set.seed(seed)
  dat <- expand.grid(area = seq_len(17L), time = seq_len(8L))
  dat$population <- 40000 + dat$area * 2100 + dat$time * 700
  spatial <- c(seq(-0.35, 0.35, length.out = 8), seq(0.25, -0.25, length.out = 8), 0)
  dat$true_rate <- exp(log(0.0004) + spatial[dat$area] + 0.04 * (dat$time - 4.5))
  dat$count <- rnbinom(nrow(dat), size = 12, mu = dat$population * dat$true_rate)
  dat
}

write_smoke_graph <- function(path) {
  # Two disconnected chains of eight nodes and one isolated node. These are
  # invented areas, not real counties or a geographic adjacency crosswalk.
  neighbours <- lapply(seq_len(17L), function(i) {
    group <- if (i <= 8L) 1:8 else if (i <= 16L) 9:16 else 17L
    intersect(c(i - 1L, i + 1L), group)
  })
  writeLines(c("17", vapply(seq_len(17L), function(i)
    paste(c(i, length(neighbours[[i]]), neighbours[[i]]), collapse = " "), character(1))), path)
  invisible(neighbours)
}

check_summary <- function(x, label, expected_rows = NULL) {
  cols <- c("mean", "sd", "0.025quant", "0.5quant", "0.975quant")
  if (is.null(x) || !all(cols %in% names(x)) ||
      (!is.null(expected_rows) && nrow(x) != expected_rows) ||
      !all(is.finite(as.matrix(x[, cols, drop = FALSE]))) ||
      any(x$sd < 0) || any(x$`0.025quant` > x$`0.5quant`) ||
      any(x$`0.5quant` > x$`0.975quant`)) stop("Invalid posterior summary: ", label)
}

run_smoke <- function(outdir, threads = 2L) {
  if (!is.finite(threads) || threads < 1L || threads > 64L || threads != as.integer(threads))
    stop("threads must be an integer from 1 to 64")
  if (dir.exists(outdir) && length(list.files(outdir, all.files = TRUE, no.. = TRUE)))
    stop("Report directory must be new or empty")
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
  outdir <- normalizePath(outdir, mustWork = TRUE)
  writeLines("RUNNING", file.path(outdir, "status.txt"))
  on.exit(writeLines(capture.output(sessionInfo()), file.path(outdir, "sessionInfo.txt")), add = TRUE)
  started <- proc.time()[["elapsed"]]
  tryCatch({
    if (!requireNamespace("INLA", quietly = TRUE)) stop("INLA is not installed in this R environment")
    # Bound both numerical-library and INLA worker counts; no automatic downloads
    # or inla.binary.install() calls are allowed during the test.
    Sys.setenv(OPENBLAS_NUM_THREADS = "1", MKL_NUM_THREADS = "1", OMP_NUM_THREADS = as.character(threads))
    INLA::inla.setOption(num.threads = paste0(threads, ":1"))
    writeLines(c(paste("R:", R.version.string), paste("INLA:", packageVersion("INLA")),
                 paste("threads:", threads), "data: synthetic only",
                 "validation scope: executable, offset, finite spatial/temporal summaries",
                 "NOT validation of FoodNet results or equivalence to Daniel's spline model"),
               file.path(outdir, "environment.txt"))
    dat <- make_smoke_data()
    write.csv(dat, file.path(outdir, "synthetic_data.csv"), row.names = FALSE)
    graph_path <- file.path(outdir, "synthetic.graph")
    write_smoke_graph(graph_path)
    graph <- INLA::inla.read.graph(graph_path)
    if (graph$n != 17L) stop("Graph node count mismatch")

    # First check: under a flat prior on log(rate), the intercept-only Poisson
    # rate posterior is Gamma(sum(y), rate=sum(population)). This independently
    # checks the population offset and posterior scale against an analytic answer.
    cat("Fitting analytic Poisson offset check...\n")
    baseline <- INLA::inla(count ~ 1 + offset(log(population)), data = dat,
      family = "poisson", control.fixed = list(mean.intercept = 0, prec.intercept = 0),
      control.predictor = list(compute = TRUE), num.threads = paste0(threads, ":1"))
    check_summary(baseline$summary.fixed, "Poisson intercept", 1L)
    expected <- c(mean = digamma(sum(dat$count)) - log(sum(dat$population)),
                  sd = sqrt(trigamma(sum(dat$count))),
                  lower = log(qgamma(0.025, shape = sum(dat$count), rate = sum(dat$population))),
                  upper = log(qgamma(0.975, shape = sum(dat$count), rate = sum(dat$population))))
    actual <- unlist(baseline$summary.fixed[1, c("mean", "sd", "0.025quant", "0.975quant")], use.names = FALSE)
    comparison <- data.frame(quantity = names(expected), analytic = unname(expected),
                             inla = actual, absolute_error = abs(actual - expected), tolerance = 0.02)
    write.csv(comparison, file.path(outdir, "poisson_analytic_check.csv"), row.names = FALSE)
    if (any(comparison$absolute_error > comparison$tolerance)) stop("Analytic offset check failed")

    # Second check: explicitly chosen test priors for an exploratory negative
    # binomial BYM2 + RW1 model. This is not a translation of the state spline.
    cat("Fitting synthetic negative-binomial BYM2 + RW1 check...\n")
    f <- INLA::f
    formula <- count ~ 1 + offset(log(population)) +
      f(area, model = "bym2", graph = graph, scale.model = TRUE,
        constr = TRUE, adjust.for.con.comp = TRUE,
        hyper = list(prec = list(prior = "pc.prec", param = c(1, 0.01)),
                     phi = list(prior = "pc", param = c(0.5, 0.5)))) +
      f(time, model = "rw1", scale.model = TRUE, constr = TRUE,
        hyper = list(prec = list(prior = "pc.prec", param = c(0.5, 0.01))))
    writeLines(capture.output(print(formula)), file.path(outdir, "synthetic_formula.txt"))
    fit <- INLA::inla(formula, data = dat, family = "nbinomial",
      control.family = list(variant = 0, hyper = list(size = list(
        prior = "normal", param = c(log(12), 1), initial = log(12)))),
      control.fixed = list(mean.intercept = log(0.0004), prec.intercept = 0.01),
      control.predictor = list(compute = TRUE),
      control.compute = list(waic = TRUE, cpo = TRUE),
      num.threads = paste0(threads, ":1"))
    check_summary(fit$summary.fixed, "negative-binomial intercept", 1L)
    check_summary(fit$summary.hyperpar, "hyperparameters")
    check_summary(fit$summary.random$area, "BYM2 area effects")
    check_summary(fit$summary.random$time, "RW1 effects", 8L)
    check_summary(fit$summary.fitted.values, "fitted counts", nrow(dat))
    if (any(fit$summary.fitted.values$mean <= 0) || !is.finite(fit$waic$waic))
      stop("Nonpositive fitted count or invalid WAIC")
    if (length(fit$cpo$failure) != nrow(dat) || any(!is.finite(fit$cpo$failure)) || any(fit$cpo$failure != 0))
      stop("CPO computation failures; inspect retained INLA output")
    write.csv(fit$summary.fixed, file.path(outdir, "fixed_effects.csv"))
    write.csv(fit$summary.hyperpar, file.path(outdir, "hyperparameters.csv"))
    write.csv(fit$summary.random$area, file.path(outdir, "synthetic_area_effects.csv"), row.names = FALSE)
    write.csv(fit$summary.fitted.values, file.path(outdir, "fitted_counts.csv"), row.names = FALSE)
    saveRDS(list(poisson = baseline, spatial = fit), file.path(outdir, "synthetic_fits.rds"))
    writeLines(c("PASS", "Synthetic data only; no FoodNet model-equivalence claim.",
                 paste("Elapsed seconds:", round(proc.time()[["elapsed"]] - started, 2)),
                 paste("WAIC:", fit$waic$waic), "CPO computation failures: 0"), file.path(outdir, "status.txt"))
    cat("INLA SYNTHETIC SMOKE PASS:", outdir, "\n")
  }, error = function(e) {
    writeLines(c("FAIL", conditionMessage(e)), file.path(outdir, "status.txt"))
    stop(e)
  })
  invisible(outdir)
}

if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) < 1L || length(args) > 2L) stop("Usage: Rscript inla_smoke.R REPORTDIR [THREADS]")
  run_smoke(args[[1]], if (length(args) == 2L) as.numeric(args[[2]]) else 2L)
}
