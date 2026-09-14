source('tests/test_monthly_classification_model.R')
source('scripts/audit_monthly_classification.R')
fixtures<-Sys.getenv('FOODNET_CLASSIFICATION_FIXTURES','/tmp/classification_synthetic')
if(!dir.exists(fixtures))stop('Generate twelve synthetic model fixtures with test_monthly_classification_model.R first')
for(id in 1:12) {
 fit<-readRDS(file.path(fixtures,sprintf('arm%d.rds',id)));dd<-attr(fit,'monthly_classification_data');s<-attr(fit,'monthly_classification_specification')
 raw<-if(s$level=='site')site else d
 key<-function(x)paste(if('fips'%in%names(x))x$fips else x$state,x$state,x$year,x$month)
 held<-dd$year>2015;truth<-dd[held,intersect(c('fips','state','year','month'),names(dd)),drop=FALSE]
 j<-match(key(truth),key(raw));truth$observed<-raw$cidt_classified[j];truth$denominator<-raw$classification_denominator[j]
 result<-classification_posterior_reports(fit,truth,2015,610000+id*1000,draws=100,batch_size=100)
 ix<-result$cell_expected$row_id
 direct<-fit$summary.fitted.values$mean[ix]*dd$Ntrials[ix]
 ratio<-sum(result$cell_expected$mean_expected)/sum(direct)
 stopifnot(is.finite(ratio),ratio>.92,ratio<1.08)
 cat('ACTUAL CLASSIFICATION SCORE ARM',id,'count/probability scale ratio',ratio,'PASS\n')
}
