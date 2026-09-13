#!/usr/bin/env Rscript
# Synthetic stress checks only; no FoodNet inputs or submissions.
source('scripts/county_forecast_model.R')
source('scripts/monthly_seasonal_prototype.R')
a<-commandArgs(TRUE)
if(length(a)!=2)stop('Usage: TASK_1_TO_8 OUTPUT_DIR')
id<-as.integer(a[1]);if(is.na(id)||!id%in%1:8)stop('Invalid task')
out<-a[2];if(dir.exists(out))stop('Refusing existing task output');dir.create(out,recursive=TRUE)
writeLines('RUNNING',file.path(out,'status.txt'))
tryCatch({
 scenario<-c('flat','seasonal','sparse_seasonal','trend_and_season')[1+(id-1)%/%2]
 seed<-8100L+id;set.seed(seed)
 d<-expand.grid(area=1:4,serial=0:83);d$year<-2004L+d$serial%/%12L;d$month<-d$serial%%12L+1L
 d$state<-ifelse(d$area<=2,'AA','BB');d$person_years<-if(scenario=='sparse_seasonal')500 else 10000
 d$observation_status<-'SYNTHETIC_COMPLETE';attr(d,'synthetic')<-TRUE
 effect<-if(scenario=='flat')rep(0,nrow(d)) else .65*cos(2*pi*(d$month-7)/12)
 drift<-if(scenario=='trend_and_season').005*d$serial else 0
 truth<-d$person_years*.002*exp(effect+drift)
 d$count<-rnbinom(nrow(d),mu=truth,size=20)
 cutoff<-2009L*12L+11L;test<-d$year>2009;results<-list()
 for(seasonal in c(FALSE,TRUE)) {
  label<-if(seasonal)'seasonal' else 'reference'
  fit<-fit_monthly_prototype(d,cutoff,seasonal,threads=2L)
  if(!isTRUE(fit$ok)||!all(is.finite(fit$summary.linear.predictor$mean)))stop('Invalid fit')
  draws<-sample_county_forecast(fit,which(test),draws=400L,seed=20000L+id*1000L+as.integer(seasonal)*500L,batch_size=100L)
  point<-rowMeans(draws$mu);lo<-apply(draws$replicated,1,quantile,.025);hi<-apply(draws$replicated,1,quantile,.975)
  # Monte Carlo mixture NB log score, stabilized before exponentiation.
  logs<-sapply(seq_len(ncol(draws$mu)),function(j)dnbinom(d$count[test],mu=draws$mu[,j],size=draws$size[j],log=TRUE))
  mx<-apply(logs,1,max);score<-mx+log(rowMeans(exp(logs-mx)))
  if(any(!is.finite(score)))stop('Nonfinite predictive score')
  results[[label]]<-data.frame(task=id,scenario=scenario,seed=seed,model=label,
    count_rmse=sqrt(mean((point-d$count[test])^2)),true_mean_rmse=sqrt(mean((point-truth[test])^2)),
    predictive_coverage=mean(d$count[test]>=lo&d$count[test]<=hi),mean_interval_width=mean(hi-lo),mean_log_score=mean(score),draws=400)
  write.csv(data.frame(year=d$year[test],month=d$month[test],area=d$area[test],observed=d$count[test],true_mean=truth[test],predicted=point,lower=lo,upper=hi),file.path(out,paste0(label,'_synthetic_predictions.csv')),row.names=FALSE)
 }
 write.csv(do.call(rbind,results),file.path(out,'metrics.csv'),row.names=FALSE)
 writeLines('SYNTHETIC_CHECK_COMPLETE',file.path(out,'status.txt'))
},error=function(e){writeLines(c('FAILED',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
