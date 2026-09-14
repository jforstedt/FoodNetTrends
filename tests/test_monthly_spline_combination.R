source('scripts/county_forecast_model.R')
source('scripts/county_spline_candidate.R')
source('scripts/monthly_seasonal_model.R')
source('scripts/monthly_spline_combination.R')
years<-2000:2004;serial<-2000*12+0:59;cutoff<-2003*12-1
basis_file<-Sys.getenv('MONTHLY_COMBINATION_TEST_BASIS')
if(nzchar(basis_file)) {
 prepared<-readRDS(basis_file);b<-prepared$b;b2<-prepared$b2
} else {
 b<-monthly_combination_basis(serial,cutoff)
 b2<-monthly_combination_basis(c(serial,2005*12+0:11),cutoff)
 if('--prepare'%in%commandArgs(TRUE))saveRDS(list(b=b,b2=b2),'/tmp/monthly_combination_test_basis.rds')
}
stopifnot(max(abs(b$nonlinear-b2$nonlinear[1:60,]))<1e-10,
  identical(b$slope,b2$slope[1:60]),qr(b$nonlinear[b$years<=cutoff,])$rank==4)
tr<-b$years<=cutoff
phase<-factor(b$years%%12,levels=0:11)
X<-cbind(1,b$slope,model.matrix(~phase)[,-1])
stopifnot(max(abs(crossprod(X[tr,],b$nonlinear[tr,])))<1e-8,
 abs(exp(mean(log(rowSums(b$nonlinear[tr,]^2))))-1)<1e-9)
d<-expand.grid(area=c('a','b','c','d'),serial=serial)
d$state<-ifelse(d$area%in%c('a','b'),'A','B');d$year<-d$serial%/%12;d$month<-d$serial%%12+1
set.seed(100);d$person_years<-20000;d$count<-rnbinom(nrow(d),mu=4*exp(.3*sin(2*pi*d$month/12)),size=20)
d$observation_status<-'SYNTHETIC_COMPLETE';attr(d,'synthetic')<-TRUE
poison<-d;poison$count[poison$serial>cutoff]<-Inf
stopifnot(identical(monthly_model_data(d,cutoff),monthly_model_data(poison,cutoff)))
# Design is a state temporal basis; counties within state share its exact row.
data<-monthly_model_data(d,cutoff)$data;dd<-data;dd$year<-d$serial
z<-county_spline_design(b,dd,data$state_id)
stopifnot(ncol(z$nonlinear)==8,ncol(z$slope)==2,
 identical(as.numeric(z$nonlinear[1,]),as.numeric(z$nonlinear[2,])))
if('--fit'%in%commandArgs(TRUE)) {
 for(temporal in c('rw1','spline'))for(seasonal in c(FALSE,TRUE)) {
  fit<-fit_monthly_combination(poison,cutoff,temporal,seasonal,threads=2,basis=b)
  stopifnot(isTRUE(fit$ok),fit$mode$mode.status==0)
  ix<-which(d$serial>cutoff)[1:12]
  post<-sample_monthly_combination(fit,ix,draws=50,seed=73521,batch_size=25)
  stopifnot(identical(dim(post$mu),c(12L,50L)),all(is.finite(post$mu)),all(post$mu>0),
   all(post$replicated>=0),all(post$size>0),mean(post$mu)>0.01,mean(post$mu)<1000)
  # Independent marginal fitted means verify APredictor exposure scale; posterior
  # Monte Carlo tolerance is deliberately broad for this tiny integration gate.
  reference<-fit$summary.fitted.values[ix,'mean']
  if(temporal=='spline')reference<-reference*d$person_years[ix] # E leaves fitted marginal on rate scale
  ratio<-mean(post$mu)/mean(reference)
  cat(temporal,seasonal,"sampling/marginal ratio",ratio,"mean count",mean(post$mu),"reference",mean(reference),"\n")
  stopifnot(is.finite(ratio),ratio>.5,ratio<2)
  if(temporal=='spline')stopifnot(identical(attr(fit,'monthly_combination_exposure'),d$person_years))
 }
}
cat('Monthly combination basis, masking, design and requested integration checks PASS\n')
