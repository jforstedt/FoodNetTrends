#!/usr/bin/env Rscript
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'run_monthly_spatial_factorial.R'))
spatial_residual_moran <- function(residual,adj) {
 if(length(residual)!=nrow(adj)||ncol(adj)!=nrow(adj)||any(!is.finite(residual))||any(!is.finite(adj)|adj<0)||!isTRUE(all.equal(adj,t(adj))))stop('Invalid residual graph')
 z<-residual-mean(residual);w<-sum(adj)
 if(length(z)<2||w==0||sum(z^2)<=.Machine$double.eps*max(1,sum(residual^2)))return(NA_real_)
 length(z)/w*sum(adj*outer(z,z))/sum(z^2)
}
spatial_residual_reports <- function(d,expected,graph) {
 # Saved INLA data use factors. Iterating a factor strips its class and yields
 # integer codes, so normalize identifiers before building state summaries.
 d$state<-as.character(d$state);d$fips<-as.character(d$fips)
 if(anyNA(d$state)||anyNA(d$fips)||any(!nzchar(d$state))||any(!nzchar(d$fips)))stop('Missing residual geographic identity')
 if(length(expected)!=nrow(d)||any(!is.finite(expected)|expected<0)||any(!is.finite(d$observed)|d$observed<0))stop('Invalid count-scale residual inputs')
 if(!setequal(unique(d$fips),graph$ids)||anyDuplicated(paste(d$fips,d$year,d$month)))stop('Residual county/month identity differs')
 d$expected<-expected;d$count_residual<-d$observed-d$expected;d$log1p_residual<-log1p(d$observed)-log1p(d$expected)
 # Descriptive within-county centered lag correlations, not an independence test.
 centered<-d$log1p_residual-ave(d$log1p_residual,d$fips,FUN=mean)
 keys<-paste(d$fips,12*d$year+d$month);previous<-match(paste(d$fips,12*d$year+d$month-1),keys)
 rows<-list();i<-0L
 annual<-aggregate(d[c('observed','expected')],d[c('fips','state','year')],sum)
 for(state in c(sort(unique(d$state)),'ALL'))for(year in sort(unique(d$year))) {
  a<-annual[annual$year==year&(state=='ALL'|annual$state==state),];ix<-match(a$fips,graph$ids);adj<-graph$adj[ix,ix,drop=FALSE]
  sel<-which(d$year==year&(state=='ALL'|d$state==state));lagix<-sel[!is.na(previous[sel])]
  corr<-if(length(lagix)>2&&sd(centered[lagix])>0&&sd(centered[previous[lagix]])>0)cor(centered[lagix],centered[previous[lagix]]) else NA_real_
  i<-i+1L;rows[[i]]<-data.frame(state,year,counties=nrow(a),edges=sum(adj)/2,observed=sum(a$observed),expected=sum(a$expected),
   log1p_residual_moran=spatial_residual_moran(log1p(a$observed)-log1p(a$expected),adj),
   within_state_centered_moran=spatial_residual_moran((log1p(a$observed)-log1p(a$expected))-ave(log1p(a$observed)-log1p(a$expected),a$state,FUN=mean),adj),
   fraction_counties_underpredicted=mean(a$observed>a$expected),within_county_centered_month_lag1=corr,lag_pairs=length(lagix),
   significance_test=FALSE,posterior_uncertainty_included=FALSE)
 }
 monthly<-list()
 for(serial in sort(unique(12*d$year+d$month-1))) {
  a<-d[12*d$year+d$month-1==serial,];a<-a[match(graph$ids,a$fips),]
  monthly[[length(monthly)+1L]]<-data.frame(year=serial%/%12,month=serial%%12+1,counties=nrow(a),log1p_residual_moran=spatial_residual_moran(a$log1p_residual,graph$adj),within_state_centered_moran=spatial_residual_moran(a$log1p_residual-ave(a$log1p_residual,a$state,FUN=mean),graph$adj),significance_test=FALSE)
 }
 list(county=d,state_year=do.call(rbind,rows),monthly=do.call(rbind,monthly))
}
spatial_saved_expected <- function(fit,obj) {
 predictor<-if(is.null(obj$predictor))'Predictor' else obj$predictor
 if(!predictor%in%c('Predictor','APredictor'))stop('Unknown saved predictor adapter')
 table<-fit$summary.fitted.values;pattern<-paste0('^fitted[.]',predictor,'[.]([0-9]+)$')
 selected<-grep(pattern,rownames(table));ids<-as.integer(sub(pattern,'\\1',rownames(table)[selected]))
 if(anyNA(ids)||anyDuplicated(ids)||length(ids)!=nrow(obj$data)||!setequal(ids,seq_len(nrow(obj$data))))stop('Fitted marginal predictor domain differs')
 expected<-table[selected[match(obj$indices,ids)],'mean']
 multiplier<-if(is.null(obj$exposure))rep(1,length(expected)) else obj$exposure
 if(length(multiplier)!=length(expected)||any(!is.finite(multiplier)|multiplier<=0))stop('Invalid saved count-scale adapter')
 expected*multiplier
}
audit_spatial_residuals <- function(fitpath,truthpath,nodespath,edgespath,cutoff,temporal,seasonal,out) {
 if(dir.exists(out))stop('Refusing existing residual output');dir.create(out,recursive=TRUE)
 files<-c(fitpath,truthpath,nodespath,edgespath);before<-tools::md5sum(files);if(anyNA(before))stop('Missing residual audit input')
 fit<-readRDS(fitpath);truth<-read.csv(truthpath,colClasses=c(fips='character'),stringsAsFactors=FALSE)
 obj<-validate_saved_monthly_spatial(fit,truth,cutoff,seasonal)
 if(attr(fit,'monthly_spatial_specification')$temporal!=temporal)stop('Temporal identity differs')
 d<-obj$data[obj$indices,];nodes<-read.csv(nodespath,colClasses='character');edges<-read.csv(edgespath,colClasses='character')
 graph<-monthly_spatial_graph(data.frame(area=d$fips,state=d$state),nodes,edges)
 expected<-spatial_saved_expected(fit,obj);d$observed<-obj$truth
 report<-spatial_residual_reports(d[c('fips','state','year','month','observed')],expected,graph)
 write.csv(report$county,file.path(out,'county_month_residuals_INTERNAL.csv'),row.names=FALSE)
 write.csv(report$state_year,file.path(out,'state_year_residuals.csv'),row.names=FALSE,na='')
 write.csv(report$monthly,file.path(out,'monthly_global_residuals.csv'),row.names=FALSE,na='')
 write.csv(data.frame(cutoff,temporal,seasonal,spatial='bym2',new_fit=FALSE,posterior_resampling=FALSE,
  period='heldout_forecast_only',expected_source='saved_INLA_marginal_fitted_mean_count_scale',residual='log1p_observed_minus_log1p_expected',graph_counties=length(graph$ids),graph_components=graph$n_components,
  moran_undefined='no_edges_or_near_zero_residual_variance',lag_undefined='insufficient_pairs_or_zero_centered_variance',significance_test=FALSE,scientific_acceptance=FALSE),file.path(out,'settings.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(files)))stop('Residual inputs changed')
 writeLines('SPATIAL_SAVED_RESIDUAL_AUDIT_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=8||!a[7]%in%c('TRUE','FALSE'))stop('Usage FIT TRUTH NODES EDGES CUTOFF TEMPORAL SEASONAL OUT');audit_spatial_residuals(a[1],a[2],a[3],a[4],as.integer(a[5]),a[6],a[7]=='TRUE',a[8])}
