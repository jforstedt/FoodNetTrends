#!/usr/bin/env Rscript
# Independent one-dimensional quadrature checks of the same Gaussian joint sampler.
# This conditional scalar reference does not validate full county joint uncertainty.
run_scalar_reference <- function(out,draws=4000L) {
 if(dir.exists(out))stop('Refusing existing reference output')
 dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
 scenarios<-list(zero=list(pop=c(1000,1000,1000),y=c(0,0,0)),
   sparse=list(pop=c(1000,1000,1000),y=c(0,1,0)),
   dense=list(pop=c(100000,100000,100000),y=c(15,25,20)),
   low_rate=list(pop=c(100000,100000,100000),y=c(0,1,2)))
 results<-list();prior_mean<-log(20/1e5);size<-8
 for(i in seq_along(scenarios)) {
  d<-as.data.frame(scenarios[[i]])
  logpost<-function(a) vapply(a,function(v)dnorm(v,prior_mean,1,log=TRUE)+sum(dnbinom(d$y,mu=d$pop*exp(v),size=size,log=TRUE)),numeric(1))
  lower<-prior_mean-14;upper<-prior_mean+14
  mode<-optimize(function(x)-logpost(x),c(lower,upper))$minimum
  density<-function(x)exp(logpost(x)-logpost(mode))
  normalizer<-integrate(density,lower,upper,rel.tol=1e-10)$value
  cdf<-function(x)integrate(density,lower,min(upper,max(lower,x)),rel.tol=1e-9)$value/normalizer
  exact<-vapply(c(.025,.5,.975),function(p)uniroot(function(x)cdf(x)-p,c(lower,upper),tol=1e-9)$root,numeric(1))
  fit<-INLA::inla(y~1+offset(log(pop)),data=d,family='nbinomial',num.threads='2:1',
    control.fixed=list(mean.intercept=prior_mean,prec.intercept=1),
    control.family=list(variant=0,hyper=list(size=list(initial=log(size),fixed=TRUE))),
    control.predictor=list(compute=TRUE,link=1),control.compute=list(config=TRUE))
  samples<-INLA::inla.posterior.sample(draws,fit,selection=list(Predictor=1),seed=210000L+i,num.threads='1:1',skew.corr=FALSE)
  alpha<-vapply(samples,function(s){stopifnot(nrow(s$latent)==1);as.numeric(s$latent[1,1])-log(d$pop[1])},numeric(1))
  estimated<-as.numeric(quantile(alpha,c(.025,.5,.975)));mass<-vapply(estimated,cdf,numeric(1))
  error<-max(abs(mass-c(.025,.5,.975)))
  results[[i]]<-data.frame(scenario=names(scenarios)[i],draws=draws,max_probability_error=error,
    exact_lower=exact[1],exact_median=exact[2],exact_upper=exact[3],sample_lower=estimated[1],sample_median=estimated[2],sample_upper=estimated[3],pass=error<=.05)
 }
 rows<-do.call(rbind,results);write.csv(rows,file.path(out,'scalar_reference.csv'),row.names=FALSE)
 passed<-all(rows$pass)
 writeLines(paste0('{"status":"',if(passed)'SCALAR_REFERENCE_PASS' else 'REVIEW_REQUIRED',
   '","probability_error_limit":0.05,"scope":"Fixed-size scalar negative-binomial log-rate; quadrature posterior vs Gaussian joint samples.",',
   '"limitation":"Conditional scalar screen; full county posterior accuracy remains unverified."}'),file.path(out,'reference_summary.json'))
 writeLines(if(passed)'SCALAR_REFERENCE_PASS' else 'REVIEW_REQUIRED',file.path(out,'status.txt'))
 if(!passed)stop('Scalar posterior reference exceeds predeclared probability-error tolerance')
 invisible(rows)
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1)stop('OUT');run_scalar_reference(a[1])}
