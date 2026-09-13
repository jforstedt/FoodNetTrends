# Aggregate-only readiness audit. No event-date precedence or zero-grid inference.
extension_parse_date <- function(x) {
  n <- length(x); out <- as.Date(rep(NA_character_, n)); method <- 'unsupported'
  missing <- is.na(x) | trimws(as.character(x)) == ''
  fmt <- toupper(as.character(attr(x, 'format.sas') %||season% ''))
  if (inherits(x, 'Date')) { out <- as.Date(x); method <- 'Date_class' }
  else if (inherits(x, 'POSIXt')) { out <- as.Date(x, tz='UTC'); method <- 'POSIX_UTC' }
  else if (is.numeric(x) && grepl('^(DATETIME|E8601DT)', fmt)) {
    out <- as.Date(as.POSIXct(as.numeric(x), origin='1960-01-01', tz='UTC')); method <- 'SAS_datetime_metadata'
  } else if (is.numeric(x) && grepl('^(DATE|YYMMDD|MMDDYY|DDMMYY|E8601DA|JULIAN)', fmt)) {
    out <- as.Date(as.numeric(x), origin='1960-01-01'); method <- 'SAS_date_metadata'
  } else if (is.character(x) || is.factor(x)) {
    z <- as.character(x); ok <- !missing & grepl('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', z)
    out[ok] <- suppressWarnings(as.Date(z[ok], format='%Y-%m-%d'))
    # Round trip prevents silent normalization of invalid calendar dates.
    bad <- !is.na(out) & format(out, '%Y-%m-%d') != z; out[bad] <- NA
    method <- 'strict_ISO_date_only'
  }
  list(date=out, missing=missing, invalid=!missing & is.na(out), method=method)
}
`%||season%` <- function(a,b) if (is.null(a) || !length(a)) b else a
season_groups <- function(keys, values) {
  if (!nrow(keys)) return(data.frame())
  stats::aggregate(values, keys, sum, na.rm=TRUE)
}
audit_extension_seasonality <- function(raw, census_b=NULL, census_p=NULL) {
  stopifnot(is.data.frame(raw)); names(raw) <- tolower(names(raw))
  if (anyDuplicated(names(raw))) stop('Duplicate normalized input names')
  get <- function(candidates) {
    nm <- intersect(candidates,names(raw)); if (!length(nm)) return(rep('UNAVAILABLE',nrow(raw)))
    z <- as.character(raw[[nm[1]]]); z[is.na(z) | trimws(z)==''] <- 'MISSING'; z
  }
  keys <- data.frame(pathogen=get('pathogen'),site=get(c('siteid','state','site')),record_year=get(c('year','mmwryear','mmwr_year')),stringsAsFactors=FALSE)
  inventory <- do.call(rbind,lapply(names(raw),function(nm) {
    x <- raw[[nm]]; label <- as.character(attr(x,'label') %||season% '')
    sas <- as.character(attr(x,'format.sas') %||season% '')
    candidate <- inherits(x,c('Date','POSIXt')) || grepl('date|onset|specimen|collect|report|diagnos|(^|_)dt($|_)',paste(nm,label),ignore.case=TRUE) || grepl('DATE|E8601D|YYMMDD|MMDDYY|DDMMYY|JULIAN',sas,ignore.case=TRUE)
    data.frame(field=nm,label=label,class=paste(class(x),collapse=';'),sas_format=sas,date_candidate=candidate,nonmissing=sum(!is.na(x) & trimws(as.character(x))!=''),stringsAsFactors=FALSE)
  }))
  parsed <- lapply(inventory$field[inventory$date_candidate],function(nm) extension_parse_date(raw[[nm]])); names(parsed) <- inventory$field[inventory$date_candidate]
  completeness <- monthly <- agreement <- list()
  for (nm in names(parsed)) {
    p <- parsed[[nm]]; v <- data.frame(records=rep(1,nrow(raw)),missing=as.integer(p$missing),unparsed=as.integer(p$invalid),parsed=as.integer(!is.na(p$date)),date_year_agrees_record_year=as.integer(!is.na(p$date) & format(p$date,'%Y')==keys$record_year))
    z <- season_groups(keys,v); z$field <- nm; z$parse_method <- p$method; completeness[[nm]] <- z
    good <- !is.na(p$date)
    if (any(good)) {
      k <- keys[good,,drop=FALSE]; k$event_year_month <- format(p$date[good],'%Y-%m')
      z <- season_groups(k,data.frame(observed_records=rep(1,sum(good)))); z$field <- nm
      z$interpretation <- 'Observed input records only; deduplication, date meaning and observation coverage not validated; absent months are not zeros'
      monthly[[nm]] <- z
    }
  }
  if (length(parsed)>1) for (pair in combn(names(parsed),2,simplify=FALSE)) {
    a <- parsed[[pair[1]]]$date; b <- parsed[[pair[2]]]$date; ok <- !is.na(a)&!is.na(b)
    z <- season_groups(keys,data.frame(both_parsed=as.integer(ok),same_day=as.integer(ok & a==b),same_month=as.integer(ok & format(a,'%Y-%m')==format(b,'%Y-%m'))))
    z$field_a <- pair[1]; z$field_b <- pair[2]; agreement[[length(agreement)+1]] <- z
  }
  pop <- lapply(list(bacterial=census_b,parasitic=census_p),function(d) {
    if(is.null(d)) return(data.frame())
    names(d)<-tolower(names(d)); if(!all(c('year','population')%in%names(d))) return(data.frame(status='Missing year or population field'))
    yr<-as.character(d$year); yr[is.na(yr)]<-'MISSING'; st<-if('state'%in%names(d))as.character(d$state)else rep('UNAVAILABLE',nrow(d)); st[is.na(st)]<-'MISSING'
    p<-suppressWarnings(as.numeric(as.character(d$population)))
    z<-season_groups(data.frame(year=yr,state=st),data.frame(rows=rep(1,nrow(d)),invalid_population=as.integer(!is.finite(p)|p<=0)))
    z$status<-'Annual population inventory only; monthly exposure and surveillance eligibility not established'; z
  })
  bind <- function(x) if(length(x))do.call(rbind,x)else data.frame()
  list(field_inventory=inventory,date_completeness=bind(completeness),date_agreement=bind(agreement),monthly_observed_records=bind(monthly),record_year_coverage=season_groups(keys,data.frame(observed_records=rep(1,nrow(raw)))),population_bacterial=pop$bacterial,population_parasitic=pop$parasitic,
       limitations=data.frame(item=c('No primary event date selected','No monthly surveillance coverage inferred from presence of cases','No zeros constructed for unobserved months','No reporting-lag estimate without validated date definitions and extraction history','Annual denominators do not establish monthly population exposure','ISO date strings only; ambiguous string formats require a data dictionary','Raw record counts are not automatically eligible deduplicated case counts'),stringsAsFactors=FALSE))
}
