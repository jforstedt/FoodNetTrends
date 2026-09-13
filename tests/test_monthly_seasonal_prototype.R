source('scripts/county_forecast_model.R')
source('scripts/monthly_seasonal_prototype.R')
set.seed(731)
d<-expand.grid(area=1:4,serial=0:83)
d$year<-2004L+d$serial%/%12L;d$month<-d$serial%%12L+1L
d$state<-ifelse(d$area<=2,'AA','BB');d$person_years<-20000
d$observation_status<-'SYNTHETIC_COMPLETE'
truth<-.65*cos(2*pi*(1:12-7)/12)
d$count<-rnbinom(nrow(d),mu=d$person_years*.002*exp(truth[d$month]),size=50)
attr(d,'synthetic')<-TRUE;cutoff<-2009L*12L+11L
obj<-monthly_prototype_data(d,cutoff)
stopifnot(all(is.na(obj$data$count[!obj$training])),all(obj$spec$trend_constraint$A[1,73:84]==0))
z<-d;z$count[!obj$training]<-Inf
stopifnot(identical(monthly_prototype_data(z,cutoff),obj))
z<-d;attr(z,'synthetic')<-NULL
stopifnot(inherits(try(monthly_prototype_data(z,cutoff),silent=TRUE),'try-error'))
for(field in c('month','person_years','count')){
 z<-d;z[[field]][1]<- -1
 stopifnot(inherits(try(monthly_prototype_data(z,cutoff),silent=TRUE),'try-error'))
}
z<-d;z$observation_status[1]<-'UNVERIFIED'
stopifnot(inherits(try(monthly_prototype_data(z,cutoff),silent=TRUE),'try-error'))
z<-d[-1,];attr(z,'synthetic')<-TRUE
stopifnot(inherits(try(monthly_prototype_data(z,cutoff),silent=TRUE),'try-error'))
cycle<-monthly_cycle_scale();stopifnot(cycle$Q[1,12]==-1,all(rowSums(cycle$Q)==0),qr(cycle$Q)$rank==11)
e<-eigen(cycle$Q*cycle$scale,symmetric=TRUE);ix<-e$values>1e-10
cov<-tcrossprod(sweep(e$vectors[,ix],2,sqrt(e$values[ix]),'/'))
stopifnot(abs(exp(mean(log(diag(cov))))-1)<1e-10)
cat('Monthly structural and leakage checks PASS\n')
if('--fit'%in%commandArgs(TRUE)) {
 # Fixed tolerances for this synthetic engineering check, not production acceptance.
 seasonal<-fit_monthly_prototype(d,cutoff,TRUE)
 baseline<-fit_monthly_prototype(d,cutoff,FALSE)
 s<-seasonal$summary.random$season$mean
 stopifnot(length(s)==12,all(is.finite(s)),abs(sum(s))<1e-5,cor(s,truth)>.9,max(abs(s-truth))<.3)
 test<-!obj$training
 mu<-exp(seasonal$summary.linear.predictor$mean[test]);reference<-exp(baseline$summary.linear.predictor$mean[test])
 target<-d$person_years[test]*.002*exp(truth[d$month[test]])
 stopifnot(all(is.finite(mu)),mean((mu-target)^2)<mean((reference-target)^2))
 # Extend only the forecast domain; training scale and centering stay fixed.
 extra<-d[d$serial<12,];extra$year<-2011L;extra$serial<-extra$serial+84L;extra$count<-Inf
 long<-rbind(d,extra);attr(long,'synthetic')<-TRUE
 extended<-fit_monthly_prototype(long,cutoff,TRUE)
 a<-seasonal$summary.linear.predictor;b<-extended$summary.linear.predictor[seq_len(nrow(d)),]
 delta<-max(abs(a$mean-b$mean)/a$sd)
 stopifnot(delta<.05)
 draws<-sample_county_forecast(seasonal,which(test),draws=200L,seed=871L,batch_size=100L)
 stopifnot(all(is.finite(draws$mu)),all(is.finite(draws$replicated)),all(draws$replicated>=0),all(draws$size>0))
 set.seed(732);flat<-d;flat$count<-rnbinom(nrow(flat),mu=flat$person_years*.002,size=50)
 nullfit<-fit_monthly_prototype(flat,cutoff,TRUE)
 nullseason<-nullfit$summary.random$season$mean
 stopifnot(sqrt(mean(nullseason^2))<.15)
 cat(sprintf('No-seasonality check PASS: seasonal RMS %.4f; 200 joint predictive draws finite\n',sqrt(mean(nullseason^2))))
 cat(sprintf('Synthetic fits PASS: seasonal correlation %.4f; max seasonal error %.4f; horizon difference %.5f SD\n',cor(s,truth),max(abs(s-truth)),delta))
}
