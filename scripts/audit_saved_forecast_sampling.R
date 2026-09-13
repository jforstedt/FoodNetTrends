#!/usr/bin/env Rscript
# Saved posterior sampling only: never calls INLA::inla().
validate_saved_forecast <- function(fit,d,cutoff,horizon,expected_model=NULL) {
  if(!is.null(expected_model)) {
    if(!expected_model%in%c("spatial_county_time","iid_county_time"))stop("Unsupported expected saved model")
    fields<-names(fit$summary.random); types<-fit$model.random
    expected<-if(expected_model=="spatial_county_time") "BYM2 model" else "IID model"
    if(length(types)!=length(fields)||anyDuplicated(fields)||!all(c("area","time","county_time")%in%fields)||
       types[match("area",fields)]!=expected||any(types[match(c("time","county_time"),fields)]!="RW1 model"))
      stop("Saved spatial/IID or temporal model identity differs from requested model")
  }
  expected<-county_forecast_specification(d$year,cutoff)
  spec<-attr(fit,'forecast_specification')
  if(!identical(spec,expected)||max(d$year)!=cutoff+horizon)stop('Saved forecast specification differs from requested domain')
  x<-fit$.args$data
  fields<-c('fips','state','year','population','area','state_id')
  if(!is.data.frame(x)||nrow(x)!=nrow(d)||!all(c(fields,'count')%in%names(x)))stop('Saved predictor data unavailable')
  for(k in fields)if(!identical(as.character(x[[k]]),as.character(d[[k]])))stop(paste('Saved predictor mismatch:',k))
  held<-d$year>cutoff
  if(!all(is.na(x$count[held]))||!identical(as.numeric(x$count[!held]),as.numeric(d$count[!held])))stop('Training counts or held-out masking differ')
  if(!identical(as.character(fit$.args$family),'nbinomial')||is.null(fit$misc$configs)||nrow(fit$summary.linear.predictor)!=nrow(d))stop('Saved posterior configuration or likelihood mismatch')
  invisible(TRUE)
}

# Scaled density moments avoid underflow even for very unlikely observations.
density_moments <- function(logdens,previous=NULL) {
  if(!is.matrix(logdens)||any(!is.finite(logdens)))stop('Nonfinite predictive log density')
  m<-apply(logdens,1,max)
  if(is.null(previous))previous<-list(max=rep(-Inf,nrow(logdens)),sum=numeric(nrow(logdens)),sum2=numeric(nrow(logdens)),n=0L)
  peak<-pmax(m,previous$max);scale<-exp(previous$max-peak)
  z<-exp(logdens-peak)
  list(max=peak,sum=previous$sum*scale+rowSums(z),sum2=previous$sum2*scale^2+rowSums(z^2),n=previous$n+ncol(logdens))
}
summarize_density <- function(z) {
  if(z$n<2L)stop('At least two draws required')
  avg<-z$sum/z$n
  variance<-pmax(0,(z$sum2-z$sum^2/z$n)/(z$n-1))
  list(log_density=z$max+log(avg),relative_mcse=sqrt(variance/z$n)/avg)
}

sample_saved_density <- function(fit,d,cutoff,draws,seed,batch_size=100L) {
  ix<-which(d$year>cutoff);truth<-d$count[ix];group<-paste(d$state[ix],d$year[ix],sep='|')
  moments<-NULL;batches<-list()
  for(start in seq.int(1L,draws,by=batch_size)) {
    n<-min(batch_size,draws-start+1L)
    samples<-INLA::inla.posterior.sample(n,fit,selection=list(Predictor=ix),seed=as.integer(seed+start),num.threads='1:1',skew.corr=FALSE)
    ld<-matrix(NA_real_,length(ix),n)
    for(j in seq_len(n)) {
      s<-samples[[j]];ids<-as.integer(sub('^Predictor:','',rownames(s$latent)))
      if(anyNA(ids)||anyDuplicated(ids)||!setequal(ids,ix))stop('Posterior predictor indexing mismatch')
      mu<-exp(as.numeric(s$latent[match(ix,ids),1]));si<-grep('size for',names(s$hyperpar),fixed=TRUE)
      if(length(si)!=1L)stop('Missing NB size')
      size<-as.numeric(s$hyperpar[si])
      if(any(!is.finite(mu))||any(mu<=0)||!is.finite(size)||size<=0)stop('Invalid posterior parameters')
      ld[,j]<-dnbinom(truth,mu=mu,size=size,log=TRUE)
    }
    moments<-density_moments(ld,moments)
    bl<-summarize_density(density_moments(ld))$log_density
    b<-aggregate(bl,list(state=as.character(d$state[ix]),year=d$year[ix]),sum);names(b)[3]<-'sum_log_predictive_density'
    b$seed<-seed;b$batch<-start;b$draws<-n;batches[[length(batches)+1L]]<-b
  }
  z<-summarize_density(moments)
  cells<-data.frame(fips=d$fips[ix],state=as.character(d$state[ix]),year=d$year[ix],seed=seed,
    log_predictive_density=z$log_density,density_relative_mcse=z$relative_mcse)
  scores<-do.call(rbind,lapply(unique(group),function(g){j<-which(group==g);data.frame(seed=seed,state=as.character(d$state[ix[j[1]]]),year=d$year[ix[j[1]]],cells=length(j),sum_log_predictive_density=sum(z$log_density[j]),max_density_relative_mcse=max(z$relative_mcse[j]))}))
  list(cells=cells,scores=scores,batches=do.call(rbind,batches))
}

