# Joint posterior binomial prediction for the frozen diagnostic-mix target.
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'audit_saved_forecast_sampling.R'))

classification_log_density <- function(y,n,eta) {
 if(any(!is.finite(eta))||length(y)!=length(eta)||length(n)!=length(eta)||any(y<0|n<y|n<0|y!=floor(y)|n!=floor(n)))stop('Invalid binomial density inputs')
 # Stable even when plogis rounds to zero/one; no arbitrary probability clipping.
 z<-log1p(exp(-abs(eta)))
 lchoose(n,y)+y*(-pmax(-eta,0)-z)+(n-y)*(-pmax(eta,0)-z)
}

classification_aggregate_summary <- function(expected,predictive,keys,observed,denominator,eligible,stream) {
 if(!is.matrix(expected)||!identical(dim(expected),dim(predictive))||nrow(expected)!=nrow(keys)||
    any(!is.finite(expected)|expected<0|expected>denominator+1e-8)||any(!is.finite(predictive)|predictive<0|predictive>denominator|predictive!=floor(predictive)))stop('Invalid aggregate binomial predictions')
 q<-t(apply(predictive,1,quantile,c(.025,.5,.975)))
 cbind(keys,stream=stream,draws=ncol(expected),eligible_cells=eligible,observed=observed,denominator=denominator,
       mean_expected=rowMeans(expected),median_expected=apply(expected,1,median),lower95=q[,1],median_predictive=q[,2],upper95=q[,3])
}

validate_classification_saved <- function(fit,truth,cutoff) {
 d<-attr(fit,'monthly_classification_data');s<-attr(fit,'monthly_classification_specification')
 if(!is.data.frame(d)||is.null(s)||s$cutoff!=cutoff||!all(c('state','year','month','y','Ntrials','row_id')%in%names(d)))stop('Missing saved classification contract')
 if(s$version!='monthly_conditional_classification_v1'||s$target!='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT'||s$link!='logit'||s$train_start!=2012||s$horizon!=36||!isTRUE(s$conditional_future_denominators)||!identical(s$incidence_adjustment,FALSE))stop('Saved classification target differs')
 if(!s$level%in%c('site','county')||!s$temporal%in%c('rw1','ar1')||!is.logical(s$seasonal)||length(s$seasonal)!=1||is.na(s$seasonal)||(s$level=='site'&&s$spatial!='none')||(s$level=='county'&&!s$spatial%in%c('iid','bym2')))stop('Saved classification model identity differs')
 if(!identical(as.integer(d$row_id),seq_len(nrow(d)))||any(!is.finite(d$Ntrials)|d$Ntrials<0|d$Ntrials!=floor(d$Ntrials)))stop('Invalid saved row/denominator identity')
 held<-d$year>cutoff;eligible<-d$Ntrials>0
 if(!all(is.na(d$y[held|!eligible]))||any(!is.finite(d$y[!held&eligible])|d$y[!held&eligible]<0|d$y[!held&eligible]>d$Ntrials[!held&eligible]))stop('Saved outcome masking differs')
 for(n in intersect(c('cidt_classified','cx_classified','cidt_classification_share'),names(d)))if(any(!is.na(d[[n]][held])))stop('Future outcome retained in model data')
 key<-function(x)paste(if('fips'%in%names(x))x$fips else x$state,x$state,x$year,x$month,sep='|')
 if(!identical(key(d[held,]),key(truth))||anyDuplicated(key(truth))||nrow(truth)!=sum(held))stop('Heldout classification identity differs')
 if(any(!is.finite(truth$observed)|truth$observed<0|truth$observed!=floor(truth$observed)|truth$observed>truth$denominator)||!identical(as.numeric(truth$denominator),as.numeric(d$Ntrials[held])))stop('Invalid heldout classification truth/denominator')
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||is.null(fit$misc$configs)||!identical(as.character(fit$.args$family),'binomial'))stop('Invalid saved binomial fit')
 if(!identical(as.numeric(fit$.args$Ntrials),as.numeric(d$Ntrials))||!identical(as.numeric(fit$.args$data$y),as.numeric(d$y)))stop('Saved likelihood args differ')
 if(nrow(fit$summary.linear.predictor)!=nrow(d))stop('Predictor domain differs')
 list(data=d,held=held,spec=s)
}

