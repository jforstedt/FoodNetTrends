#!/usr/bin/env Rscript
.source<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.source))dirname(.source) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'county_forecast_model.R'));source(file.path(.here,'monthly_seasonal_model.R'));source(file.path(.here,'fit_county_pilot.R'))

load_monthly_comparison <- function(candidate,audit,cutoff,end_year=2019L) {
 if(!end_year%in%c(2017L,2019L)||cutoff+3L>end_year)stop('Invalid monthly evaluation window')
 d<-readRDS(candidate);annual<-validate_panel(audit,expected_production=FALSE)$data
 needed<-c('fips','state','year','month','record_count','modeled_count','observation_status','population','candidate_person_years','exposure_status')
 if(!all(needed%in%names(d))||nrow(d)!=486L*12L*(end_year-2004L+1L)||!setequal(unique(d$year),2004:end_year)||anyNA(d[setdiff(needed,'modeled_count')]))stop('Invalid candidate domain')
 if(any(!is.na(d$modeled_count))||any(d$observation_status!='UNVERIFIED')||any(d$exposure_status!='UNVALIDATED_ANNUAL_POPULATION_DAY_FRACTION'))stop('Unexpected prior candidate certification')
 key<-function(x)paste(x$fips,x$year)
 if(any(!is.finite(d$month)|d$month!=floor(d$month)|d$month<1|d$month>12)||anyDuplicated(paste(key(d),d$month))||any(!key(d)%in%key(annual)))stop('Invalid monthly keys')
 j<-match(key(d),key(annual))
 if(any(d$state!=annual$state[j])||any(d$population!=annual$population[j])||any(!is.finite(d$record_count)|d$record_count<0|d$record_count!=floor(d$record_count)))stop('Candidate differs from annual audit')
 totals<-tapply(d$record_count,key(d),sum)
 if(any(as.numeric(totals[key(annual)])!=annual$count))stop('Annual counts differ')
 first<-as.Date(sprintf('%04d-%02d-01',d$year,d$month));nextm<-as.Date(sprintf('%04d-%02d-01',d$year+as.integer(d$month==12),d$month%%12+1))
 days<-as.numeric(nextm-first);year_days<-as.numeric(as.Date(paste0(d$year+1,'-01-01'))-as.Date(paste0(d$year,'-01-01')))
 expected<-d$population*days/year_days
 if(any(!is.finite(d$candidate_person_years))||any(abs(d$candidate_person_years-expected)>pmax(1e-8,expected*1e-10)))stop('Invalid monthly exposure')
 d<-d[d$year<=cutoff+3,,drop=FALSE];d<-d[order(d$fips,d$year,d$month),]
 d$area<-d$fips;d$count<-d$record_count;d$person_years<-d$candidate_person_years
 d$observation_status<-'EXPLORATORY_ASSUMED_CONTINUOUS'
 d
}

