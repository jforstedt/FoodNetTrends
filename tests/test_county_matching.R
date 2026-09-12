source('scripts/county_matching.R')
p <- data.frame(year=c(2023,2023,2023,2023,2023,2023),state=c('CA','CA','CA','CT','CA','CA'),county=c('Alpha','Beta','Missing','Old county','Collision!','Collision'),fips=c('06001','06003','06005','09001','06007','06009'),population=c(100,200,NA,NA,100,100),entryyear=c(1996,2024,1996,1996,1996,1996))
cases <- data.frame(year=rep(2023,9),state=c(rep('CA',7),'CT','CA'),county=c('Alpha','Alpha','Alpha','Beta','Missing','Alpha','Collision','Old county','Other'),fips=c('6001','','06003','','06005','junk','','09001','06999'))
r <- match_county_candidates(cases,p)
stopifnot(identical(r$match_status,c('direct_fips_candidate','name_candidate_requires_review','fips_name_conflict','before_census_entryyear','missing_or_nonpositive_population','invalid_case_fips','no_unique_year_state_name_match','missing_or_nonpositive_population','no_fips_year_population_row')))
stopifnot(r$candidate_fips[1]=='06001',r$geography_review[8]=='connecticut_boundary_reconciliation',all(!r$model_ready),all(r$coverage_status=='not_verified'))
x <- cases[1,,drop=FALSE];x$state <- 'NY'
stopifnot(match_county_candidates(x,p)$match_status=='fips_state_conflict')
pdup <- rbind(p,p[1,]);stopifnot(match_county_candidates(cases[1,,drop=FALSE],pdup)$match_status=='duplicate_population_key')
x <- cases[2,,drop=FALSE];p$fips[1] <- ''
stopifnot(match_county_candidates(x,p)$match_status=='invalid_population_fips')
stopifnot(nrow(match_county_candidates(cases[FALSE,],p))==0)
cat('PASS leading zeroes, exact-name candidates, populated conflicts, invalid FIPS, ambiguous names, entry years, CT, duplicate keys, missing populations and no automatic eligibility\n')