classification_posterior_reports <- function(fit,truth,cutoff,seed,draws=2000L,batch_size=100L,sampler=INLA::inla.posterior.sample) {
 if(length(seed)!=1||!is.finite(seed)||seed<1||seed>1e9||seed!=floor(seed)||length(draws)!=1||draws<20||draws>4000||draws!=floor(draws)||batch_size<1||batch_size!=floor(batch_size))stop('Invalid posterior sampling request')
 obj<-validate_classification_saved(fit,truth,cutoff);d<-obj$data[obj$held,,drop=FALSE]
 group<-paste(d$state,d$year,sep='|');groups<-sort(unique(group));first<-match(groups,group)
 keys<-data.frame(state=as.character(d$state[first]),year=d$year[first]);years<-sort(unique(d$year))
 if(!identical(as.integer(years),seq.int(cutoff+1L,cutoff+3L))||nrow(keys)!=length(unique(d$state))*3L)stop('Incomplete heldout state/year grid')
 aggregate_keys<-rbind(keys,data.frame(state='ALL',year=years));eligible<-truth$denominator>0;ix<-which(obj$held)[eligible]
 # Aggregate by explicit keys, preserving zero-denominator groups.
 agg<-function(x) {
  if(is.null(dim(x)))x<-matrix(x,ncol=1L)
  a<-rowsum(x,factor(group,levels=groups),reorder=TRUE);a<-a[match(groups,rownames(a)),,drop=FALSE]
  b<-rowsum(x,d$year,reorder=TRUE);rbind(a,b[match(as.character(years),rownames(b)),,drop=FALSE])
 }
 observed<-as.numeric(agg(truth$observed));denominator<-as.numeric(agg(truth$denominator));n_eligible<-as.numeric(agg(as.integer(eligible)))
 score_summary<-function(moments,stream,n) {
  z<-if(any(eligible))summarize_density(moments) else NULL
  result<-data.frame(keys,stream=stream,draws=n,eligible_cells=0L,mean_log_score=NA_real_,max_cell_density_relative_mcse=NA_real_)
  for(i in seq_along(groups)) {
   selected<-group[eligible]==groups[i];result$eligible_cells[i]<-sum(selected)
   if(any(selected)){result$mean_log_score[i]<-mean(z$log_density[selected]);result$max_cell_density_relative_mcse[i]<-max(z$relative_mcse[selected])}
  }
  result
 }
 scores<-predictions<-list();allmoments<-NULL;all_expected<-all_predictive<-NULL;expected_cell_sum<-numeric(sum(eligible))
 for(stream in 1:4) {
  stream_seed<-seed+(stream-1L)*50000L;moments<-NULL;total_expected<-total_predictive<-NULL
  for(start in seq.int(1L,draws,by=batch_size)) {
   n<-min(batch_size,draws-start+1L);mu<-sim<-matrix(0,nrow(d),n)
   if(any(eligible)) {
    set.seed(as.integer(stream_seed+20000L+start))
    samples<-sampler(n,fit,selection=list(Predictor=ix),seed=as.integer(stream_seed+start),num.threads='1:1',skew.corr=FALSE)
    if(length(samples)!=n)stop('Incomplete posterior batch')
    set.seed(as.integer(stream_seed+10000L+start));ld<-matrix(NA_real_,sum(eligible),n)
    for(j in seq_len(n)) {
     latent<-samples[[j]]$latent;names<-rownames(latent)
     if(any(!grepl('^Predictor:[0-9]+$',names)))stop('Unexpected posterior predictor names')
     ids<-as.integer(sub('^Predictor:','',names))
     if(anyNA(ids)||anyDuplicated(ids)||!setequal(ids,ix))stop('Posterior predictor rows differ')
     eta<-as.numeric(latent[match(ix,ids),1]);prob<-plogis(eta)
     if(any(!is.finite(eta)))stop('Nonfinite posterior logit')
     mu[eligible,j]<-truth$denominator[eligible]*prob
     sim[eligible,j]<-rbinom(sum(eligible),truth$denominator[eligible],prob)
     ld[,j]<-classification_log_density(truth$observed[eligible],truth$denominator[eligible],eta)
    }
    moments<-density_moments(ld,moments);allmoments<-density_moments(ld,allmoments)
    expected_cell_sum<-expected_cell_sum+rowSums(mu[eligible,,drop=FALSE])
   }
   total_expected<-cbind(total_expected,agg(mu));total_predictive<-cbind(total_predictive,agg(sim))
  }
  scores[[stream]]<-score_summary(moments,stream,draws)
  predictions[[stream]]<-classification_aggregate_summary(total_expected,total_predictive,aggregate_keys,observed,denominator,n_eligible,stream)
  all_expected<-cbind(all_expected,total_expected);all_predictive<-cbind(all_predictive,total_predictive)
 }
 scores[[5]]<-score_summary(allmoments,0L,4L*draws)
 predictions[[5]]<-classification_aggregate_summary(all_expected,all_predictive,aggregate_keys,observed,denominator,n_eligible,0L)
 list(stream_scores=do.call(rbind,scores),aggregate_predictions=do.call(rbind,predictions),
      aggregate_draws=list(keys=aggregate_keys,expected=all_expected,predictive=all_predictive),
      cell_expected=data.frame(row_id=ix,mean_expected=expected_cell_sum/(4L*draws)),
      rng=data.frame(protocol='explicit_config_v2',config_offset=20000L,predictive_offset=10000L,stream_spacing=50000L,
       RNG_kind=paste(RNGkind(),collapse=';'),R_version=as.character(getRversion()),INLA_version=as.character(packageVersion('INLA'))))
}
