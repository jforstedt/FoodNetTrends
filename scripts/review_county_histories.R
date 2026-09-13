#!/usr/bin/env Rscript
# Read-only county history review. No model fitting or record-level exports.
source_history <- function(x,panel,nodes) {
  norm<-function(z){z<-toupper(trimws(as.character(z)));z[is.na(z)]<-'';z}
  x$year<-suppressWarnings(as.integer(x$year));x$pathogen<-norm(x$pathogen)
  if(anyNA(x$year[x$pathogen=='SALMONELLA']))stop('Invalid Salmonella year')
  x<-x[x$pathogen=='SALMONELLA'&!is.na(x$year)&x$year>=2004&x$year<=2019,,drop=FALSE]
  for(k in c('state','county','travelint','cxcidt'))x[[k]]<-norm(x[[k]])
  x$fips<-county_fips(x$fips)
  selected<-x$travelint%in%c('NO','UNKNOWN','YES')&x$cxcidt%in%c('CIDT+','CX+','PARASITIC')&!x$county%in%c('OUT OF STATE','UNKNOWN','99997')
  key<-function(d)paste(d$fips,d$year,sep='|')
  counts<-table(factor(key(x[selected,,drop=FALSE]),levels=key(panel)))
  if(any(!key(x[selected,,drop=FALSE])%in%key(panel))||any(as.integer(counts)!=panel$count))stop('Selected clean records do not reproduce fitted county counts')
  good<-x$fips%in%nodes$fips
  if(any(x$state[selected]!=nodes$state[match(x$fips[selected],nodes$fips)]))stop('Selected state/FIPS mismatch')
  # Classifications are disjoint; missing geography cannot be assigned to a county.
  reason<-ifelse(selected,'selected',ifelse(!x$travelint%in%c('NO','UNKNOWN','YES'),'excluded_travel',
     ifelse(!x$cxcidt%in%c('CIDT+','CX+','PARASITIC'),'excluded_diagnosis','excluded_county_label')))
  mapping<-ifelse(good,'in_pilot_fips',ifelse(x$fips=='','missing_fips','other_or_invalid_fips'))
  flow<-aggregate(rep(1L,nrow(x)),list(state=x$state,year=x$year,filter_status=reason,geography=mapping),sum);names(flow)[5]<-'records'
  list(data=x,selected=selected,flow=flow)
}

