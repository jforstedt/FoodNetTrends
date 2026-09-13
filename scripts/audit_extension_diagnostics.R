# Read-only feasibility audit. Source this file; no fits or data mutations.
audit_extension_diagnostics <- function(raw, clean = NULL) {
  stopifnot(is.data.frame(raw), is.null(clean) || is.data.frame(clean))
  sources <- list(raw = raw)
  if (!is.null(clean)) sources$clean <- clean
  tables <- list(fields = list(), categories = list(), missingness = list(),
                 overlap = list(), identifier_candidates = list())
  # Keep blank, NA, and literal unknown categories distinct; do not decode SAS codes.
  value <- function(x) {
    y <- as.character(x)
    y[is.na(x)] <- '<NA>'
    y[!is.na(x) & trimws(y) == ''] <- '<BLANK>'
    y
  }
  grouped <- function(d, cols, values) {
    if (!nrow(d)) return(data.frame())
    stats::aggregate(values, d[cols], sum)
  }
  for (source in names(sources)) {
    d <- sources[[source]]
    if (anyDuplicated(names(d)) || any(names(d) != tolower(names(d))))
      stop('Input names must be unique and normalized to lowercase')
    names_present <- names(d)
    key <- c('pathogen', 'year', 'state', 'siteid')
    candidates <- names_present[grepl('cidt|culture|diagnos|test|specimen|case_?id|record_?id', names_present)]
    inventory <- unique(c(key, 'cxcidt', candidates))
    tables$fields[[source]] <- do.call(rbind, lapply(inventory, function(nm) {
      present <- nm %in% names_present
      x <- if (present) d[[nm]] else NULL
      labs <- attr(x, 'labels')
      data.frame(source = source, field = nm, present = present,
        role = if (nm == 'cxcidt') 'confirmed_diagnostic_category' else if (nm %in% key) 'confirmed_grouping_field' else 'unverified_name_candidate',
        storage_class = paste(class(x), collapse = '|'),
        label = if (is.null(attr(x, 'label'))) '' else as.character(attr(x, 'label')),
        value_labels = if (is.null(labs)) '' else paste(paste(names(labs), labs, sep = '='), collapse = '|'),
        stringsAsFactors = FALSE)
    }))
    # Candidate IDs are not approved identifiers: report completeness/duplication only.
    ids <- names_present[grepl('(^|_)(case|record)_?id$|^caseid$|^recordid$', names_present)]
    if (length(ids)) tables$identifier_candidates[[source]] <- do.call(rbind, lapply(ids, function(nm) {
      x <- d[[nm]]; keep <- !is.na(x) & trimws(as.character(x)) != ''
      data.frame(source = source, field = nm, records = nrow(d), nonmissing = sum(keep),
        distinct_nonmissing = length(unique(x[keep])), duplicated_nonmissing = sum(duplicated(x[keep])),
        linkage_status = 'UNVERIFIED_CANDIDATE_NO_LINKAGE_PERFORMED')
    })) else tables$identifier_candidates[[source]] <- data.frame(source = source,
      field = '<NONE_DETECTED>', records = nrow(d), nonmissing = NA_integer_,
      distinct_nonmissing = NA_integer_, duplicated_nonmissing = NA_integer_,
      linkage_status = 'NO_CONFIRMED_IDENTIFIER')
    g <- as.data.frame(setNames(lapply(key, function(nm) if (nm %in% names_present) value(d[[nm]]) else rep('<FIELD_ABSENT>', nrow(d))), key))
    g$source <- rep(source, nrow(d))
    cols <- c('source', key)
    if (!'cxcidt' %in% names_present) next
    x <- d$cxcidt
    g$diagnostic_category <- value(x)
    tables$categories[[source]] <- grouped(g, c(cols, 'diagnostic_category'), data.frame(records = rep(1L, nrow(d))))
    tables$missingness[[source]] <- grouped(g, cols, data.frame(records = rep(1L, nrow(d)),
      missing = as.integer(is.na(x)), blank = as.integer(!is.na(x) & trimws(as.character(x)) == ''),
      explicit_unknown = as.integer(!is.na(x) & toupper(trimws(as.character(x))) %in% c('UNKNOWN', 'UNK'))))
    # Exact production category strings; labels/codes needing recoding remain visible above.
    z <- grouped(g, cols, data.frame(cx_records = as.integer(!is.na(x) & as.character(x) == 'CX+'),
      cidt_records = as.integer(!is.na(x) & as.character(x) == 'CIDT+'),
      parasitic_records = as.integer(!is.na(x) & as.character(x) == 'PARASITIC')))
    if (nrow(z)) {
      z$cx_and_cidt_categories_present <- z$cx_records > 0 & z$cidt_records > 0
      z$interpretation <- 'CASE_CATEGORY_COOCCURRENCE_NOT_DUAL_TESTING_OR_ADOPTION'
    }
    tables$overlap[[source]] <- z
  }
  result <- lapply(tables, function(x) if (length(x)) do.call(rbind, x) else data.frame())
  result$readiness <- data.frame(component = c('diagnostic_category', 'dual_testing', 'testing_denominator', 'site_adoption', 'raw_clean_linkage', 'surveillance_eligibility'),
    assessment = c('INVENTORY_ONLY_REVIEW_SITE_YEAR_COMPLETENESS', 'NOT_ESTABLISHED_BY_CXCIDT',
      'NOT_ESTABLISHED_BY_CASE_RECORDS', 'REQUIRES_EXTERNAL_TESTING_HISTORY',
      'NOT_PERFORMED_IDENTIFIER_MEANING_UNVERIFIED', 'NO_ELIGIBILITY_FILTER_APPLIED'),
    limitation = c('Raw and clean pathogen labels are separate; no assumed recoding or causal adjustment.',
      'A single classification cannot establish which tests were performed on the same specimen.',
      'Population is an incidence denominator, not the number tested or test sensitivity.',
      'First recorded CIDT-positive case is not a validated laboratory adoption date.',
      'Candidate identifier completeness does not establish stable cross-file identity.',
      'Summaries include all provided rows; modeled surveillance windows must be applied separately.'))
  result
}
