#!/usr/bin/env Rscript
# Aggregate literal CX/CIDT labels using the existing audited monthly selection.
classification_monthly_tables <- function(selected, panel) {
  needed <- c('state','fips','year','dtspec','cxcidt')
  if (!all(needed %in% names(selected)) || !inherits(selected$dtspec,'Date')) stop('Missing classification/date fields')
  if (any(!selected$cxcidt %in% c('CX+','CIDT+'))) stop('Unsupported diagnostic category')
  key <- function(x) paste(x$state,x$fips,x$year,sep='|')
  if (anyDuplicated(key(panel)) || any(!key(selected) %in% key(panel))) stop('Classification county domain mismatch')
  if (any(as.numeric(table(factor(key(selected),levels=key(panel)))) != panel$count)) stop('Classification annual counts differ')
  dy <- suppressWarnings(as.integer(format(selected$dtspec,'%Y')))
  dm <- suppressWarnings(as.integer(format(selected$dtspec,'%m')))
  ok <- !is.na(dy) & dy==selected$year & !is.na(dm)
  grid <- panel[rep(seq_len(nrow(panel)),each=12L),c('state','fips','year')]
  grid$month <- rep(1:12,nrow(panel)); rownames(grid)<-NULL
  mk <- function(x) paste(key(x),x$month,sep='|')
  assigned <- selected[ok,,drop=FALSE]; assigned$month <- dm[ok]
  for (category in c('CX+','CIDT+')) {
    n <- if(category=='CX+') 'cx_classified' else 'cidt_classified'
    grid[[n]] <- as.integer(table(factor(mk(assigned[assigned$cxcidt==category,,drop=FALSE]),levels=mk(grid))))
  }
  grid$classification_denominator <- grid$cx_classified+grid$cidt_classified
  grid$cidt_classification_share <- ifelse(grid$classification_denominator>0,grid$cidt_classified/grid$classification_denominator,NA_real_)
  grid$likelihood_eligible <- grid$classification_denominator>0
  grid$target <- 'CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT'
  nums <- c('cx_classified','cidt_classified','classification_denominator')
  site <- aggregate(grid[nums],grid[c('state','year','month')],sum)
  site$cidt_classification_share <- ifelse(site$classification_denominator>0,site$cidt_classified/site$classification_denominator,NA_real_)
  site$likelihood_eligible <- site$classification_denominator>0
  annual <- aggregate(grid[nums],grid[c('state','year')],sum)
  annual$unassigned_records <- as.integer(table(factor(paste(selected$state[!ok],selected$year[!ok]),levels=paste(annual$state,annual$year))))
  issues <- data.frame(state=selected$state,year=selected$year,category=selected$cxcidt,records=1L,unassigned=as.integer(!ok))
  issues <- aggregate(issues[c('records','unassigned')],issues[c('state','year','category')],sum)
  list(county=grid,site=site,annual=annual,date_issues_by_category=issues)
}
prepare_classification_monthly <- function(raw,clean,mapping,audit,out,pathogen,support,scripts) {
  allowed <- c('SALMONELLA','CAMPYLOBACTER','SHIGELLA','STEC','VIBRIO','YERSINIA')
  if (!pathogen %in% allowed) stop('Unsupported classification pathogen')
  before <- tools::md5sum(support); if(anyNA(before)) stop('Missing audited annual classification support')
  env <- new.env(parent=globalenv())
  for(n in c('county_matching.R','reconcile_raw_county.R','fit_county_pilot.R','prepare_monthly_county.R')) sys.source(file.path(scripts,n),envir=env)
  original <- env$monthly_inventory; captured <- NULL
  env$monthly_inventory <- function(selected,panel) {
    result <- original(selected,panel)
    captured <<- classification_monthly_tables(selected,panel)
    result
  }
  env$prepare_monthly_county(raw,clean,mapping,audit,out,pathogen)
  # Base preparation has completed; classification stage must have its own status.
  writeLines('CLASSIFICATION_MONTHLY_VALIDATING',file.path(out,'classification_status.txt'))
  old <- read.csv(support,stringsAsFactors=FALSE)
  ann <- captured$annual; k<-function(x)paste(x$state,x$year)
  i<-match(k(ann),k(old))
  if(anyNA(i)||anyDuplicated(k(old)))stop('Audited annual classification domain mismatch')
  nums<-c('cx_classified','cidt_classified','classification_denominator')
  # Missing dates are retained explicitly, never silently dropped to match totals.
  issues<-captured$date_issues_by_category
  for(n in nums) {
    category<-if(n=='cx_classified')'CX+' else if(n=='cidt_classified')'CIDT+' else c('CX+','CIDT+')
    u<-issues[issues$category %in% category,,drop=FALSE]
    sums<-tapply(u$unassigned,paste(u$state,u$year),sum); missing<-as.numeric(sums[k(ann)]);missing[is.na(missing)]<-0
    if(any(ann[[n]]+missing!=old[[n]][i]))stop('Annual literal category counts differ from audited support')
  }
  selected<-captured$county$year>=2012 & captured$county$year<=2019
  saveRDS(captured$county[selected,],file.path(out,'classification_county_month_INTERNAL.rds'),version=2)
  for(n in c('site','annual','date_issues_by_category'))write.csv(captured[[n]],file.path(out,paste0('classification_',n,'.csv')),row.names=FALSE,na='')
  d<-captured$county[selected,];s<-captured$site[captured$site$year>=2012&captured$site$year<=2019,]
  write.csv(data.frame(pathogen=pathogen,county_month_rows=nrow(d),site_month_rows=nrow(s),county_zero_denominator=sum(d$classification_denominator==0),site_zero_denominator=sum(s$classification_denominator==0),unassigned_2012_2019=sum(ann$unassigned_records[ann$year>=2012&ann$year<=2019]),models_fitted=FALSE,incidence_adjustment=FALSE,readiness='REVIEW_REQUIRED'),file.path(out,'classification_readiness.csv'),row.names=FALSE)
  if(!identical(before,tools::md5sum(support)))stop('Annual support changed')
  write.csv(data.frame(file=support,md5=unname(before)),file.path(out,'classification_support_checksum.csv'),row.names=FALSE)
  writeLines('CLASSIFICATION_MONTHLY_PREPARATION_COMPLETE',file.path(out,'classification_status.txt'))
}
if(sys.nframe()==0L) {
 a<-commandArgs(TRUE);if(length(a)!=7L)stop('Usage RAW CLEAN MAPPING AUDIT OUT PATHOGEN ANNUAL_SUPPORT')
 here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]))
 prepare_classification_monthly(a[1],a[2],a[3],a[4],a[5],a[6],a[7],here)
}