interval_report <- function(draws,truth,keys) {
 q<-t(apply(draws,1,quantile,probs=c(.025,.25,.5,.75,.975)))
 cbind(keys,observed=truth,mean=rowMeans(draws),median=q[,3],lower95=q[,1],upper95=q[,5],lower50=q[,2],upper50=q[,4])
}
run_monthly_comparison <- function(candidate,audit,cutoff,seasonal,out,seed) {
 if(dir.exists(out))stop('Refusing existing result directory');dir.create(out,recursive=TRUE)
 writeLines('RUNNING',file.path(out,'status.txt'))
 tryCatch({
  d<-load_monthly_comparison(candidate,audit,cutoff);truth<-d$count;test<-d$year>cutoff
  warning_messages<-character()
  fit<-withCallingHandlers(fit_monthly_model(d,cutoff*12+11L,seasonal,threads=4L,
    coverage='EXPLORATORY_ASSUMED_CONTINUOUS',rate_center=.0002),warning=function(w){warning_messages<<-c(warning_messages,conditionMessage(w))})
  writeLines(warning_messages,file.path(out,'warnings.txt'))
  if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(!is.finite(fit$summary.linear.predictor$mean))||any(!is.finite(fit$summary.linear.predictor$sd))||any(fit$summary.linear.predictor$sd<=0)||any(grepl('vb.correction.*aborted',warning_messages,ignore.case=TRUE)))stop('Numerical fit gate failed')
  saveRDS(fit,file.path(out,'fit_INTERNAL.rds'),version=2)
  write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
  if(seasonal)write.csv(fit$summary.random$season,file.path(out,'seasonal_effect.csv'),row.names=FALSE)
  a<-sample_county_forecast(fit,which(test),draws=500L,seed=seed,batch_size=100L)
  b<-sample_county_forecast(fit,which(test),draws=500L,seed=seed+20000L,batch_size=100L)
  mu<-cbind(a$mu,b$mu);replicated<-cbind(a$replicated,b$replicated);sizes<-c(a$size,b$size)
  saveRDS(list(indices=which(test),replicated=replicated,mu=mu,size=sizes,seed=c(seed,seed+20000L)),file.path(out,'draws_INTERNAL.rds'),version=2)
  keys<-d[test,c('fips','state','year','month')];keys$horizon_year<-keys$year-cutoff
  report<-interval_report(replicated,truth[test],keys)
  logs<-sapply(seq_len(ncol(mu)),function(i)dnbinom(truth[test],mu=mu[,i],size=sizes[i],log=TRUE))
  logmean<-function(x){mx<-apply(x,1,max);mx+log(rowMeans(exp(x-mx)))}
  report$log_score<-logmean(logs);report$log_score_stream_difference<-logmean(logs[,1:500])-logmean(logs[,501:1000])
  if(any(!is.finite(report$log_score)))stop('Nonfinite log score')
  report$interval_score95<-report$upper95-report$lower95+40*pmax(report$lower95-report$observed,0)+40*pmax(report$observed-report$upper95,0)
  report$coverage95<-report$observed>=report$lower95&report$observed<=report$upper95
  report$coverage50<-report$observed>=report$lower50&report$observed<=report$upper50
  report$absolute_error<-abs(report$mean-report$observed)
  write.csv(report,file.path(out,'county_month_predictions.csv'),row.names=FALSE)
  metrics<-aggregate(report[c('log_score','log_score_stream_difference','interval_score95','coverage95','coverage50','absolute_error')],report[c('state','horizon_year')],mean)
  write.csv(metrics,file.path(out,'site_horizon_metrics.csv'),row.names=FALSE)
  aggregate_draws<-function(cols,name) {
   group<-do.call(paste,c(keys[cols],sep='|'));levels<-unique(group);first<-match(levels,group)
   draws<-rowsum(replicated,group,reorder=FALSE);actual<-as.numeric(rowsum(truth[test],group,reorder=FALSE))
   write.csv(interval_report(draws,actual,keys[first,cols,drop=FALSE]),file.path(out,name),row.names=FALSE)
  }
  aggregate_draws(c('state','year','month'),'site_month_predictions.csv')
  aggregate_draws(c('state','year'),'site_year_predictions.csv')
  aggregate_draws(c('year','month'),'catchment_month_predictions.csv')
  aggregate_draws('year','catchment_year_predictions.csv')
  write.csv(data.frame(status='EXPLORATORY_FIT_COMPLETE',coverage='EXPLORATORY_ASSUMED_CONTINUOUS',coverage_certified=FALSE,
    cutoff=cutoff,seasonal=seasonal,training_count=sum(truth[!test]),heldout_count=sum(truth[test]),heldout_cells=sum(test),draws=1000L,rate_center=.0002),file.path(out,'readiness.csv'),row.names=FALSE)
  writeLines('EXPLORATORY_FIT_COMPLETE',file.path(out,'status.txt'))
 },error=function(e){writeLines(c('FAILED',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=6L)stop('Usage: CANDIDATE AUDIT CUTOFF SEASONAL OUTPUT SEED');run_monthly_comparison(a[1],a[2],as.integer(a[3]),a[4]=='TRUE',a[5],as.integer(a[6]))}
