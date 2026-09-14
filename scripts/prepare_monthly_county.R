#!/usr/bin/env Rscript
# Candidate record inventory only. No monthly observation eligibility is inferred.
monthly_inventory <- function(selected,panel) {
  required<-c('year','state','fips','dtspec','month')
  if(!all(required%in%names(selected))||!inherits(selected$dtspec,'Date'))stop('Selected records require an actual Date specimen field')
  if(!all(c('year','state','fips','population','count')%in%names(panel)))stop('Missing annual panel fields')
  key<-function(x)paste(x$state,x$fips,x$year,sep='|')
  if(anyDuplicated(key(panel))||anyNA(panel[c('year','state','fips','population','count')])||any(!is.finite(panel$population)|panel$population<=0)||any(!is.finite(panel$count)|panel$count<0|panel$count!=floor(panel$count)))stop('Invalid annual panel')
  if(anyNA(selected[c('year','state','fips')])||any(!key(selected)%in%key(panel)))stop('Selected record outside annual panel')
  counts<-table(factor(key(selected),levels=key(panel)))
  if(any(as.numeric(counts)!=panel$count))stop('Raw selected-to-annual panel reconciliation failed')
  date<-selected$dtspec;date[!is.finite(as.numeric(date))]<-NA
  dateyear<-suppressWarnings(as.integer(format(date,'%Y')));datemonth<-suppressWarnings(as.integer(format(date,'%m')))
  mo<-suppressWarnings(as.numeric(as.character(selected$month)))
  mo[!is.finite(mo)|mo!=floor(mo)]<-NA_real_
  missing<-is.na(date);yearbad<-!missing&dateyear!=selected$year
  assignable<-!missing&!yearbad
  issues<-data.frame(state=as.character(selected$state),year=selected$year,records=rep(1L,nrow(selected)),missing_specimen_date=as.integer(missing),specimen_year_disagreement=as.integer(yearbad),
    month_missing_invalid=as.integer(is.na(mo)|mo<1|mo>12),month_disagreement=as.integer(!missing&!is.na(mo)&mo>=1&mo<=12&mo!=datemonth),unassigned_records=as.integer(!assignable))
  issues<-if(nrow(issues))aggregate(issues[,setdiff(names(issues),c('state','year'))],issues[c('state','year')],sum)else data.frame()
  grid<-panel[rep(seq_len(nrow(panel)),each=12),c('year','state','fips','population')];grid$month<-rep(1:12,nrow(panel));rownames(grid)<-NULL
  start<-as.Date(sprintf('%04d-%02d-01',grid$year,grid$month));nextmonth<-as.Date(sprintf('%04d-%02d-01',grid$year+as.integer(grid$month==12),grid$month%%12+1L))
  grid$days_in_month<-as.integer(nextmonth-start)
  grid$days_in_year<-as.integer(as.Date(paste0(grid$year+1L,'-01-01'))-as.Date(paste0(grid$year,'-01-01')))
  grid$candidate_person_years<-grid$population*grid$days_in_month/grid$days_in_year
  mkey<-function(x)paste(key(x),x$month,sep='|')
  assigned<-selected[assignable,,drop=FALSE];assigned$month<-datemonth[assignable]
  grid$record_count<-as.integer(table(factor(mkey(assigned),levels=mkey(grid))))
  grid$modeled_count<-NA_integer_;grid$observation_status<-'UNVERIFIED';grid$exposure_status<-'UNVALIDATED_ANNUAL_POPULATION_DAY_FRACTION'
  annual<-panel[c('state','fips','year','count','population')];names(annual)[4]<-'annual_records'
  annual$assigned_records<-as.numeric(table(factor(key(assigned),levels=key(panel))))
  annual$unassigned_records<-annual$annual_records-annual$assigned_records
  sums<-tapply(grid$candidate_person_years,key(grid),sum)
  if(any(abs(as.numeric(sums[key(panel)])-panel$population)>pmax(1e-8,panel$population*1e-12)))stop('Annual exposure reconciliation failed')
  annual$candidate_person_years<-as.numeric(sums[key(panel)])
  state_month<-aggregate(grid[c('record_count','candidate_person_years')],grid[c('state','year','month')],sum)
  state_month$observation_status<-'UNVERIFIED';state_month$modeled_count<-NA_integer_
  # Compare two explicit month definitions without changing either source field.
  source_ok<-!is.na(mo)&mo>=1&mo<=12
  alternative<-selected[source_ok,,drop=FALSE];alternative$month<-mo[source_ok]
  alternative_grid<-grid[c('state','fips','year','month')]
  alternative_grid$source_month_records<-as.integer(table(factor(mkey(alternative),levels=mkey(grid))))
  source_summary<-aggregate(alternative_grid['source_month_records'],alternative_grid[c('state','year','month')],sum)
  month_comparison<-merge(state_month[c('state','year','month','record_count')],source_summary,by=c('state','year','month'),all=TRUE)
  names(month_comparison)[names(month_comparison)=='record_count']<-'specimen_month_records'
  month_comparison$difference<-month_comparison$source_month_records-month_comparison$specimen_month_records
  calendar<-unique(grid[c('state','year','month')]);calendar$observation_status<-'UNVERIFIED';calendar$observed_days<-NA_integer_;calendar$evidence_reference<-''
  list(grid=grid,annual=annual,issues=issues,state_month=state_month,calendar=calendar,month_comparison=month_comparison)
}

