#!/usr/bin/env Rscript
# Read-only preparation of the Salmonella 2004–2019 pilot. No model fitting.
audit_pilot <- function(clean, census_path, geography, out) {
  if(dir.exists(out))stop('Output directory already exists')
  dir.create(out,recursive=TRUE)
  writeLines('RUNNING',file.path(out,'status.txt'))
  write <- function(x,name)write.csv(x,file.path(out,name),row.names=FALSE,na='')
  norm <- function(x) {x<-toupper(trimws(as.character(x)));x[is.na(x)]<-'';x}
  required <- c('year','state','county','fips','pathogen','travelint','cxcidt')
  x <- readr::read_csv(clean,col_types=readr::cols(.default=readr::col_character()),
                       col_select=tidyselect::all_of(required),show_col_types=FALSE)
  if(nrow(readr::problems(x)))stop('CSV parsing issues in pilot fields')
  x <- as.data.frame(x); x$pathogen<-norm(x$pathogen)
  x <- x[x$pathogen=='SALMONELLA',]
  y<-suppressWarnings(as.integer(x$year))
  if(anyNA(y))stop('Salmonella records with invalid year')
  x<-x[y>=2004&y<=2019,];x$year<-as.integer(x$year)
  x$state<-norm(x$state); x$county<-norm(x$county)
  categories<-as.data.frame(table(travel=norm(x$travelint),diagnosis=norm(x$cxcidt)))
  categories<-categories[categories$Freq>0,];categories$Freq<-ifelse(categories$Freq<5,'<5',as.character(categories$Freq))
  write(categories,'travel_diagnosis_inventory.csv')
  selected <- norm(x$travelint)%in%c('NO','UNKNOWN','YES') & norm(x$cxcidt)%in%c('CIDT+','CX+','PARASITIC') &
    !x$county%in%c('OUT OF STATE','UNKNOWN','99997')
  flow<-data.frame(stage=c('Salmonella 2004-2019','Excluded by existing travel/CIDT/county filters','Selected'),
                   records=c(nrow(x),sum(!selected),sum(selected)))
  write(flow,'case_flow.csv');x<-x[selected,]
  if(!nrow(x))stop('No selected pilot cases')
  p<-as.data.frame(haven::read_sas(census_path));names(p)<-tolower(names(p))
  stopifnot(all(c('year','state','county','population','stfip','cofip')%in%names(p)))
  p<-p[p$year>=2004&p$year<=2019,];p$state<-norm(p$state)
  p$fips<-ifelse(is.na(p$stfip)|is.na(p$cofip),'',sprintf('%02d%03d',as.integer(p$stfip),as.integer(p$cofip)))
  cty<-read.csv(file.path(geography,'counties.csv'),colClasses='character')
  edge<-read.csv(file.path(geography,'edges.csv'),colClasses='character')
  if(anyDuplicated(cty$fips)||any(!edge$fips_a%in%cty$fips)|any(!edge$fips_b%in%cty$fips))stop('Invalid graph identifiers')
  if(any(edge$fips_a>=edge$fips_b)||anyDuplicated(edge))stop('Invalid/duplicate edges')
  grid<-merge(cty,data.frame(year=2004:2019),by=NULL)
  key<-function(d)paste(d$year,d$fips,sep='|')
  ix<-match(key(grid),key(p));dup<-duplicated(key(p))|duplicated(key(p),fromLast=TRUE)
  grid$population<-p$population[ix]
  grid$population_status<-ifelse(is.na(ix),'missing',ifelse(dup[ix],'duplicate',
    ifelse(p$state[ix]!=grid$state,'state_mismatch',ifelse(!is.finite(grid$population)|grid$population<=0,'nonpositive','ok'))))
  write(grid,'population_audit.csv')
  # Match aggregate geographic tuples; no identifiers or individual rows exported.
  g<-x[c('year','state','county','fips')];g[]<-lapply(g,function(v){v<-as.character(v);v[is.na(v)]<-'';v})
  g<-aggregate(rep(1L,nrow(g)),g,sum);names(g)[5]<-'records';g$year<-as.integer(g$year)
  r<-match_county_candidates(g,p)
  r$in_pilot_footprint<-r$candidate_fips%in%cty$fips
  ok<-r$match_status=='direct_fips_candidate' & r$in_pilot_footprint
  issues<-r[!ok,];issues$records<-ifelse(issues$records<5,'<5',as.character(issues$records))
  write(issues,'case_exceptions_INTERNAL.csv')
  totals<-aggregate(r$records,r[c('year','state')],sum);names(totals)[3]<-'selected_cases'
  matched<-aggregate(ifelse(ok,r$records,0),r[c('year','state')],sum);names(matched)[3]<-'direct_matched_cases'
  write(merge(totals,matched),'state_year_reconciliation.csv')
  # Report graph structure, preserving islands and disconnected components.
  adj<-lapply(cty$fips,function(f)unique(c(edge$fips_b[edge$fips_a==f],edge$fips_a[edge$fips_b==f])))
  names(adj)<-cty$fips;component<-setNames(rep(0L,nrow(cty)),cty$fips);k<-0L
  for(f in cty$fips)if(component[f]==0L){k<-k+1L;todo<-f
    while(length(todo)){v<-todo[1];todo<-todo[-1];if(component[v]!=0L)next;component[v]<-k;todo<-c(todo,adj[[v]][component[adj[[v]]]==0L])}}
  cty$component<-unname(component[cty$fips]);cty$neighbors<-lengths(adj)
  write(cty,'graph_nodes.csv');write(edge,'graph_edges.csv')
  write(data.frame(file=c(clean,census_path),md5=unname(tools::md5sum(c(clean,census_path)))), 'input_checksums.csv')
  ready<-all(ok)&all(grid$population_status=='ok')
  if(ready){
    counts<-aggregate(r$records,list(year=r$year,fips=r$candidate_fips),sum);names(counts)[3]<-'count'
    grid<-merge(grid,counts,by=c('year','fips'),all.x=TRUE);grid$count[is.na(grid$count)]<-0L
    stopifnot(sum(grid$count)==sum(flow$records[flow$stage=='Selected']))
    # Exact counts remain on HPC and are deliberately excluded from the report archive.
    saveRDS(grid,file.path(dirname(out),'county_panel_INTERNAL.rds'))
  }
  writeLines(c(if(ready)'INPUT_AUDIT_PASS' else 'REVIEW_REQUIRED',
    paste('Selected cases:',sum(r$records)),paste('Unresolved geographic tuples:',sum(!ok)),
    paste('Population rows needing review:',sum(grid$population_status!='ok')),
    paste('Graph components:',k),paste('Isolated counties:',sum(cty$neighbors==0)),
    'No INLA fit performed. Candidate graph and model specification require review.'),file.path(out,'status.txt'))
  cat(paste(readLines(file.path(out,'status.txt')),collapse='\n'),'\n')
}
if(sys.nframe()==0L){
 args<-commandArgs(TRUE);if(length(args)!=4)stop('Usage: audit_county_pilot.R CLEAN_CSV CENSUS_SAS GEOGRAPHY_DIR REPORTDIR')
 here<-dirname(sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1]));source(file.path(here,'county_matching.R'))
 tryCatch(audit_pilot(args[1],args[2],args[3],args[4]),error=function(e){
   if(dir.exists(args[4]))writeLines(c('FAIL',conditionMessage(e)),file.path(args[4],'status.txt'));stop(e)})
}
