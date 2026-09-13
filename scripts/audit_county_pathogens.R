#!/usr/bin/env Rscript
# Audit combined pathogen inputs without changing the state analysis or fitting.
pathogen_names <- c('CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA',
                    'SALMONELLA','SHIGELLA','STEC','VIBRIO','YERSINIA')
check_pathogen_rules <- function(x, pathogen) {
  if(pathogen=='LISTERIA') {
    if(!'cste'%in%names(x))stop('CSTE field missing; Listeria eligibility cannot be verified')
    if(any(county_norm(x$cste)!='YES'))stop('Listeria has records without CSTE=YES; review preprocessing')
  }
  TRUE
}
audit_pathogens <- function(clean,bacterial,parasitic,geography,rules_path,out) {
  if(dir.exists(out))stop('Output already exists')
  dir.create(out,recursive=TRUE)
  write <- function(x,p)write.csv(x,p,row.names=FALSE,na='')
  # Character types preserve FIPS and avoid automatic inference on subtype fields.
  wanted<-c('year','state','county','fips','pathogen','travelint','cxcidt','cste',
    'siteid','serotypesummary2','serotypesummary_original','serotypesummary','sero1',
    'stec_class','stec_class_original','dxo157','dx0157')
  x<-readr::read_csv(clean,col_types=readr::cols(.default=readr::col_character()),
    col_select=tidyselect::any_of(wanted),show_col_types=FALSE)
  if(nrow(readr::problems(x)))stop('Parsing errors in audit fields')
  x<-as.data.frame(x);x$pathogen<-county_norm(x$pathogen)
  y<-suppressWarnings(as.numeric(x$year))
  if(any(!is.finite(y)|y!=floor(y)))stop('Invalid cleaned case year')
  x<-x[y>=2004&y<=2019,,drop=FALSE]
  rules<-read_classification_rules(rules_path)
  summary<-list()
  for(pathogen in pathogen_names) {
    dest<-file.path(out,pathogen);dir.create(dest)
    kind<-if(pathogen%in%c('CRYPTOSPORIDIUM','CYCLOSPORA'))'parasitic' else 'bacterial'
    census<-if(kind=='parasitic')parasitic else bacterial
    z<-x[x$pathogen==pathogen,,drop=FALSE]
    rule_error<-tryCatch({check_pathogen_rules(z,pathogen);''},error=function(e)conditionMessage(e))
    # Inventory classification only: do not change combined selection or manufacture subgroups.
    classification_error<-tryCatch({
      c<-classify_cases(z,rules)
      for(field in intersect(c('salmonella_type','stec_group','serotypesummary','serotype_source','cste'),names(c))) {
        v<-county_norm(c[[field]]);v[v=='']<-'<missing>'
        tab<-as.data.frame(table(value=v));tab<-tab[tab$Freq>0,]
        tab$Freq<-ifelse(tab$Freq<5,'<5',as.character(tab$Freq))
        write(tab,file.path(dest,paste0(field,'_inventory.csv')))
      };''
    },error=function(e)conditionMessage(e))
    status<-tryCatch({
      audit_pilot(clean,census,geography,file.path(dest,'reports'),pathogen)
      readLines(file.path(dest,'reports/status.txt'))[1]
    },error=function(e){writeLines(conditionMessage(e),file.path(dest,'error.txt'));'FAIL'})
    if(nzchar(rule_error)||nzchar(classification_error)) {
      status<-'REVIEW_REQUIRED'
      unlink(file.path(dest,'county_panel_INTERNAL.rds'))
    }
    writeLines(c(status,rule_error,classification_error),file.path(dest,'status.txt'))
    summary[[pathogen]]<-data.frame(pathogen=pathogen,subgroup='combined',start_year=2004,
      end_year=2019,census=kind,input_status=status,rule_issue=rule_error,
      classification_issue=classification_error,raw_reconciliation='PENDING',
      model_validation='NOT_PERFORMED')
    write(do.call(rbind,summary),file.path(out,'summary.csv'))
  }
  write(data.frame(file=c(clean,bacterial,parasitic,rules_path),
    md5=unname(tools::md5sum(c(clean,bacterial,parasitic,rules_path)))),file.path(out,'input_checksums.csv'))
  cat('\n');print(do.call(rbind,summary),row.names=FALSE)
  cat('AUDIT COLLECTION COMPLETE. Input PASS is not statistical validation. No models fitted.\n')
}
if(sys.nframe()==0L) {
  a<-commandArgs(TRUE);if(length(a)!=6)stop('Expected clean, bacterial, parasitic, geography, classification rules, output')
  here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
  for(f in c('county_matching.R','audit_county_pilot.R','classification.R'))source(file.path(here,f))
  audit_pathogens(a[1],a[2],a[3],a[4],a[5],a[6])
}
