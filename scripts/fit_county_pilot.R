#!/usr/bin/env Rscript
# Exploratory models only. No changes to source inputs or production outputs.
validate_panel <- function(audit, expected_production=TRUE) {
  if(readLines(file.path(audit,'reports/status.txt'))[1]!='INPUT_AUDIT_PASS')stop('Input audit has not passed')
  d<-readRDS(file.path(audit,'county_panel_INTERNAL.rds'))
  nodes<-read.csv(file.path(audit,'reports/graph_nodes.csv'),colClasses='character')
  edges<-read.csv(file.path(audit,'reports/graph_edges.csv'),colClasses='character')
  pop<-read.csv(file.path(audit,'reports/population_audit.csv'),colClasses='character')
  rec<-read.csv(file.path(audit,'reports/state_year_reconciliation.csv'))
  needed<-c('year','fips','state','population','count')
  if(!all(needed%in%names(d)))stop('Missing panel columns')
  d$fips<-as.character(d$fips);d$state<-as.character(d$state)
  if(anyNA(d[needed])||any(!is.finite(d$population))||any(d$population<=0)||
     any(!is.finite(d$count))||any(d$count<0)||any(d$count!=floor(d$count)))stop('Invalid count/population')
  key<-function(x)paste(x$year,x$fips,sep='|')
  if(anyDuplicated(key(d))||anyDuplicated(nodes$fips)||anyDuplicated(key(pop)))stop('Duplicate panel/geography key')
  years<-sort(unique(d$year));ids<-sort(nodes$fips)
  if(!identical(years,seq.int(min(years),max(years))) || length(years)<3)stop('Invalid year sequence')
  expected<-expand.grid(year=years,fips=ids,stringsAsFactors=FALSE)
  if(!setequal(key(d),key(expected)) || !setequal(key(d),key(pop)))stop('Incomplete county/year grid')
  p<-pop[match(key(d),key(pop)),]
  if(any(p$population_status!='ok')||any(d$population!=as.numeric(p$population))||any(d$state!=p$state))stop('Panel differs from population audit')
  if(any(!d$fips%in%nodes$fips)||any(d$state!=nodes$state[match(d$fips,nodes$fips)]))stop('State/FIPS mismatch')
  totals<-aggregate(d$count,d[c('state','year')],sum);names(totals)[3]<-'count'
  r<-merge(totals,rec,by=c('state','year'),all=TRUE)
  if(anyNA(r)||any(r$count!=r$selected_cases)||any(r$count!=r$direct_matched_cases))stop('Case totals differ from audit')
  if(expected_production && (nrow(d)!=7776||length(ids)!=486||!identical(years,2004:2019)||sum(d$count)!=122024))stop('Panel differs from reviewed pilot scope')
  if(anyNA(edges)||any(!edges$fips_a%in%ids)||any(!edges$fips_b%in%ids)||any(edges$fips_a>=edges$fips_b)||anyDuplicated(edges))stop('Invalid graph edges')
  # Repeat original input checksums on HPC. Do not silently fit if source files changed.
  checks<-read.csv(file.path(audit,'reports/input_checksums.csv'),stringsAsFactors=FALSE)
  if(!all(file.exists(checks$file))||any(unname(tools::md5sum(checks$file))!=checks$md5))stop('Source inputs changed since audit')
  d<-d[order(d$fips,d$year),];rownames(d)<-NULL
  d$area<-match(d$fips,ids);d$state<-factor(d$state,levels=sort(unique(d$state)))
  d$state_id<-as.integer(d$state);d$time<-match(d$year,years)
  adj<-matrix(0,length(ids),length(ids));a<-match(edges$fips_a,ids);b<-match(edges$fips_b,ids)
  adj[cbind(a,b)]<-1;adj[cbind(b,a)]<-1
  if(any(rowSums(adj)!=as.integer(nodes$neighbors[match(ids,nodes$fips)])))stop('Graph degree differs from audit')
  list(data=d,adj=adj,ids=ids,years=years)
}

scaled_intrinsic <- function(Q) {
  # INLA scales each connected component. Its helper is version-pinned below.
  scaled<-INLA:::inla.scale.model.bym.internal(Matrix::Matrix(Q,sparse=TRUE))$Q
  e<-eigen(as.matrix(scaled),symmetric=TRUE)
  good<-e$values>max(e$values)*1e-9
  L<-sweep(e$vectors[,good,drop=FALSE],2,sqrt(e$values[good]),'/')
  list(Q=scaled,L=L,variance=rowSums(L^2),eigenvalues=e$values,rankdef=sum(!good))
}

