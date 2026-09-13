source('scripts/county_matching.R');source('scripts/review_county_histories.R')
p<-data.frame(fips=c('01001','01001','01003'),year=c(2004,2005,2004),count=c(1,0,1))
n<-data.frame(fips=c('01001','01003'),state='AA')
x<-data.frame(fips=c('1001','01003','','01001'),year=2004,state='AA',county=c('ONE','TWO','UNKNOWN','ONE'),
 pathogen='SALMONELLA',travelint=c('NO','YES','NO','EXCLUDED'),cxcidt='CX+')
y<-source_history(x,p,n)
stopifnot(sum(y$selected)==2,sum(y$flow$records)==4,any(y$flow$geography=='missing_fips'))
bad<-p;bad$count[2]<-1
stopifnot(inherits(try(source_history(x,bad,n),silent=TRUE),'try-error'))
x$state[1]<-'BB'
stopifnot(inherits(try(source_history(x,p,n),silent=TRUE),'try-error'))
cat('PASS exact county/year reconciliation, zero preservation, exclusions and mismatched state rejection\n')
