source('scripts/county_forecast_model.R')
source('scripts/county_spline_candidate.R')
source('scripts/monthly_seasonal_model.R')
source('scripts/monthly_spline_combination.R')
source('scripts/monthly_spatial_combination.R')
source('scripts/run_monthly_spatial_factorial.R')
serial<-2000*12+0:71;cutoff<-2003*12-1
nodes<-data.frame(fips=c('a','b','c','d'),state=c('A','A','B','B'))
edges<-data.frame(fips_a=c('a','c'),fips_b=c('b','d'))
d<-expand.grid(area=nodes$fips,serial=serial)
d$fips<-as.character(d$area)
d$state<-nodes$state[match(d$area,nodes$fips)];d$year<-d$serial%/%12;d$month<-d$serial%%12+1
set.seed(100);d$person_years<-20000;d$count<-rnbinom(nrow(d),mu=4*exp(.3*sin(2*pi*d$month/12)),size=20)
d$observation_status<-'SYNTHETIC_COMPLETE';attr(d,'synthetic')<-TRUE
G<-monthly_spatial_graph(d,nodes,edges)
stopifnot(G$n_components==2,G$n_edges==2,identical(G$ids,sort(nodes$fips)),
 identical(G,monthly_spatial_graph(d,nodes[4:1,],edges[2:1,])))
reject<-function(x)stopifnot(inherits(try(force(x),silent=TRUE),'try-error'))
reject(monthly_spatial_graph(d,nodes[-1,],edges))
reject(monthly_spatial_graph(d,nodes,edges[1,,drop=FALSE]))
reject(monthly_spatial_graph(d,nodes,rbind(edges,edges[1,])))
bad<-nodes;bad$state[1]<-'B';reject(monthly_spatial_graph(d,bad,edges))
actualnodes<-read.csv('analysis_configs/county_pilot/counties.csv',colClasses='character')
actualedges<-read.csv('analysis_configs/county_pilot/edges.csv',colClasses='character')
actual<-monthly_spatial_graph(data.frame(area=actualnodes$fips,state=actualnodes$state),actualnodes,actualedges)
stopifnot(length(actual$ids)==486,actual$n_components==10)
poison<-d;poison$count[poison$serial>cutoff]<-Inf
stopifnot(identical(monthly_model_data(d,cutoff),monthly_model_data(poison,cutoff)))
if('--prepare'%in%commandArgs(TRUE))saveRDS(monthly_combination_basis(serial,cutoff),'/tmp/monthly_spatial_test_basis.rds')
if(any(c('--fit','--ast')%in%commandArgs(TRUE))) {
 ff<-count~0+state+offset(log(person_years))+f(area,model='iid')+f(time,model='rw1')
 changed<-monthly_bym2_effect(G)(ff,monthly_model_data(d,cutoff)$data)
 stopifnot(identical(changed[[3]][[3]],ff[[3]][[3]]),grepl('bym2',paste(deparse(changed),collapse=''),fixed=TRUE))
 reject(monthly_bym2_effect(G)(count~state,monthly_model_data(d,cutoff)$data))
 cat('Noncounty formula preservation and absent area rejection PASS\n')
}
if('--fit'%in%commandArgs(TRUE)) {
 b<-readRDS('/tmp/monthly_spatial_test_basis.rds')
 for(temporal in c('rw1','ar1','spline'))for(seasonal in c(FALSE,TRUE)) {
  fit<-fit_monthly_spatial_combination(poison,cutoff,nodes,edges,temporal,seasonal,threads=2,basis=b)
  stopifnot(isTRUE(fit$ok),fit$mode$mode.status==0)
  # Exercise saved-result adapter with the production coverage contract.
  spec<-attr(fit,'monthly_specification');spec$coverage<-'EXPLORATORY_ASSUMED_CONTINUOUS';attr(fit,'monthly_specification')<-spec
  pred<-d[d$serial>cutoff,c('fips','state','year','month')];pred$observed<-d$count[d$serial>cutoff]
  checked<-validate_saved_monthly_spatial(fit,pred,2002L,seasonal)
  stopifnot(identical(checked$indices,which(d$serial>cutoff)))
  ix<-which(d$serial>cutoff)[1:12]
  post<-sample_monthly_combination(fit,ix,draws=50,seed=73521,batch_size=25)
  reference<-fit$summary.fitted.values[ix,'mean']
  if(temporal=='spline')reference<-reference*d$person_years[ix]
  ratio<-mean(post$mu)/mean(reference)
  stopifnot(all(is.finite(post$mu)),all(post$mu>0),is.finite(ratio),ratio>.5,ratio<2)
  cat('SPATIAL',temporal,seasonal,'count-scale ratio',ratio,'PASS\n')
 }
}
cat('Monthly spatial graph/masking/requested integration checks PASS\n')
