source('scripts/fit_classification_trends.R')
d<-expand.grid(state=c('AA','BB','CC'),year=2012:2019,stringsAsFactors=FALSE);d$classification_denominator<-200;d$parasitic_classified<-0
set.seed(401);d$cidt_classified<-rbinom(nrow(d),200,plogis(-2+.25*(d$year-2012)+ifelse(d$state=='AA',-.2,.2)));d$cx_classified<-200-d$cidt_classified
x<-classification_data(d,2016);stopifnot(all(is.na(x$success[x$year>2016])),all(x$time_scaled==(x$year-2012)/4))
bad<-d;bad$classification_denominator[1]<-0;stopifnot(inherits(try(classification_data(bad,2016),silent=TRUE),'try-error'))
if('--fit'%in%commandArgs(TRUE)) {
 for(model in c('shared','site_slopes')) {
  input<-tempfile(fileext='.csv');write.csv(d,input,row.names=FALSE);out<-tempfile()
  run_classification(input,out,2016,model,390000000L,draws=100L)
  p<-read.csv(file.path(out,'predictions.csv'));stopifnot(nrow(p)==24,all(p$mean_probability>0&p$mean_probability<1),sum(p$evaluation=='CONDITIONAL_HINDCAST')==9)
  fit<-readRDS(file.path(out,'fit_INTERNAL.rds'));stopifnot(all(is.na(fit$.args$data$success[fit$.args$data$year>2016])))
 }
}
cat('Classification masking, domain and integration PASS\n')
changed<-d;held<-changed$year>2016;changed$cidt_classified[held]<-changed$classification_denominator[held]-changed$cidt_classified[held];changed$cx_classified<-changed$classification_denominator-changed$cidt_classified
used<-c('success','trials','time_scaled','site','slope_site','cell')
stopifnot(identical(classification_data(d,2016)[used],classification_data(changed,2016)[used]))