prepare_monthly_county <- function(rawpath,cleanpath,mappingpath,audit,out,pathogen) {
  if(!pathogen%in%c('SALMONELLA','CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA','SHIGELLA','STEC','VIBRIO','YERSINIA'))stop('Unsupported pathogen')
  end_year<-if(pathogen=='CRYPTOSPORIDIUM')2017L else 2019L
  if(dir.exists(out))stop('Refusing existing output')
  dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  files<-c(rawpath,cleanpath,mappingpath,file.path(audit,'county_panel_INTERNAL.rds'));before<-tools::md5sum(files)
  tryCatch({
    if(anyNA(before))stop('Missing monthly input')
    obj<-validate_panel(audit,expected_production=FALSE);panel<-obj$data
    if(nrow(panel)!=486L*(end_year-2004L+1L)||!identical(sort(unique(panel$year)),2004:end_year))stop('Unexpected monthly pilot domain')
    auditchecks<-read.csv(file.path(audit,'reports/input_checksums.csv'),stringsAsFactors=FALSE)
    ix<-match(normalizePath(cleanpath),normalizePath(auditchecks$file,mustWork=FALSE))
    if(is.na(ix)||auditchecks$md5[ix]!=unname(before[2]))stop('Clean input differs from annual audit')
    raw<-as.data.frame(haven::read_sas(rawpath));names(raw)<-tolower(names(raw))
    fields<-c('year','state','county','fips','pathogen','travelint','cxcidt','siteid')
    if(pathogen=='LISTERIA')fields<-c(fields,'cste')
    if(!all(c(fields,'dtspec','month')%in%names(raw)))stop('Missing raw monthly fields')
    raw<-raw[c(fields,'dtspec','month')]
    clean<-as.data.frame(readr::read_csv(cleanpath,col_types=readr::cols(.default=readr::col_character()),col_select=tidyselect::all_of(fields),show_col_types=FALSE,num_threads=2))
    if(nrow(readr::problems(clean)))stop('Clean parsing failure')
    map<-read.csv(mappingpath,stringsAsFactors=FALSE)
    if(!all(c('original','standardized')%in%names(map)))stop('Invalid preprocessing mapping')
    aliases<-unique(as.character(map$original[county_norm(map$standardized)==pathogen]));if(!length(aliases))stop('No authoritative recorded pathogen aliases')
    for(n in c('raw','clean')) {x<-get(n);x$year<-suppressWarnings(as.integer(x$year));assign(n,x)}
    if(anyNA(raw$year[as.character(raw$pathogen)%in%aliases])||anyNA(clean$year[county_norm(clean$pathogen)==pathogen]))stop('Invalid relevant year')
    raw<-raw[!is.na(raw$year)&raw$year>=2004&raw$year<=end_year&as.character(raw$pathogen)%in%aliases,,drop=FALSE]
    clean<-clean[!is.na(clean$year)&clean$year>=2004&clean$year<=end_year&county_norm(clean$pathogen)==pathogen,,drop=FALSE]
    for(k in c('county','siteid')){raw[[k]]<-as.character(raw[[k]]);raw[[k]][is.na(raw[[k]])]<-''}
    keep<-classify_removals(raw)=='retained_candidate'
    if(pathogen=='LISTERIA') {
      keep<-keep&county_norm(raw$cste)=='YES'
      if(any(county_norm(clean$cste)!='YES'))stop('Clean Listeria CSTE eligibility differs')
    }
    for(k in c('state','county','travelint','cxcidt','siteid')){raw[[k]]<-county_norm(raw[[k]]);clean[[k]]<-county_norm(clean[[k]])}
    raw$fips<-county_fips(raw$fips);clean$fips<-county_fips(clean$fips);raw<-raw[keep,,drop=FALSE]
    comparison<-reconcile_counts(raw,clean,c('year','state','fips','travelint','cxcidt','siteid'))
    if(any(comparison$difference!=0))stop('Raw-to-clean aggregate strata differ; monthly linkage not established')
    select<-function(x)x[x$travelint%in%c('NO','UNKNOWN','YES')&x$cxcidt%in%c('CIDT+','CX+','PARASITIC')&!x$county%in%c('UNKNOWN','OUT OF STATE','99997'),,drop=FALSE]
    selected<-select(raw);clean_selected<-select(clean)
    clean_cmp<-reconcile_counts(selected,clean_selected,c('year','state','fips'))
    if(any(clean_cmp$difference!=0))stop('Selected raw/clean county totals differ')
    result<-monthly_inventory(selected,panel)
    saveRDS(result$grid,file.path(out,'candidate_monthly_INTERNAL.rds'),version=2)
    write.csv(result$month_comparison,file.path(out,'source_month_comparison.csv'),row.names=FALSE)
    write.csv(result$state_month,file.path(out,'state_month_records.csv'),row.names=FALSE,na='')
    annual<-aggregate(result$annual[c('annual_records','assigned_records','unassigned_records','population','candidate_person_years')],result$annual[c('state','year')],sum)
    write.csv(annual,file.path(out,'annual_reconciliation.csv'),row.names=FALSE)
    write.csv(result$issues,file.path(out,'date_issues.csv'),row.names=FALSE)
    write.csv(result$calendar,file.path(out,'calendar_template.csv'),row.names=FALSE,na='')
    write.csv(data.frame(pathogen=pathogen,status='REVIEW_REQUIRED',monthly_observation_verified=FALSE,candidate_rows=nrow(result$grid),raw_clean_strata_match=TRUE,individual_linkage_validated=FALSE,
      note='Zero record inventories are not observed zero incidence; modeled_count remains missing. Calendar template is required evidence, not certified coverage.'),file.path(out,'readiness.csv'),row.names=FALSE)
    if(!identical(before,tools::md5sum(files)))stop('Inputs changed during monthly preparation')
    write.csv(data.frame(file=files,md5=unname(before)),file.path(out,'input_checksums.csv'),row.names=FALSE)
    writeLines('MONTHLY_PREPARATION_COMPLETE',file.path(out,'status.txt'))
  },error=function(e){writeLines(c('MONTHLY_PREPARATION_BLOCKED',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=6L)stop('Usage: RAW CLEAN MAPPING AUDIT OUT PATHOGEN');here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'county_matching.R'));source(file.path(here,'reconcile_raw_county.R'));source(file.path(here,'fit_county_pilot.R'));prepare_monthly_county(a[1],a[2],a[3],a[4],a[5],a[6])}
