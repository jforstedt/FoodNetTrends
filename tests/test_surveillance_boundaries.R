# Observation boundaries must precede count-zero construction and model fitting.
source('bin/input_validation.R')
expect_error <- function(expr, pattern) {
  err <- tryCatch({force(expr); NULL}, error=function(e) conditionMessage(e))
  stopifnot(!is.null(err), grepl(pattern, err, fixed=TRUE))
}
p <- data.frame(year=1996:2025, state='CA', population=100000)
x <- data.frame(year=1996:2025, state='CA', pathogen='STEC')
r <- prepare_analysis_inputs(x,p,p,'STEC',subgroup='nonO157')
stopifnot(identical(r$years,2000:2025), min(r$cases$year)==2000,
          min(r$census$year)==2000, sum(r$excluded$records)==4,
          r$coverage$surveillance_start_year==2000)
# Neither O157 nor the combined model receives an invented start-date change.
for (sg in c('O157','combined','NOT SEROGROUPED')) {
  r <- prepare_analysis_inputs(x,p,p,'STEC',subgroup=sg)
  stopifnot(identical(r$years,1996:2025),nrow(r$cases)==30)
}
# Eligibility is necessary even when the supplied extract has no later cases.
x <- x[x$year<=2023,];x$pathogen <- 'CAMPYLOBACTER'
r <- prepare_analysis_inputs(x,p,p,'CAMPYLOBACTER',observation_years=1996:2025)
stopifnot(identical(r$years,1996:2023),max(r$census$year)==2023,
          nrow(r$excluded)==0,r$coverage$surveillance_end_year==2023,
          grepl('reporting changed',r$coverage$reason))
x <- rbind(x,transform(x[x$year==2023,],year=2024))
r <- prepare_analysis_inputs(x,p,p,'CAMPYLOBACTER')
stopifnot(sum(r$excluded$records)==1,max(r$cases$year)==2023)
# A culture-only label cannot silently certify comparability after the change.
x$cxcidt <- 'CX+'
stopifnot(max(prepare_analysis_inputs(x,p,p,'CAMPYLOBACTER')$years)==2023)
for (path in c('LISTERIA','SHIGELLA','VIBRIO','YERSINIA','CYCLOSPORA')) {
  x <- data.frame(year=2024:2025,state='CA',pathogen=path,cste='YES')
  expect_error(prepare_analysis_inputs(x,p,p,path,parasite_end_year=2025),
               'reporting became optional')
  r <- prepare_analysis_inputs(x,p,p,path,parasite_end_year=2025,observation_years=2024L)
  stopifnot(identical(r$years,2024L),nrow(r$cases)==1,r$cases$year==2024,
            sum(r$excluded$records)==1)
}
# The known Crypto ending applies before optional-reporting checks.
x <- data.frame(year=c(2017,2025),state='CA',pathogen='CRYPTOSPORIDIUM')
r <- prepare_analysis_inputs(x,p,p,'CRYPTOSPORIDIUM',parasite_end_year=2025)
stopifnot(identical(r$years,2017L),nrow(r$cases)==1,
          r$coverage$surveillance_end_year==2017)
expect_error(prepare_analysis_inputs(x,p,p,'CRYPTOSPORIDIUM',observation_years=2018:2025),
             'No analysis years remain')
# Yersinia did not follow the statewide Colorado expansion.
co <- expand.grid(year=2022:2024,cofip=c(1,3))
co$state <- 'CO';co$stfip<-8;co$county<-ifelse(co$cofip==1,'ADAMS','ARAPAHOE');co$population<-100
expanded <- rbind(co,transform(co[co$year>=2023 & co$cofip==1,],cofip=5,county='EXPANSION'))
x <- data.frame(year=2022:2024,state='CO',county='ADAMS',siteid='CO',pathogen='YERSINIA')
expect_error(prepare_analysis_inputs(x,expanded,expanded,'YERSINIA','expanded'),
             'seven historical counties')
