source('scripts/fit_classification_trends.R');source('scripts/diagnose_classification_saved.R');source('scripts/recompute_classification_cpo.R')
x<-data.frame(state=c('AA','AA','AA'),year=2015:2017,success=c(0,1,NA))
a<-list(cpo=list(failure=c(1,0,NA),cpo=c(.01,.5,NA),pit=c(.1,.6,NA)));b<-a;b$cpo$failure[1]<-0;b$cpo$cpo[1]<-.2
z<-cpo_comparison(a,b,x);stopifnot(z$summary$resolved==1,z$summary$remaining_flagged==0)
b$cpo$cpo[1]<-NA;stopifnot(cpo_comparison(a,b,x)$summary$invalid_requested==1)
b<-a;b$cpo$cpo[2]<-.3;stopifnot(inherits(try(cpo_comparison(a,b,x),silent=TRUE),'try-error'))
if('--fit'%in%commandArgs(TRUE)) {
 # Artificially flag one cell to exercise manual CPO with a small synthetic model.
 d<-expand.grid(state=c('AA','BB'),year=2012:2019,stringsAsFactors=FALSE);d$classification_denominator<-10;d$cidt_classified<-2;d$cx_classified<-8;d$parasitic_classified<-0
 f<-fit_classification(d,2016L,'shared',threads=2L);f$cpo$failure[]<-NA;f$cpo$failure[!is.na(f$.args$data$success)]<-0;f$cpo$failure[1]<-1
 fitpath<-tempfile();input<-tempfile();flags<-tempfile();saveRDS(f,fitpath);write.csv(d,input,row.names=FALSE);write.csv(inspect_classification(f,classification_data(d,2016L))$row_diagnostics,flags,row.names=FALSE)
 run_classification_cpo(fitpath,input,flags,tempfile(),2016L,'shared',cores=2L)
}
cat('CPO comparison and preservation PASS\n')
