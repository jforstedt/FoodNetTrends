source('scripts/run_monthly_spline_factorial.R')
serial<-seq(2004*12,2008*12+11);cutoff<-2005L
path<-Sys.getenv('SPLINE_FACTORIAL_TEST_BASIS','/tmp/spline_factorial_test_basis.rds')
if('--prepare'%in%commandArgs(TRUE)) {
 saveRDS(monthly_combination_basis(serial,cutoff*12+11),path)
 quit(status=0)
}
b<-readRDS(path)
d<-expand.grid(area=c('01001','01003','02001','02003'),serial=serial)
d$fips<-as.character(d$area);d$state<-ifelse(d$area%in%c('01001','01003'),'AA','BB')
d$year<-d$serial%/%12;d$month<-d$serial%%12+1
d$person_years<-10000+(seq_len(nrow(d))%%7)*2000
set.seed(815);d$count<-rnbinom(nrow(d),mu=d$person_years*.0002*exp(.3*sin(2*pi*d$month/12)),size=20)
d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
held<-d$year>cutoff;pred<-d[held,c('fips','state','year','month')];pred$observed<-d$count[held]
poison<-d;poison$count[held]<-Inf
for(seasonal in c(FALSE,TRUE)) {
 fit<-fit_monthly_combination(poison,cutoff*12+11,'spline',seasonal,threads=2,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',basis=b)
 obj<-validate_saved_monthly_spline(fit,pred,cutoff,seasonal)
 stopifnot(identical(obj$indices,which(held)),all(is.na(obj$data$count[held])))
 bad<-pred;bad$month[1]<-12
 stopifnot(inherits(try(validate_saved_monthly_spline(fit,bad,cutoff,seasonal),silent=TRUE),'try-error'))
 work<-tempfile('spline-sampling-',tmpdir='/tmp');dir.create(work)
 saveRDS(fit,file.path(work,'fit.rds'));write.csv(pred,file.path(work,'truth.csv'),row.names=FALSE)
 set.seed(9251) # INLA also uses R RNG for hyperparameter configuration selection.
 audit_monthly_saved(file.path(work,'fit.rds'),file.path(work,'truth.csv'),cutoff,seasonal,file.path(work,'result'),640000000,draws=100L,adapter=validate_saved_monthly_spline)
 tails<-read.csv(file.path(work,'result/aggregate_tails.csv'));scores<-read.csv(file.path(work,'result/stream_scores.csv'))
 stopifnot(nrow(tails)==45,nrow(scores)==30,all(is.finite(scores$mean_log_score)),all(tails$mean_expected>0))
 # Marginal rate means times exposure independently check the audited count scale.
 expected<-fit$summary.fitted.values[which(held),'mean']*d$person_years[held]
 ratio<-sum(tails$mean_expected[tails$stream==0&tails$state=='ALL'])/sum(expected)
 cat('Seasonal',seasonal,'audited/marginal mean ratio',ratio,'\n')
 # Long-horizon arithmetic means are tail-sensitive; test count scale against
 # the independent sampler using exactly the same posterior seed instead.
 set.seed(9251)
 direct<-sample_monthly_combination(fit,which(held),draws=100L,seed=640000000,batch_size=100L)
 stored<-readRDS(file.path(work,'result/aggregate_draws_INTERNAL.rds'))
 expected_annual<-rowsum(direct$mu,pred$year,reorder=TRUE)
 stopifnot(isTRUE(all.equal(unname(stored$expected[stored$keys$state=='ALL',1:100]),unname(expected_annual),tolerance=1e-10)))
 first<-held & d$year==cutoff+1
 first_ratio<-sum(tails$mean_expected[tails$stream==0&tails$state=='ALL'&tails$year==cutoff+1])/sum(fit$summary.fitted.values[which(first),'mean']*d$person_years[first])
 cat('First-year audited/marginal ratio',first_ratio,'saved test',work,'\n')
 stopifnot(is.finite(first_ratio),first_ratio>.6,first_ratio<1.5)
}
cat('Actual spline fit, masking, APredictor exposure and four-stream scoring PASS\n')
