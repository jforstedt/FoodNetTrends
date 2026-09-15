#!/usr/bin/env Rscript
# Descriptive input audit only. Does not fit or modify a model.
campylobacter_history_tables <- function(d,origins=c(2011L,2013L,2016L)) {
 needed<-c('fips','state','year','month','count','person_years','population')
 if(!all(needed%in%names(d))||anyNA(d[needed])||anyDuplicated(paste(d$fips,d$year,d$month))||
    any(!is.finite(d$count)|d$count<0|d$count!=floor(d$count))||any(!is.finite(d$person_years)|d$person_years<=0)||
    any(!is.finite(d$population)|d$population<=0)||any(!d$month%in%1:12)||any(!is.finite(d$year)|d$year!=floor(d$year)))stop('Invalid history panel')
 if(any(vapply(split(as.character(d$state),d$fips),function(x)length(unique(x))!=1L,logical(1))))stop('County changes state across years')
 cy<-split(d,paste(d$fips,d$year,sep='|'))
 for(x in cy)if(nrow(x)!=12L||length(unique(x$state))!=1L||length(unique(x$population))!=1L||
    abs(sum(x$person_years)-x$population[1])>max(1e-8,x$population[1]*1e-10))stop('Incomplete county calendar/exposure')
 county<-do.call(rbind,lapply(cy,function(x)data.frame(fips=as.character(x$fips[1]),state=as.character(x$state[1]),year=x$year[1],count=sum(x$count),person_years=sum(x$person_years),zero_months=sum(x$count==0))))
 month<-aggregate(d[c('count','person_years')],d[c('state','year','month')],sum)
 year<-aggregate(county[c('count','person_years')],county[c('state','year')],sum)
 month$record_rate_per_100000_person_years<-month$count/month$person_years*1e5
 year$record_rate_per_100000_person_years<-year$count/year$person_years*1e5
 year<-year[order(year$state,year$year),];month<-month[order(month$state,month$year,month$month),]
 year$previous_year_count<-year$previous_year_person_years<-NA_real_
 for(i in seq_len(nrow(year))){j<-which(year$state==year$state[i]&year$year==year$year[i]-1L);if(length(j)){year$previous_year_count[i]<-year$count[j];year$previous_year_person_years[i]<-year$person_years[j]}}
 year$count_change<-year$count-year$previous_year_count
 year$population_change_fraction<-year$person_years/year$previous_year_person_years-1
 domain<-do.call(rbind,lapply(split(county,paste(county$state,county$year)),function(x){
  prev<-county$fips[county$state==x$state[1]&county$year==x$year[1]-1L]
  hasprev<-length(prev)>0
  data.frame(state=x$state[1],year=x$year[1],counties=nrow(x),zero_record_counties=sum(x$count==0),
    all_zero_month_counties=sum(x$zero_months==12),entered_counties=if(hasprev)length(setdiff(x$fips,prev)) else NA_integer_,
    departed_counties=if(hasprev)length(setdiff(prev,x$fips)) else NA_integer_)
 }))
 phases<-do.call(rbind,lapply(origins,function(o){x<-year;x$cutoff<-o;x$phase<-ifelse(x$year<=o,'training',ifelse(x$year<=o+3,'heldout','outside_origin_evaluation'));x$horizon_year<-ifelse(x$phase=='heldout',x$year-o,NA_integer_);x}))
 list(month=month,year=year,county=county,domain=domain,phases=phases)
}

campylobacter_clean_strata <- function(d) {
 needed<-c('pathogen','year','state')
 if(!all(needed%in%names(d)))stop('Clean inventory lacks pathogen/year/state')
 norm<-function(x)toupper(trimws(as.character(x)))
 keep<-norm(d$pathogen)%in%'CAMPYLOBACTER';y<-suppressWarnings(as.integer(d$year))
 if(any(is.na(y[keep])))stop('Invalid Campylobacter clean year')
 d<-d[keep&y>=2004&y<=2019,,drop=FALSE];d$year<-as.integer(d$year)
 d$state<-norm(d$state);d$state[is.na(d$state)|d$state=='']<-'MISSING'
 fields<-intersect(c('cxcidt','travelint','siteid'),names(d));out<-list()
 for(field in fields){x<-d[c('state','year')];x$field<-field;x$value<-as.character(d[[field]])
  x$value[is.na(x$value)]<-'[MISSING]';x$value[x$value=='']<-'[BLANK]'
  out[[field]]<-aggregate(rep(1L,nrow(x)),x,sum);names(out[[field]])[5]<-'records'}
 list(rows=if(length(out))do.call(rbind,out) else data.frame(),available=fields,
  unavailable=setdiff(c('cxcidt','travelint','siteid'),fields),records=nrow(d))
}

