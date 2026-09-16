source('scripts/monthly_local_seasonality.R')
fails<-function(expr) stopifnot(inherits(tryCatch({force(expr);NULL},error=identity),'error'))
d<-expand.grid(month=1:12,state=c('A','B','C'),stringsAsFactors=FALSE)
c<-local_seasonality_component(d)
stopifnot(ncol(c$A)==22L,qr(c$A)$rank==22L,min(eigen(c$Q,symmetric=TRUE,only.values=TRUE)$values)>0)
set.seed(418);z<-rnorm(ncol(c$A));h<-matrix(c$basis%*%z,12,3)
stopifnot(max(abs(rowSums(h)))<1e-12,max(abs(colSums(h)))<1e-12)
stopifnot(max(abs(diag(c$basis%*%solve(c$Q,t(c$basis)))-1))<1e-10)
# Cyclic smoothness is invariant to rotating calendar labels.
r<-local_seasonality_component(transform(d,month=month%%12+1L))
stopifnot(max(abs(c$A%*%solve(c$Q,t(c$A))-r$A%*%solve(r$Q,t(r$A))))<1e-10)
# Future rows, repeated observations, outcomes, and input order cannot change prior.
future<-local_seasonality_component(rbind(d,d),states=c$states)
stopifnot(identical(c$Q,future$Q),identical(c$A,future$A[1:36,,drop=FALSE]))
rev<-local_seasonality_component(d[36:1,],states=c$states)
stopifnot(identical(c$A,rev$A[36:1,,drop=FALSE]))
fails(local_seasonality_component(transform(d,month=0)))
fails(local_seasonality_component(transform(d,state='A')))
fails(local_seasonality_component(d,states=c('A','B')))
fails(local_seasonality_component(d,sd_tail=1))
f<-y~1;ff<-local_seasonality_formula(f,c)
stopifnot(identical(f,y~1),'local_season'%in%all.vars(ff))
fails(local_seasonality_formula(ff,c))
cat('LOCAL SEASONALITY ALGEBRA PASS\n')
if('--inla'%in%commandArgs(TRUE)) {
  stopifnot(requireNamespace('INLA',quietly=TRUE),packageVersion('INLA')==package_version('26.08.07'))
  # Dense repeated synthetic series: opposite A/B seasons, no C departure.
  dd<-d[rep(1:36,each=8),];cc<-local_seasonality_component(dd)
  truth<-c(A=1,B=-1,C=0)[dd$state]*.6*sin(2*pi*dd$month/12)
  set.seed(420);dd$y<-rpois(nrow(dd),exp(4+truth))
  stack<-INLA::inla.stack(data=list(y=dd$y),A=list(1,cc$A),
    effects=list(data.frame(intercept=rep(1,nrow(dd))),cc$effects),tag='all')
  f<-INLA::f;formula<-local_seasonality_formula(y~0+intercept,cc)
  fit<-INLA::inla(formula,data=INLA::inla.stack.data(stack),family='poisson',
    control.predictor=list(A=INLA::inla.stack.A(stack),compute=TRUE),num.threads='2:1')
  beta<-fit$summary.random$local_season$mean
  predicted<-drop(cc$A%*%beta)
  stopifnot(isTRUE(fit$ok),all(is.finite(predicted)),sqrt(mean((predicted-truth)^2))<.15)
  hh<-matrix(cc$basis%*%beta,12,3)
  stopifnot(max(abs(rowSums(hh)))<1e-10,max(abs(colSums(hh)))<1e-10)
  cat('LOCAL SEASONALITY PINNED INLA SYNTHETIC PASS\n')
}
# Off path delegates original function arguments exactly, without INLA setup.
fit_monthly_model<-function(...)list(...)
args<-fit_monthly_local_seasonality(d,24000,local_seasonality=FALSE)
stopifnot(identical(args[[1]],d),identical(args[[2]],24000),identical(args[[3]],TRUE))
if('--inla'%in%commandArgs(TRUE)) {
  source('scripts/county_forecast_model.R');source('scripts/monthly_seasonal_model.R')
  dates<-expand.grid(month=1:12,year=2010:2013,area=c('01','02','03'),stringsAsFactors=FALSE)
  dates$state<-c('A','B','C')[match(dates$area,c('01','02','03'))]
  dates$person_years<-c(25000,50000,100000)[match(dates$area,c('01','02','03'))];dates$observation_status<-'SYNTHETIC_COMPLETE';attr(dates,'synthetic')<-TRUE
  set.seed(444);dates$count<-rnbinom(nrow(dates),mu=dates$person_years*.002*exp(c(A=1,B=-1,C=0)[dates$state]*.4*sin(2*pi*dates$month/12)),size=20)
  fit<-fit_monthly_local_seasonality(dates,2012*12+11,temporal_model='ar1',threads=2L)
  stopifnot(isTRUE(fit$ok),length(attr(fit,'local_seasonality_prediction_indices'))==nrow(dates),
    all(is.finite(fit$summary.fitted.values$mean)),
    identical(attr(fit,'monthly_specification')$reference_version,'monthly_ar1_cycle_v1'))
  stopifnot(fit$mode$mode.status==0)
  selected<-which(dates$year<=2012)
  truth<-dates$person_years*.002*exp(c(A=1,B=-1,C=0)[dates$state]*.4*sin(2*pi*dates$month/12))
  count_mean<-local_seasonality_count_mean(fit)
  stopifnot(mean(abs(count_mean[selected]-truth[selected])/truth[selected])<.2)
  # Rate summaries must be converted exactly once; permuted indices preserve order.
  stopifnot(max(fit$summary.fitted.values$mean[attr(fit,'local_seasonality_prediction_indices')])<.01)
  sampled<-sample_monthly_local_seasonality(fit,c(120,1,70),draws=120L,seed=421L,batch_size=40L)
  stopifnot(identical(sampled$exposure,dates$person_years[c(120,1,70)]),
    max(abs(rowMeans(sampled$mu)/count_mean[c(120,1,70)]-1))<.15)
  fails(sample_monthly_local_seasonality(fit,1,seed=NA_real_))
  fit_rw1<-fit_monthly_local_seasonality(dates,2012*12+11,temporal_model='rw1',threads=2L)
  stopifnot(isTRUE(fit_rw1$ok),fit_rw1$mode$mode.status==0,
    mean(abs(local_seasonality_count_mean(fit_rw1)[selected]-truth[selected])/truth[selected])<.25)
  cat('LOCAL SEASONALITY NB AR1/RW1 AND VARIABLE EXPOSURE COUNT SCALE PASS\n')
}
