#!/usr/bin/env Rscript
args <- commandArgs(TRUE)
if(length(args)!=2)stop('Usage: prepare_county_inputs.R DATA_DIRECTORY OUTPUT_DIRECTORY')
data_dir <- args[1];out <- args[2]
if(dir.exists(out))stop('Output directory already exists; refusing overwrite')
dir.create(out,recursive=TRUE)
script_arg <- grep('^--file=',commandArgs(),value=TRUE)
source(file.path(dirname(sub('^--file=','',script_arg[1])),'county_matching.R'))
if(!requireNamespace('haven',quietly=TRUE)||!requireNamespace('tidyselect',quietly=TRUE))stop('Run inside foodnet.sif')
read_fields <- function(path,wanted) {
  h <- haven::read_sas(path,n_max=0)
  selected <- names(h)[tolower(names(h))%in%wanted]
  x <- haven::read_sas(path,col_select=tidyselect::all_of(selected));names(x)<-tolower(names(x));as.data.frame(x)
}
report <- file.path(out,'county_readiness.txt')
sink(report,split=TRUE)
cat('COUNTY GEOGRAPHY PREPARATION — CANDIDATES ONLY\n')
cat('No data modified, no cases reassigned, no models fitted, no county-year zeros generated.\n')
cat('All coverage is unverified. Exact-name matches require review. Connecticut 2020+ requires boundary reconciliation.\n')
cat('Inputs:',data_dir,'\n')
paths <- file.path(data_dir,c('mmwr9625.sas7bdat','cen9625.sas7bdat','cen9625_para.sas7bdat'))
stopifnot(all(file.exists(paths)))
info <- file.info(paths)
write.csv(data.frame(file=basename(paths),bytes=info$size,modified=as.character(info$mtime)),file.path(out,'input_inventory.csv'),row.names=FALSE)
x <- read_fields(paths[1],c('year','state','county','fips','pathogen','siteid'))
stopifnot(all(c('year','state','county','fips','pathogen')%in%names(x)))
x$pathogen <- county_norm(x$pathogen)
x$population_class <- ifelse(x$pathogen%in%c('CRYPTOSPORIDIUM','CYCLOSPORA'),'parasitic',
                     ifelse(x$pathogen%in%c('CAMPYLOBACTER','LISTERIA','SALMONELLA','SHIGELLA','STEC','VIBRIO','YERSINIA'),'bacterial','unsupported'))
cat('Raw records:',nrow(x),' Unsupported pathogen labels:',sum(x$population_class=='unsupported'),'\n')
# Aggregate before matching: no case IDs, dates or individual records written.
cols <- intersect(c('year','state','county','fips','siteid','population_class'),names(x))
g <- x[cols];g[]<-lapply(g,function(v){v<-as.character(v);v[is.na(v)]<-'';v})
g <- aggregate(rep(1L,nrow(g)),g,sum);names(g)[ncol(g)] <- 'records';g$year <- as.integer(g$year)
rm(x);gc()
all_results <- list()
for(kind in c('bacterial','parasitic')) {
  pop <- read_fields(paths[if(kind=='bacterial')2 else 3],c('year','state','county','stfip','cofip','entryyear','population'))
  stopifnot(all(c('year','state','county','stfip','cofip','population')%in%names(pop)))
  pop$fips <- ifelse(is.na(pop$stfip)|is.na(pop$cofip),'',sprintf('%02d%03d',as.integer(pop$stfip),as.integer(pop$cofip)))
  matched <- match_county_candidates(g[g$population_class==kind,],pop)
  all_results[[kind]] <- matched
  # Population-only inventory doubles as a coverage-review template. No eligibility inferred.
  inventory <- pop[intersect(c('year','state','county','fips','entryyear','population'),names(pop))]
  inventory$coverage_status <- 'not_verified';inventory$coverage_evidence <- ''
  inventory$geography_vintage <- '';inventory$review_note <- ''
  write.csv(inventory,file.path(out,paste0(kind,'_county_year_coverage_review.csv')),row.names=FALSE,na='')
  cat(kind,': population years ',min(pop$year,na.rm=TRUE),'-',max(pop$year,na.rm=TRUE),
      '; missing FIPS ',sum(pop$fips==''),'; duplicate year/FIPS rows ',sum(duplicated(paste(pop$year,pop$fips))), '\n',sep='')
}
r <- do.call(rbind,all_results)
summary <- aggregate(r$records,r[c('population_class','year','state','match_status','geography_review')],sum)
names(summary)[ncol(summary)] <- 'records'
summary$records <- ifelse(summary$records<5,'<5',as.character(summary$records))
write.csv(summary,file.path(out,'match_summary.csv'),row.names=FALSE)
# Geographic tuples, with counts suppressed below five, are for internal review.
r$records <- ifelse(r$records<5,'<5',as.character(r$records))
write.csv(r,file.path(out,'geographic_candidates_INTERNAL.csv'),row.names=FALSE,na='')
ct <- r[r$state=='CT',]
write.csv(ct,file.path(out,'connecticut_exceptions_INTERNAL.csv'),row.names=FALSE,na='')
cat('Geographic candidate tuples:',nrow(r),'\n')
print(as.data.frame(table(r$match_status)),row.names=FALSE)
cat('Counts in the table above are geographic tuples, not cases. See match_summary.csv for case counts.\n')
cat('NO MODEL-READY COUNTY DATASET CREATED: coverage evidence and geographic review are required.\n')
cat('Internal geographic tables are not certified public-release outputs.\n')
cat('PREPARATION COMPLETE\n')
sink()
