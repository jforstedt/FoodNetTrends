source('scripts/audit_extension_diagnostics.R')
x <- data.frame(pathogen='X', year=c(2018,2018,2018,2018,2019,2019), state='CA',
  siteid=c('CA','CA',NA,NA,'CA','CA'), cxcidt=c('CX+','CIDT+',NA,'UNKNOWN','','PARASITIC'),
  caseid=c('PRIVATE_A','PRIVATE_A','PRIVATE_B',NA,'','PRIVATE_C'))
a <- audit_extension_diagnostics(x)
stopifnot(sum(a$categories$records)==6, sum(a$missingness$missing)==1,
  sum(a$missingness$blank)==1, sum(a$missingness$explicit_unknown)==1,
  sum(a$overlap$cx_and_cidt_categories_present)==1,
  a$identifier_candidates$duplicated_nonmissing==1,
  !any(grepl('PRIVATE_',unlist(a))), identical(x$cxcidt[3],NA_character_))
b <- audit_extension_diagnostics(x, x[1:2,])
stopifnot(sum(b$categories$records[b$categories$source=='clean'])==2)
c <- audit_extension_diagnostics(x[c('pathogen','year')])
stopifnot(!c$fields$present[c$fields$field=='cxcidt'], nrow(c$categories)==0)
d <- audit_extension_diagnostics(x[FALSE,])
stopifnot(nrow(d$categories)==0)
y <- x; y$cxcidt <- c(1,2,NA,9,9,3);attr(y$cxcidt,'labels')<-c('CX+'=1,'CIDT+'=2)
e<-audit_extension_diagnostics(y)
stopifnot(any(grepl('CX+=1',e$fields$value_labels,fixed=TRUE)),sum(e$overlap$cx_records)==0)
cat('Diagnostic extension audit tests passed\n')