prior_check <- function(obj,variant,out,n=1000L,seed=20260912L,observed_total=NULL) {
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
  spatial_sd<-rexp(n,rate=-log(.01)/1);time_sd<-rexp(n,rate=-log(.01)/.5)
  intercept<-matrix(rnorm(ns*n,log(20/1e5),1),ns,n)
  result<-matrix(NA_real_,n,5);colnames(result)<-c('mean_rate_per100k','zero_fraction','count_above_population_fraction','spatial_sd','time_sd')
  for(j in seq_len(n)) {
    u<-as.vector(spatial$L%*%rnorm(ncol(spatial$L)))
    county<-if(variant=='spatial')spatial_sd[j]*(sqrt(phi[j])*u+sqrt(1-phi[j])*rnorm(na)) else spatial_sd[j]*rnorm(na)
    tt<-temporal$L%*%matrix(rnorm(ncol(temporal$L)*ns),ncol(temporal$L),ns)*time_sd[j]
    eta<-intercept[d$state_id,j]+county[d$area]+tt[cbind(d$time,d$state_id)]
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
    'Broad draft priors retained for exploratory fit; inspect plot before interpreting results.'),file.path(out,'prior_review.txt'))
  invisible(result)
}

fit_pilot <- function(obj,variant,out,threads=4L,draws=1000L) {
  d<-obj$data;f<-INLA::f
  Q<-Matrix::Matrix(diag(rowSums(obj$adj))-obj$adj,sparse=TRUE)
  graph<-INLA::inla.read.graph(Q)
  if(variant=='spatial') {
    formula<-count~0+state+offset(log(population))+
      f(area,model='bym2',graph=graph,scale.model=TRUE,constr=TRUE,adjust.for.con.comp=TRUE,
        hyper=list(prec=list(prior='pc.prec',param=c(1,.01)),phi=list(prior='pc',param=c(.5,.5))))+
      f(time,model='rw1',replicate=state_id,scale.model=TRUE,constr=TRUE,
        hyper=list(prec=list(prior='pc.prec',param=c(.5,.01))))
  } else {
    formula<-count~0+state+offset(log(population))+
      f(area,model='iid',hyper=list(prec=list(prior='pc.prec',param=c(1,.01))))+
      f(time,model='rw1',replicate=state_id,scale.model=TRUE,constr=TRUE,
        hyper=list(prec=list(prior='pc.prec',param=c(.5,.01))))
  }
  writeLines(capture.output(formula),file.path(out,'formula.txt'))
  fit<-INLA::inla(formula,data=d,family='nbinomial',num.threads=paste0(threads,':1'),
    control.fixed=list(mean=log(20/1e5),prec=1),
    control.family=list(variant=0,hyper=list(size=list(prior='normal',param=c(log(12),1),initial=log(12)))),
    control.predictor=list(compute=TRUE),control.compute=list(config=TRUE,waic=TRUE,cpo=TRUE))
  # Checkpoint before diagnostics so a reporting failure cannot discard the fit.
  saveRDS(fit,file.path(dirname(out),'fit_INTERNAL.rds'))
  if(any(!is.finite(as.matrix(fit$summary.fixed[,1:5])))||any(!is.finite(as.matrix(fit$summary.hyperpar[,1:5]))))stop('Nonfinite posterior summary')
  write.csv(fit$summary.fixed,file.path(out,'fixed_effects.csv'))
  write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'))
  cat('Drawing joint posterior samples for aggregation...\n')
  samples<-INLA::inla.posterior.sample(draws,fit,selection=list(Predictor=seq_len(nrow(d))),
    seed=20260912L,num.threads='1:1',skew.corr=FALSE)
  eta<-vapply(samples,function(s){
    ids<-as.integer(sub('^Predictor:','',rownames(s$latent)))
    if(anyNA(ids)||!setequal(ids,seq_len(nrow(d))))stop('Unexpected posterior predictor indexing')
    as.numeric(s$latent[match(seq_len(nrow(d)),ids),1])},numeric(nrow(d)))
  # Offset is part of INLA Predictor; exponentiating gives expected COUNTS.
  mu<-exp(eta);if(any(!is.finite(eta))||any(!is.finite(mu)))stop('Nonfinite posterior counts')
  sfun<-function(m)t(apply(m,1,function(x)c(mean=mean(x),median=median(x),lower=quantile(x,.025,names=FALSE),upper=quantile(x,.975,names=FALSE))))
  county<-cbind(d[c('fips','state','year')],sfun(mu/d$population*1e5))
  write.csv(county,file.path(out,'county_incidence_INTERNAL.csv'),row.names=FALSE)
  reference<-match(paste(d$fips,max(d$year)),paste(d$fips,d$year))
  county_rr<-(mu/d$population)/(mu[reference,,drop=FALSE]/d$population[reference])
  write.csv(cbind(d[c('fips','state','year')],sfun(county_rr)),file.path(out,'county_reference_rr_INTERNAL.csv'),row.names=FALSE)
  groups<-paste(d$state,d$year,sep='|');counts<-rowsum(mu,groups,reorder=TRUE)
  population<-rowsum(d$population,groups,reorder=TRUE)[,1]
  rates<-counts/population*1e5
  groupkeys<-do.call(rbind,strsplit(rownames(rates),'|',fixed=TRUE))
  state<-data.frame(state=groupkeys[,1],year=as.integer(groupkeys[,2]),sfun(rates),row.names=NULL)
  write.csv(state,file.path(out,'state_incidence.csv'),row.names=FALSE)
  refs<-match(paste(state$state, max(d$year),sep='|'),rownames(rates))
  rr<-rates/rates[refs,,drop=FALSE]
  write.csv(cbind(state[c('state','year')],sfun(rr)),file.path(out,'state_reference_rr.csv'),row.names=FALSE)
  # Posterior predictive checks from joint draws, retaining totals/zero fractions only.
  set.seed(20260913L)
  pp<-vapply(seq_along(samples),function(j){
    hp<-samples[[j]]$hyperpar;idx<-grep('size for',names(hp),fixed=TRUE)
    if(length(idx)!=1)stop('Cannot locate posterior NB size')
    y<-rnbinom(nrow(d),mu=mu[,j],size=hp[idx]);c(total=sum(y),zero_fraction=mean(y==0))},numeric(2))
  if(any(!is.finite(pp)))stop('Nonfinite posterior-predictive summary')
  write.csv(data.frame(draw=seq_len(draws),t(pp)),file.path(out,'posterior_predictive.csv'),row.names=FALSE)
  fail<-fit$cpo$failure
  if(length(fail)!=nrow(d)||!is.finite(fit$waic$waic))stop('Missing CPO or WAIC diagnostics')
  diagnostics<-data.frame(model=variant,waic=fit$waic$waic,cpo_failures=sum(!is.finite(fail)|fail!=0),
    observed_total=sum(d$count),observed_zero_fraction=mean(d$count==0),posterior_draws=draws)
  write.csv(diagnostics,file.path(out,'diagnostics.csv'),row.names=FALSE)
  pdf(file.path(out,'state_trends.pdf'),width=10,height=8);par(mfrow=c(ceiling(nlevels(d$state)/2),2),mar=c(3,4,2,1))
  for(s in levels(d$state)){z<-state[state$state==s,];plot(z$year,z$median,type='l',ylim=range(z$lower,z$upper),xlab='Year',ylab='Incidence /100,000',main=s);lines(z$year,z$lower,lty=2);lines(z$year,z$upper,lty=2)};dev.off()
  writeLines(c('EXPLORATORY_FIT_COMPLETE',paste('Model:',variant),paste('CPO failures:',diagnostics$cpo_failures),
    'Not approved for dashboard/public interpretation; review priors, prediction and sensitivities.'),file.path(out,'status.txt'))
  invisible(fit)
}

run_pilot <- function(audit,destination,variant,threads=4L) {
  if(!variant%in%c('spatial','iid'))stop('Unknown model variant')
  if(dir.exists(destination))stop('Refusing existing model destination')
  out<-file.path(destination,'reports');dir.create(out,recursive=TRUE)
  writeLines('RUNNING',file.path(out,'status.txt'))
  on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
  tryCatch({
    if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected pinned INLA version')
    INLA::inla.setOption(num.threads=paste0(threads,':1'))
    obj<-validate_panel(audit)
    write.csv(data.frame(file='county_panel_INTERNAL.rds',md5=unname(tools::md5sum(file.path(audit,'county_panel_INTERNAL.rds')))),file.path(out,'panel_checksum.csv'),row.names=FALSE)
    cat('Checking priors...\n');prior_check(obj,variant,out)
    cat('Fitting',variant,'pilot...\n');fit_pilot(obj,variant,out,threads)
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=4)stop('Usage: fit_county_pilot.R AUDIT_DIR DESTINATION spatial|iid THREADS');run_pilot(a[1],a[2],a[3],as.integer(a[4]))}
