#!/usr/bin/env Rscript
# Diagnostic aggregate reconciliation only. Never run preprocessing or fitting.
aggregate_keys <- function(d,keys,name) {
  if(!nrow(d)){z<-d[FALSE,keys,drop=FALSE];z[[name]]<-integer();return(z)}
  z<-aggregate(rep(1L,nrow(d)),d[keys],sum);names(z)[ncol(z)]<-name;z
}
reconcile_counts <- function(raw,clean,keys) {
  z<-merge(aggregate_keys(raw,keys,'raw_records'),aggregate_keys(clean,keys,'clean_records'),by=keys,all=TRUE)
  z$raw_records[is.na(z$raw_records)]<-0L;z$clean_records[is.na(z$clean_records)]<-0L
  z$difference<-z$raw_records-z$clean_records;z
}
classify_removals <- function(d) {
  # Test known default hypotheses, not a claim about historical rule provenance.
  ifelse(d$county=='OUT OF STATE','county_OUT_OF_STATE',
    ifelse(d$county=='UNKNOWN','county_UNKNOWN',ifelse(d$siteid=='COEX'&d$year<2023,'site_COEX_pre2023','retained_candidate')))
}
raw_review <- function(rawpath,cleanpath,reportpath,audit,out) {
  if(dir.exists(out))stop('Refusing existing report directory')
  dir.create(out,recursive=TRUE)
  w<-function(d,n)write.csv(d,file.path(out,n),row.names=FALSE,na='')
  writeLines('RUNNING',file.path(out,'status.txt'))
  tryCatch({
    files<-c(rawpath,cleanpath,reportpath,file.path(audit,'county_panel_INTERNAL.rds'))
    before<-tools::md5sum(files);if(anyNA(before))stop('Missing input')
    checks<-read.csv(file.path(audit,'reports/input_checksums.csv'),stringsAsFactors=FALSE)
    j<-match(normalizePath(cleanpath),normalizePath(checks$file,mustWork=FALSE))
    if(is.na(j)||checks$md5[j]!=unname(before[2]))stop('Clean checksum differs from audit')
    required<-c('year','state','county','fips','pathogen','travelint','cxcidt','siteid')
    raw<-as.data.frame(haven::read_sas(rawpath));names(raw)<-tolower(names(raw))
    if(!all(required%in%names(raw)))stop('Missing raw review fields')
    raw<-raw[required]
    clean<-as.data.frame(readr::read_csv(cleanpath,col_types=readr::cols(.default=readr::col_character()),
      col_select=tidyselect::all_of(required),show_col_types=FALSE,num_threads=4))
    if(nrow(readr::problems(clean)))stop('Clean CSV parsing problems')
    mapping<-read.csv(reportpath,stringsAsFactors=FALSE)
    if(!all(c('original','standardized')%in%names(mapping)))stop('Unrecognized original preprocessing report')
    norm<-function(z){z<-toupper(trimws(as.character(z)));z[is.na(z)]<-'';z}
    aliases<-unique(as.character(mapping$original[norm(mapping$standardized)=='SALMONELLA']))
    if(!length(aliases))stop('No Salmonella mappings in original report')
    w(mapping[mapping$original%in%aliases,],'recorded_salmonella_mappings.csv')
    raw$year<-suppressWarnings(as.integer(raw$year));clean$year<-suppressWarnings(as.integer(clean$year))
    if(anyNA(raw$year[as.character(raw$pathogen)%in%aliases])||anyNA(clean$year[norm(clean$pathogen)=='SALMONELLA']))stop('Invalid relevant year')
    period<-!is.na(raw$year)&raw$year>=2004&raw$year<=2019
    inventory<-raw[period,c('pathogen'),drop=FALSE];inventory$pathogen<-as.character(inventory$pathogen);inventory$pathogen[is.na(inventory$pathogen)]<-'<MISSING>'
    inventory<-aggregate_keys(inventory,'pathogen','records');inventory$mapped_to_salmonella<-inventory$pathogen%in%aliases
    inventory$present_in_recorded_mapping<-inventory$pathogen%in%mapping$original
    w(inventory,'raw_pathogen_inventory.csv')
    raw<-raw[period&as.character(raw$pathogen)%in%aliases,,drop=FALSE]
    clean<-clean[!is.na(clean$year)&clean$year>=2004&clean$year<=2019&norm(clean$pathogen)=='SALMONELLA',,drop=FALSE]
    # Preserve source labels for default-rule matching; normalize only reconciliation keys.
    raw$county<-as.character(raw$county);raw$county[is.na(raw$county)]<-''
    raw$siteid<-as.character(raw$siteid);raw$siteid[is.na(raw$siteid)]<-''
    raw$removal_hypothesis<-classify_removals(raw)
    for(k in c('state','county','travelint','cxcidt','siteid')){raw[[k]]<-norm(raw[[k]]);clean[[k]]<-norm(clean[[k]])}
    raw$fips<-county_fips(raw$fips);clean$fips<-county_fips(clean$fips)
    nodes<-read.csv(file.path(audit,'reports/graph_nodes.csv'),colClasses='character')
    raw$geography<-ifelse(raw$fips%in%nodes$fips,'in_pilot_fips',ifelse(raw$fips=='','missing_fips','other_or_invalid_fips'))
    w(aggregate_keys(raw,c('state','year','removal_hypothesis','geography'),'records'),'raw_removal_hypotheses_INTERNAL.csv')
    keys<-c('year','state','fips','travelint','cxcidt','siteid')
    allcmp<-reconcile_counts(raw,clean,keys);w(allcmp,'all_raw_vs_clean_INTERNAL.csv')
    candidate<-raw[raw$removal_hypothesis=='retained_candidate',,drop=FALSE]
    cmp<-reconcile_counts(candidate,clean,keys);w(cmp,'default_hypothesis_reconciliation_INTERNAL.csv')
    w(cmp[cmp$difference!=0,],'unexplained_differences_INTERNAL.csv')
    targets<-c('41023','35033','41063','47083','13141','27065','41015','47117','47129','35003','27117','47127','13159','35028','47161')
    w(aggregate_keys(raw[raw$fips%in%targets,],c('year','state','fips','county','siteid','removal_hypothesis'),'records'),'target_raw_geographic_tuples_INTERNAL.csv')
    # State-level unknown records remain state-level; never redistribute to counties.
    panel<-readRDS(files[4]);selected<-clean[clean$travelint%in%c('NO','UNKNOWN','YES')&clean$cxcidt%in%c('CIDT+','CX+','PARASITIC')&!clean$county%in%c('UNKNOWN','OUT OF STATE','99997'),]
    counts<-aggregate_keys(selected,c('year','fips'),'clean_records')
    z<-merge(panel[c('year','fips','count')],counts,by=c('year','fips'),all=TRUE);z$clean_records[is.na(z$clean_records)]<-0L
    if(nrow(z)!=7776||anyNA(z$count)||any(z$count!=z$clean_records)||sum(z$count)!=122024)stop('Clean-to-panel reconciliation failed')
    if(!identical(before,tools::md5sum(files)))stop('Inputs changed during review')
    w(data.frame(file=files,md5=unname(before),unchanged=TRUE),'input_checksums.csv')
    w(data.frame(raw_mapped_records=nrow(raw),clean_records=nrow(clean),candidate_retained=nrow(candidate),
      unexplained_cells=sum(cmp$difference!=0),unexplained_absolute_records=sum(abs(cmp$difference)),panel_reconciled=TRUE),'summary.csv')
    writeLines(c(if(all(cmp$difference==0))'RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH' else 'RAW_CLEAN_REVIEW_REQUIRED',
      'Diagnostic completed without refitting or preprocessing; source files unchanged.',
      'Scope uses Salmonella aliases from the recorded preprocessing mapping, not new fuzzy matching.',
      'Removal labels test known defaults; historical rule use is NOT established by matching counts.',
      'County names are exported separately; comparison keys use state/FIPS/year/travel/diagnosis/site.',
      'External reporting completeness remains unverified.'),file.path(out,'status.txt'))
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=5L)stop('Usage: RAW CLEAN PREPROCESSING_REPORT AUDIT REPORT_DIR');here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'county_matching.R'));raw_review(a[1],a[2],a[3],a[4],a[5])}