run_saved_forecast_sampling <- function(audit,fitpath,cutoff,horizon,out,draws=4000L,seeds=c(91001L,191003L,291007L,391009L),threads=2L,expected_model=NULL) {
  if(dir.exists(out))stop('Refusing existing output directory')
  if(!file.exists(fitpath))stop('Saved checkpoint missing; no refit will be attempted')
  if(length(draws)!=1L||!is.finite(draws)||draws<4000L||draws!=as.integer(draws)||length(seeds)!=4L||anyNA(seeds)||anyDuplicated(seeds)||any(seeds<1|seeds>1e9|seeds!=floor(seeds))||min(diff(sort(seeds)))<=draws)stop('Require four disjoint seed streams and at least 4000 draws each')
  dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  inputs<-c(fit=fitpath,panel=file.path(audit,'county_panel_INTERNAL.rds'));before<-tools::md5sum(inputs)
  on.exit(writeLines(capture.output(sessionInfo()),file.path(out,'sessionInfo.txt')))
  tryCatch({
    if(packageVersion('INLA')!=package_version('26.08.07'))stop('Expected pinned INLA')
    INLA::inla.setOption(num.threads=paste0(threads,':1'))
    obj<-validate_panel(audit,expected_production=FALSE);obj<-restrict_forecast_horizon(obj,cutoff,horizon)
    fit<-readRDS(fitpath);validate_saved_forecast(fit,obj$data,cutoff,horizon,expected_model)
    started<-proc.time()[3]
    results<-lapply(seeds,function(seed)sample_saved_density(fit,obj$data,cutoff,draws,seed))
    cells<-do.call(rbind,lapply(results,`[[`,'cells'))
    write.csv(cells,file.path(out,'seed_cells_INTERNAL.csv'),row.names=FALSE)
    write.csv(do.call(rbind,lapply(results,`[[`,'scores')),file.path(out,'seed_state_year_scores.csv'),row.names=FALSE)
    write.csv(do.call(rbind,lapply(results,`[[`,'batches')),file.path(out,'batch_state_year_scores.csv'),row.names=FALSE)
    keys<-paste(cells$fips,cells$year,sep='|')
    stable<-do.call(rbind,lapply(split(cells,keys),function(x)data.frame(fips=x$fips[1],state=x$state[1],year=x$year[1],mean_log_density=mean(x$log_predictive_density),sd_log_density=sd(x$log_predictive_density),range_log_density=diff(range(x$log_predictive_density)),max_density_relative_mcse=max(x$density_relative_mcse))))
    write.csv(stable,file.path(out,'cell_stability_INTERNAL.csv'),row.names=FALSE)
    if(!identical(before,tools::md5sum(inputs)))stop('Saved fit or panel changed during audit')
    write.csv(data.frame(kind=names(inputs),file=unname(inputs),md5=unname(before)),file.path(out,'inputs.csv'),row.names=FALSE)
    write.csv(data.frame(draws_per_seed=draws,seeds=paste(seeds,collapse=';'),origin=cutoff,horizon=horizon,elapsed_seconds=proc.time()[3]-started,skew_correction=FALSE,refitted=FALSE,model=if(is.null(expected_model)) 'UNSPECIFIED' else expected_model),file.path(out,'settings.csv'),row.names=FALSE)
    writeLines(c('SAVED_FORECAST_SAMPLING_COMPLETE','Scores sum marginal county log densities; they are not joint predictive densities.','Across-seed variability measures numerical sampling variation, not forecast accuracy or model uncertainty.','Batch scores use fewer draws and have log-transform bias; use full-seed scores for comparisons.'),file.path(out,'status.txt'))
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=6L)stop('Usage: AUDIT FIT ORIGIN HORIZON OUT EXPECTED_MODEL');here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'fit_county_pilot.R'));source(file.path(here,'county_forecast_check.R'));run_saved_forecast_sampling(a[1],a[2],as.integer(a[3]),as.integer(a[4]),a[5],expected_model=a[6])}
