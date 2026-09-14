source('scripts/audit_spatial_residuals.R')
reject<-function(x)stopifnot(inherits(try(force(x),silent=TRUE),'try-error'))
nodes<-data.frame(fips=c('a','b','c','d'),state=c('A','A','B','B'));edges<-data.frame(fips_a=c('a','c'),fips_b=c('b','d'))
g<-monthly_spatial_graph(data.frame(area=nodes$fips,state=nodes$state),nodes,edges)
stopifnot(is.na(spatial_residual_moran(rep(1,4),g$adj)),is.na(spatial_residual_moran(1:4,matrix(0,4,4))),abs(spatial_residual_moran(c(1,1,-1,-1),g$adj)-1)<1e-12)
d<-expand.grid(fips=nodes$fips,month=1:6,year=2013);d$state<-nodes$state[match(d$fips,nodes$fips)];d$observed<-10
mu<-11/exp(ifelse(d$state=='A',1,-1))-1
r<-spatial_residual_reports(d,mu,g);stopifnot(all(is.na(r$monthly$within_state_centered_moran)),all(abs(r$monthly$log1p_residual_moran-1)<1e-12))
j<-rev(seq_len(nrow(d)));r2<-spatial_residual_reports(d[j,],mu[j],g);stopifnot(isTRUE(all.equal(r$state_year,r2$state_year)),isTRUE(all.equal(r$monthly,r2$monthly)))
# January/February then April/May/June: no February-to-April lag is invented.
keep<-d$month!=3;r3<-spatial_residual_reports(d[keep,],mu[keep]+d$month[keep]/10,g)
stopifnot(r3$state_year$lag_pairs[r3$state_year$state=='ALL']==12)
reject(spatial_residual_reports(d,c(mu[-1],Inf),g));reject(spatial_residual_reports(rbind(d,d[1,]),c(mu,mu[1]),g))
# APredictor rows are the observations; appended latent Predictor rows are not.
fake<-list(summary.fitted.values=data.frame(mean=c(7,2,999),row.names=c('fitted.APredictor.002','fitted.APredictor.001','fitted.Predictor.001')))
obj<-list(data=data.frame(x=1:2),indices=1:2,predictor='APredictor',exposure=c(10,100))
stopifnot(identical(as.numeric(spatial_saved_expected(fake,obj)),c(20,700)))
rownames(fake$summary.fitted.values)[2]<-'fitted.APredictor.003';reject(spatial_saved_expected(fake,obj))
if('--fit'%in%commandArgs(TRUE)) {
 d<-expand.grid(area=nodes$fips,year=2000:2005,month=1:12);d$fips<-as.character(d$area);d$state<-nodes$state[match(d$area,nodes$fips)];d$person_years<-20000;d$observation_status<-'SYNTHETIC_COMPLETE';attr(d,'synthetic')<-TRUE
 set.seed(456);d$count<-rnbinom(nrow(d),mu=4,size=20)
 temporal<-if('--spline'%in%commandArgs(TRUE))'spline' else 'ar1'
 basis<-if(temporal=='spline')readRDS('/tmp/monthly_spatial_test_basis.rds') else NULL
 fit<-fit_monthly_spatial_combination(d,2002*12+11,nodes,edges,temporal,TRUE,threads=1,basis=basis)
 spec<-attr(fit,'monthly_specification');spec$coverage<-'EXPLORATORY_ASSUMED_CONTINUOUS';attr(fit,'monthly_specification')<-spec
 work<-tempfile();dir.create(work);saveRDS(fit,file.path(work,'fit.rds'));if(temporal=='spline')saveRDS(fit,'/tmp/spatial_residual_spline_fit.rds');truth<-d[d$year>2002,c('fips','state','year','month')];truth$observed<-d$count[d$year>2002]
 write.csv(truth,file.path(work,'truth.csv'),row.names=FALSE);write.csv(nodes,file.path(work,'nodes.csv'),row.names=FALSE);write.csv(edges,file.path(work,'edges.csv'),row.names=FALSE)
 audit_spatial_residuals(file.path(work,'fit.rds'),file.path(work,'truth.csv'),file.path(work,'nodes.csv'),file.path(work,'edges.csv'),2002,temporal,TRUE,file.path(work,'audit'))
 stopifnot(file.exists(file.path(work,'audit/county_month_residuals_INTERNAL.csv')),nrow(read.csv(file.path(work,'audit/monthly_global_residuals.csv')))==36,nrow(read.csv(file.path(work,'audit/state_year_residuals.csv')))==9)
 reported<-read.csv(file.path(work,'audit/county_month_residuals_INTERNAL.csv'))
 ix<-which(d$year>2002);expected<-fit$summary.fitted.values[ix,'mean']*(if(temporal=='spline')d$person_years[ix] else 1)
 stopifnot(isTRUE(all.equal(reported$expected,as.numeric(expected),tolerance=1e-10)))
 cat('Actual saved',temporal,'BYM2 residual audit count-scale PASS\n')
}
cat('Moran degeneracy, state-centering, permutation, temporal-gap and invalid-input tests PASS\n')
