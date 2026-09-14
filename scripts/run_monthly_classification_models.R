#!/usr/bin/env Rscript
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'monthly_classification_model.R'))
source(file.path(.here,'monthly_spatial_combination.R'))
source(file.path(.here,'audit_monthly_classification.R'))

run_monthly_classification_models <- function(input,level,temporal,seasonal,spatial,cutoff,out,seed,nodespath,edgespath,draws=2000L) {
 if(dir.exists(out))stop('Refusing existing result')
 if(packageVersion('INLA')!=package_version('26.08.07'))stop('Pinned INLA required')
 inputs<-c(input,nodespath,edgespath);before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing bound inputs')
 raw<-if(grepl('[.]rds$',input,ignore.case=TRUE))readRDS(input) else read.csv(input,stringsAsFactors=FALSE)
 obj<-prepare_monthly_classification(raw,cutoff,level);d<-obj$data
 key<-function(x)paste(if('fips'%in%names(x))x$fips else x$state,x$state,x$year,x$month,sep='|')
 j<-match(key(d),key(raw));if(anyNA(j)||anyDuplicated(key(raw)))stop('Source rows differ')
 held<-d$year>cutoff;truth<-d[held,intersect(c('fips','state','year','month'),names(d)),drop=FALSE]
 truth$observed<-raw$cidt_classified[j[held]];truth$denominator<-raw$classification_denominator[j[held]]
 if(any(!is.finite(truth$observed)|truth$observed<0|truth$observed!=floor(truth$observed)|truth$observed>truth$denominator))stop('Invalid heldout truth')
 nodes<-read.csv(nodespath,colClasses='character');edges<-read.csv(edgespath,colClasses='character')
 dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'));warnings<-character()
 on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
 fit<-withCallingHandlers(fit_monthly_classification(raw,cutoff,level,temporal,seasonal,spatial,nodes,edges,threads=4L),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 saveRDS(fit,file.path(out,'fit_INTERNAL.rds'),version=2);write.csv(truth,file.path(out,'truth_INTERNAL.csv'),row.names=FALSE)
 writeLines(warnings,file.path(out,'fit_warnings.txt'))
 write.csv(data.frame(fit_ok=isTRUE(fit$ok),mode_status=paste(fit$mode$mode.status,collapse=';')),file.path(out,'fit_diagnostics.csv'),row.names=FALSE)
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl("vb[.]correction['\"]?.*aborted",warnings,ignore.case=TRUE)))stop('Classification numerical fit gate failed')
 result<-classification_posterior_reports(fit,truth,cutoff,seed,draws)
 for(n in c('stream_scores','aggregate_predictions'))write.csv(result[[n]],file.path(out,paste0(n,'.csv')),row.names=FALSE,na='')
 saveRDS(result$aggregate_draws,file.path(out,'aggregate_draws_INTERNAL.rds'),version=2)
 write.csv(result$cell_expected,file.path(out,'cell_expected_INTERNAL.csv'),row.names=FALSE)
 write.csv(result$rng,file.path(out,'rng_protocol.csv'),row.names=FALSE)
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 write.csv(data.frame(level=level,temporal=temporal,seasonal=seasonal,spatial=spatial,cutoff=cutoff,train_start=2012,horizon=36,
  streams=4,draws_per_stream=draws,base_seed=seed,coverage_certified=FALSE,incidence_adjustment=FALSE,independent_validation=FALSE,
  target='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT',rng_protocol='explicit_config_v2',fitting_threads='4:1'),file.path(out,'settings.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(inputs)))stop('Inputs changed during classification model')
 write.csv(data.frame(file=inputs,md5=unname(before)),file.path(out,'input_checksums.csv'),row.names=FALSE)
 writeLines('MONTHLY_CLASSIFICATION_MODEL_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=10L||!a[4]%in%c('TRUE','FALSE'))stop('Usage INPUT LEVEL TEMPORAL SEASONAL SPATIAL CUTOFF OUT SEED NODES EDGES');run_monthly_classification_models(a[1],a[2],a[3],a[4]=='TRUE',a[5],as.integer(a[6]),a[7],as.integer(a[8]),a[9],a[10])}
