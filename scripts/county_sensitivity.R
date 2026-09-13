#!/usr/bin/env Rscript
# Separate exploratory sensitivity models; original fit implementation is untouched.
sensitivity_prior <- function(obj,variant,out,county_sd=1,county_time=FALSE,n=1000L,seed=20260912L,observed_total=NULL) {
  set.seed(seed);d<-obj$data;na<-length(obj$ids);nt<-length(obj$years);ns<-nlevels(d$state)
  Q<-diag(rowSums(obj$adj))-obj$adj
  if(any(diag(Q)==0))stop('This pilot prior sampler requires the audited non-isolated graph')
  spatial<-scaled_intrinsic(Q)
  qt<-matrix(0,nt,nt);qt[cbind(1:(nt-1),2:nt)]<-1;qt<-qt+t(qt)
  temporal<-scaled_intrinsic(diag(rowSums(qt))-qt)
  # Obtain INLA's actual graph-dependent PC mixing prior, not a uniform surrogate.
  phi_density<-INLA:::inla.pc.bym.phi(eigenvalues=spatial$eigenvalues,
    marginal.variances=spatial$variance,rankdef=spatial$rankdef,alpha=.5,u=.5)
  theta<-seq(-14,12,length.out=20000);phi_grid<-plogis(theta)
  density<-exp(phi_density(phi_grid)+log(phi_grid)+log1p(-phi_grid))
  weights<-c(0,(head(density,-1)+tail(density,-1))/2*diff(theta));cdf<-cumsum(weights);cdf<-cdf/max(cdf)
  phi<-approx(cdf,phi_grid,xout=runif(n),ties='ordered',rule=2)$y
  # PC precision prior implies an exponential prior on SD.
  spatial_sd<-rexp(n,rate=-log(.01)/county_sd);time_sd<-rexp(n,rate=-log(.01)/.5)
  intercept<-matrix(rnorm(ns*n,log(20/1e5),1),ns,n)
  result<-matrix(NA_real_,n,5);colnames(result)<-c('mean_rate_per100k','zero_fraction','count_above_population_fraction','spatial_sd','time_sd')
  for(j in seq_len(n)) {
    u<-as.vector(spatial$L%*%rnorm(ncol(spatial$L)))
    county<-if(variant=='spatial')spatial_sd[j]*(sqrt(phi[j])*u+sqrt(1-phi[j])*rnorm(na)) else spatial_sd[j]*rnorm(na)
    tt<-temporal$L%*%matrix(rnorm(ncol(temporal$L)*ns),ncol(temporal$L),ns)*time_sd[j]
    eta<-intercept[d$state_id,j]+county[d$area]+tt[cbind(d$time,d$state_id)]
    if(county_time) {
      local_sd<-rexp(1,rate=-log(.01)/.5)
      local<-temporal$L%*%matrix(rnorm(ncol(temporal$L)*na),ncol(temporal$L),na)*local_sd
      eta<-eta+local[cbind(d$time,d$area)]
    }
    mu<-d$population*exp(eta);size<-exp(rnorm(1,log(12),1))
    y<-rnbinom(nrow(d),mu=mu,size=size)
    if(any(!is.finite(mu))||any(!is.finite(y)))stop('Nonfinite prior-predictive counts')
    result[j,]<-c(sum(mu)/sum(d$population)*1e5,mean(y==0),mean(y>d$population),spatial_sd[j],time_sd[j])
  }
  write.csv(result,file.path(out,'prior_predictive_draw_summary.csv'),row.names=FALSE)
  observed<-if(is.null(observed_total))sum(d$count) else observed_total
  observed<-observed/sum(d$population)*1e5
  pdf(file.path(out,'prior_predictive.pdf'),width=9,height=5)
  hist(log10(result[,1]),breaks=40,main=paste(variant,'prior: population-weighted incidence'),xlab='log10 rate per 100,000')
  abline(v=log10(observed),col='red',lwd=2);legend('topright','Observed pooled incidence',col='red',lwd=2,bty='n');dev.off()
  writeLines(c('PRIOR_SIMULATION_COMPLETE: numerical check, not scientific approval',
    paste('Prior pooled incidence 2.5/50/97.5%:',paste(signif(quantile(result[,1],c(.025,.5,.975)),5),collapse=', ')),
    paste('Observed pooled incidence:',signif(observed,5)),
    paste('Mean fraction simulated counts exceeding population:',mean(result[,3])),
    'Sensitivity prior simulation; inspect before interpreting results.'),file.path(out,'prior_review.txt'))
  invisible(result)
}