audit_campylobacter_regional_history <- function(taskpath) {
 if(!requireNamespace('jsonlite',quietly=TRUE))stop('jsonlite required')
 task<-jsonlite::read_json(taskpath,simplifyVector=TRUE)
 if(is.null(task$source_run)||is.null(task$output)||dir.exists(task$output))stop('Missing source/output or existing output')
 source_run<-normalizePath(task$source_run,mustWork=TRUE)
 files<-list.files(source_run,pattern='^CAMPYLOBACTER_.*[.]json$',full.names=TRUE)
 tasks<-lapply(files,jsonlite::read_json,simplifyVector=TRUE)
 if(length(tasks)!=36L||any(vapply(tasks,function(t)!identical(t$pathogen,'CAMPYLOBACTER'),logical(1)))||
    !setequal(vapply(tasks,function(t)t$cutoff,numeric(1)),c(2011,2013,2016)))stop('Expected complete frozen Campylobacter task set')
 candidate<-unique(vapply(tasks,function(t)t$candidate,character(1)));audit<-unique(vapply(tasks,function(t)t$audit,character(1)))
 if(length(candidate)!=1L||length(audit)!=1L)stop('Task inputs disagree')
 src<-if(is.null(task$source_scripts))file.path(source_run,'bundle','scripts') else task$source_scripts
 reports<-file.path(audit,'reports');checks<-read.csv(file.path(reports,'input_checksums.csv'),stringsAsFactors=FALSE)
 preparation<-file.path(dirname(candidate),'input_checksums.csv')
 prepchecks<-if(file.exists(preparation))read.csv(preparation,stringsAsFactors=FALSE) else NULL
 side_names<-c('state_month_records.csv','annual_reconciliation.csv','readiness.csv','date_issues.csv','source_month_comparison.csv')
 side<-file.path(dirname(candidate),side_names);side<-side[file.exists(side)]
 inputs<-unique(c(side,taskpath,files,candidate,file.path(audit,'county_panel_INTERNAL.rds'),
   list.files(reports,full.names=TRUE),list.files(src,pattern='[.]R$',full.names=TRUE),checks$file,
   if(!is.null(prepchecks))c(preparation,prepchecks$file)))
 before<-tools::md5sum(inputs);if(anyNA(before))stop('Missing provenance input')
 if(!is.null(prepchecks)&&any(unname(tools::md5sum(prepchecks$file))!=prepchecks$md5))stop('Monthly preparation sources changed')
 dir.create(task$output,recursive=TRUE);complete<-FALSE
 on.exit(if(!complete)writeLines('FAILED',file.path(task$output,'status.txt')),add=TRUE)
 # Frozen source uses sys.frame(1)$ofile to resolve its sibling scripts.
 frame<-sys.frame(1);had<-exists('ofile',frame,inherits=FALSE);old<-if(had)get('ofile',frame) else NULL
 assign('ofile',file.path(src,'run_monthly_comparison.R'),frame)
 tryCatch(source(file.path(src,'run_monthly_comparison.R'),local=globalenv()),finally={if(had)assign('ofile',old,frame) else rm('ofile',envir=frame)})
 d<-load_monthly_comparison(candidate,audit,2016L,2019L)
 if(!setequal(as.character(unique(d$state)),c('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'))||!setequal(unique(d$year),2004:2019))stop('Unexpected historical scope')
 tables<-campylobacter_history_tables(d)
 names<-c(month='state_month_history.csv',year='state_year_history.csv',county='county_year_INTERNAL.csv',domain='county_domain_summary.csv',phases='state_year_origin_history.csv')
 for(n in names(names))write.csv(tables[[n]],file.path(task$output,names[[n]]),row.names=FALSE)
 # Preserve earlier raw/clean reconciliation evidence without treating this as a new replay.
 annual_replayed<-'NOT_AVAILABLE'
 for(p in side){x<-read.csv(p,stringsAsFactors=FALSE)
  if(basename(p)=='annual_reconciliation.csv') {
   if(!all(c('state','year','assigned_records','population','candidate_person_years')%in%names(x)))stop('Original annual reconciliation schema differs')
   key<-function(z)paste(z$state,z$year,sep='|');a<-tables$year
   if(anyDuplicated(key(x))||!setequal(key(x),key(a)))stop('Original annual reconciliation domain differs')
   x<-x[match(key(a),key(x)),]
   if(anyNA(x[c('assigned_records','population','candidate_person_years')])||any(x$assigned_records!=a$count)||
      any(abs(x$population-a$person_years)>pmax(1e-8,a$person_years*1e-10))||
      any(abs(x$candidate_person_years-a$person_years)>pmax(1e-8,a$person_years*1e-10)))stop('Original annual reconciliation differs from frozen panel')
   if(all(c('annual_records','unassigned_records')%in%names(x))&&(anyNA(x[c('annual_records','unassigned_records')])||any(x$unassigned_records<0)||any(x$annual_records!=x$assigned_records+x$unassigned_records)))stop('Original annual/date assignment accounting differs')
   annual_replayed<-'VERIFIED_AGAINST_FROZEN_PANEL'
  }
  if(!any(grepl('fips|county',names(x),ignore.case=TRUE)))write.csv(x,file.path(task$output,paste0('original_',basename(p))),row.names=FALSE)
 }
 cleanpaths<-if(is.null(prepchecks))character() else prepchecks$file[grepl('^clean.*[.]csv$',basename(prepchecks$file),ignore.case=TRUE)]
 cleanmeta<-list(status='UNAVAILABLE',reason='No unique hash-bound clean CSV identified in original monthly preparation inputs')
 if(length(cleanpaths)==1L){
  clean<-read.csv(cleanpaths,colClasses='character',check.names=FALSE,stringsAsFactors=FALSE)
  strata<-campylobacter_clean_strata(clean)
  if(length(strata$available))write.csv(strata$rows,file.path(task$output,'clean_state_year_strata.csv'),row.names=FALSE)
  cleanmeta<-list(status='DESCRIPTIVE_INVENTORY_COMPLETE',file=cleanpaths,available=strata$available,unavailable=strata$unavailable,
    records=strata$records,scope='All clean Campylobacter records 2004-2019 before county/travel/CIDT selection; labels preserved, not interpreted or corrected')
 }
 metadata<-list(version='campylobacter_regional_history_v1',scientific_acceptance=FALSE,original_annual_reconciliation=annual_replayed,models_fitted=FALSE,clean_inventory=cleanmeta,status='CAMPYLOBACTER_REGIONAL_HISTORY_COMPLETE',pathogen='CAMPYLOBACTER',refitted=FALSE,
  source_run=source_run,candidate=candidate,audit=audit,source_tasks=length(tasks),years=2004:2019,
  states=sort(unique(as.character(d$state))),coverage_certified=FALSE,
  interpretation='Frozen selected case records and annual-population day-fraction exposure; zero records do not certify observed zero incidence',
  candidate_annual_reconciliation='VERIFIED_BY_FROZEN_LOADER',
  original_preparation_source_hashes=if(is.null(prepchecks))'NOT_AVAILABLE' else 'VERIFIED_UNCHANGED',
  direct_clean_monthly_comparison='NOT_REPLAYED: prior preparation reports/hash-bound inputs retained where available; clean inventory is unselected and cannot substitute for dated raw selection',
  model_context='Existing Campylobacter RW1 already has state-specific trajectories with shared smoothing precision; this audit cannot identify reporting changes or causal mechanisms')
 if(!identical(before,tools::md5sum(inputs)))stop('Audit input changed')
 write.csv(data.frame(file=inputs,md5=unname(before)),file.path(task$output,'input_checksums.csv'),row.names=FALSE)
 jsonlite::write_json(metadata,file.path(task$output,'audit_metadata.json'),auto_unbox=TRUE,pretty=TRUE)
 writeLines(metadata$status,file.path(task$output,'status.txt'));complete<-TRUE
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=1L)stop('Usage TASK_JSON');audit_campylobacter_regional_history(a[1])}
