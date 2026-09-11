#!/usr/bin/env Rscript
# Read-only input audit. Writes aggregate diagnostics, never case records.
args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args)) args[1] else '/scicomp/groups-pure/EDEB/foodnet/trends/data'
report <- if (length(args) >= 2) args[2] else paste0('foodnet_input_audit_', format(Sys.time(), '%Y%m%d_%H%M%S'), '.txt')
if (file.exists(report)) stop('Report already exists; choose a new filename.')
if (!dir.exists(data_dir)) stop('Data directory does not exist.')
if (!requireNamespace('haven', quietly=TRUE) || !requireNamespace('tidyselect', quietly=TRUE)) stop('Run inside foodnet.sif (haven and tidyselect required).')
con <- file(report, 'wt')
sink(con)
options(width=180, max.print=100000)
section <- function(title) cat('\n\n========== ', title, ' ==========\n', sep='')
show <- function(x) print(as.data.frame(x), row.names=FALSE)
norm <- function(x) { x <- toupper(trimws(as.character(x))); x[is.na(x)] <- ''; x }
county_key <- function(x) gsub('[^A-Z0-9]', '', norm(x))
read_selected <- function(path, wanted) {
  h <- haven::read_sas(path, n_max=0)
  keep <- names(h)[tolower(names(h)) %in% wanted]
  x <- haven::read_sas(path, col_select=tidyselect::all_of(keep))
  names(x) <- tolower(names(x)); as.data.frame(x)
}
counts <- function(x, cols, suppress=FALSE) {
  if (!nrow(x) || !all(cols %in% names(x))) return(invisible(NULL))
  z <- x[cols]; z[] <- lapply(z, function(v) { v <- as.character(v); v[is.na(v)] <- '<missing>'; v })
  z$n <- 1L
  out <- aggregate(z$n, z[cols], sum); names(out)[ncol(out)] <- 'records'
  if (suppress) out$records <- ifelse(out$records < 5, '<5', as.character(out$records))
  show(out)
}
tryCatch({
section('Scope and interpretation')
cat('Generated:', format(Sys.time(), tz='UTC'), 'UTC\nR:', R.version.string, '\n')
cat('Directory:', data_dir, '\nNo source files are modified. No individual case records, IDs, dates, or free text are printed.\n')
cat('Case subgroup counts below five are displayed as <5. This is a diagnostic report, not certified public-release output.\n')
cat('Case checks use raw input before pipeline exclusions. Missing populations may represent inactive geography; they are not automatically errors.\n')
cat('Name matching is diagnostic only, not an approved geographic conversion. No populations are imputed.\n')
section('Input inventory')
files <- list.files(data_dir, pattern='^(cen|mmwr).*\\.(sas7bdat|csv)$', full.names=TRUE)
i <- file.info(files)
show(data.frame(file=basename(files), bytes=i$size, modified=as.character(i$mtime)))

census_files <- list.files(data_dir, pattern='^cen9625.*[.]sas7bdat$', full.names=TRUE)
censuses <- list()
for (path in census_files) tryCatch({
  section(paste('CENSUS', basename(path)))
  h <- haven::read_sas(path, n_max=0)
  show(data.frame(column=names(h), type=vapply(h, function(v) paste(class(v),collapse='/'), ''), label=vapply(h,function(v) { a <- attr(v,'label'); if(is.null(a)) '' else as.character(a) }, '')))
  # The demographic file has tens of millions of overlapping category rows.
  if (grepl('demo', basename(path), ignore.case=TRUE)) {
    x <- read_selected(path, 'year'); counts(x,'year')
    cat('Demographic population sums intentionally omitted: category definitions must be established before aggregation.\n')
    next
  }
  x <- read_selected(path,c('year','state','county','stfip','cofip','entryyear','population'))
  if (!all(c('year','state','stfip','cofip','population') %in% names(x))) stop('Required census columns absent')
  x$fips <- ifelse(is.na(x$stfip)|is.na(x$cofip), NA_character_, sprintf('%02d%03d',as.integer(x$stfip),as.integer(x$cofip)))
  x$key <- paste(x$year,x$fips,sep='|')
  cat('Rows:',nrow(x),' Duplicate year/FIPS keys:',sum(duplicated(x$key)),' Missing FIPS:',sum(is.na(x$fips)), '\n')
  cat('Missing populations:',sum(is.na(x$population)), ' Zero:',sum(x$population==0,na.rm=TRUE),' Negative:',sum(x$population<0,na.rm=TRUE),'\n')
  x$missing_pop <- as.integer(is.na(x$population)); x$zero_pop <- as.integer(!is.na(x$population)&x$population==0); x$rows <- 1L
  s <- aggregate(x[c('rows','missing_pop','zero_pop')],x[c('year','state')],sum)
  p <- aggregate(list(sum_nonmissing_population=x$population),x[c('year','state')],function(v) sum(v,na.rm=TRUE))
  show(merge(s,p,by=c('year','state')))
  cat('\nConnecticut geographic rows (2019 onward):\n')
  show(x[norm(x$state)=='CT' & x$year>=2019,intersect(c('year','county','fips','entryyear','population'),names(x))])
  cat('\nMissing or nonpositive populations outside Connecticut:\n')
  show(x[norm(x$state)!='CT' & (is.na(x$population)|x$population<=0),intersect(c('year','state','county','fips','population'),names(x))])
  if ('entryyear' %in% names(x)) cat('Rows before EntryYear:',sum(x$year<x$entryyear,na.rm=TRUE),'\n')
  censuses[[basename(path)]] <- x
},error=function(e) cat('CENSUS ERROR:',conditionMessage(e),'\n'))

section('Bacterial versus other census variants by year')
b <- censuses[['cen9625.sas7bdat']]
if (!is.null(b)) for (name in setdiff(names(censuses),'cen9625.sas7bdat')) {
  cat('\nComparison:',name,'\n'); p <- censuses[[name]]
  for (y in sort(unique(c(b$year,p$year)))) {
    bb <- b[b$year==y,]; pp <- p[p$year==y,]
    ix <- match(bb$fips,pp$fips); a <- bb$population; v <- pp$population[ix]
    ok <- !is.na(ix)&!is.na(a)&!is.na(v)
    cat(y,'bacterial rows=',nrow(bb),'other rows=',nrow(pp),'only bacterial=',sum(!bb$fips %in% pp$fips),'only other=',sum(!pp$fips %in% bb$fips),'comparable=',sum(ok),'different populations=',sum(abs(a[ok]-v[ok])>0.01),'\n')
  }
}

section('MMWR aggregate audit')
path <- file.path(data_dir,'mmwr9625.sas7bdat')
h <- haven::read_sas(path,n_max=0)
wanted <- c('year','state','county','fips','pathogen','siteid','travelint','cxcidt','serotypesummary2','serotypesummary','stec_class','stec_class_orig','dx0157','dxo157','typh_salm')
cat('Available audit fields:',paste(names(h)[tolower(names(h)) %in% wanted],collapse=', '),'\n')
cat('DxO157 letter-O present:', 'dxo157' %in% tolower(names(h)), '| dx0157 zero present:', 'dx0157' %in% tolower(names(h)),'\n')
x <- read_selected(path,wanted)
if (!all(c('year','state','county','fips','pathogen') %in% names(x))) stop('Required MMWR audit fields absent')
cat('Total raw records:',nrow(x),'\n')
for (n in names(x)) cat(n,'missing/blank:',sum(norm(x[[n]])==''),'\n')
x$state <- norm(x$state); x$pathogen <- norm(x$pathogen); x$fips <- norm(x$fips)
section('Case records by year and pathogen'); counts(x,c('year','pathogen'),TRUE)
section('Case records by year and state'); counts(x,c('year','state'),TRUE)
section('Case records by year and submitting site'); counts(x,c('year','siteid'),TRUE)
section('FIPS structure')
x$fips_status <- ifelse(x$fips=='','Missing',ifelse(grepl('^[0-9]{5}$',x$fips),'Five digits','Other format'))
counts(x,c('year','fips_status'),TRUE)
section('Connecticut geography by year')
ct <- x[x$state=='CT',]
ct$geography <- ifelse(ct$fips=='','Missing',ifelse(ct$fips %in% sprintf('09%03d',seq(1,15,2)),'Historical county',ifelse(ct$fips %in% sprintf('09%03d',seq(110,190,10)),'Planning region','Other')))
counts(ct,c('year','geography'),TRUE)

section('Case-to-denominator matches, by intended pathogen class')
cat('Parasitic assignment here: CRYPTOSPORIDIUM, CYCLOSPORA. Other raw pathogen labels use bacterial table for this diagnostic only.\n')
for (kind in c('Bacterial','Parasitic')) {
  cfile <- if(kind=='Bacterial') 'cen9625.sas7bdat' else 'cen9625_para.sas7bdat'
  cdata <- censuses[[cfile]]; if(is.null(cdata)) next
  z <- x[(x$pathogen %in% c('CRYPTOSPORIDIUM','CYCLOSPORA')) == (kind=='Parasitic'),]
  ix <- match(paste(z$year,z$fips,sep='|'),cdata$key)
  z$match_status <- ifelse(z$fips=='','Missing case FIPS',ifelse(is.na(ix),'No county/year match',ifelse(is.na(cdata$population[ix]),'Matched missing population',ifelse(cdata$population[ix]<=0,'Matched nonpositive population','Matched positive population'))))
  cat('\n',kind,'direct FIPS matches:\n'); counts(z,c('year','match_status'),TRUE)
  # Resolve only unique year/state/normalized-name keys; never arbitrary ambiguous matches.
  nk <- paste(cdata$year,norm(cdata$state),county_key(cdata$county),sep='|')
  ambiguous <- duplicated(nk)|duplicated(nk,fromLast=TRUE)
  ni <- match(paste(z$year,z$state,county_key(z$county),sep='|'),nk)
  unique_match <- !is.na(ni)&!ambiguous[ni]
  good <- unique_match & !is.na(cdata$population[ni]) & cdata$population[ni]>0
  good[is.na(good)] <- FALSE
  z$name_result <- ifelse(good,'Unique name match with positive population','No unique positive-population name match')
  cat('\n',kind,'name fallback among missing FIPS:\n'); counts(z[z$fips=='',],c('year','name_result'),TRUE)
  comparable <- unique_match & z$fips!=''; comparable[is.na(comparable)] <- FALSE
  cat('Populated case FIPS disagreeing with unique state/county-name match:',sum(z$fips[comparable]!=cdata$fips[ni[comparable]]),'\n')
}
section('Classification and travel aggregate checks')
for (n in intersect(c('travelint','cxcidt'),names(x))) { cat('\n',n,'\n'); counts(x,c('year',n),TRUE) }
stec <- x[x$pathogen=='STEC',]
for(n in intersect(c('dxo157','dx0157','stec_class','stec_class_orig'),names(stec))) { cat('\nSTEC:',n,'\n'); counts(stec,c('year',n),TRUE) }
cat('\nSerotype field completeness by pathogen/year:\n')
for(n in intersect(c('serotypesummary2','serotypesummary'),names(x))) {
  z <- x[c('year','pathogen')]; z$status <- ifelse(norm(x[[n]])=='','Blank','Present'); cat(n,'\n'); counts(z,c('year','pathogen','status'),TRUE)
}
section('Audit complete')
cat('These are raw-input diagnostics. They do not establish surveillance eligibility, record deduplication, or geographic equivalence.\n')
cat('Remaining decisions: approved surveillance footprint for 2025 parasites; consistent spatial units over time; provenance/vintage of population estimates.\n')
},error=function(e) { section('AUDIT STOPPED'); cat(conditionMessage(e),'\nPartial results above remain available.\n') },finally={sink();close(con)})
cat('Report written:', normalizePath(report), '\n')
