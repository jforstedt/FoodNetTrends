#!/usr/bin/env Rscript
# Retrospective time-block forecast evaluation; never train on held-out counts.
training_panel <- function(d,cutoff) {
  if(length(cutoff)!=1||!is.finite(cutoff)||!any(d$year>cutoff)||length(unique(d$year[d$year<=cutoff]))<3)stop('Invalid training cutoff')
  d$count[d$year>cutoff]<-NA_real_;d
}
forecast_groups <- function(d,heldout,cutoff) {
  groups<-zero_groups(d[heldout,])
  totals<-tapply(d$count[d$year<=cutoff],d$fips[d$year<=cutoff],sum)
  train<-as.numeric(totals[d$fips[heldout]])
  if(anyNA(train))stop('Missing county training histories')
  groups$training_cases<-as.character(cut(train,c(-1,0,5,20,100,Inf),
      labels=c('01 zero','02 1-5','03 6-20','04 21-100','05 101+')))
  groups
}
log_average <- function(x) {m<-max(x);if(!is.finite(m))return(-Inf);m+log(mean(exp(x-m)))}

forecast_diagnostics <- function(fit,d,out,cutoff=2016L,draws=4000L) {
  heldout<-which(d$year>cutoff);truth<-d$count[heldout];n<-length(heldout)
  if(n==0||anyNA(truth)||draws<100L)stop('Invalid evaluation inputs')
  groups<-forecast_groups(d,heldout,cutoff)
  mu<-replicated<-log_density<-pzero<-lower_cdf<-upper_cdf<-matrix(NA_real_,n,draws)
  for(start in seq.int(1L,draws,by=100L)) {
    jj<-start:min(start+99L,draws)
    samples<-INLA::inla.posterior.sample(length(jj),fit,selection=list(Predictor=heldout),
      seed=as.integer(20260916L+start),num.threads='1:1',skew.corr=FALSE)
    set.seed(20270916L+start)
    for(k in seq_along(samples)) {
      s<-samples[[k]];ids<-as.integer(sub('^Predictor:','',rownames(s$latent)))
      if(anyNA(ids)||length(ids)!=n||anyDuplicated(ids)||!setequal(ids,heldout))stop('Unexpected forecast indexing')
      m<-exp(as.numeric(s$latent[match(heldout,ids),1]));ix<-grep('size for',names(s$hyperpar),fixed=TRUE)
      if(length(ix)!=1)stop('Missing NB size')
      size<-as.numeric(s$hyperpar[ix]);if(any(!is.finite(m))||!is.finite(size)||size<=0)stop('Invalid forecast parameters')
      j<-jj[k];mu[,j]<-m;replicated[,j]<-rnbinom(n,mu=m,size=size)
      log_density[,j]<-dnbinom(truth,mu=m,size=size,log=TRUE)
      pzero[,j]<-exp(-size*log1p(m/size))
      lower_cdf[,j]<-pnbinom(truth-1,mu=m,size=size);upper_cdf[,j]<-pnbinom(truth,mu=m,size=size)
    }
    cat('Forecast draws:',max(jj),'of',draws,'\n')
  }
  if(any(!is.finite(replicated))||any(!is.finite(pzero)))stop('Invalid predictive draws')
  q<-t(apply(replicated,1,quantile,probs=c(.025,.25,.5,.75,.975),names=FALSE))
  lp<-apply(log_density,1,log_average);if(any(!is.finite(lp)))stop('Nonfinite predictive log scores')
  # Relative Monte Carlo SE of the estimated predictive density, not data uncertainty.
  relse<-apply(log_density,1,function(x){w<-exp(x-max(x));sd(w)/sqrt(length(w))/mean(w)})
  set.seed(20280916L);pit<-rowMeans(lower_cdf)+runif(n)*(rowMeans(upper_cdf)-rowMeans(lower_cdf))
  cell<-d[heldout,c('fips','state','year','population')];cell$observed<-truth
  cell$training_cases_band<-groups$training_cases;cell$mean_expected<-rowMeans(mu)
  cell$lower95<-q[,1];cell$lower50<-q[,2];cell$median<-q[,3];cell$upper50<-q[,4];cell$upper95<-q[,5]
  cell$log_predictive_density<-lp;cell$density_relative_mcse<-relse
  cell$predicted_zero_probability<-rowMeans(pzero);cell$zero_brier<-(cell$predicted_zero_probability-as.integer(truth==0))^2
  cell$covered95<-truth>=q[,1]&truth<=q[,5];cell$covered50<-truth>=q[,2]&truth<=q[,4];cell$randomized_pit<-pit
  write.csv(cell,file.path(out,'heldout_cells_INTERNAL.csv'),row.names=FALSE)
  aggregate_report<-list();score_report<-list()
  for(kind in names(groups)) {
    g<-groups[[kind]];lev<-sort(unique(g))
    totals<-rowsum(replicated,g,reorder=TRUE);zeros<-rowsum(1L*(replicated==0),g,reorder=TRUE)
    tq<-t(apply(totals,1,quantile,probs=c(.025,.5,.975),names=FALSE));zq<-t(apply(zeros,1,quantile,probs=c(.025,.5,.975),names=FALSE))
    observed<-as.numeric(rowsum(truth,g,reorder=TRUE));oz<-as.numeric(rowsum(as.integer(truth==0),g,reorder=TRUE))
    aggregate_report[[kind]]<-data.frame(grouping=kind,group=lev,cells=as.integer(table(factor(g,levels=lev))),
      observed_total=observed,expected_total=rowMeans(rowsum(mu,g,reorder=TRUE)),total_lower95=tq[,1],total_median=tq[,2],total_upper95=tq[,3],
      observed_zeros=oz,expected_zeros=rowMeans(rowsum(pzero,g,reorder=TRUE)),zero_lower95=zq[,1],zero_median=zq[,2],zero_upper95=zq[,3],
      zero_upper_tail=rowMeans(zeros>=oz),row.names=NULL)
    score_report[[kind]]<-do.call(rbind,lapply(lev,function(label){ix<-which(g==label);data.frame(grouping=kind,group=label,cells=length(ix),
      sum_log_predictive_density=sum(lp[ix]),mean_absolute_error=mean(abs(cell$mean_expected[ix]-truth[ix])),
      mean_zero_brier=mean(cell$zero_brier[ix]),coverage95=mean(cell$covered95[ix]),coverage50=mean(cell$covered50[ix]),
      mean_interval95_width=mean(cell$upper95[ix]-cell$lower95[ix]),max_density_relative_mcse=max(relse[ix]))}))
  }
  agg<-do.call(rbind,aggregate_report);scores<-do.call(rbind,score_report)
  write.csv(agg,file.path(out,'heldout_aggregate_checks_INTERNAL.csv'),row.names=FALSE)
  write.csv(scores,file.path(out,'heldout_scores_INTERNAL.csv'),row.names=FALSE)
  pdf(file.path(out,'forecast_checks.pdf'),width=10,height=7)
  for(kind in c('year','state','training_cases')) {
    z<-agg[agg$grouping==kind,];par(mar=c(5,10,3,1));yy<-seq_len(nrow(z))
    plot(z$zero_median/z$cells,yy,xlim=range(c(z$zero_lower95,z$zero_upper95,z$observed_zeros)/z$cells),yaxt='n',ylab='',
      xlab='Fraction of held-out county/year cells with zero cases',main=paste(kind,'forecast zero check'),pch=16,col='steelblue')
    segments(z$zero_lower95/z$cells,yy,z$zero_upper95/z$cells,yy,col='steelblue');points(z$observed_zeros/z$cells,yy,pch=4,col='firebrick')
    axis(2,at=yy,labels=z$group,las=1);legend('bottomright',c('Predicted median and 95% interval','Observed'),col=c('steelblue','firebrick'),pch=c(16,4),bty='n')
  }
  par(mar=c(4,4,3,1));hist(pit,breaks=seq(0,1,.1),main='Randomized predictive PIT (descriptive)',xlab='PIT');abline(h=n/10,lty=2)
  dev.off()
  invisible(cell)
}

