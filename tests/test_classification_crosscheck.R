source('scripts/fit_classification_trends.R');source('scripts/diagnose_classification_saved.R');source('scripts/crosscheck_classification.R')
x<-data.frame(success=c(0,1,NA),year=2015:2017,trials=c(10,10,10))
y<-masked_classification(x,1L);stopifnot(is.na(y$success[1]),is.na(y$success[3]),y$success[2]==1,identical(y$trials,x$trials))
stopifnot(inherits(try(masked_classification(x,3L),silent=TRUE),'try-error'),inherits(try(masked_classification(x,integer()),silent=TRUE),'try-error'))
if('--fit'%in%commandArgs(TRUE)) {
 d<-expand.grid(state=c('AA','BB'),year=2012:2019,stringsAsFactors=FALSE);d$classification_denominator<-10;d$cidt_classified<-2;d$cx_classified<-8;d$parasitic_classified<-0
 fit<-fit_classification(d,2016L,'shared',threads=2L);fp<-tempfile();ip<-tempfile();flags<-tempfile();saveRDS(fit,fp);write.csv(d,ip,row.names=FALSE);write.csv(inspect_classification(fit,classification_data(d,2016L))$row_diagnostics,flags,row.names=FALSE)
 run_classification_crosscheck(fp,ip,flags,tempfile(),'AA',2012L,850000000L,draws=100L)
}
cat('Singleton mask and crosscheck PASS\n')
