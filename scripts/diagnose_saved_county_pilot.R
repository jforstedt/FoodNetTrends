#!/usr/bin/env Rscript
# Read saved checkpoints only: this script never calls INLA::inla().
zero_groups <- function(d) {
  list(overall=rep('all',nrow(d)),state=as.character(d$state),year=as.character(d$year),
       state_year=paste(d$state,d$year,sep='|'),county=paste(d$state,d$fips,sep='|'),
       population=as.character(cut(d$population,c(0,5000,10000,25000,50000,100000,Inf),
         right=FALSE,labels=c('01 <5000','02 5000-9999','03 10000-24999','04 25000-49999','05 50000-99999','06 100000+'))))
}

summarize_zeros <- function(d,groups,replicates,expected) {
  do.call(rbind,lapply(names(groups),function(kind){
    g<-groups[[kind]];lev<-sort(unique(g));rr<-replicates[[kind]];ee<-expected[[kind]]
    observed<-as.numeric(rowsum(as.integer(d$count==0),g,reorder=TRUE))
    cells<-as.numeric(table(factor(g,levels=lev)))
    qs<-t(apply(rr,1,quantile,probs=c(.025,.5,.975),names=FALSE))
    tails<-rowMeans(rr>=observed)
    data.frame(grouping=kind,group=lev,cells=cells,observed_zeros=observed,
      observed_zero_fraction=observed/cells,replicated_lower=qs[,1],replicated_median=qs[,2],replicated_upper=qs[,3],
      expected_zeros_mean=rowMeans(ee),excess_observed_zeros=observed-rowMeans(ee),
      predictive_upper_tail=tails,tail_mcse=sqrt(tails*(1-tails)/ncol(rr)),draws=ncol(rr),row.names=NULL)
  }))
}

saved_diagnostics <- function(fit,d,out,draws=2000L,seed=20260914L) {
  n<-nrow(d);groups<-zero_groups(d)
  init<-function()lapply(groups,function(g)matrix(NA_real_,length(unique(g)),draws))
  replicated<-init();expected<-init()
  if(length(fit$waic$local.waic)!=n || any(!is.finite(fit$waic$local.waic)) ||
     abs(sum(fit$waic$local.waic)-fit$waic$waic)>1e-5)stop('Invalid pointwise WAIC')
  if(length(fit$cpo$cpo)!=n || length(fit$cpo$failure)!=n)stop('Missing pointwise CPO')
  # Batches bound memory; seeds and absence of skew correction match the documented approximation.
  for(start in seq.int(1L,draws,by=100L)) {
    indices<-start:min(start+99L,draws)
    samples<-INLA::inla.posterior.sample(length(indices),fit,selection=list(Predictor=seq_len(n)),
      seed=as.integer(seed+start),num.threads='1:1',skew.corr=FALSE)
    set.seed(seed+100000L+start)
    for(k in seq_along(samples)) {
      s<-samples[[k]];ids<-as.integer(sub('^Predictor:','',rownames(s$latent)))
      if(anyNA(ids)||length(ids)!=n||anyDuplicated(ids)||!setequal(ids,seq_len(n)))stop('Unexpected predictor indexing')
      mu<-exp(as.numeric(s$latent[match(seq_len(n),ids),1]))
      ix<-grep('size for',names(s$hyperpar),fixed=TRUE)
      if(length(ix)!=1)stop('Missing NB size')
      size<-as.numeric(s$hyperpar[ix])
      if(any(!is.finite(mu))||!is.finite(size)||size<=0)stop('Invalid posterior count parameters')
      zeros<-as.integer(rnbinom(n,mu=mu,size=size)==0)
      pzero<-exp(-size*log1p(mu/size))
      for(kind in names(groups)) {
        replicated[[kind]][,indices[k]]<-rowsum(zeros,groups[[kind]],reorder=TRUE)[,1]
        expected[[kind]][,indices[k]]<-rowsum(pzero,groups[[kind]],reorder=TRUE)[,1]
      }
    }
    cat('Posterior predictive draws:',max(indices),'of',draws,'\n')
  }
  result<-summarize_zeros(d,groups,replicated,expected)
  write.csv(result,file.path(out,'zero_checks_INTERNAL.csv'),row.names=FALSE)
  # No county/year case counts or cell-level predictive draws are exported.
  pdf(file.path(out,'zero_checks.pdf'),width=11,height=7)
  for(kind in c('state','year','population','county')) {
    z<-result[result$grouping==kind,]
    if(kind=='county')z<-head(z[order(z$excess_observed_zeros,decreasing=TRUE),],25)
    par(mar=c(5,11,3,1));y<-seq_len(nrow(z))
    plot(z$replicated_median/z$cells,y,xlim=range(c(z$replicated_lower,z$replicated_upper,z$observed_zeros)/z$cells),
      yaxt='n',ylab='',xlab='Fraction of county/year cells with zero cases',main=paste(kind,'zero-count check'),pch=16,col='steelblue')
    segments(z$replicated_lower/z$cells,y,z$replicated_upper/z$cells,y,col='steelblue')
    points(z$observed_zero_fraction,y,pch=4,col='firebrick',lwd=2)
    axis(2,at=y,labels=z$group,las=1,cex.axis=.7)
    legend('bottomright',c('Replicated median and 95% predictive interval','Observed'),col=c('steelblue','firebrick'),pch=c(16,4),bty='n',cex=.8)
  }
  dev.off()
  cpo<-fit$cpo$cpo;failure<-fit$cpo$failure
  valid<-is.finite(cpo)&cpo>0&is.finite(failure)&failure==0
  write.csv(data.frame(cells=n,waic=fit$waic$waic,cpo_failures=sum(!is.finite(failure)|failure!=0),
    cpo_nonpositive_or_nonfinite=sum(!is.finite(cpo)|cpo<=0),
    sum_log_cpo=if(all(valid))sum(log(cpo)) else NA_real_),file.path(out,'model_diagnostics.csv'),row.names=FALSE)
  list(waic=fit$waic$local.waic,log_cpo=ifelse(valid,log(pmax(cpo,.Machine$double.xmin)),NA_real_))
}

