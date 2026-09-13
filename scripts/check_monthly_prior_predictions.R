#!/usr/bin/env Rscript
# Marginal prior predictive audit of candidate settings; no data-driven tuning.
source('scripts/county_forecast_model.R');source('scripts/monthly_seasonal_prototype.R')
a<-commandArgs(TRUE);if(length(a)!=1)stop('Usage: OUTPUT_CSV')
set.seed(9271);n<-20000L;nt<-72L;horizon<-12L
trend_scale<-rw1_training_scale(nt)
# Draw exactly from PC priors on standardized SD, then centered Gaussian walks.
sd_trend<-rexp(n,rate=-log(.01)/.5)/sqrt(trend_scale)
x<-apply(matrix(rnorm((nt+horizon-1)*n),nt+horizon-1,n),2,cumsum)
x<-rbind(0,x);x<-sweep(x,2,colMeans(x[1:nt,,drop=FALSE]),'-');x<-sweep(x,2,sd_trend,'*')
cycle<-monthly_cycle_scale();e<-eigen(cycle$Q*cycle$scale,symmetric=TRUE);ix<-e$values>1e-10
B<-sweep(e$vectors[,ix],2,sqrt(e$values[ix]),'/')
season<-B%*%matrix(rnorm(11*n),11,n);season<-sweep(season,2,rexp(n,rate=-log(.01)/.5),'*')
county<-rnorm(n)*rexp(n,rate=-log(.01));intercept_noise<-rnorm(n);size<-exp(rnorm(n,log(20),1))
rows<-list();i<-0
for(center in c(.0002,.002))for(exposure in c(500,10000))for(month in c(72L,84L)) {
 rate<-exp(log(center)+intercept_noise+county+x[month,]+season[12,]);counts<-rnbinom(n,mu=exposure*rate,size=size)
 if(any(!is.finite(rate))||any(!is.finite(counts)))stop('Nonfinite prior draws')
 i<-i+1;rows[[i]]<-data.frame(intercept_rate=center,person_years=exposure,month_index=month,draws=n,
  rate_per_100k_p025=unname(quantile(rate*1e5,.025)),rate_per_100k_median=median(rate*1e5),rate_per_100k_p975=unname(quantile(rate*1e5,.975)),
  count_p025=unname(quantile(counts,.025)),count_median=median(counts),count_p975=unname(quantile(counts,.975)),zero_fraction=mean(counts==0))
}
write.csv(do.call(rbind,rows),a[1],row.names=FALSE)
cat('PRIOR AUDIT COMPLETE; settings remain unapproved for production\n')
