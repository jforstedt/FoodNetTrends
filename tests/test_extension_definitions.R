source('scripts/audit_extension_definitions.R')
x<-data.frame(pathogen='TEST',state='AA',year=c(2016,2016,2016),month=c(1,3,NA),dtspec=as.Date(c('2016-01-01','2016-02-15',NA)),dtonset=as.Date(c('2015-12-30','2016-02-18',NA)),cxcidt=c('CX+','CIDT+',NA),pcrclinic=c('Y','UNKNOWN',NA),labname=c('LAB A',' lab  a ',NA),personid=c('secret','secret',NA))
r<-audit_extension_definitions(x)
stopifnot(r$date_checks$month_disagreement==1,r$date_checks$spec_missing==1,r$laboratory_consistency$distinct_case_space_normalized_names==1,r$identifier_support$duplicate_values==1)
stopifnot(!any(grepl('secret',unlist(lapply(r,as.character)))))
cat('PASS targeted dates, raw codes, normalized lab counts and nonexported identifiers\n')

x$labname[3]<-' unknown ';x$personid[3]<-' unk ';r<-audit_extension_definitions(x)
stopifnot(r$laboratory_consistency$known_name_records==2,r$identifier_support$nonmissing==2)
