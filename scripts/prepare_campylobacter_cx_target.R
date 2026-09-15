#!/usr/bin/env Rscript
# Separate recorded CX+ incidence target. Original combined data are never overwritten.
cx_subset_inventory <- function(selected,panel,combined,inventory) {
 if(!'cxcidt'%in%names(selected)||anyNA(selected$cxcidt))stop('Missing recorded diagnostic category')
 cx<-selected[selected$cxcidt=='CX+',,drop=FALSE]
 key<-function(x)paste(x$state,x$fips,x$year,sep='|')
 if(any(!key(cx)%in%key(panel)))stop('CX records outside original domain')
 p<-panel;p$count<-as.integer(table(factor(key(cx),levels=key(panel))))
 result<-inventory(cx,p)
 k<-function(x)paste(key(x),x$month,sep='|');g<-result$grid
 j<-match(k(g),k(combined))
 if(anyNA(j)||anyDuplicated(k(g))||!setequal(k(g),k(combined))||any(g$record_count>combined$record_count[j])||
    any(g$population!=combined$population[j])||any(g$candidate_person_years!=combined$candidate_person_years[j]))stop('CX subset/count/exposure reconciliation failed')
 if(any(result$annual$unassigned_records!=0))stop('Unassigned CX specimen dates require review')
 result
}
prepare_campylobacter_cx_target <- function(taskpath) {
 required<-c('jsonlite','haven','readr','tidyselect')
 missing<-required[!vapply(required,requireNamespace,logical(1),quietly=TRUE)]
 if(length(missing))stop('SAS preparation runtime missing packages: ',paste(missing,collapse=', '))
 task<-jsonlite::read_json(taskpath,simplifyVector=TRUE)
 if(!all(c('source_run','source_scripts','preparation_scripts','output')%in%names(task))||dir.exists(task$output))stop('Invalid/existing preparation task')
 files<-list.files(task$source_run,pattern='^CAMPYLOBACTER_.*[.]json$',full.names=TRUE)
 ts<-lapply(files,jsonlite::read_json,simplifyVector=TRUE)
 if(length(ts)!=36L)stop('Missing frozen Campylobacter tasks')
 candidate<-unique(vapply(ts,function(t)t$candidate,character(1)));audit<-unique(vapply(ts,function(t)t$audit,character(1)))
 if(length(candidate)!=1L||length(audit)!=1L)stop('Original candidate/audit differs')
 cp<-file.path(dirname(candidate),'input_checksums.csv');checks<-read.csv(cp,stringsAsFactors=FALSE)
 if(nrow(checks)!=4L||any(!file.exists(checks$file))||any(unname(tools::md5sum(checks$file))!=checks$md5))stop('Original monthly preparation inputs changed')
 # Original prepare_monthly_county writes raw, clean, mapping, annual panel in this order.
 rawpath<-checks$file[1];cleanpath<-checks$file[2];mappingpath<-checks$file[3]
 if(normalizePath(checks$file[4])!=normalizePath(file.path(audit,'county_panel_INTERNAL.rds')))stop('Original annual input identity mismatch')
 inputs<-unique(c(taskpath,files,cp,checks$file,candidate,list.files(task$source_scripts,pattern='[.]R$',full.names=TRUE),list.files(task$preparation_scripts,pattern='[.]R$',full.names=TRUE)))
 before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing frozen preparation source')
 dir.create(task$output,recursive=TRUE);complete<-FALSE;on.exit(if(!complete)writeLines('FAILED',file.path(task$output,'status.txt')),add=TRUE)
 for(n in c('county_matching.R','reconcile_raw_county.R','fit_county_pilot.R','prepare_monthly_county.R'))source(file.path(task$preparation_scripts,n),local=globalenv())
 replay<-file.path(task$output,'replay_INTERNAL')
 prepare_monthly_county(rawpath,cleanpath,mappingpath,audit,replay,'CAMPYLOBACTER')
 original<-readRDS(candidate);recreated<-readRDS(file.path(replay,'candidate_monthly_INTERNAL.rds'))
 keys<-function(x)paste(x$state,x$fips,x$year,x$month,sep='|')
 cols<-c('state','fips','year','month','record_count','population','candidate_person_years','modeled_count','observation_status','exposure_status')
 if(anyDuplicated(keys(original))||!setequal(keys(original),keys(recreated))||!isTRUE(all.equal(original[order(keys(original)),cols],recreated[order(keys(recreated)),cols],check.attributes=FALSE)))stop('Replayed combined candidate differs')
 raw<-as.data.frame(haven::read_sas(rawpath));names(raw)<-tolower(names(raw))
 fields<-c('year','state','county','fips','pathogen','travelint','cxcidt','siteid','dtspec','month')
 if(!all(fields%in%names(raw)))stop('Missing original raw fields');raw<-raw[fields]
 map<-read.csv(mappingpath,stringsAsFactors=FALSE);aliases<-unique(as.character(map$original[county_norm(map$standardized)=='CAMPYLOBACTER']))
 if(!length(aliases))stop('Missing authoritative Campylobacter aliases')
 raw$year<-suppressWarnings(as.integer(raw$year));raw<-raw[!is.na(raw$year)&raw$year>=2004&raw$year<=2019&as.character(raw$pathogen)%in%aliases,,drop=FALSE]
 for(k in c('county','siteid')){raw[[k]]<-as.character(raw[[k]]);raw[[k]][is.na(raw[[k]])]<-''}
 keep<-classify_removals(raw)=='retained_candidate'
 for(k in c('state','county','travelint','cxcidt','siteid'))raw[[k]]<-county_norm(raw[[k]])
 raw$fips<-county_fips(raw$fips);raw<-raw[keep,,drop=FALSE]
 select<-function(x)x[x$travelint%in%c('NO','UNKNOWN','YES')&x$cxcidt%in%c('CIDT+','CX+','PARASITIC')&!x$county%in%c('UNKNOWN','OUT OF STATE','99997'),,drop=FALSE]
 selected<-select(raw)
 clean<-as.data.frame(readr::read_csv(cleanpath,col_types=readr::cols(.default=readr::col_character()),col_select=tidyselect::all_of(setdiff(fields,c('dtspec','month'))),show_col_types=FALSE,num_threads=2))
 if(nrow(readr::problems(clean)))stop('Clean parsing failure')
 clean$year<-suppressWarnings(as.integer(clean$year));clean<-clean[!is.na(clean$year)&clean$year>=2004&clean$year<=2019&county_norm(clean$pathogen)=='CAMPYLOBACTER',,drop=FALSE]
 for(k in c('state','county','travelint','cxcidt','siteid'))clean[[k]]<-county_norm(clean[[k]])
 clean$fips<-county_fips(clean$fips);clean<-select(clean)
 cmp<-reconcile_counts(selected[selected$cxcidt=='CX+',],clean[clean$cxcidt=='CX+',],c('year','state','fips','travelint','cxcidt','siteid'))
 if(any(cmp$difference!=0))stop('Recorded CX raw/clean strata differ')
 panel<-validate_panel(audit,expected_production=FALSE)$data
 result<-cx_subset_inventory(selected,panel,original,monthly_inventory)
 k<-keys(result$grid);j<-match(k,keys(original));early<-result$grid$year<=2011L
 if(any(result$grid$record_count[early]!=original$record_count[j][early]))stop('Pre-2012 recorded CX target differs from combined; premise requires review')
 saveRDS(result$grid,file.path(task$output,'cx_monthly_INTERNAL.rds'),version=2)
 write.csv(cmp,file.path(task$output,'cx_raw_clean_reconciliation_INTERNAL.csv'),row.names=FALSE)
 a<-aggregate(result$grid[c('record_count','candidate_person_years')],result$grid[c('state','year')],sum)
 orig<-aggregate(original['record_count'],original[c('state','year')],sum);names(orig)[3]<-'combined_records'
 a<-merge(a,orig,by=c('state','year'));names(a)[3]<-'cx_records'
 write.csv(a,file.path(task$output,'state_year_target_counts.csv'),row.names=FALSE)
 meta<-list(version='campylobacter_cx_target_v1',status='CX_TARGET_PREPARATION_COMPLETE',pathogen='CAMPYLOBACTER',target='recorded_CX_positive',
  combined_candidate=candidate,audit=audit,combined_replay_verified=TRUE,raw_clean_cx_strata_verified=TRUE,pre2012_cx_equals_combined=TRUE,
  coverage_certified=FALSE,scientific_acceptance=FALSE,models_fitted=FALSE,
  interpretation='Recorded CX+ subset; not corrected total incidence, testing effort or stable diagnostic ascertainment',
  cx_candidate_md5=unname(tools::md5sum(file.path(task$output,'cx_monthly_INTERNAL.rds'))))
 if(!identical(before,tools::md5sum(inputs)))stop('Preparation inputs changed')
 write.csv(data.frame(file=inputs,md5=unname(before)),file.path(task$output,'input_checksums.csv'),row.names=FALSE)
 jsonlite::write_json(meta,file.path(task$output,'preparation_metadata.json'),auto_unbox=TRUE,pretty=TRUE)
 writeLines(meta$status,file.path(task$output,'status.txt'));complete<-TRUE
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage TASK_JSON');prepare_campylobacter_cx_target(a[1])}
