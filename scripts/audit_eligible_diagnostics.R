#!/usr/bin/env Rscript
# Literal category accounting in the frozen eligible annual case universe.
eligible_category_tables <- function(cases,panel,pathogen) {
 end<-if(pathogen=='CRYPTOSPORIDIUM')2017L else 2019L
 needed<-c('year','state','county','fips','pathogen','travelint','cxcidt')
 if(!all(needed%in%names(cases)))stop('Missing case fields')
 cases$pathogen<-county_norm(cases$pathogen);cases<-cases[cases$pathogen==pathogen,,drop=FALSE]
 years<-suppressWarnings(as.numeric(cases$year))
 if(any(!is.finite(years)|years!=floor(years)))stop('Invalid pathogen year')
 cases$year<-as.integer(years);cases<-cases[cases$year>=2004&cases$year<=end,,drop=FALSE]
 if(pathogen=='LISTERIA'&&(!'cste'%in%names(cases)||any(county_norm(cases$cste)!='YES')))stop('Listeria CSTE eligibility not established')
 for(n in c('state','county','travelint','cxcidt'))cases[[n]]<-county_norm(cases[[n]])
 cases$fips<-county_fips(cases$fips)
 selected<-cases$travelint%in%c('NO','UNKNOWN','YES')&cases$cxcidt%in%c('CX+','CIDT+','PARASITIC')&!cases$county%in%c('UNKNOWN','OUT OF STATE','99997')
 flow<-data.frame(stage=c('In established window','Existing filters excluded','Selected'),records=c(nrow(cases),sum(!selected),sum(selected)))
 cases<-cases[selected,,drop=FALSE]
 key<-function(x)paste(x$state,x$fips,x$year,sep='|')
 if(anyDuplicated(key(panel))||any(!key(cases)%in%key(panel)))stop('County-year universe differs')
 observed<-as.integer(table(factor(key(cases),levels=key(panel))))
 if(any(observed!=panel$count))stop('Eligible counts do not match frozen county panel')
 annual<-aggregate(panel[c('count','population')],panel[c('state','year')],sum);names(annual)[3]<-'eligible_records'
 grid<-annual[rep(seq_len(nrow(annual)),each=3),c('state','year')];grid$category<-rep(c('CX+','CIDT+','PARASITIC'),nrow(annual))
 k<-function(x)paste(x$state,x$year,x$category,sep='|')
 cases$category<-cases$cxcidt;grid$records<-as.integer(table(factor(k(cases),levels=k(grid))))
 support<-annual
 lookup<-function(cat)grid$records[match(paste(annual$state,annual$year,cat,sep='|'),k(grid))]
 support$cx_classified<-lookup('CX+');support$cidt_classified<-lookup('CIDT+');support$parasitic_classified<-lookup('PARASITIC')
 support$classification_denominator<-support$cx_classified+support$cidt_classified
 support$cidt_classification_share<-ifelse(support$classification_denominator>0,support$cidt_classified/support$classification_denominator,NA_real_)
 support$interpretation<-ifelse(support$parasitic_classified>0,'PARASITIC_RETAINED_SEPARATELY',ifelse(support$classification_denominator==0,'NO_CLASSIFIED_CASES','DESCRIPTIVE_CLASSIFICATION_ONLY'))
 list(categories=grid,annual=annual,support=support,flow=flow)
}
run_audit <- function(clean,audit,out,pathogen) {
 if(dir.exists(out))stop('Refusing existing output');dir.create(out,recursive=TRUE)
 writeLines('RUNNING',file.path(out,'status.txt'))
 tryCatch({
  files<-c(clean,file.path(audit,'county_panel_INTERNAL.rds'));before<-tools::md5sum(files)
  panel<-validate_panel(audit,expected_production=FALSE)$data
  end<-if(pathogen=='CRYPTOSPORIDIUM')2017L else 2019L
  if(nrow(panel)!=486*(end-2004+1)||!setequal(panel$year,2004:end))stop('Unexpected audited domain')
  checks<-read.csv(file.path(audit,'reports/input_checksums.csv'),stringsAsFactors=FALSE);i<-match(normalizePath(clean),normalizePath(checks$file,mustWork=FALSE))
  if(is.na(i)||checks$md5[i]!=unname(before[1]))stop('Clean data does not match audited source')
  needed<-c('year','state','county','fips','pathogen','travelint','cxcidt');if(pathogen=='LISTERIA')needed<-c(needed,'cste')
  d<-as.data.frame(readr::read_csv(clean,col_types=readr::cols(.default=readr::col_character()),col_select=tidyselect::all_of(needed),num_threads=2,show_col_types=FALSE))
  if(nrow(readr::problems(d)))stop('Case parsing problems')
  result<-eligible_category_tables(d,panel,pathogen)
  for(n in names(result))write.csv(result[[n]],file.path(out,paste0(n,'.csv')),row.names=FALSE,na='')
  write.csv(data.frame(pathogen=pathogen,start_year=2004,end_year=end,county_count=486,state_count=10,selected_records=sum(panel$count),counts_reconciled=TRUE,model_fitted=FALSE,classification_definition='LITERAL_CXCIDT',coverage_certified=FALSE,readiness='REVIEW_REQUIRED'),file.path(out,'readiness.csv'),row.names=FALSE)
  if(!identical(before,tools::md5sum(files)))stop('Inputs changed during audit')
  write.csv(data.frame(file=files,md5=unname(before)),file.path(out,'input_checksums.csv'),row.names=FALSE)
  writeLines('ELIGIBLE_DIAGNOSTICS_COMPLETE',file.path(out,'status.txt'))
 },error=function(e){writeLines(c('FAILED',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=4L)stop('Usage CLEAN AUDIT OUT PATHOGEN');here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'county_matching.R'));source(file.path(here,'fit_county_pilot.R'));run_audit(a[1],a[2],a[3],a[4])}
