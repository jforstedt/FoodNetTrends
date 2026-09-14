source('scripts/monthly_classification_model.R');source('scripts/audit_monthly_classification.R')
reject<-function(x)stopifnot(inherits(try(force(x),silent=TRUE),'try-error'))
# Stable exact log densities, including probabilities too close to boundaries for plogis.
eta<-c(-1000,1000,-2,2,0);n<-c(10,10,12,12,0);y<-c(1,9,2,10,0)
z<-classification_log_density(y,n,eta);stopifnot(all(is.finite(z)),max(abs(z[3:5]-dbinom(y[3:5],n[3:5],plogis(eta[3:5]),log=TRUE)))<1e-12)
reject(classification_log_density(11,10,0))
d<-expand.grid(state=c('A','B'),month=1:12,year=2012:2018,stringsAsFactors=FALSE)
d$classification_denominator<-10L;d$classification_denominator[d$state=='B'&d$year==2016]<-0L
# Include an all-zero-success training site; no pseudocounts introduced.
d$cidt_classified<-ifelse(d$state=='B',0L,2L);d$cx_classified<-d$classification_denominator-d$cidt_classified
x<-prepare_monthly_classification(d,2015,'site');x$spec$temporal<-'rw1';x$spec$seasonal<-FALSE;x$spec$spatial<-'none';fit<-list(ok=TRUE,mode=list(mode.status=0),misc=list(configs=list()),.args=list(family='binomial',Ntrials=x$data$Ntrials,data=x$data),summary.linear.predictor=data.frame(mean=rep(0,nrow(x$data))))
attr(fit,'monthly_classification_data')<-x$data;attr(fit,'monthly_classification_specification')<-x$spec
held<-x$data$year>2015;truth<-x$data[held,c('state','year','month')];j<-match(paste(truth$state,truth$year,truth$month),paste(d$state,d$year,d$month))
truth$observed<-d$cidt_classified[j];truth$denominator<-d$classification_denominator[j]
# Shared random offset preserves joint correlations across rows; sample IDs reversed to test mapping.
mock<-function(n,fit,selection,seed,num.threads,skew.corr) {
 ix<-rev(selection$Predictor)
 lapply(seq_len(n),function(j){eta<-rep(qlogis(.2)+rnorm(1,0,.2),length(ix));list(latent=matrix(eta,ncol=1,dimnames=list(paste0('Predictor:',ix),NULL)))})
}
set.seed(11);a<-classification_posterior_reports(fit,truth,2015,12345,draws=20,batch_size=10,sampler=mock)
set.seed(999);b<-classification_posterior_reports(fit,truth,2015,12345,draws=20,batch_size=10,sampler=mock)
stopifnot(identical(a,b),nrow(a$stream_scores)==2*3*5,nrow(a$aggregate_predictions)==3*3*5)
zero<-a$stream_scores$state=='B'&a$stream_scores$year==2016
stopifnot(all(a$stream_scores$eligible_cells[zero]==0),all(is.na(a$stream_scores$mean_log_score[zero])),all(is.na(a$stream_scores$max_cell_density_relative_mcse[zero])))
z<-a$aggregate_predictions[a$aggregate_predictions$state=='B'&a$aggregate_predictions$year==2016,]
stopifnot(all(z$denominator==0),all(z$mean_expected==0),all(z$upper95==0))
# Catchment predictions must be sums of the same joint site draws, not interval endpoints.
g<-a$aggregate_draws
for(year in 2016:2018){i<-which(g$keys$state=='ALL'&g$keys$year==year);j<-which(g$keys$state!='ALL'&g$keys$year==year);stopifnot(max(abs(g$expected[i,]-colSums(g$expected[j,,drop=FALSE])))<1e-12,identical(as.numeric(g$predictive[i,]),as.numeric(colSums(g$predictive[j,,drop=FALSE]))))}
bad<-truth;bad$denominator[1]<-11;reject(classification_posterior_reports(fit,bad,2015,123,20,sampler=mock))
badfit<-fit;badfit$.args$data$y[held]<-1;reject(validate_classification_saved(badfit,truth,2015))
badfit<-fit;dd<-attr(badfit,'monthly_classification_data');dd$cidt_classified[held]<-1;attr(badfit,'monthly_classification_data')<-dd;reject(validate_classification_saved(badfit,truth,2015))
# All heldout zero denominators should produce explicit missing scores, without sampling.
allzero<-d;allzero$classification_denominator[allzero$year>2015]<-0;allzero$cidt_classified[allzero$year>2015]<-0;allzero$cx_classified[allzero$year>2015]<-0
xx<-prepare_monthly_classification(allzero,2015,'site');ff<-fit;ff$.args$data<-xx$data;ff$.args$Ntrials<-xx$data$Ntrials;attr(ff,'monthly_classification_data')<-xx$data
zt<-truth;zt$observed<-0;zt$denominator<-0
zz<-classification_posterior_reports(ff,zt,2015,123,20,sampler=function(...)stop('Must not sample empty scored domain'))
stopifnot(all(is.na(zz$stream_scores$mean_log_score)),all(zz$aggregate_predictions$mean_expected==0))
cat('Classification density, joint aggregation, masking, sparse-domain and reproducibility checks PASS\n')
