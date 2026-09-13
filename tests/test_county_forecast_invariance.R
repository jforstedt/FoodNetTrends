#!/usr/bin/env Rscript
# Standalone synthetic numerical gate. No FoodNet data or historical fits read.
.this<-sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1])
.helper<-file.path(dirname(.this),'county_forecast_model.R')
if (!file.exists(.helper)) .helper<-file.path('scripts','county_forecast_model.R')
source(.helper)
args<-commandArgs(TRUE)
if (length(args)>1L) stop('Usage: test_county_forecast_invariance.R [REPORT_DIR]')
out<-if(length(args)) args[1] else tempfile('county-horizon-gate-')
dir.create(out,recursive=TRUE,showWarnings=FALSE)
if (file.exists(file.path(out,'status.txt'))) stop('Refusing existing gate status')
writeLines('RUNNING',file.path(out,'status.txt'))
# Fixed before observing these checks. Empirical-CDF tolerance uses a union
# DKW bound for two independent samples, not a tuned visual agreement threshold.
tolerance<-list(mean_in_sd=.02,sd_relative=.02,quantile_in_sd=.02,
  hyper_mean_relative=.02,draws=1000L,cdf_alpha=.001)
write.csv(as.data.frame(tolerance),file.path(out,'tolerances.csv'),row.names=FALSE)
tryCatch({
  if (packageVersion('INLA')!=package_version('26.08.07')) stop('Expected pinned INLA 26.08.07')
  INLA::inla.setOption(num.threads='2:1')
  # Exact covariance from independent increments, centered only on training.
  covariance<-function(nt,ntrain) {
    B<-outer(seq_len(nt),seq_len(nt-1L),function(i,j)as.numeric(j<i))
    B<-sweep(B,2,colMeans(B[seq_len(ntrain),,drop=FALSE]),'-')
    tcrossprod(B)/rw1_training_scale(ntrain)
  }
  for(ntrain in c(3L,8L,13L)) {
    a<-covariance(ntrain+1L,ntrain);b<-covariance(ntrain+3L,ntrain)
    stopifnot(max(abs(a-b[seq_len(ntrain+1L),seq_len(ntrain+1L)]))<1e-12,
      abs(exp(mean(log(diag(a)[seq_len(ntrain)])))-1)<1e-12)
    short<-county_forecast_specification(seq_len(ntrain+1L),ntrain)
    long<-county_forecast_specification(seq_len(ntrain+3L),ntrain)
    stopifnot(identical(short$innovation_sd_upper,long$innovation_sd_upper),
      all(long$constraint$A[1,(ntrain+1L):(ntrain+3L)]==0))
  }
  set.seed(12);adj<-matrix(0,12,12)
  for(i in c(1:5,7:11)){adj[i,i+1]<-1;adj[i+1,i]<-1}
  d<-expand.grid(area=1:12,year=2001:2011);d<-d[order(d$area,d$year),]
  d$fips<-sprintf('%05d',d$area);d$state<-factor(ifelse(d$area<=6,'AA','BB'));d$state_id<-as.integer(d$state)
  d$population<-10000+d$area*500
  d$count<-rnbinom(nrow(d),mu=d$population*exp(log(.0002)+.04*(d$year-2005)),size=12)
  obj<-function(end)list(data=d[d$year<=end,],adj=adj,ids=sprintf('%05d',1:12),years=2001:end)
  original<-d;results<-list()
  for(variant in c('spatial','iid'))for(time in c(FALSE,TRUE)) {
    name<-paste(variant,if(time)'county_time' else 'baseline',sep='_')
    short<-obj(2009);long<-obj(2011)
    # Later outcomes are deliberately impossible: they must be ignored.
    long$data$count[long$data$year>2008]<-999999L
    a<-fit_county_forecast(short,variant,2008,county_time=time,threads=2)
    b<-fit_county_forecast(long,variant,2008,county_time=time,threads=2)
    key<-function(z)paste(z$fips,z$year,sep='|')
    ix<-match(key(short$data),key(long$data));stopifnot(!anyNA(ix))
    sa<-a$summary.linear.predictor;sb<-b$summary.linear.predictor[ix,,drop=FALSE]
    stopifnot(nrow(sa)==nrow(short$data),all(is.finite(sa$sd)),all(sa$sd>0))
    row<-data.frame(model=name,max_mean_in_sd=max(abs(sa$mean-sb$mean)/sa$sd),
      max_sd_relative=max(abs(sa$sd-sb$sd)/sa$sd),
      max_quantile_in_sd=max(abs(as.matrix(sa[c('0.025quant','0.5quant','0.975quant')])-
        as.matrix(sb[c('0.025quant','0.5quant','0.975quant')]))/sa$sd),
      max_hyper_mean_relative=max(abs(a$summary.hyperpar$mean-b$summary.hyperpar$mean)/abs(a$summary.hyperpar$mean)))
    stopifnot(row$max_mean_in_sd<tolerance$mean_in_sd,row$max_sd_relative<tolerance$sd_relative,
      row$max_quantile_in_sd<tolerance$quantile_in_sd,row$max_hyper_mean_relative<tolerance$hyper_mean_relative)
    for(fit in list(a,b)) {
      nt<-attr(fit,'forecast_specification')$domain_years
      configs<-fit$misc$configs;A<-configs$constr$A;contents<-configs$contents
      for(component in c('time',if(time)'county_time')) {
        index<-match(component,contents$tag)
        start<-contents$start[index]-configs$Npred;size<-contents$length[index]
        stopifnot(size%%nt==0L)
        for(rep in seq_len(size/nt)) {
          wanted<-numeric(ncol(A));wanted[start+(rep-1L)*nt+0:7]<-1/8
          stopifnot(any(rowSums(abs(sweep(A,2,wanted,'-')))<1e-12))
        }
      }
      # Independently corrected marginal means need not obey a linear constraint
      # exactly. Check the actual latent constraints and conditional means instead.
      stopifnot(max(vapply(configs$config,function(z)max(abs(A%*%z$mean-configs$constr$e)),numeric(1)))<1e-6)
    }
    ia<-which(short$data$year==2009);ib<-which(long$data$year==2009)
    pa<-sample_county_forecast(a,ia,draws=tolerance$draws,seed=41001L)
    pb<-sample_county_forecast(b,ib,draws=tolerance$draws,seed=51001L)
    cdf_distance<-function(x,y) {at<-sort(unique(c(x,y)));max(abs(ecdf(x)(at)-ecdf(y)(at)))}
    row$aggregate_mu_cdf_distance<-cdf_distance(colSums(pa$mu),colSums(pb$mu))
    row$aggregate_count_cdf_distance<-cdf_distance(colSums(pa$replicated),colSums(pb$replicated))
    row$cdf_tolerance<-2*sqrt(log(4/tolerance$cdf_alpha)/(2*tolerance$draws))
    stopifnot(row$aggregate_mu_cdf_distance<row$cdf_tolerance,row$aggregate_count_cdf_distance<row$cdf_tolerance)
    row$check<-name;row$pass<-TRUE;row$status<-'PASS';results[[name]]<-row
    write.csv(do.call(rbind,results),file.path(out,'checks.csv'),row.names=FALSE)
    cat('PASS',name,'training/one-year predictive invariance after appending two future years\n')
  }
  stopifnot(identical(original,d))
  writeLines(c('HORIZON_INVARIANCE_PASS',
    'Exact prior covariance and replicated training constraints checked.',
    'Actual spatial/IID baseline and county-time fits preserve shared marginal/joint predictions within recorded tolerances.',
    'Numerical consistency only; predictive accuracy and posterior approximation calibration remain separate gates.'),file.path(out,'status.txt'))
  writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt'))
  cat('HORIZON_INVARIANCE_PASS:',normalizePath(out),'\n')
},error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
