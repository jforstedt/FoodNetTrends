#!/usr/bin/env Rscript
.src<-tryCatch(sys.frame(1)$ofile,error=function(e)NULL)
.here<-if(!is.null(.src))dirname(.src) else dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
source(file.path(.here,'run_monthly_spline_factorial.R'))
source(file.path(.here,'monthly_spatial_combination.R'))

validate_saved_monthly_spatial <- function(fit,pred,cutoff,seasonal) {
 s<-attr(fit,'monthly_spatial_specification')
 if(is.null(s)||s$version!='monthly_static_bym2_v1'||!s$temporal%in%c('rw1','ar1','spline')||
    !identical(s$seasonal,seasonal)||!identical(s$sd_upper,1)||!identical(s$sd_tail,.01)||
    !identical(s$phi_u,.5)||!identical(s$phi_probability,.5)||!isTRUE(s$scale_model)||
    !isTRUE(s$component_constraints)||!identical(s$county_temporal,FALSE))stop('Spatial specification differs')
 obj<-if(s$temporal=='spline')validate_saved_monthly_spline(fit,pred,cutoff,seasonal) else validate_monthly_saved(fit,pred,cutoff,seasonal,expected_temporal=s$temporal)
 if(!identical(sort(unique(as.character(obj$data$fips))),s$ids))stop('Saved graph identity differs')
 # BYM2 reports both combined and unstructured latent parts. The stored formula
 # must identify the exact opt-in model; metadata alone is not sufficient.
 formula_text<-paste(deparse(fit$.args$formula),collapse=' ')
 if(!grepl('bym2',formula_text,fixed=TRUE)||!grepl('adjust.for.con.comp = TRUE',formula_text,fixed=TRUE))stop('Saved BYM2 formula differs')
 obj
}

run_monthly_spatial_factorial <- function(candidate,audit,cutoff,out,seed,temporal,seasonal,end_year,basispath,nodespath,edgespath,draws=2000L) {
 if(dir.exists(out))stop('Refusing existing output')
 work<-dirname(out);fitpath<-file.path(work,'fit_INTERNAL.rds');truthpath<-file.path(work,'heldout_truth_INTERNAL.csv')
 if(file.exists(fitpath)||file.exists(truthpath))stop('Refusing existing checkpoint')
 inputpaths<-c(candidate,file.path(audit,'county_panel_INTERNAL.rds'),basispath,nodespath,edgespath);before<-tools::md5sum(inputpaths)
 if(anyNA(before))stop('Missing spatial input')
 d<-load_monthly_comparison(candidate,audit,cutoff,end_year)
 b<-if(temporal=='spline')read_monthly_spline_basis(basispath,cutoff) else NULL
 nodes<-read.csv(nodespath,colClasses='character');edges<-read.csv(edgespath,colClasses='character');warnings<-character()
 fit<-withCallingHandlers(fit_monthly_spatial_combination(d,cutoff*12+11L,nodes,edges,temporal,seasonal,
   threads=4L,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',basis=b),warning=function(w){warnings<<-c(warnings,conditionMessage(w))})
 writeLines(warnings,file.path(work,'fit_warnings.txt'))
 if(!isTRUE(fit$ok)||!identical(as.numeric(fit$mode$mode.status),0)||any(grepl("vb[.]correction['\"]?.*aborted",warnings,ignore.case=TRUE)))stop('Spatial numerical fit gate failed')
 saveRDS(fit,fitpath,version=2)
 truth<-d[d$year>cutoff,c('fips','state','year','month')];truth$observed<-d$count[d$year>cutoff];write.csv(truth,truthpath,row.names=FALSE)
 audit_monthly_saved(fitpath,truthpath,cutoff,seasonal,out,seed,draws=draws,adapter=validate_saved_monthly_spatial)
 write.csv(fit$summary.hyperpar,file.path(out,'hyperparameters.csv'),row.names=TRUE)
 s<-attr(fit,'monthly_spatial_specification')
 write.csv(data.frame(new_fit=TRUE,temporal_model=temporal,end_year=end_year,seasonal=seasonal,rate_center=.0002,
   spatial='bym2',sd_upper=1,sd_tail=.01,phi_u=.5,phi_probability=.5,n_counties=length(s$ids),n_components=s$n_components,n_edges=s$n_edges,
   coverage_certified=FALSE,comparison='monthly_spatial_factorial_v1'),file.path(out,'sensitivity_settings.csv'),row.names=FALSE)
 if(!identical(before,tools::md5sum(inputpaths)))stop('Spatial monthly inputs changed')
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=11L||!a[7]%in%c('TRUE','FALSE'))stop('Usage CANDIDATE AUDIT CUTOFF OUT SEED TEMPORAL SEASONAL END_YEAR BASIS NODES EDGES');run_monthly_spatial_factorial(a[1],a[2],as.integer(a[3]),a[4],as.integer(a[5]),a[6],a[7]=='TRUE',as.integer(a[8]),a[9],a[10],a[11])}
