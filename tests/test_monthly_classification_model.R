source('scripts/monthly_classification_model.R');source('scripts/monthly_spatial_combination.R')
nodes<-data.frame(fips=c('a','b','c','d'),state=c('A','A','B','B'));edges<-data.frame(fips_a=c('a','c'),fips_b=c('b','d'))
d<-expand.grid(fips=nodes$fips,month=1:12,year=2012:2019);d$state<-nodes$state[match(d$fips,nodes$fips)]
set.seed(937);d$classification_denominator<-sample(8:25,nrow(d),TRUE);d$classification_denominator[1]<-0
p<-plogis(-2+.3*sin(2*pi*d$month/12)+.08*(d$year-2012));d$cidt_classified<-rbinom(nrow(d),d$classification_denominator,p);d$cx_classified<-d$classification_denominator-d$cidt_classified
site<-aggregate(d[c('cidt_classified','cx_classified','classification_denominator')],d[c('state','year','month')],sum)
reject<-function(x)stopifnot(inherits(try(force(x),silent=TRUE),'try-error'))
x<-prepare_monthly_classification(d,2015,'county');stopifnot(nrow(x$data)==4*84,all(is.na(x$data$y[x$data$year>2015|x$data$Ntrials==0])),all(is.na(x$data$cx_classified[x$data$year>2015])),ncol(x$spec$trend_constraint$A)==84)
poison<-d;poison$cidt_classified[d$year>2015]<-Inf;poison$cx_classified[d$year>2015]<- -Inf
stopifnot(identical(x,prepare_monthly_classification(poison,2015,'county')))
stopifnot(identical(x,prepare_monthly_classification(d[nrow(d):1,],2015,'county')))
reject(prepare_monthly_classification(d[-1,],2015,'county'));bad<-d;bad$classification_denominator[2]<- -1;reject(prepare_monthly_classification(bad,2015,'county'))
bad<-d;bad$cidt_classified[3]<-999;reject(prepare_monthly_classification(bad,2015,'county'))
for(n in c(48,60)) {a<-monthly_classification_scale(n);stopifnot(abs(exp(mean(log(rowSums((a$factor/sqrt(a$scale))^2))))-1)<1e-10,max(abs(colSums(a$factor)))<1e-10)}
args<-commandArgs(TRUE)
if(length(args)) {
 id<-as.integer(args[1]);arms<-rbind(expand.grid(level='site',temporal=c('rw1','ar1'),seasonal=c(FALSE,TRUE),spatial='none'),expand.grid(level='county',temporal=c('rw1','ar1'),seasonal=c(FALSE,TRUE),spatial=c('iid','bym2')))
 a<-arms[id,];fit<-fit_monthly_classification(if(a$level=='site')site else d,2015,as.character(a$level),as.character(a$temporal),a$seasonal,as.character(a$spatial),nodes,edges,threads=1)
 stopifnot(isTRUE(fit$ok),fit$mode$mode.status==0)
 dd<-attr(fit,'monthly_classification_data');stopifnot(all(is.na(fit$.args$data$y[dd$year>2015|dd$Ntrials==0])),identical(as.numeric(fit$.args$Ntrials),as.numeric(dd$Ntrials)),all(is.finite(fit$summary.fitted.values$mean)),all(fit$summary.fitted.values$mean>=0&fit$summary.fitted.values$mean<=1))
 s<-INLA::inla.posterior.sample(10,fit,seed=123,num.threads='1:1',skew.corr=FALSE);nm<-rownames(s[[1]]$latent);ix<-grep('^Predictor:',nm);stopifnot(length(ix)==nrow(dd),all(is.finite(plogis(s[[1]]$latent[ix]))))
 if(length(args)>1)saveRDS(fit,args[2])
 cat('CLASSIFICATION SYNTHETIC ARM',id,as.character(a$level),as.character(a$temporal),a$seasonal,as.character(a$spatial),'PASS\n')
}
cat('Classification domain,masking,prior-scale checks PASS\n')
