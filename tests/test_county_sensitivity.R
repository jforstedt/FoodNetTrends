source('scripts/fit_county_pilot.R');source('scripts/diagnose_saved_county_pilot.R');source('scripts/county_sensitivity.R')
set.seed(25);n<-16L;adj<-matrix(0,n,n)
for(i in c(1:7,9:15)){adj[i,i+1]<-1;adj[i+1,i]<-1}
d<-expand.grid(area=1:n,time=1:6);d<-d[order(d$area,d$time),]
d$fips<-sprintf('%05d',d$area);d$year<-2003L+d$time;d$state<-factor(ifelse(d$area<=8,'AA','BB'));d$state_id<-as.integer(d$state)
d$population<-10000+d$area*500;d$count<-rnbinom(nrow(d),mu=d$population*exp(log(.0002)+.05*d$time),size=12)
obj<-list(data=d,adj=adj,ids=sort(unique(d$fips)),years=2004:2009)
b<-tempfile();dir.create(b);INLA::inla.setOption(num.threads='2:1')
for(v in c('spatial','iid'))for(time in c(FALSE,TRUE)) {
 out<-file.path(b,paste(v,time));dir.create(out)
 sensitivity_prior(obj,v,out,county_sd=if(time)1 else 2,county_time=time,n=100)
 fit<-sensitivity_fit(obj,v,county_sd=if(time)1 else 2,county_time=time,threads=2)
 fitted_report(fit,d,out);saved_diagnostics(fit,d,out,draws=100)
 stopifnot(is.finite(fit$waic$waic),length(fit$cpo$cpo)==nrow(d),
   ('county_time'%in%names(fit$summary.random))==time,
   sum(fit$summary.fitted.values$mean)/sum(d$count)>.5,sum(fit$summary.fitted.values$mean)/sum(d$count)<2)
 if(time)stopifnot(nrow(fit$summary.random$county_time)==n*6)
 cat('PASS actual',v,'county_time=',time,'fit, prior simulation, posterior checks and count scale\n')
}
unlink(b,recursive=TRUE)
