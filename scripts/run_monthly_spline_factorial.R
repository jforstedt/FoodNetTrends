#!/usr/bin/env Rscript
.source<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.source))dirname(.source) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'run_monthly_comparison.R'))
source(file.path(.here,'county_spline_candidate.R'))
source(file.path(.here,'monthly_spline_combination.R'))
source(file.path(.here,'audit_saved_monthly.R'))

read_monthly_spline_basis <- function(path,cutoff) {
 x<-read.csv(path);serial<-seq(2004L*12L,(cutoff+3L)*12L+11L)
 if(!identical(names(x),c('serial','slope',paste0('X',1:4)))||!identical(as.numeric(x$serial),as.numeric(serial)))stop('Basis CSV domain differs')
 b<-list(years=as.numeric(x$serial),slope=x$slope,nonlinear=as.matrix(x[,3:6]),k=6L,cutoff=cutoff*12L+11L,version='monthly_training_phase_orthogonal_thin_plate_v1')
 validate_monthly_combination_basis(b,serial,b$cutoff);b
}

validate_saved_monthly_spline <- function(fit,pred,cutoff,seasonal) {
 spec<-attr(fit,'monthly_specification');d<-attr(fit,'monthly_combination_data');basis<-attr(fit,'monthly_combination_basis')
 if(is.null(spec)||spec$version!='monthly_training_phase_orthogonal_thin_plate_v1'||spec$temporal!='spline'||spec$cutoff!=cutoff*12+11||!identical(spec$seasonal,seasonal)||spec$coverage!='EXPLORATORY_ASSUMED_CONTINUOUS'||spec$rate_center!=.0002||spec$k!=6||spec$slope_sd!=.5||spec$nonlinear_sd_upper!=.5||!identical(spec$county_temporal,FALSE))stop('Spline specification differs')
 if(!is.data.frame(d)||!all(c('fips','state','year','month','count','person_years')%in%names(d)))stop('Spline data missing')
 held<-d$year>cutoff;key<-function(x)paste(x$fips,x$state,x$year,x$month,sep='|')
 if(max(d$year)!=cutoff+3||!any(held)||any(!is.na(d$count[held]))||any(!is.finite(d$count[!held]))||any(!is.finite(d$person_years)|d$person_years<=0)||!identical(key(d[held,]),key(pred))||anyDuplicated(key(pred))||any(!is.finite(pred$observed)|pred$observed<0|pred$observed!=floor(pred$observed)))stop('Spline truth/masking/exposure differs')
 validate_monthly_combination_basis(basis,d$year*12+d$month-1,cutoff*12+11)
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||is.null(fit$misc$configs)||!identical(as.character(fit$.args$family),'nbinomial')||!identical(attr(fit,'monthly_combination_indices'),seq_len(nrow(d)))||!identical(attr(fit,'monthly_combination_exposure'),d$person_years)||!isTRUE(all.equal(as.numeric(fit$.args$E),d$person_years)))stop('Invalid spline fit/configuration')
 if(!all(c('area','state_smooth','state_slope')%in%names(fit$summary.random))||('season'%in%names(fit$summary.random))!=seasonal)stop('Spline effect identity differs')
 list(data=d,indices=which(held),truth=pred$observed,predictor='APredictor',exposure=d$person_years[held])
}

run_monthly_spline_factorial <- function(candidate,audit,cutoff,out,seed,seasonal,end_year,basispath,draws=2000L) {
 if(dir.exists(out))stop('Refusing existing output')
 work<-dirname(out);fitpath<-file.path(work,'fit_INTERNAL.rds');truthpath<-file.path(work,'heldout_truth_INTERNAL.csv')
 if(file.exists(fitpath)||file.exists(truthpath))stop('Refusing existing checkpoint')
 inputpaths<-c(candidate,file.path(audit,'county_panel_INTERNAL.rds'),basispath);before<-tools::md5sum(inputpaths)
 d<-load_monthly_comparison(candidate,audit,cutoff,end_year);b<-read_monthly_spline_basis(basispath,cutoff);warnings<-character()
 fit<-withCallingHandlers(fit_monthly_combination(d,cutoff*12+11L,'spline',seasonal,threads=4L,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',basis=b),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 writeLines(warnings,file.path(work,'fit_warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl("vb[.]correction['\"]?.*aborted",warnings,ignore.case=TRUE)))stop('Spline numerical fit gate failed')
 saveRDS(fit,fitpath,version=2)
 truth<-d[d$year>cutoff,c('fips','state','year','month')];truth$observed<-d$count[d$year>cutoff];write.csv(truth,truthpath,row.names=FALSE)
 audit_monthly_saved(fitpath,truthpath,cutoff,seasonal,out,seed,draws=draws,adapter=validate_saved_monthly_spline)
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 write.csv(data.frame(new_fit=TRUE,temporal_model='spline',end_year=end_year,seasonal=seasonal,rate_center=.0002,k=6L,slope_sd=.5,nonlinear_sd_upper=.5,coverage_certified=FALSE,comparison='monthly_spline_factorial_v1'),file.path(out,'sensitivity_settings.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(inputpaths)))stop('Monthly spline inputs changed')
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=8L||!a[6]%in%c('TRUE','FALSE'))stop('Usage CANDIDATE AUDIT CUTOFF OUT SEED SEASONAL END_YEAR BASIS');run_monthly_spline_factorial(a[1],a[2],as.integer(a[3]),a[4],as.integer(a[5]),a[6]=='TRUE',as.integer(a[7]),a[8])}
