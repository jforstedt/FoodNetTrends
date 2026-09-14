source('scripts/shigella_numerical_restart.R')
work<-tempfile();dir.create(work)
f<-list(ok=TRUE,mode=list(mode.status=2),.args=list(formula=y~x,data=data.frame(x=1,y=2),family='nbinomial',control.fixed=list(prec=1),control.family=list(),control.predictor=list(),control.compute=list()))
attr(f,'monthly_specification')<-list(version='test')
r<-shigella_restart(f,work,rerun=function(x){attributes(x)$monthly_specification<-NULL;x$mode$mode.status<-0;x})
stopifnot(identical(attr(f,'monthly_specification'),attr(r,'monthly_specification')),file.exists(file.path(work,'initial_optimizer_fit_INTERNAL.rds')),file.exists(file.path(work,'restarted_optimizer_fit_INTERNAL.rds')))
bad<-tempfile();dir.create(bad)
stopifnot(inherits(try(shigella_restart(f,bad,rerun=function(x){x$.args$family<-'poisson';x}),silent=TRUE),'try-error'))
for(field in c('num.threads','E','Ntrials','offset','weights','scale')) {
 w<-tempfile();dir.create(w)
 stopifnot(inherits(try(shigella_restart(f,w,rerun=function(x){x$.args[[field]]<-999;x}),silent=TRUE),'try-error'))
}
cat('Shigella checkpoint, metadata and model-invariance tests PASS\n')
