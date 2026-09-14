source('scripts/fit_classification_trends.R');source('scripts/diagnose_classification_saved.R')
d<-expand.grid(state=c('AA','BB'),year=2012:2019,stringsAsFactors=FALSE);d$classification_denominator<-10;d$cidt_classified<-2;d$cx_classified<-8;d$parasitic_classified<-0
x<-classification_data(d,2016L)
f<-list(cpo=list(failure=c(1,rep(0,15)),cpo=rep(.2,16),pit=rep(.5,16)))
z<-inspect_classification(f,x);stopifnot(nrow(z$row_diagnostics)==16,sum(z$summary$flagged)==1,sum(z$summary$rows)==16)
f$cpo$failure<-1;stopifnot(inherits(try(inspect_classification(f,x),silent=TRUE),'try-error'))
if('--fit'%in%commandArgs(TRUE)) {
 # Only this synthetic test constructs a fit; the production diagnostic never does.
 fitpath<-tempfile(fileext='.rds');input<-tempfile(fileext='.csv')
 fit<-fit_classification(d,2016L,'shared',threads=2L);saveRDS(fit,fitpath);write.csv(d,input,row.names=FALSE)
 validate_classification_saved(fit,d,2016L,'shared')
 bad<-fit;bad$.args$data$success[bad$.args$data$year>2016]<-0
 stopifnot(inherits(try(validate_classification_saved(bad,d,2016L,'shared'),silent=TRUE),'try-error'))
 bad<-fit;bad$.args$data$trials[1]<-1
 stopifnot(inherits(try(validate_classification_saved(bad,d,2016L,'shared'),silent=TRUE),'try-error'))
 for(mode in c('inspect','precision'))run_saved_classification(fitpath,input,tempfile(),2016L,'shared',700000000L,mode,draws=50L)
}
cat('Saved classification diagnostics PASS\n')
stopifnot(inherits(try(run_saved_classification('missing','missing',tempfile(),2019L,'shared',1L,'precision'),silent=TRUE),'try-error'))
