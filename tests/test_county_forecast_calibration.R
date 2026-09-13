source('scripts/fit_county_pilot.R')
source('scripts/county_forecast_calibration.R')
for(v in c('spatial','iid'))for(density in c('sparse','dense')) {
 a<-calibration_truth(density,v,1L,1L);b<-calibration_truth(density,v,1L,3L)
 ix<-b$truth$year<=a$cutoff+1L
 stopifnot(identical(a$truth,b$truth[ix,]),nrow(a$truth)==12L*9L,
   all(is.finite(a$truth$true_mu)),all(a$truth$count>=0))
 # Independent future increments preserve training latent draw/count prefix.
 stopifnot(identical(a$state_last,b$state_last),identical(a$county_last,b$county_last),
           identical(a$county,b$county))
 x<-calibration_oracle(a,1000L);y<-calibration_oracle(b,1000L)
 future<-b$truth[b$truth$year>b$cutoff,]
 stopifnot(identical(x$predictive,y$predictive[future$year==b$cutoff+1L,,drop=FALSE]))
 m<-calibration_metrics(a$truth[a$truth$year>a$cutoff,],x$predictive,x$mu,'ORACLE',1L,density,v,a$cutoff)
 stopifnot(nrow(m)==3L,all(m$coverage>=0&m$coverage<=1),all(m$mean_width>=0))
}
z<-calibration_interval(rep(1,20));stopifnot(z['lower']<1,z['upper']==1)
z<-calibration_interval(rep(c(.8,1),10));stopifnot(z['lower']<.9,z['upper']>.9)
cat('PASS synthetic training-domain truth, horizon prefix, oracle correlation and clustered uncertainty\n')
