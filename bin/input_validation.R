# Explicit analysis coverage and denominator validation; no population imputation.
prepare_analysis_inputs <- function(cases, bacterial, parasitic, pathogen,
                                    colorado_coverage = 'historical', parasite_end_year = 2024L, observation_years = NULL,
                                    subgroup = 'combined', analysis_end_year = NULL) {
  if (!colorado_coverage %in% c('historical', 'expanded')) stop('colorado_coverage must be historical or expanded')
  if (length(parasite_end_year) != 1 || is.na(parasite_end_year) || parasite_end_year != as.integer(parasite_end_year))
    stop('parasite_end_year must be an integer')
  para <- pathogen %in% c('CRYPTOSPORIDIUM', 'CYCLOSPORA')
  kind <- if (para) 'Parasitic' else 'Bacterial'
  raw <- if (para) parasitic else bacterial
  names(raw) <- tolower(names(raw))
  if (!all(c('year', 'state', 'population') %in% names(raw))) stop('Census requires year, state and population')
  if (!is.numeric(raw$population) || !is.numeric(raw$year)) stop('Census year and population must be numeric')
  raw$state <- toupper(trimws(as.character(raw$state)))
  selected <- cases[cases$pathogen == pathogen, , drop = FALSE]
  excluded <- data.frame(reason=character(), year=numeric(), records=integer())
  record_exclusion <- function(rows, reason) {
    if (nrow(rows)) {
      out <- aggregate(list(records=rep(1L,nrow(rows))),list(year=rows$year),sum)
      out$reason <- reason
      excluded <<- rbind(excluded,out[c('reason','year','records')])
    }
  }
  years <- if (is.null(observation_years)) seq.int(min(cases$year,na.rm=TRUE), max(cases$year,na.rm=TRUE)) else observation_years
  if (!is.null(analysis_end_year)) {
    if (length(analysis_end_year)!=1L || !is.numeric(analysis_end_year) ||
        !is.finite(analysis_end_year) || analysis_end_year!=as.integer(analysis_end_year))
      stop('analysis_end_year must be an integer')
    years <- years[years <= analysis_end_year]
    if (!length(years)) stop('No analysis years remain after analysis_end_year')
  }
  if (para) {
    record_exclusion(selected[selected$year > parasite_end_year,,drop=FALSE], 'After parasite_end_year')
    selected <- selected[selected$year <= parasite_end_year,,drop=FALSE]
    years <- years[years >= 1997 & years <= parasite_end_year]
  }
  # FoodNet Cryptosporidium surveillance ended after 2017 (CDC FoodNet timeline).
  # Census availability and the Cyclospora end-year option cannot extend observation.
  if (pathogen == 'CRYPTOSPORIDIUM') {
    record_exclusion(selected[selected$year > 2017,,drop=FALSE], 'After Cryptosporidium surveillance ended (2017)')
    selected <- selected[selected$year <= 2017,,drop=FALSE]
    years <- years[years <= 2017]
  }
  # Observation eligibility precedes zero-cell construction. These boundaries
  # describe surveillance, not modifications to the spline or its priors.
  scope_start <- if (para) 1997L else 1996L
  scope_end <- if (para) as.integer(parasite_end_year) else Inf
  scope_reason <- if (para) 'Parasite observation window' else 'Bacterial observation window'
  if (pathogen == 'CRYPTOSPORIDIUM') {
    scope_end <- min(scope_end, 2017L)
    scope_reason <- 'Cryptosporidium surveillance ended in 2017'
  }
  if (pathogen == 'STEC' && identical(subgroup, 'nonO157')) {
    scope_start <- 2000L
    scope_reason <- 'Non-O157 STEC surveillance began in 2000'
    record_exclusion(selected[selected$year < scope_start,,drop=FALSE], scope_reason)
    selected <- selected[selected$year >= scope_start,,drop=FALSE]
    years <- years[years >= scope_start]
  }
  if (pathogen == 'CAMPYLOBACTER') {
    scope_end <- 2023L
    scope_reason <- 'Campylobacter diagnosis reporting changed after 2023; later annual trends require a separate comparability review'
    record_exclusion(selected[selected$year > scope_end,,drop=FALSE], scope_reason)
    selected <- selected[selected$year <= scope_end,,drop=FALSE]
    years <- years[years <= scope_end]
  }
  if (!length(years)) stop('No analysis years remain after surveillance eligibility limits')
  if (!pathogen %in% c('SALMONELLA', 'STEC') && any(years >= 2025))
    stop('FoodNet reporting became optional in July 2025 for ', pathogen,
         '; site-specific reporting completeness is unverified. Explicitly restrict analysis years through 2024 or earlier. ',
         'Optional reporting is not equivalent to zero cases.')
  # Explicit observation windows also restrict cases; out-of-window cases cannot
  # survive into a zero grid whose eligible years have already been restricted.
  record_exclusion(selected[!selected$year %in% years,,drop=FALSE], 'Outside selected observation years')
  selected <- selected[selected$year %in% years,,drop=FALSE]
  # Enforce reportability even for a reused or externally preprocessed CSV.
  if (pathogen == 'LISTERIA' && nrow(selected)) {
    if (!'cste' %in% names(selected))
      stop('LISTERIA requires the cste reportability column in selected preprocessed cases')
    eligible <- !is.na(selected$cste) & selected$cste == 'YES'
    record_exclusion(selected[!eligible,,drop=FALSE], 'Listeria not verified CSTE-reportable (requires YES)')
    selected <- selected[eligible,,drop=FALSE]
  }
  coverage <- data.frame(pathogen=pathogen, subgroup=subgroup,
    observation_start_year=min(years), observation_end_year=max(years),
    surveillance_start_year=scope_start, surveillance_end_year=scope_end,
    reason=scope_reason, stringsAsFactors=FALSE)

  co_reference <- raw[raw$state == 'CO' & raw$year < 2023,,drop=FALSE]
  raw <- raw[raw$year %in% years,,drop=FALSE]
  if (anyNA(raw$year) || anyNA(raw$state) || any(!nzchar(raw$state))) stop('Missing census year/state')
  # COEX is a surveillance-site indicator, not a state or a pathogen.
  has_co <- any(cases$state == 'CO') || any(raw$state == 'CO')
  if (has_co && any(years >= 2023) && pathogen == 'YERSINIA' && colorado_coverage == 'expanded')
    stop('Expanded Colorado coverage is not valid for Yersinia: surveillance remains in the seven historical counties. Use historical coverage with matching denominators.')
  if (has_co && any(years >= 2023) && colorado_coverage == 'historical') {
    if (!'siteid' %in% names(selected)) stop('Historical Colorado coverage requires siteid in the cleaned case data')
    is_co <- selected$state == 'CO'
    if (any(is_co & (is.na(selected$siteid) | !nzchar(trimws(selected$siteid)))))
      stop('Colorado cases have missing siteid; cannot establish historical coverage')
    remove <- toupper(trimws(selected$siteid)) == 'COEX'; remove[is.na(remove)] <- FALSE
    record_exclusion(selected[remove,,drop=FALSE], 'Colorado expansion site excluded (historical coverage)')
    selected <- selected[!remove,,drop=FALSE]
  }
  if (has_co && any(years >= 2023) && any(raw$state == 'CO')) {
    if (!all(c('stfip','cofip','county') %in% names(raw)))
      stop('Colorado coverage validation requires county, STFIP and COFIP census columns')
    co <- raw[raw$state == 'CO',,drop=FALSE]
    ref <- co_reference
    if (!nrow(ref)) stop('Colorado coverage validation requires a pre-2023 census reference year')
    ref <- ref[ref$year == max(ref$year),,drop=FALSE]
    historical <- unique(ref$cofip)
    if (anyNA(historical)) stop('Missing Colorado county identifier')
    for (y in unique(co$year)) {
      ids <- co$cofip[co$year == y]
      if (colorado_coverage == 'historical' && y >= 2023 && !setequal(ids,historical))
        stop('Historical Colorado coverage requires the historical county population footprint; mismatch in ',y)
      # Colorado statewide coverage contains 64 counties: odd codes 001-125
      # plus Broomfield (014). Case presence cannot certify denominator coverage.
      if (colorado_coverage == 'expanded' && y >= 2023 &&
          !setequal(ids, c(seq.int(1L,125L,2L),14L)))
        stop('Expanded Colorado coverage requires all 64 county denominators in ',y)
    }
    # Name check catches cases outside the selected county footprint without relying on missing recent FIPS.
    key <- function(v) gsub('[^A-Z0-9]','',toupper(trimws(as.character(v))))
    keys <- paste(co$year,key(co$county))
    cc <- selected[selected$state == 'CO',,drop=FALSE]
    if (nrow(cc) && (!'county' %in% names(cc) || any(!paste(cc$year,key(cc$county)) %in% keys)))
      stop('Colorado case county/year does not match the selected population footprint')
  }
  if (all(c('stfip','cofip') %in% names(raw))) {
    if (anyNA(raw$stfip) || anyNA(raw$cofip)) stop('Missing census county identifier')
    if (anyDuplicated(raw[c('year','stfip','cofip')])) stop('Duplicate census county/year rows; demographic tables cannot be summed without category selection')
    # CT carries eight inactive historical counties plus nine planning regions.
    # Only the observed, documented inactive geography may carry NA/zero values.
    old_ct <- raw$state == 'CT' & raw$cofip %in% seq(1,15,2)
    new_ct <- raw$state == 'CT' & raw$cofip %in% seq(110,190,10)
    inactive <- (old_ct & raw$year >= 2020) | (new_ct & raw$year < 2020)
    if (any(inactive & !is.na(raw$population) & raw$population != 0))
      stop('Connecticut has populated overlapping geographic systems; reconcile before aggregation')
    if (any(!inactive & (!is.finite(raw$population) | raw$population <= 0)))
      stop('Missing, nonfinite or nonpositive population in an active census geography')
    for (y in unique(raw$year[raw$state=='CT' & raw$year>=2020])) {
      if (!setequal(raw$cofip[new_ct & raw$year==y],seq(110,190,10)))
        stop('Connecticut planning-region population coverage is incomplete in ',y)
    }
  } else {
    if (anyDuplicated(raw[c('year','state')])) stop('Duplicate state/year census rows without county identifiers')
    if (any(!is.finite(raw$population) | raw$population <= 0)) stop('Invalid state population')
  }
  census <- aggregate(list(population=raw$population),raw[c('year','state')],function(v) sum(v,na.rm=TRUE))
  if (any(!is.finite(census$population) | census$population<=0)) stop('Invalid aggregated state population')
  census$pathogentype <- kind
  missing_years <- setdiff(years,unique(census$year))
  if (length(missing_years)) stop('Missing ',kind,' population years: ',paste(missing_years,collapse=', '),
                                '. Supply matching denominators or explicitly restrict the analysis years.')
  list(cases=selected,census=census,years=years,excluded=excluded,coverage=coverage)
}

# Call again after custom catchment filtering, before spending time on a fit.
assert_baseline_available <- function(years, baseline_start, baseline_end) {
  if (length(baseline_start)!=1L || length(baseline_end)!=1L ||
      !is.finite(baseline_start) || !is.finite(baseline_end) ||
      baseline_start!=as.integer(baseline_start) || baseline_end!=as.integer(baseline_end) ||
      baseline_start>baseline_end) stop('Baseline must be an ordered pair of integer years')
  missing <- setdiff(seq.int(baseline_start,baseline_end),unique(years))
  if (length(missing)) stop('Baseline years unavailable after observation/catchment filtering: ',
                           paste(missing,collapse=', '))
  invisible(TRUE)
}