sensitivity_fit <- function(obj,variant,county_sd=1,county_time=FALSE,threads=8L) {
  d<-obj$data;d$county_time<-d$time;f<-INLA::f
  graph<-INLA::inla.read.graph(Matrix::Matrix(diag(rowSums(obj$adj))-obj$adj,sparse=TRUE))
  if(variant=='spatial') {
    formula<-count~0+state+offset(log(population))+
      f(area,model='bym2',graph=graph,scale.model=TRUE,constr=TRUE,adjust.for.con.comp=TRUE,
        hyper=list(prec=list(prior='pc.prec',param=c(county_sd,.01)),phi=list(prior='pc',param=c(.5,.5))))+
      f(time,model='rw1',replicate=state_id,scale.model=TRUE,constr=TRUE,hyper=list(prec=list(prior='pc.prec',param=c(.5,.01))))
  } else if(variant=='iid') {
    formula<-count~0+state+offset(log(population))+
      f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(county_sd,.01))))+
      f(time,model='rw1',replicate=state_id,scale.model=TRUE,constr=TRUE,hyper=list(prec=list(prior='pc.prec',param=c(.5,.01))))
  } else stop('Invalid variant')
  if(county_time)formula<-update(formula,.~.+f(county_time,model='rw1',replicate=area,scale.model=TRUE,constr=TRUE,
      hyper=list(prec=list(prior='pc.prec',param=c(.5,.01)))))
  fit<-INLA::inla(formula,data=d,family='nbinomial',num.threads=paste0(threads,':1'),
    control.fixed=list(mean=log(20/1e5),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(log(12),1),initial=log(12)))),
    control.predictor=list(compute=TRUE),control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  attr(fit,'sensitivity_formula')<-deparse(formula)
  fit
}

fitted_report <- function(fit,d,out) {
  s<-fit$summary.fitted.values
  if(nrow(s)!=nrow(d)||any(!is.finite(as.matrix(s[,c('mean','0.025quant','0.5quant','0.975quant')]))))stop('Invalid fitted summaries')
  z<-d[c('fips','state','year')];z$expected_count_mean<-s$mean
  for(k in c('mean','0.025quant','0.5quant','0.975quant'))z[[paste0('rate_',k)]]<-s[[k]]/d$population*1e5
  write.csv(z,file.path(out,'county_fitted_INTERNAL.csv'),row.names=FALSE)
  write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'))
  write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'))
  if(!is.null(attr(fit,'sensitivity_formula')))writeLines(attr(fit,'sensitivity_formula'),file.path(out,'formula.txt'))
}