review_histories <- function(audit,fitroot,clean,out) {
  if(dir.exists(out))stop('Refusing existing output directory')
  dir.create(out,recursive=TRUE);writeLines('RUNNING',file.path(out,'status.txt'))
  write<-function(x,name)write.csv(x,file.path(out,name),row.names=FALSE,na='')
  tryCatch({
    checks<-read.csv(file.path(audit,'reports/input_checksums.csv'),stringsAsFactors=FALSE)
    ix<-match(normalizePath(clean),normalizePath(checks$file,mustWork=FALSE))
    if(is.na(ix)||unname(tools::md5sum(clean))!=checks$md5[ix])stop('Clean input differs from audited source')
    panelpath<-file.path(audit,'county_panel_INTERNAL.rds');panel<-readRDS(panelpath)
    nodes<-read.csv(file.path(audit,'reports/graph_nodes.csv'),colClasses='character')
    edges<-read.csv(file.path(audit,'reports/graph_edges.csv'),colClasses='character')
    paths<-c(clean,panelpath,file.path(fitroot,c('spatial','iid'),'reports/county_incidence_INTERNAL.csv'))
    before<-tools::md5sum(paths)
    if(anyNA(before))stop('Missing input')
    if(readLines(file.path(audit,'reports/status.txt'))[1]!='INPUT_AUDIT_PASS')stop('Audit has not passed')
    if(nrow(panel)!=7776||sum(panel$count)!=122024||anyDuplicated(paste(panel$fips,panel$year)))stop('Unexpected pilot panel')
    for(v in c('spatial','iid')) {
      old<-file.path(fitroot,v,'reports')
      if(readLines(file.path(old,'status.txt'))[1]!='EXPLORATORY_FIT_COMPLETE')stop('Incomplete fit')
      chk<-read.csv(file.path(old,'panel_checksum.csv'))
      if(nrow(chk)!=1||chk$md5!=unname(before[2]))stop('Panel checksum mismatch')
    }
    required<-c('year','state','county','fips','pathogen','travelint','cxcidt')
    x<-readr::read_csv(clean,col_types=readr::cols(.default=readr::col_character()),
      col_select=tidyselect::all_of(required),show_col_types=FALSE,num_threads=4)
    if(nrow(readr::problems(x)))stop('Parsing issues in review fields')
    src<-source_history(as.data.frame(x),panel,nodes);rm(x)
    write(src$flow,'state_year_filter_geography_INTERNAL.csv')
    # Union of the largest county excess-zero contributors from both reviewed models.
    targets<-c('41023','35033','41063','47083','13141','27065','41015','47117','47129','35003','27117','47127','13159','35028','47161')
    if(any(!targets%in%nodes$fips))stop('Target county absent from audited graph')
    pairs<-unique(rbind(data.frame(target=edges$fips_a,neighbor=edges$fips_b),data.frame(target=edges$fips_b,neighbor=edges$fips_a)))
    pairs<-pairs[pairs$target%in%targets,];write(pairs,'target_neighbors.csv')
    wanted<-union(targets,pairs$neighbor)
    hist<-panel[panel$fips%in%wanted,c('fips','state','year','population','count')]
    hist$county<-nodes$county[match(hist$fips,nodes$fips)]
    hist$role<-ifelse(hist$fips%in%targets,'target','neighbor')
    hist$observed_rate_per100k<-hist$count/hist$population*1e5
    key<-function(d)paste(d$fips,d$year,sep='|')
    for(v in c('spatial','iid')) {
      rates<-read.csv(file.path(fitroot,v,'reports/county_incidence_INTERNAL.csv'),colClasses=c(fips='character'))
      if(anyDuplicated(key(rates))||!setequal(key(rates),key(panel)))stop('Fitted rate keys differ from panel')
      j<-match(key(hist),key(rates))
      for(k in c('mean','median','lower','upper'))hist[[paste(v,k,sep='_')]]<-rates[[k]][j]
      hist[[paste0(v,'_expected_count_mean')]]<-rates$mean[j]*hist$population/1e5
    }
    hist<-hist[order(hist$fips,hist$year),];write(hist,'county_year_history_INTERNAL.csv')
    # Names/FIPS and filter categories only: aggregate, never record-level rows.
    xx<-src$data[src$data$fips%in%wanted,,drop=FALSE]
    if(nrow(xx)) {
      tuple<-aggregate(rep(1L,nrow(xx)),xx[c('state','year','fips','county','travelint','cxcidt')],sum)
      names(tuple)[7]<-'records';write(tuple,'county_source_categories_INTERNAL.csv')
    }
    summary<-do.call(rbind,lapply(targets,function(f){
      z<-hist[hist$fips==f,];total<-sum(z$count)
      data.frame(fips=f,state=z$state[1],county=z$county[1],zero_years=sum(z$count==0),total_cases=total,
        largest_year=z$year[which.max(z$count)],largest_year_cases=max(z$count),
        largest_year_share=if(total>0)max(z$count)/total else NA_real_,
        reporting_completeness='NOT_ESTABLISHED_BY_CASE_RECORDS')
    }));write(summary,'target_summary_INTERNAL.csv')
    pdf(file.path(out,'county_histories_INTERNAL.pdf'),width=11,height=8)
    for(f in targets) {
      z<-hist[hist$fips==f,];nb<-hist[hist$fips%in%pairs$neighbor[pairs$target==f],]
      par(mfrow=c(2,1),mar=c(4,4,3,1))
      plot(z$year,z$count,type='h',lwd=3,ylim=range(0,z$count,z$spatial_expected_count_mean,z$iid_expected_count_mean),
        xlab='Year',ylab='Cases / expected cases',main=paste(z$county[1],z$state[1],f))
      lines(z$year,z$spatial_expected_count_mean,col='blue',lwd=2);lines(z$year,z$iid_expected_count_mean,col='orange',lwd=2)
      legend('topright',c('Observed','Spatial mean','IID mean'),col=c('black','blue','orange'),lty=1,bty='n')
      n<-aggregate(nb[c('count','population')],list(year=nb$year),sum)
      plot(z$year,z$observed_rate_per100k,type='b',ylim=range(0,z$observed_rate_per100k,n$count/n$population*1e5),
        xlab='Year',ylab='Observed incidence /100,000',main='Target and pooled graph neighbors (descriptive)')
      lines(n$year,n$count/n$population*1e5,col='gray40',lwd=2)
      legend('topright',c('Target','Pooled neighbors'),col=c('black','gray40'),lty=1,bty='n')
    };dev.off()
    if(!identical(before,tools::md5sum(paths)))stop('Inputs changed during review')
    write(data.frame(file=paths,md5=unname(before),unchanged=TRUE),'input_checksums.csv')
    writeLines(c('COUNTY_HISTORY_REVIEW_COMPLETE','Selected clean records reproduce all 7776 fitted county/year counts.',
      'No refitting; source inputs unchanged. Reports contain internal county aggregates.',
      'No records is not independent proof of complete reporting with zero cases.',
      'Unknown or invalid county geography is summarized by state/year, never assigned to targets.',
      'Reporting completeness requires external surveillance/participation documentation.'),file.path(out,'status.txt'))
  },error=function(e){writeLines(c('FAIL',conditionMessage(e)),file.path(out,'status.txt'));stop(e)})
}
if(sys.nframe()==0L){a<-commandArgs(TRUE);if(length(a)!=4L)stop('Usage: AUDIT FIT_ROOT CLEAN REPORT_DIR');here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'county_matching.R'));review_histories(a[1],a[2],a[3],a[4])}
