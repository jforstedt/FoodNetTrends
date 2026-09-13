source('scripts/diagnose_saved_county_pilot.R')
# Test against existing synthetic checkpoints; never generate new fits here.
a<-commandArgs(TRUE);if(length(a)!=1L)stop('Supply synthetic saved-fit root')
set.seed(25);d<-expand.grid(area=1:16,time=1:6);d<-d[order(d$area,d$time),]
d$fips<-sprintf('%05d',d$area);d$year<-2003L+d$time;d$state<-factor(ifelse(d$area<=8,'AA','BB'))
d$population<-10000+d$area*500;d$count<-rnbinom(nrow(d),mu=d$population*exp(log(.0002)+.05*d$time),size=12)
# Deliberately forbid a fitting call while allowing posterior sampling.
trace('inla',where=asNamespace('INLA'),tracer=quote(stop('Refit forbidden')),print=FALSE)
base<-tempfile();dir.create(base)
for(v in c('spatial','iid')) {
 path<-file.path(a[1],v,'fit_INTERNAL.rds');before<-tools::md5sum(path)
 out<-file.path(base,v);dir.create(out)
 z<-saved_diagnostics(readRDS(path),d,out,draws=100L)
 r<-read.csv(file.path(out,'zero_checks_INTERNAL.csv'))
 overall<-r[r$grouping=='overall',]
 stopifnot(overall$observed_zeros==sum(d$count==0),overall$cells==nrow(d),
   all(r$replicated_lower<=r$replicated_median),all(r$replicated_median<=r$replicated_upper),
   all(r$predictive_upper_tail>=0&r$predictive_upper_tail<=1),
   identical(before,tools::md5sum(path)),length(z$waic)==nrow(d))
 for(kind in c('county','state','year','population','state_year')) {
   subset<-r[r$grouping==kind,]
   stopifnot(sum(subset$cells)==nrow(d),sum(subset$observed_zeros)==overall$observed_zeros,
     abs(sum(subset$expected_zeros_mean)-overall$expected_zeros_mean)<1e-8)
 }
 cat('PASS saved',v,'sampling, zero aggregation, intervals and immutable checkpoint\n')
}
untrace('inla',where=asNamespace('INLA'));unlink(base,recursive=TRUE)