r <- prepare_analysis_inputs(x,co,co,'YERSINIA','historical')
stopifnot(nrow(r$cases)==3,all(r$census$population==200))
# Historical 2004-2019 scopes common to the paper/pilots retain all eligible years.
for (path in c('SALMONELLA','STEC','CAMPYLOBACTER','CYCLOSPORA','LISTERIA','SHIGELLA','VIBRIO','YERSINIA')) {
  x <- data.frame(year=2004:2019,state='CA',pathogen=path,cste='YES')
  r <- prepare_analysis_inputs(x,p,p,path)
  stopifnot(identical(r$years,2004:2019),nrow(r$cases)==16,nrow(r$excluded)==0)
}
cat('PASS surveillance boundaries, zero-free unobserved years, explicit optional windows, and unchanged historical scopes\n')
# Early pre-fit guard sees the actual grid after a custom site's window is applied.
stopifnot(assert_baseline_available(c(2016,2017,2018),2016,2018))
expect_error(assert_baseline_available(c(2017,2018),2016,2018),'2016')
expect_error(assert_baseline_available(c(2016,2018),2016,2018),'2017')
expect_error(assert_baseline_available(integer(),2016,2018),'2016, 2017, 2018')
expect_error(assert_baseline_available(2016:2018,2018,2016),'ordered pair')
x <- data.frame(year=2023:2025,state='CA',pathogen='LISTERIA',cste='YES')
r <- prepare_analysis_inputs(x,p,p,'LISTERIA',analysis_end_year=2024L)
stopifnot(identical(r$years,2023:2024),max(r$cases$year)==2024,
          max(r$census$year)==2024,sum(r$excluded$records)==1)
expect_error(prepare_analysis_inputs(x,p,p,'LISTERIA',analysis_end_year=2024.5),
             'analysis_end_year must be an integer')
expect_error(prepare_analysis_inputs(x,p,p,'LISTERIA',analysis_end_year=2022),
             'No analysis years remain')
# A user-selected end cannot extend a pathogen's known observation boundary.
x$pathogen <- 'CAMPYLOBACTER'
r <- prepare_analysis_inputs(x,p,p,'CAMPYLOBACTER',analysis_end_year=2024L)
stopifnot(identical(r$years,2023L),max(r$cases$year)==2023)
# Expanded coverage requires every statewide county, even if only one has cases.
historical_codes <- c(1L,5L,13L,14L,31L,35L,59L)
statewide_codes <- c(seq.int(1L,125L,2L),14L)
make_co <- function(year,codes) data.frame(year=year,state='CO',stfip=8L,cofip=codes,
 county=paste0('COUNTY',codes),population=1000)
full <- rbind(make_co(2022L,historical_codes),make_co(2023L,statewide_codes))
co_cases <- data.frame(year=2023L,state='CO',county='COUNTY1',siteid='CO',pathogen='SALMONELLA')
r <- prepare_analysis_inputs(co_cases,full,full,'SALMONELLA',colorado_coverage='expanded')
stopifnot(r$census$population==64000,nrow(r$cases)==1L)
partial <- rbind(make_co(2022L,historical_codes),make_co(2023L,c(historical_codes,3L)))
expect_error(prepare_analysis_inputs(co_cases,partial,partial,'SALMONELLA',colorado_coverage='expanded'),'all 64 county denominators')
missing_broomfield <- full[!(full$year==2023L & full$cofip==14L),]
expect_error(prepare_analysis_inputs(co_cases,missing_broomfield,missing_broomfield,'SALMONELLA',colorado_coverage='expanded'),'all 64 county denominators')
wrong <- full;wrong$cofip[wrong$year==2023L & wrong$cofip==125L]<-127L
expect_error(prepare_analysis_inputs(co_cases,wrong,wrong,'SALMONELLA',colorado_coverage='expanded'),'all 64 county denominators')
cat('Exact expanded Colorado footprint, missing county and wrong identifier checks passed.\n')
