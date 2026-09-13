source('scripts/county_forecast_historical_reference.R')
d<-data.frame(fips=rep(c('00001','00002'),each=5),state='AA',year=rep(2004:2008,2),population=100,count=c(0,0,0,1,0,3,4,5,8,9))
a<-tempfile();b<-tempfile();z<-county_historical_reference(d,2006,a)
x<-d;x$count[x$year>2006]<-1000;zz<-county_historical_reference(x,2006,b)
stopifnot(identical(z$mean_expected,zz$mean_expected),identical(z$lower95,zz$lower95),all(is.finite(z$log_predictive_density)),
 all(z$lower95<=z$upper95),abs(z$mean_expected[1]-(.5/300*100))<1e-12)
truncated<-d[d$year<2008,];zzz<-county_historical_reference(truncated,2006,tempfile())
stopifnot(identical(z$mean_expected[z$year==2007],zzz$mean_expected))
cat('PASS training-only historical reference, zero histories and horizon invariance\n')