run_sensitivity <- function(audit,dest,name,threads=8L,draws=2000L) {
  valid<-c('spatial_county_sd2','iid_county_sd2','spatial_county_time','iid_county_time')
  if(!name%in%valid)stop('Invalid sensitivity name')
  if(dir.exists(dest))stop('Existing destination; refusing to overwrite')
  out<-file.path(dest,'reports');dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
  tryCatch({
    if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected pinned INLA')
    INLA::inla.setOption(num.threads=paste0(threads,':1'))
    panel<-file.path(audit,'county_panel_INTERNAL.rds');before<-tools::md5sum(panel)
    obj<-validate_panel(audit);variant<-if(startsWith(name,'spatial'))'spatial' else 'iid'
    time<-endsWith(name,'county_time');sd<-if(time)1 else 2
    write.csv(data.frame(name=name,variant=variant,county_sd_upper=sd,county_time=time,county_time_sd_upper=if(time).5 else NA),file.path(out,'specification.csv'),row.names=FALSE)
    sensitivity_prior(obj,variant,out,county_sd=sd,county_time=time)
    fit<-sensitivity_fit(obj,variant,sd,time,threads)
    saveRDS(fit,file.path(dest,'fit_INTERNAL.rds'))
    fitted_report(fit,obj$data,out)
    saved_diagnostics(fit,obj$data,out,draws=draws)
    if(!identical(before,tools::md5sum(panel)))stop('Panel changed')
    write.csv(data.frame(file=panel,md5=unname(before)),file.path(out,'panel_checksum.csv'),row.names=FALSE)
    writeLines('SENSITIVITY_FIT_COMPLETE',file.path(out,'status.txt'))
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}

compare_sensitivities <- function(audit,baseline,baseline_diagnostics,dest) {
  d<-validate_panel(audit)$data;out<-file.path(dest,'comparison');dir.create(out)
  panel<-file.path(audit,'county_panel_INTERNAL.rds');panelmd5<-unname(tools::md5sum(panel))
  points<-list();summary<-list()
  for(v in c('spatial','iid')) {
    report<-file.path(out,paste0(v,'_baseline'));dir.create(report)
    chk<-read.csv(file.path(baseline,v,'reports/panel_checksum.csv'),stringsAsFactors=FALSE)
    if(nrow(chk)!=1||chk$md5!=panelmd5)stop('Baseline panel mismatch')
    checkpoint<-file.path(baseline,v,'fit_INTERNAL.rds');before<-tools::md5sum(checkpoint)
    original<-read.csv(file.path(baseline_diagnostics,'reports/input_checksums.csv'),stringsAsFactors=FALSE)
    j<-match(checkpoint,original$file)
    if(is.na(j)||unname(before)!=original$md5[j])stop('Saved baseline diagnostic checkpoint mismatch')
    fit<-readRDS(checkpoint);fitted_report(fit,d,report)
    for(n in c('zero_checks_INTERNAL.csv','zero_checks.pdf','model_diagnostics.csv'))
      if(!file.copy(file.path(baseline_diagnostics,'reports',v,n),file.path(report,n)))stop('Missing baseline diagnostic report')
    points[[v]]<-fit$waic$local.waic
    if(!identical(before,tools::md5sum(checkpoint)))stop('Baseline changed')
    rm(fit);gc()
  }
  for(name in c('spatial_county_sd2','iid_county_sd2','spatial_county_time','iid_county_time')) {
    report<-file.path(dest,name,'reports')
    good<-file.exists(file.path(report,'status.txt'))&&readLines(file.path(report,'status.txt'))[1]=='SENSITIVITY_FIT_COMPLETE'
    if(!good){summary[[name]]<-data.frame(model=name,status='INCOMPLETE',waic_gain=NA,naive_paired_se=NA);next}
    chk<-read.csv(file.path(report,'panel_checksum.csv'));if(chk$md5!=panelmd5)stop('Sensitivity panel mismatch')
    fit<-readRDS(file.path(dest,name,'fit_INTERNAL.rds'));v<-if(startsWith(name,'spatial'))'spatial' else 'iid'
    delta<-points[[v]]-fit$waic$local.waic
    if(length(delta)!=nrow(d)||any(!is.finite(delta)))stop('Invalid paired comparison')
    summary[[name]]<-data.frame(model=name,status='COMPLETE',waic_gain=sum(delta),naive_paired_se=sqrt(length(delta)*var(delta)))
    g<-paste(d$state,d$fips,sep='|')
    write.csv(data.frame(county=sort(unique(g)),baseline_minus_sensitivity_waic=as.numeric(rowsum(delta,g,reorder=TRUE))),file.path(report,'waic_change_by_county_INTERNAL.csv'),row.names=FALSE)
    rm(fit);gc()
  }
  write.csv(do.call(rbind,summary),file.path(out,'paired_comparison.csv'),row.names=FALSE)
  writeLines('Comparison complete; predictive/parameter review required. No automatic winner or dashboard update.',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){
 a<-commandArgs(TRUE);here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
 source(file.path(here,'fit_county_pilot.R'));source(file.path(here,'diagnose_saved_county_pilot.R'))
 if(length(a)==5&&a[1]=='fit')run_sensitivity(a[2],a[3],a[4],as.integer(a[5]))
 else if(length(a)==5&&a[1]=='compare')compare_sensitivities(a[2],a[3],a[4],a[5])
 else stop('Usage: fit AUDIT DEST NAME THREADS | compare AUDIT BASELINE BASELINE_DIAGNOSTICS DEST')
}
