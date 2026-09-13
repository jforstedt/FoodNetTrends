#!/usr/bin/env Rscript
# Read and summarize an existing INLA object. No fitting or posterior sampling.
inspect_saved_spline <- function(path,out,variant,origin=2011L) {
  if(dir.exists(out))stop('Use a new output directory')
  suppressPackageStartupMessages(library(Matrix))
  before<-tools::md5sum(path);fit<-readRDS(path)
  if(!inherits(fit,'inla'))stop('Expected saved INLA object')
  spec<-attr(fit,'forecast_specification')
  if(is.null(spec)||spec$version!='training_only_thin_plate_v1'||spec$training_end!=origin)stop('Saved spline origin/specification mismatch')
  random_names<-names(fit$summary.random);area<-match('area',random_names)
  if(is.na(area)||length(fit$model.random)!=length(random_names))stop('Missing random-effect identity')
  expected<-if(variant=='spatial')'bym2' else if(variant=='iid')'iid' else stop('Unknown variant')
  if(!grepl(expected,tolower(fit$model.random[area]),fixed=TRUE))stop('Saved county structure differs')
  dir.create(out,recursive=TRUE)
  numeric_summary<-function(x,label){x<-as.numeric(x);ok<-is.finite(x);q<-if(any(ok))quantile(x[ok],c(0,.01,.5,.99,1))else rep(NA_real_,5)
    data.frame(field=label,n=length(x),nonfinite=sum(!ok),minimum=q[1],q01=q[2],median=q[3],q99=q[4],maximum=q[5],row.names=NULL)}
  for(name in c('summary.hyperpar','summary.fixed')) {
    x<-fit[[name]]
    if(!is.null(x))write.csv(data.frame(parameter=rownames(x),x,check.names=FALSE),file.path(out,paste0(name,'.csv')),row.names=FALSE)
  }
  summaries<-list()
  for(name in c('summary.linear.predictor','summary.fitted.values')) {
    x<-fit[[name]]
    for(col in intersect(c('mean','sd','0.025quant','0.5quant','0.975quant'),names(x)))summaries[[paste(name,col)]]<-numeric_summary(x[[col]],paste(name,col))
  }
  for(name in random_names)for(col in intersect(c('mean','sd'),names(fit$summary.random[[name]])))
    summaries[[paste(name,col)]]<-numeric_summary(fit$summary.random[[name]][[col]],paste(name,col))
  if(length(summaries))write.csv(do.call(rbind,summaries),file.path(out,'parameter_ranges.csv'),row.names=FALSE)
  write.csv(data.frame(component=random_names,model=fit$model.random),file.path(out,'random_structure.csv'),row.names=FALSE)
  write.csv(as.data.frame(spec),file.path(out,'specification.csv'),row.names=FALSE)
  if(!is.null(fit$cpo$failure))write.csv(numeric_summary(fit$cpo$failure,'CPO failure flags'),file.path(out,'cpo_failure_summary.csv'),row.names=FALSE)
  fields<-c('ok','mode','cpu.used','waic','dic','mlik','internal.summary.hyperpar','logfile')
  capture.output(for(n in fields){cat('\nFIELD:',n,'\n');str(fit[[n]],max.level=2,vec.len=10,list.len=12)},file=file.path(out,'optimizer_and_fit_structure.txt'))
  configs<-fit$misc$configs
  capture.output({cat('misc names:',names(fit$misc),'\n');cat('config names:',names(configs),'\n');
    cat('configuration count:',length(configs$config),'\n');
    if(length(configs$config))cat('first configuration fields:',names(configs$config[[1]]),'\n')},file=file.path(out,'configuration_structure.txt'))
  if(length(configs$config)) {
    theta<-lapply(seq_along(configs$config),function(i){x<-configs$config[[i]]$theta;if(!length(x))return(NULL)
      data.frame(configuration=i,parameter=seq_along(x),theta=as.numeric(x))})
    theta<-Filter(Negate(is.null),theta)
    if(length(theta))write.csv(do.call(rbind,theta),file.path(out,'configuration_theta.csv'),row.names=FALSE)
  }
  if(!identical(before,tools::md5sum(path)))stop('Saved fit changed during inspection')
  write.csv(data.frame(file=path,md5=unname(before),unchanged=TRUE),file.path(out,'input_check.csv'),row.names=FALSE)
  writeLines(c('SAVED_SPLINE_INSPECTION_COMPLETE','Read-only metadata and existing summaries; no fitting or sampling.',
    'Native predictor/fitted-value scales are retained; exponentiated means are not posterior mean counts.',
    'CPO includes prediction-only rows; nonfinite values are not automatically training failures.',
    'Current checkpoint identity does not establish original completion bytes for legacy fits.'),file.path(out,'status.txt'))
  capture.output(sessionInfo(),file=file.path(out,'sessionInfo.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=4L)stop('Usage: FIT OUT VARIANT ORIGIN');inspect_saved_spline(a[1],a[2],a[3],as.integer(a[4]))}
