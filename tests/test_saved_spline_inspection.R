source('scripts/inspect_saved_spline.R')
d<-tempfile();dir.create(d);p<-file.path(d,'fit.rds')
f<-structure(list(summary.random=list(area=data.frame(mean=1:2,sd=c(.1,.2))),model.random='BYM2 model',
 summary.hyperpar=data.frame(mean=1,sd=.1,row.names='precision'),summary.fixed=data.frame(mean=1,sd=.2,row.names='stateAA'),
 summary.linear.predictor=data.frame(mean=c(1,Inf),sd=c(.1,.2)),mode=list(mode.status=0,theta=c(1,2)),
 misc=list(configs=list(config=list(list(theta=c(1,2))))),cpo=list(failure=c(0,NA))),class='inla')
attr(f,'forecast_specification')<-list(version='training_only_thin_plate_v1',training_end=2011L)
saveRDS(f,p);before<-tools::md5sum(p)
inspect_saved_spline(p,file.path(d,'reports'),'spatial')
stopifnot(identical(before,tools::md5sum(p)),readLines(file.path(d,'reports/status.txt'))[1]=='SAVED_SPLINE_INSPECTION_COMPLETE')
x<-read.csv(file.path(d,'reports/parameter_ranges.csv'));stopifnot(any(x$nonfinite==1))
stopifnot(inherits(try(inspect_saved_spline(p,file.path(d,'wrong'),'iid'),silent=TRUE),'try-error'))
stopifnot(!dir.exists(file.path(d,'wrong')))
cat('PASS immutable saved-object inspection, wrong-model rejection and nonfinite diagnostics\n')