run_forecast <- function(audit,dest,name,threads=8L,draws=4000L,cutoff=2016L,expected_production=TRUE) {
  if(!name%in%c('spatial_baseline','iid_baseline','spatial_county_time','iid_county_time'))stop('Invalid model')
  if(dir.exists(dest))stop('Existing destination; refusing overwrite')
  out<-file.path(dest,'reports');dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
  tryCatch({
    if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected pinned INLA')
    INLA::inla.setOption(num.threads=paste0(threads,':1'))
    panel<-file.path(audit,'county_panel_INTERNAL.rds');before<-tools::md5sum(panel)
    obj<-validate_panel(audit,expected_production=expected_production);training<-obj;training$data<-training_panel(obj$data,cutoff)
    heldout<-obj$data$year>cutoff
    stopifnot(all(is.na(training$data$count[heldout])),identical(training$data$count[!heldout],as.numeric(obj$data$count[!heldout])))
    variant<-if(startsWith(name,'spatial'))'spatial' else 'iid';time<-endsWith(name,'county_time')
    write.csv(data.frame(model=name,train_start=min(obj$data$year),train_end=cutoff,test_start=cutoff+1,test_end=max(obj$data$year),
      training_cells=sum(!heldout),heldout_cells=sum(heldout),draws=draws,heldout_counts_masked=TRUE),file.path(out,'split.csv'),row.names=FALSE)
    # No full-data fits or tuned hyperparameter estimates are supplied to this call.
    fit<-sensitivity_fit(training,variant,county_sd=1,county_time=time,threads=threads,predictor_link=1)
    saveRDS(fit,file.path(dest,'fit_INTERNAL.rds'))
    write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'));write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'))
    writeLines(attr(fit,'sensitivity_formula'),file.path(out,'formula.txt'))
    forecast_diagnostics(fit,obj$data,out,cutoff,draws)
    if(!identical(before,tools::md5sum(panel)))stop('Panel changed')
    write.csv(data.frame(file=panel,md5=unname(before)),file.path(out,'panel_checksum.csv'),row.names=FALSE)
    writeLines(c('FORECAST_CHECK_COMPLETE','Training outcomes stop at cutoff; later outcomes used only for scoring.',
      'Retrospective single-origin test; these years previously informed model exploration.',
      'Known future population denominators and fixed graph/year domain are conditioned upon.',
      'Cell log scores are marginal, not a joint multi-year sequence log score.',
      'No production model or dashboard changes.'),file.path(out,'status.txt'))
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'fit_county_pilot.R'));source(file.path(here,'diagnose_saved_county_pilot.R'));source(file.path(here,'county_sensitivity.R'));if(length(a)!=4L)stop('Usage: AUDIT DEST MODEL THREADS');run_forecast(a[1],a[2],a[3],as.integer(a[4]))}
