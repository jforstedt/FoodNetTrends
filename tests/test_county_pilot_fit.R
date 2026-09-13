source('scripts/fit_county_pilot.R')
set.seed(25);n<-16L;adj<-matrix(0,n,n)
for(i in c(1:7,9:15)){adj[i,i+1]<-1;adj[i+1,i]<-1}
d<-expand.grid(area=1:n,time=1:6);d<-d[order(d$area,d$time),]
d$fips<-sprintf('%05d',d$area);d$year<-2003L+d$time;d$state<-factor(ifelse(d$area<=8,'AA','BB'));d$state_id<-as.integer(d$state)
d$population<-10000+d$area*500;d$count<-rnbinom(nrow(d),mu=d$population*exp(log(.0002)+.05*d$time),size=12)
obj<-list(data=d,adj=adj,ids=sort(unique(d$fips)),years=2004:2009)
base<-tempfile('pilot-fit-test-');dir.create(base);audit<-file.path(base,'audit');dir.create(file.path(audit,'reports'),recursive=TRUE)
writeLines('INPUT_AUDIT_PASS',file.path(audit,'reports/status.txt'))
saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'))
write.csv(data.frame(fips=obj$ids,state=as.character(d$state[match(obj$ids,d$fips)]),neighbors=rowSums(adj)),file.path(audit,'reports/graph_nodes.csv'),row.names=FALSE)
e<-which(upper.tri(adj)&adj==1,arr.ind=TRUE)
write.csv(data.frame(fips_a=obj$ids[e[,1]],fips_b=obj$ids[e[,2]]),file.path(audit,'reports/graph_edges.csv'),row.names=FALSE)
write.csv(transform(d,population_status='ok'),file.path(audit,'reports/population_audit.csv'),row.names=FALSE)
r<-aggregate(d$count,d[c('state','year')],sum);names(r)[3]<-'selected_cases';r$direct_matched_cases<-r$selected_cases
write.csv(r,file.path(audit,'reports/state_year_reconciliation.csv'),row.names=FALSE)
f<-file.path(base,'source');writeLines('unchanged input',f)
write.csv(data.frame(file=f,md5=unname(tools::md5sum(f))),file.path(audit,'reports/input_checksums.csv'),row.names=FALSE)
validated<-validate_panel(audit,FALSE);stopifnot(identical(validated$adj,adj))
for(bad in list(d[-1,],transform(d,population=population+1),transform(d,count=count+1))){
 saveRDS(bad,file.path(audit,'county_panel_INTERNAL.rds'))
 stopifnot(inherits(try(validate_panel(audit,FALSE),silent=TRUE),'try-error'))
}
saveRDS(d,file.path(audit,'county_panel_INTERNAL.rds'));writeLines('changed input',f)
stopifnot(inherits(try(validate_panel(audit,FALSE),silent=TRUE),'try-error'))
cat('PASS incomplete panel, changed populations/counts, and changed source checksums rejected\n')
if(requireNamespace('INLA',quietly=TRUE)) {
 INLA::inla.setOption(num.threads='2:1')
 for(v in c('spatial','iid')){
  out<-file.path(base,v,'reports');dir.create(out,recursive=TRUE)
  prior_check(obj,v,out,n=100)
  fit<-fit_pilot(obj,v,out,threads=2,draws=100)
  rr<-read.csv(file.path(out,'state_reference_rr.csv'))
  stopifnot(all(rr$median[rr$year==2009]==1),all(rr$lower[rr$year==2009]==1),all(rr$upper[rr$year==2009]==1))
  cr<-read.csv(file.path(out,'county_reference_rr_INTERNAL.csv'))
  stopifnot(all(cr$median[cr$year==2009]==1),all(cr$lower[cr$year==2009]==1),all(cr$upper[cr$year==2009]==1))
  z<-read.csv(file.path(out,'county_incidence_INTERNAL.csv'));stopifnot(nrow(z)==nrow(d),all(is.finite(z$mean)))
  # Detect a missing/doubled offset or incorrect posterior Predictor extraction.
  expected_total<-sum(z$mean*d$population/1e5)
  stopifnot(expected_total/sum(d$count)>.5,expected_total/sum(d$count)<2)
  st<-read.csv(file.path(out,'state_incidence.csv'))
  pop<-aggregate(d$population,d[c('state','year')],sum)
  st<-merge(st,pop,by=c('state','year'))
  stopifnot(abs(sum(st$mean*st$x/1e5)-expected_total)<1e-6)
  stopifnot(file.exists(file.path(dirname(out),'fit_INTERNAL.rds')))
  cat('PASS actual',v,'fit, joint aggregation, reference identity and saved checkpoint\n')
 }
} else cat('SKIP actual fits: INLA unavailable in this R environment\n')
unlink(base,recursive=TRUE)
