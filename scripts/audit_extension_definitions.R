# Targeted definition audit. Never exports lab names or identifier values.
audit_extension_definitions <- function(raw) {
  stopifnot(is.data.frame(raw));names(raw)<-tolower(names(raw));if(anyDuplicated(names(raw)))stop('Duplicate field names')
  value<-function(x){z<-as.character(x);z[is.na(x)]<-'<NA>';z[!is.na(x)&trimws(z)=='']<-'<BLANK>';z}
  get<-function(n)if(n%in%names(raw))value(raw[[n]])else rep('<ABSENT>',nrow(raw))
  keys<-data.frame(pathogen=get('pathogen'),state=get('state'),year=get('year'),stringsAsFactors=FALSE)
  grouped<-function(values)if(nrow(raw))aggregate(values,keys,sum,na.rm=TRUE)else data.frame()
  date<-function(n){x<-raw[[n]];if(is.null(x))return(as.Date(rep(NA_character_,nrow(raw))));if(!inherits(x,'Date'))stop(paste('Expected haven Date class:',n));x[!is.finite(as.numeric(x))]<-NA;x}
  spec<-date('dtspec');yr<-suppressWarnings(as.integer(get('year')));mo<-suppressWarnings(as.integer(get('month')))
  date_checks<-grouped(data.frame(records=rep(1L,nrow(raw)),spec_missing=as.integer(is.na(spec)),month_missing_or_invalid=as.integer(is.na(mo)|mo<1|mo>12),
    month_disagreement=as.integer(!is.na(spec)&!is.na(mo)&mo>=1&mo<=12&as.integer(format(spec,'%m'))!=mo),
    year_disagreement=as.integer(!is.na(spec)&!is.na(yr)&as.integer(format(spec,'%Y'))!=yr),
    specimen_day1=as.integer(format(spec,'%d')=='01'),specimen_day15=as.integer(format(spec,'%d')=='15'),
    specimen_jan1=as.integer(format(spec,'%m-%d')=='01-01')))
  delays<-list()
  for(n in intersect(c('dtonset','dtrcvd','dtentered','dtrptcomp'),names(raw))) {
    days<-as.numeric(date(n)-spec)
    groups<-split(seq_len(nrow(raw)),interaction(keys,drop=TRUE))
    delays[[n]]<-do.call(rbind,lapply(groups,function(ix){x<-days[ix];ok<-is.finite(x);q<-if(any(ok))as.numeric(quantile(x[ok],c(.01,.5,.99)))else rep(NA_real_,3)
      cbind(keys[ix[1],,drop=FALSE],data.frame(field=n,paired_dates=sum(ok),missing_pairs=sum(!ok),negative=sum(x[ok]<0),
        abs_over365=sum(abs(x[ok])>365),days_q01=q[1],days_median=q[2],days_q99=q[3]))}))
  }
  code_fields<-intersect(c('cxcidt','culturestatus','cultclinic','pcrclinic','pcrsphl','agclinic','agsphl','bioid','stecpcr'),names(raw))
  codes<-lapply(code_fields,function(n){g<-keys;g$field<-n;g$code<-get(n);x<-aggregate(rep(1L,nrow(raw)),g,sum);names(x)[ncol(x)]<-'records';x})
  pairs<-list()
  for(n in setdiff(code_fields,'cxcidt')) {
    g<-keys;g$category<-get('cxcidt');g$field<-n;g$result_code<-get(n)
    x<-aggregate(rep(1L,nrow(raw)),g,sum);names(x)[ncol(x)]<-'records';pairs[[n]]<-x
  }
  lab<-get('labname');normalized<-toupper(gsub('[[:space:]]+',' ',trimws(lab)))
  known<-!normalized%in%c('<NA>','<BLANK>','<ABSENT>','UNKNOWN','UNK')
  groups<-split(seq_len(nrow(raw)),interaction(keys,drop=TRUE))
  laboratories<-do.call(rbind,lapply(groups,function(ix){k<-ix[known[ix]];cbind(keys[ix[1],,drop=FALSE],data.frame(records=length(ix),known_name_records=length(k),
    distinct_raw_names=length(unique(lab[k])),distinct_case_space_normalized_names=length(unique(normalized[k]))))}))
  ids<-intersect(c('patid','personid','resultid','specid','localid','slabsid','narms_genrecid'),names(raw))
  identity<-lapply(ids,function(n){x<-get(n);ok<-!toupper(trimws(x))%in%c('<NA>','<BLANK>','<ABSENT>','UNKNOWN','UNK');
    data.frame(field=n,records=length(x),nonmissing=sum(ok),distinct_values=length(unique(x[ok])),
      duplicate_values=sum(duplicated(x[ok])),duplicate_state_value_pairs=sum(duplicated(paste(keys$state[ok],x[ok],sep='|'))),
      interpretation='Candidate key inventory only; repeats can represent legitimate specimens or illnesses; no records removed')})
  bind<-function(x)if(length(x))do.call(rbind,x)else data.frame()
  list(date_checks=date_checks,date_intervals=bind(delays),test_codes=bind(codes),category_test_crosswalk=bind(pairs),
    laboratory_consistency=laboratories,identifier_support=bind(identity),
    limitations=data.frame(note=c('Raw records, not filtered eligible incidence; date differences are not automatically errors.',
      'Day-1/day-15 frequency cannot establish date imputation; obtain the data dictionary.',
      'Laboratory normalization covers case/whitespace only, not mergers or stable identities.',
      'Test codes are not decoded as positive/negative without their definitions; same-record overlap is not specimen linkage.',
      'No adoption date, testing denominator, deduplication, monthly zero grid or causal adjustment is inferred.')))
}
