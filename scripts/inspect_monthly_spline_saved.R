#!/usr/bin/env Rscript
# Saved posterior component summaries only: no INLA fitting or sampling.
inspect_monthly_spline_saved <- function(fitpath,truthpath,out,cutoff,seasonal) {
 if(dir.exists(out))stop('Refusing existing inspection output');dir.create(out,recursive=TRUE)
 before<-tools::md5sum(c(fitpath,truthpath));fit<-readRDS(fitpath)
 d<-attr(fit,'monthly_combination_data');b<-attr(fit,'monthly_combination_basis');spec<-attr(fit,'monthly_specification')
 if(is.null(d)||is.null(b)||is.null(spec)||spec$version!='monthly_training_phase_orthogonal_thin_plate_v1'||spec$temporal!='spline'||spec$cutoff!=cutoff*12+11||!identical(spec$seasonal,seasonal)||!identical(spec$county_temporal,FALSE))stop('Saved spline identity differs')
 if(!all(c('fips','state','state_id','year','month','count','person_years')%in%names(d)))stop('Missing masked observation metadata')
 serial<-d$year*12+d$month-1;held<-d$year>cutoff
 if(any(!is.na(d$count[held]))||any(!is.finite(d$count[!held])|d$count[!held]<0|d$count[!held]!=floor(d$count[!held]))||any(!is.finite(d$person_years)|d$person_years<=0)||max(d$year)!=cutoff+3)stop('Invalid saved masking or exposure')
 truth<-read.csv(truthpath,colClasses=c(fips='character'));key<-function(x)paste(x$fips,x$state,x$year,x$month,sep='|')
 if(!identical(key(d[held,]),key(truth))||anyDuplicated(key(truth))||any(!is.finite(truth$observed)|truth$observed<0|truth$observed!=floor(truth$observed)))stop('Held-out truth order differs')
 observed<-d$count;observed[held]<-truth$observed
 states<-unique(d[c('state','state_id')]);states<-states[order(states$state_id),]
 if(anyDuplicated(states$state)||!identical(as.integer(states$state_id),seq_len(nrow(states))))stop('Invalid state coefficient mapping')
 q<-ncol(b$nonlinear);ix<-match(sort(unique(serial)),b$years)
 if(anyNA(ix)||anyDuplicated(b$years)||q!=4L||any(!is.finite(b$nonlinear))||any(!is.finite(b$slope)))stop('Invalid basis')
 slope<-fit$summary.random$state_slope;smooth<-fit$summary.random$state_smooth
 if(is.null(slope)||is.null(smooth)||anyDuplicated(slope$ID)||anyDuplicated(smooth$ID)||!setequal(slope$ID,seq_len(nrow(states)))||!setequal(smooth$ID,seq_len(nrow(states)*q))||any(!is.finite(c(slope$mean,smooth$mean))))stop('Invalid temporal coefficient summaries')
 result<-list();changes<-list();coefficients<-list()
 for(i in seq_len(nrow(states))) {
  s<-as.character(states$state[i]);g<-states$state_id[i]
  linear<-b$slope[ix]*slope$mean[match(g,slope$ID)]
  nonlinear<-as.numeric(b$nonlinear[ix,,drop=FALSE]%*%smooth$mean[match((g-1L)*q+seq_len(q),smooth$ID)])
  months<-b$years[ix];anchor<-match(cutoff*12+11,months)
  pick<-as.character(d$state)==s;ds<-d[pick,];obs<-observed[pick]
  observed_by_month<-tapply(obs,serial[pick],sum);exposure_by_month<-tapply(ds$person_years,serial[pick],sum)
  result[[i]]<-data.frame(state=s,year=months%/%12,month=months%%12+1,in_training=months<=cutoff*12+11,
   observed=as.numeric(observed_by_month[as.character(months)]),person_years=as.numeric(exposure_by_month[as.character(months)]),
   mean_log_linear=linear,mean_log_nonlinear=nonlinear,mean_log_temporal=linear+nonlinear,
   linear_change_from_origin=linear-linear[anchor],nonlinear_change_from_origin=nonlinear-nonlinear[anchor],
   temporal_change_from_origin=linear+nonlinear-linear[anchor]-nonlinear[anchor])
  y<-result[[i]];changes[[i]]<-y[y$year>cutoff&y$month==12,]
  coefficients[[i]]<-rbind(data.frame(state=s,component='linear',basis_column=0,posterior_mean=slope$mean[match(g,slope$ID)]),data.frame(state=s,component='nonlinear',basis_column=seq_len(q),posterior_mean=smooth$mean[match((g-1L)*q+seq_len(q),smooth$ID)]))
 }
 write.csv(do.call(rbind,result),file.path(out,'state_month_components.csv'),row.names=FALSE)
 write.csv(do.call(rbind,changes),file.path(out,'december_temporal_changes.csv'),row.names=FALSE)
 write.csv(do.call(rbind,coefficients),file.path(out,'state_coefficients.csv'),row.names=FALSE)
 write.csv(data.frame(cutoff=cutoff,seasonal=seasonal,refitted=FALSE,resampled=FALSE,component_scale='posterior mean log-rate contribution; excludes intercept county seasonal effects',joint_intervals=FALSE),file.path(out,'settings.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(c(fitpath,truthpath))))stop('Saved source changed')
 write.csv(data.frame(path=c(fitpath,truthpath),md5=unname(before)),file.path(out,'input_checksums.csv'),row.names=FALSE)
 writeLines('SAVED_SPLINE_COMPONENT_INSPECTION_COMPLETE',file.path(out,'status.txt'))
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=5L||!a[5]%in%c('TRUE','FALSE'))stop('Usage FIT TRUTH OUT CUTOFF SEASONAL');inspect_monthly_spline_saved(a[1],a[2],a[3],as.integer(a[4]),a[5]=='TRUE')}
