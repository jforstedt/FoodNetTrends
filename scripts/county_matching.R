# Pure geographic candidate matching. This does not authorize surveillance coverage.
county_norm <- function(x) {
  y <- toupper(trimws(as.character(x)));y[is.na(x)] <- '';y
}
county_name_key <- function(x) gsub('[^A-Z0-9]','',county_norm(x))
county_fips <- function(x) {
  y <- county_norm(x)
  # Numeric SAS fields lose leading zeroes. Pad only a wholly numeric 4/5-digit code.
  ok <- grepl('^[0-9]{4,5}$',y)
  y[ok] <- sprintf('%05d',as.integer(y[ok]));y
}
match_county_candidates <- function(cases,pop) {
  stopifnot(all(c('year','state','county','fips')%in%names(cases)),
            all(c('year','state','county','fips','population')%in%names(pop)))
  cases$state <- county_norm(cases$state);pop$state <- county_norm(pop$state)
  pop$fips <- county_fips(pop$fips)
  cases$fips_original <- as.character(cases$fips);cases$fips <- county_fips(cases$fips)
  nk <- function(x) paste(x$year,x$state,county_name_key(x$county),sep='|')
  pk <- paste(pop$year,pop$fips,sep='|'); name_keys <- nk(pop)
  dup <- duplicated(pk)|duplicated(pk,fromLast=TRUE)
  name_dup <- duplicated(name_keys)|duplicated(name_keys,fromLast=TRUE)
  ix <- match(paste(cases$year,cases$fips,sep='|'),pk)
  ni <- match(nk(cases),name_keys)
  name_unique <- !is.na(ni)&!name_dup[ni]&county_name_key(cases$county)!=''
  name_unique[is.na(name_unique)] <- FALSE
  status <- rep('unresolved',nrow(cases)); method <- rep('none',nrow(cases))
  chosen <- rep(NA_integer_,nrow(cases))
  missing <- cases$fips==''
  malformed <- !missing & !grepl('^[0-9]{5}$',cases$fips)
  status[malformed] <- 'invalid_case_fips'
  direct <- !missing & !malformed
  status[direct & is.na(ix)] <- 'no_fips_year_population_row'
  good <- direct & !is.na(ix)
  status[good] <- 'direct_fips_candidate';chosen[good] <- ix[good];method[good] <- 'direct_fips'
  status[missing] <- 'no_unique_year_state_name_match'
  fallback <- missing & name_unique
  chosen[fallback] <- ni[fallback];method[fallback] <- 'unique_year_state_name'
  status[fallback] <- 'name_candidate_requires_review'
  # Never replace a populated but conflicting/missing FIPS with a name match.
  conflict <- good & name_unique & pop$fips[ix]!=pop$fips[ni]
  conflict[is.na(conflict)] <- FALSE;status[conflict] <- 'fips_name_conflict'
  selected <- !is.na(chosen)
  state_bad <- selected & cases$state!=pop$state[chosen];state_bad[is.na(state_bad)] <- FALSE
  status[state_bad] <- 'fips_state_conflict'
  duplicate <- selected & dup[chosen];duplicate[is.na(duplicate)] <- FALSE
  status[duplicate] <- 'duplicate_population_key'
  invalid_pop_fips <- selected & !grepl('^[0-9]{5}$',pop$fips[chosen])
  invalid_pop_fips[is.na(invalid_pop_fips)] <- FALSE
  status[invalid_pop_fips] <- 'invalid_population_fips'
  eligible_check <- status %in% c('direct_fips_candidate','name_candidate_requires_review')
  invalid <- eligible_check & (!is.finite(pop$population[chosen]) | pop$population[chosen]<=0)
  invalid[is.na(invalid)] <- FALSE;status[invalid] <- 'missing_or_nonpositive_population'
  if('entryyear'%in%names(pop)) {
    pre <- eligible_check & !invalid & !is.na(pop$entryyear[chosen]) & cases$year<pop$entryyear[chosen]
    pre[is.na(pre)] <- FALSE;status[pre] <- 'before_census_entryyear'
  }
  result <- cases
  result$candidate_fips <- ifelse(selected,pop$fips[chosen],NA_character_)
  result$candidate_population <- ifelse(selected,pop$population[chosen],NA_real_)
  result$match_method <- method;result$match_status <- status
  result$geography_review <- ifelse(cases$state=='CT' & cases$year>=2020,
                                   'connecticut_boundary_reconciliation','none_identified')
  result$coverage_status <- rep('not_verified',nrow(result))
  result$model_ready <- rep(FALSE,nrow(result))
  result
}
