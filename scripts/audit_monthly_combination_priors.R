#!/usr/bin/env Rscript
# Data-free joint prior audit; no pathogen-specific tuning or fitted model changes.
source('scripts/county_forecast_model.R');source('scripts/county_spline_candidate.R')
source('scripts/monthly_seasonal_model.R');source('scripts/monthly_spline_combination.R')
prior_monthly_components <- function(cutoff,draws=20000L,seed=93417L,horizon=36L) {
 if(length(draws)!=1||draws<100||draws!=as.integer(draws)||!cutoff%in%c(2011L,2013L,2014L,2016L)||horizon<36L)stop('Unsupported prior audit dimensions')
 serial<-2004*12+seq_len((cutoff-2004+1)*12+horizon)-1L;end<-cutoff*12+11L;nt<-sum(serial<=end);n<-length(serial)
 basis<-monthly_combination_basis(serial,end);extended<-monthly_combination_basis(c(serial,max(serial)+seq_len(12)),end)
 if(max(abs(basis$nonlinear-extended$nonlinear[seq_len(n),]))>1e-10||!identical(basis$slope,extended$slope[seq_len(n)]))stop('Appended horizon changed prior basis')
 set.seed(seed);county<-rnorm(draws)*rexp(draws,-log(.01));intercept<-rnorm(draws,log(.0002),1);size<-exp(rnorm(draws,log(20),1))
 rw_sd<-rexp(draws,-log(.01)/.5)/sqrt(rw1_training_scale(nt))
 rw<-rbind(0,apply(matrix(rnorm((n-1)*draws),n-1,draws),2,cumsum));rw<-sweep(rw,2,colMeans(rw[seq_len(nt),,drop=FALSE]),'-');rw<-sweep(rw,2,rw_sd,'*')
 spline_sd<-rexp(draws,-log(.01)/.5);coef<-sweep(matrix(rnorm(ncol(basis$nonlinear)*draws),ncol(basis$nonlinear),draws),2,spline_sd,'*')
 spline<-basis$nonlinear%*%coef+outer(basis$slope,rnorm(draws,0,.5))
 # AR1 precision is marginal precision; transform internal rho=log((1+rho)/(1-rho)).
 ar_sd<-rexp(draws,-log(.01));rho<-tanh(rnorm(draws,log(19),1.5)/2)
 ar<-matrix(0,n,draws);ar[1,]<-rnorm(draws)*ar_sd
 for(i in 2:n)ar[i,]<-rho*ar[i-1,]+rnorm(draws)*ar_sd*sqrt(1-rho^2)
 cycle<-monthly_cycle_scale();e<-eigen(cycle$Q*cycle$scale,symmetric=TRUE);j<-e$values>1e-10
 B<-sweep(e$vectors[,j,drop=FALSE],2,sqrt(e$values[j]),'/');season<-B%*%matrix(rnorm(11*draws),11,draws);season<-sweep(season,2,rexp(draws,-log(.01)/.5),'*')
 if(max(abs(colSums(season)))>1e-8||any(!is.finite(c(rw,spline,ar,season))))stop('Invalid prior trajectories')
 list(serial=serial,nt=nt,intercept=intercept,county=county,size=size,trend=list(rw1=rw,ar1=ar,spline=spline),season=season,basis=basis,draws=draws)
}
run_combination_prior_audit <- function(out,draws=20000L) {
 if(dir.exists(out))stop('Refusing existing prior audit');dir.create(out,recursive=TRUE)
 summaries<-list();trajectories<-list();extrapolation<-list();counter<-tc<-ec<-0
 for(cutoff in c(2011L,2013L,2014L,2016L)) {
  obj<-prior_monthly_components(cutoff,draws,93417L+cutoff);n<-length(obj$serial);phase<-obj$serial%%12+1L
  for(model in names(obj$trend))for(seasonal in c(FALSE,TRUE)) {
   latent<-obj$trend[[model]]
   if(seasonal)latent<-latent+obj$season[phase,,drop=FALSE]
   rate<-exp(sweep(latent,2,obj$intercept+obj$county,'+'))
   if(any(!is.finite(rate)))stop('Nonfinite joint prior rates')
   q<-t(apply(rate*1e5,1,quantile,c(.025,.5,.975,.999)))
   tc<-tc+1;trajectories[[tc]]<-data.frame(cutoff=cutoff,temporal=model,seasonal=seasonal,month_from_origin=seq_len(n)-obj$nt,rate_p025=q[,1],rate_median=q[,2],rate_p975=q[,3],rate_p999=q[,4])
   for(h in c(0L,1L,12L,24L,36L)) {
    k<-obj$nt+h;ratio<-exp(latent[k,]-latent[obj$nt,]);ec<-ec+1
    extrapolation[[ec]]<-data.frame(cutoff=cutoff,temporal=model,seasonal=seasonal,horizon_month=h,ratio_p025=unname(quantile(ratio,.025)),ratio_median=median(ratio),ratio_p975=unname(quantile(ratio,.975)),ratio_p999=unname(quantile(ratio,.999)))
    for(exposure in c(500,10000)) {
     mu<-rate[k,]*exposure;y<-rnbinom(draws,mu=mu,size=obj$size);counter<-counter+1
     summaries[[counter]]<-data.frame(cutoff=cutoff,temporal=model,seasonal=seasonal,horizon_month=h,person_years=exposure,draws=draws,mean_expected=mean(mu),median_expected=median(mu),predicted_p025=unname(quantile(y,.025)),predicted_median=median(y),predicted_p975=unname(quantile(y,.975)),predicted_p999=unname(quantile(y,.999)),zero_fraction=mean(y==0),rate_above_one_fraction=mean(rate[k,]>1),top_one_percent_expected_share=sum(sort(mu,decreasing=TRUE)[seq_len(ceiling(.01*draws))])/sum(mu))
    }
   }
  }
 }
 write.csv(do.call(rbind,summaries),file.path(out,'prior_predictions.csv'),row.names=FALSE)
 write.csv(do.call(rbind,trajectories),file.path(out,'prior_trajectories.csv'),row.names=FALSE)
 write.csv(do.call(rbind,extrapolation),file.path(out,'prior_extrapolation.csv'),row.names=FALSE)
 writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt'))
 write.csv(data.frame(draws=draws,base_seed=93417L,data_used=FALSE,models_fitted=FALSE,accepted=FALSE),file.path(out,'settings.csv'),row.names=FALSE)
 writeLines('PRIOR_AUDIT_COMPLETE_NOT_ACCEPTANCE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage OUTPUT_DIRECTORY');run_combination_prior_audit(a[1])}
