#!/usr/bin/env Rscript
suppressPackageStartupMessages({library(dplyr); library(tidyr); library(HDInterval)})
source('bin/classification.R')
# Load pure analysis functions without loading the Stan/plotting stack.
for (expr in parse('bin/functions.R')) {
  if (is.call(expr) && identical(expr[[1]], as.name('<-')) &&
      is.call(expr[[3]]) && identical(expr[[3]][[1]], as.name('function'))) eval(expr)
}
rules <- read_classification_rules('analysis_configs/classification_rules.csv')
x <- data.frame(pathogen = rep('SALMONELLA', 8), serotypesummary2 =
  c('ENTERITIDIS', '', 'UNKNOWN', 'HEIDELBERG', 'TYPHI', 'PARATYPHI B',
    'PARATYPHI B TARTRATE-NEGATIVE', 'I 4,[5],12:i:-'), sero1 = 'NEWPORT')
y <- classify_cases(x, rules)
stopifnot(y$serotypesummary[2] == 'NOT SEROTYPED',
          y$serotypesummary_original[2] == '',
          y$salmonella_type[5] == 'TYPHOIDAL',
          y$salmonella_type[6] == 'UNCLASSIFIED',
          y$salmonella_type[7] == 'TYPHOIDAL',
          identical(y, classify_cases(y, rules)))
selected <- c('ENTERITIDIS', 'I 4,[5],12:i:-')
other <- select_analysis_cases(y, 'SALMONELLA', 'OTHER SEROTYPES', selected)
stopifnot(nrow(other) == 4, !any(other$serotypesummary %in% c(selected, 'NOT SEROTYPED')))
stopifnot(nrow(select_analysis_cases(y, 'SALMONELLA', 'NOT SEROTYPED')) == 2)
# Category definitions really can change without rewriting model code.
custom <- rbind(rules, data.frame(classification='typhoidal', match_type='exact', value='PARATYPHI B'))
stopifnot(classify_cases(x, custom)$salmonella_type[6] == 'TYPHOIDAL')
custom <- rbind(rules, data.frame(classification='nontyphoidal', match_type='exact', value='PARATYPHI B'))
stopifnot(classify_cases(x, custom)$salmonella_type[6] == 'NONTYPHOIDAL')
stopifnot(classify_cases(x, rules, 'sero1')$serotypesummary[2] == 'NEWPORT')
x <- data.frame(pathogen='STEC', stec_class=c('STEC NONO157','STEC O157','STEC O AG UNDET','STEC O157'),
                dx0157=c('positive','NEGATIVE','unknown',NA))
y <- classify_cases(x, rules)
stopifnot(identical(y$stec_group,c('O157','nonO157','NOT SEROGROUPED','O157')),
          identical(y, classify_cases(y, rules)))
x <- data.frame(pathogen='CAMPYLOBACTER', serotypesummary=c('JEJUNI','COLI',NA))
stopifnot(nrow(select_analysis_cases(classify_cases(x,rules),'CAMPYLOBACTER','JEJUNI')) == 1)

census <- expand.grid(year=2016:2018, state=c('CA','OR'), stringsAsFactors=FALSE) %>%
  mutate(population=100000, pathogentype='Bacterial')
cases <- data.frame(year=c(2016,2018), state='CA', pathogen='SALMONELLA')
result <- PATH_ANALYSIS(cases,census)
stopifnot(nrow(result)==6, sum(result$count)==2, sum(result$population)==600000,
          all(result$count[result$state=='OR']==0), all(result$count[result$year==2017]==0))
restricted <- PATH_ANALYSIS(cases, census, surveillance=data.frame(year=2016:2018,state='CA'))
stopifnot(nrow(restricted)==3, all(restricted$state=='CA'))
# Parasitic denominator and catchment windows are retained.
census2 <- bind_rows(census, mutate(census, population=200000, pathogentype='Parasitic'))
stopifnot(all(PATH_ANALYSIS(mutate(cases,pathogen='CYCLOSPORA'),census2)$population==200000))
window <- data.frame(state=c('CA','OR'),start_year=c(2017,2016),end_year=c(9999,9999))
stopifnot(nrow(PATH_ANALYSIS(cases,census,window))==5)

catch <- expand.grid(year=2016:2018,.draw=1:100) %>%
  mutate(population=if_else(year==2017,300000,100000), count=if_else(year==2017,90,10),
         .epred=if_else(year==2017,120,12)*(.draw/100+0.5))
baseline <- IR_COMP_CATCH(catch,2016,2017)
stopifnot(all(baseline$baseline_raw_ir==25),
          all(abs(baseline$baseline_median_ir-33*1.005)<1e-6),
          all(baseline$comparison_period=='2016-2017'))
single <- IR_COMP_CATCH(catch,2018,2018)
stopifnot(single$relative_risk_est[single$year==2018]==1,
          all(single$baseline_raw_ir==10))
stopifnot(inherits(try(IR_COMP_CATCH(catch,2015,2017),silent=TRUE),'try-error'),
          inherits(try(IR_COMP_CATCH(catch,2018,2016),silent=TRUE),'try-error'),
          inherits(try(IR_COMP_CATCH(filter(catch,year!=2017),2016,2018),silent=TRUE),'try-error'))
cat('Classification, subgroup membership, zero counts, denominators and baseline tests passed.\n')
