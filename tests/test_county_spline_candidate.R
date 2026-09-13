#!/usr/bin/env Rscript
args<-commandArgs(TRUE)
source('scripts/county_spline_candidate.R')
mode<-if(length(args))args[1] else 'basis'
if(mode%in%c('basis','prepare')) {
  a<-county_spline_basis(2004:2012,2011);b<-county_spline_basis(2004:2014,2011)
  stopifnot(max(abs(a$nonlinear-b$nonlinear[1:9,]))<1e-12,
    max(abs(a$slope-b$slope[1:9]))<1e-12,
    max(abs(colMeans(b$nonlinear[1:8,])))<1e-12,
    max(abs(crossprod(b$slope[1:8],b$nonlinear[1:8,])))<1e-12)
  if(length(args)>1L){dir.create(args[2],recursive=TRUE,showWarnings=FALSE);saveRDS(a,file.path(args[2],'basis1.rds'));saveRDS(b,file.path(args[2],'basis3.rds'))}
  cat('SPLINE_BASIS_PASS\n')
} else {
  stopifnot(mode%in%c('inla','run'),length(args)>=2)
  out<-if(length(args)>=3)args[3] else args[2];dir.create(out,recursive=TRUE,showWarnings=FALSE)
  writeLines('RUNNING',file.path(out,'status.txt'))
  b1<-readRDS(file.path(args[2],'basis1.rds'));b3<-readRDS(file.path(args[2],'basis3.rds'))
  make<-function(b) {
    d<-expand.grid(area=1:6,year=b$years);d$state_id<-1L+(d$area>3);d$state<-factor(d$state_id)
    d$population<-1e5;d$count<-as.numeric(10+d$area+round(3*sin((d$year-2004)/2)))
    adj<-matrix(0,6,6);for(i in c(1,2,4,5)){adj[i,i+1]<-adj[i+1,i]<-1}
    list(data=d,adj=adj,spline_basis=b)
  }
  # Exact Gaussian reference checks the saved basis/A-matrix implementation.
  Z<-cbind(b3$slope,b3$nonlinear);observed<-b3$years<=2011
  y<-sin(seq_len(nrow(Z))/2);y[!observed]<-NA_real_
  stk<-INLA::inla.stack(data=list(y=y),A=list(Matrix::Matrix(Z,sparse=TRUE)),
    effects=list(list(coefficient=seq_len(ncol(Z)))),compress=FALSE,remove.unused=FALSE)
  f<-INLA::f
  gf<-INLA::inla(y~ -1+f(coefficient,model='iid',hyper=list(prec=list(initial=log(4),fixed=TRUE))),
    data=INLA::inla.stack.data(stk),family='gaussian',num.threads='2:1',
    control.family=list(hyper=list(prec=list(initial=log(4),fixed=TRUE))),
    control.predictor=list(A=INLA::inla.stack.A(stk),compute=TRUE))
  V<-solve(diag(4,ncol(Z))+4*crossprod(Z[observed,,drop=FALSE]))
  exact_mean<-as.numeric(Z%*%V%*%(4*crossprod(Z[observed,,drop=FALSE],y[observed])))
  exact_sd<-sqrt(rowSums((Z%*%V)*Z))
  gm<-gf$summary.linear.predictor[seq_len(nrow(Z)),]
  gaussian_mean_error<-max(abs(gm$mean-exact_mean));gaussian_sd_error<-max(abs(gm$sd-exact_sd))
  stopifnot(gaussian_mean_error<1e-4,gaussian_sd_error<1e-4)
  write.csv(data.frame(mean_error=gaussian_mean_error,sd_error=gaussian_sd_error,status='PASS'),
    file.path(out,'spline_gaussian_reference.csv'),row.names=FALSE)
  checks<-list()
  for(v in c('iid','spatial')) {
    a<-make(b1);b<-make(b3)
    f1<-fit_county_spline(a,v,2011,threads=2);f3<-fit_county_spline(b,v,2011,threads=2)
    poisoned<-b;poisoned$data$count[poisoned$data$year>2011]<-1e9
    fp<-fit_county_spline(poisoned,v,2011,threads=2)
    mask_change<-max(abs(fp$summary.linear.predictor$mean-f3$summary.linear.predictor$mean)/f3$summary.linear.predictor$sd)
    stopifnot(mask_change<.02)
    # Appending prediction-only rows must not change the shared posterior.
    m1<-f1$summary.linear.predictor[1:nrow(a$data),];m3<-f3$summary.linear.predictor[1:nrow(a$data),]
    change<-max(abs(m1$mean-m3$mean)/m1$sd);sdchange<-max(abs(m1$sd/m3$sd-1))
    stopifnot(is.finite(change),change<.02,sdchange<.02)
    samp<-sample_county_spline(f3,which(b$data$year>2011),draws=200L)
    stopifnot(all(is.finite(samp$mu)),all(is.finite(samp$replicated)),all(samp$replicated>=0))
    # Check observation-scale offset: expected counts should be on the count scale.
    stopifnot(median(samp$mu)>1,median(samp$mu)<100)
    checks[[v]]<-data.frame(model=v,standardized_mean_change=change,relative_sd_change=sdchange,heldout_mask_change=mask_change,status='PASS')
  }
  write.csv(do.call(rbind,checks),file.path(out,'spline_gate_checks.csv'),row.names=FALSE)
  writeLines('SPLINE_NUMERICAL_GATE_PASS',file.path(out,'status.txt'))
  cat('SPLINE_NUMERICAL_GATE_PASS\n')
}