run_saved_diagnostics <- function(root,audit,out,draws=2000L) {
  if(dir.exists(out))stop('Refusing existing report directory')
  dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
  tryCatch({
    if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected INLA 26.08.07')
    if(is.na(draws)||draws<100L)stop('At least 100 draws required')
    panel<-file.path(audit,'county_panel_INTERNAL.rds')
    inputs<-c(panel,file.path(root,c('spatial','iid'),'fit_INTERNAL.rds'))
    if(!all(file.exists(inputs)))stop('Missing saved fit/panel; no refitting fallback')
    before<-tools::md5sum(inputs)
    if(readLines(file.path(audit,'reports/status.txt'))[1]!='INPUT_AUDIT_PASS')stop('Audit did not pass')
    d<-readRDS(panel);d<-d[order(d$fips,d$year),];rownames(d)<-NULL
    if(nrow(d)!=7776L||length(unique(d$fips))!=486L||!setequal(d$year,2004:2019)||
       anyNA(d[c('fips','state','year','population','count')])||any(d$population<=0)||
       any(!is.finite(d$population))||any(d$count<0)||any(d$count!=floor(d$count))||sum(d$count)!=122024)stop('Unexpected audited panel')
    points<-list()
    for(v in c('spatial','iid')) {
      old<-file.path(root,v,'reports')
      if(readLines(file.path(old,'status.txt'))[1]!='EXPLORATORY_FIT_COMPLETE')stop('Saved fit did not complete')
      checksum<-read.csv(file.path(old,'panel_checksum.csv'),stringsAsFactors=FALSE)
      if(nrow(checksum)!=1L||checksum$md5!=unname(before[1]))stop('Panel checksum differs from fitted panel')
      keys<-read.csv(file.path(old,'county_incidence_INTERNAL.csv'),colClasses=c(fips='character'))
      if(!identical(paste(keys$fips,keys$year),paste(d$fips,d$year)))stop('Saved predictor row order differs from panel')
      vd<-file.path(out,v);dir.create(vd);cat('Reading saved',v,'checkpoint; no fit performed\n')
      fit<-readRDS(file.path(root,v,'fit_INTERNAL.rds'))
      points[[v]]<-saved_diagnostics(fit,d,vd,draws);rm(fit);gc()
    }
    delta<-points$iid$waic-points$spatial$waic
    write.csv(data.frame(iid_minus_spatial_waic=sum(delta),
      naive_pointwise_se=sqrt(length(delta)*var(delta)),cells=length(delta),
      spatial_minus_iid_log_cpo=if(all(is.finite(c(points$iid$log_cpo,points$spatial$log_cpo))))sum(points$spatial$log_cpo-points$iid$log_cpo) else NA_real_),
      file.path(out,'paired_comparison.csv'),row.names=FALSE)
    for(kind in names(zero_groups(d))) {
      g<-zero_groups(d)[[kind]]
      write.csv(data.frame(group=sort(unique(g)),iid_minus_spatial_waic=as.numeric(rowsum(delta,g,reorder=TRUE))),
        file.path(out,paste0('waic_by_',kind,'_INTERNAL.csv')),row.names=FALSE)
    }
    if(!identical(before,tools::md5sum(inputs)))stop('Input checksums changed during diagnostics')
    write.csv(data.frame(file=inputs,md5=unname(before),unchanged=TRUE),file.path(out,'input_checksums.csv'),row.names=FALSE)
    writeLines(c('SAVED_DIAGNOSTICS_COMPLETE','No models refitted; saved inputs unchanged.',
      'Predictive intervals describe replicated zero counts, conditional on the fitted model.',
      'Upper tails are descriptive posterior predictive checks, not calibrated hypothesis tests.',
      'County rankings are exploratory and subject to multiple comparisons.',
      'Pointwise WAIC SE assumes independent contributions; spatial/temporal dependence limits its interpretation.',
      'CPO describes leave-one-cell-out prediction, not held-out counties or future years.',
      'Posterior draws use skew.corr=FALSE; same approximation as the original reports.'),file.path(out,'status.txt'))
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=4L)stop('Usage: FIT_ROOT AUDIT_ROOT REPORT_DIR DRAWS');run_saved_diagnostics(a[1],a[2],a[3],as.integer(a[4]))}
