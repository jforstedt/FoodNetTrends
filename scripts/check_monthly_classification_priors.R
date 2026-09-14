#!/usr/bin/env Rscript
# Prior-only structural checks: no outcomes, fitting, or empirical tuning.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'monthly_classification_model.R'));source(file.path(.here,'monthly_spatial_combination.R'))
classification_graph_prior <- function(nodes,edges) {
 g<-monthly_spatial_graph(data.frame(area=nodes$fips,state=nodes$state),nodes,edges)
 variances<-numeric(length(g$ids));eigenvalues<-numeric();rankdef<-0L
 for(component in unique(g$components)) {
  ix<-which(g$components==component);A<-g$adj[ix,ix];Q<-diag(rowSums(A))-A
  ee<-eigen(Q,symmetric=TRUE);keep<-ee$values>max(ee$values)*1e-10
  V<-sweep(ee$vectors[,keep,drop=FALSE],2,sqrt(ee$values[keep]),'/');scale<-exp(mean(log(rowSums(V^2))))
  variances[ix]<-rowSums(V^2)/scale;eigenvalues<-c(eigenvalues,ee$values*scale);rankdef<-rankdef+sum(!keep)
  stopifnot(abs(exp(mean(log(variances[ix])))-1)<1e-8)
 }
 # Use the pinned implementation of the BYM2 mixing prior, including its
 # numerical normalization, rather than replacing it with a beta/uniform prior.
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 inla_graph<-INLA::inla.read.graph(Matrix::Matrix(diag(rowSums(g$adj))-g$adj,sparse=TRUE))
 tab<-get('inla.pc.bym.phi',asNamespace('INLA'))(graph=inla_graph,alpha=.5,u=.5,scale.model=TRUE,adjust.for.con.comp=TRUE,return.as.table=TRUE)
 # R cbind is flattened column-major by this pinned helper: first theta,
 # then log density ON THETA. Integrate directly, avoiding any Jacobian ambiguity.
 x<-matrix(as.numeric(strsplit(sub('^table: ','',tab),' ')[[1]]),ncol=2)
 theta<-x[,1];phi<-plogis(theta);density<-exp(x[,2])
 mass<-c(0,cumsum(diff(theta)*(head(density,-1)+tail(density,-1))/2));integral<-tail(mass,1)
 if(!is.finite(integral)||abs(integral-1)>.001)stop('Pinned BYM2 numerical prior table failed normalization')
 mass<-mass/integral
 list(graph=g,variance=variances,phi=function(n)approx(mass,phi,xout=runif(n),ties='ordered')$y,
  phi_median=approx(mass,phi,xout=.5)$y,phi_cdf_half=approx(theta,mass,xout=0)$y,phi_table_integral=integral)

}
check_monthly_classification_priors <- function(out,nodes,edges,draws=5000L,seed=741321L) {
 if(dir.exists(out))stop('Refusing existing prior-check output');dir.create(out,recursive=TRUE)
 set.seed(seed);gp<-classification_graph_prior(nodes,edges)
 if(!is.finite(gp$phi_median)||gp$phi_median<=0||gp$phi_median>=1)stop('Invalid BYM2 numerical prior')
 pc<-function(upper)rexp(draws,rate=-log(.01)/upper)
 cycle<-monthly_classification_scale(12,TRUE);seasonbase<-cycle$factor%*%matrix(rnorm(ncol(cycle$factor)*draws),ncol=draws)/sqrt(cycle$scale)
 stopifnot(max(abs(colMeans(seasonbase)))<1e-10)
 records<-list();i<-0L
 for(cutoff in c(2015L,2016L)) {
  ntrain<-(cutoff-2012+1L)*12L;nt<-ntrain+36L;sc<-monthly_classification_scale(ntrain)$scale
  for(temporal in c('rw1','ar1')) {
   sd<-pc(1)
   if(temporal=='rw1') {
    trend<-apply(matrix(rnorm((nt-1)*draws),ncol=draws),2,function(x)c(0,cumsum(x)))
    trend<-sweep(trend,2,colMeans(trend[seq_len(ntrain),,drop=FALSE]),'-')/sqrt(sc)
    trend<-sweep(trend,2,sd,'*');stopifnot(max(abs(colMeans(trend[seq_len(ntrain),,drop=FALSE])))<1e-10)
   } else {
    rho<-2*plogis(rnorm(draws,log(19),1.5))-1
    trend<-matrix(0,nt,draws);trend[1,]<-rnorm(draws)*sd
    for(t in 2:nt)trend[t,]<-rho*trend[t-1,]+rnorm(draws)*sd*sqrt(1-rho^2)
   }
   for(level in c('site','county'))for(spatial in if(level=='site')'none' else c('iid','bym2'))for(seasonal in c(FALSE,TRUE)) {
    intercept<-rnorm(draws,qlogis(.1),1.5);site<-rnorm(draws)*pc(1.5)
    eta<-sweep(trend,2,intercept+site,'+')+sweep(matrix(rnorm(nt*draws),nt,draws),2,pc(1),'*')
    if(level=='county') {
     sdarea<-pc(1)
     variance<-if(spatial=='iid')rep(1,draws) else {phi<-gp$phi(draws);(1-phi)+phi*sample(gp$variance,draws,TRUE)}
     eta<-sweep(eta,2,rnorm(draws)*sdarea*sqrt(variance),'+')
    }
    if(seasonal)eta<-eta+sweep(seasonbase[rep(1:12,length.out=nt),],2,pc(1),'*')
    prob<-plogis(eta);stopifnot(all(is.finite(prob)),all(prob>=0&prob<=1))
    for(period in c('training','forecast')) {
     ix<-if(period=='training')seq_len(ntrain) else (ntrain+1):nt;v<-as.numeric(prob[ix,]);q<-quantile(v,c(.025,.5,.975))
     i<-i+1L;records[[i]]<-data.frame(cutoff,level,temporal,seasonal,spatial,period,draws,
      probability_q025=q[1],probability_median=q[2],probability_q975=q[3],fraction_below_001=mean(v<.01),fraction_above_099=mean(v>.99),
      mean_adjacent_month_logit_change=mean(abs(eta[ix[-1],,drop=FALSE]-eta[ix[-length(ix)],,drop=FALSE])))
    }
   }
  }
 }
 result<-do.call(rbind,records);rownames(result)<-NULL
 write.csv(result,file.path(out,'prior_trajectories.csv'),row.names=FALSE)
 write.csv(data.frame(parameter=c('site_sd','cell_sd','spatial_sd','trend_sd','seasonal_sd'),upper=c(1.5,1,1,1,1),tail_probability=.01,pc_exponential_rate=-log(.01)/c(1.5,1,1,1,1)),file.path(out,'prior_parameters.csv'),row.names=FALSE)
 write.csv(data.frame(seed,draws,graph_nodes=length(gp$graph$ids),graph_components=gp$graph$n_components,graph_phi_median=gp$phi_median,graph_phi_cdf_half=gp$phi_cdf_half,graph_phi_table_integral=gp$phi_table_integral,
  outcome_data_used=FALSE,prior_selection='fixed_shared_logit_scale_before_outcome_fits',INLA_version=as.character(packageVersion('INLA'))),file.path(out,'prior_check_settings.csv'),row.names=FALSE)
 writeLines('CLASSIFICATION_PRIOR_STRUCTURAL_CHECK_PASS',file.path(out,'status.txt'))
 result
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=3)stop('Usage OUT NODES EDGES');check_monthly_classification_priors(a[1],read.csv(a[2],colClasses='character'),read.csv(a[3],colClasses='character'))}
