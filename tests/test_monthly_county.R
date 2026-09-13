source('scripts/prepare_monthly_county.R')
p<-data.frame(year=c(2004L,2005L),state='AA',fips='00001',population=c(366,365),count=c(3L,1L))
x<-data.frame(year=c(2004L,2004L,2004L,2005L),state='AA',fips='00001',dtspec=as.Date(c('2004-02-29',NA,'2005-01-01','2005-02-28')),month=c(2,1,1,3))
y<-monthly_inventory(x,p)
stopifnot(nrow(y$grid)==24L,all(is.na(y$grid$modeled_count)),all(y$grid$observation_status=='UNVERIFIED'),
 all(is.na(y$calendar$observed_days)),all(y$calendar$evidence_reference==''),
 y$grid$record_count[y$grid$year==2004&y$grid$month==2]==1L,
 y$grid$candidate_person_years[y$grid$year==2004&y$grid$month==2]==29,
 y$grid$candidate_person_years[y$grid$year==2005&y$grid$month==2]==28,
 sum(y$grid$candidate_person_years)==731,sum(y$annual$unassigned_records)==2,
 sum(y$issues$specimen_year_disagreement)==1,sum(y$issues$missing_specimen_date)==1,
 sum(y$issues$month_disagreement)==1,sum(y$grid$record_count)==2)
z<-x;z$month[1]<-2.5
stopifnot(sum(monthly_inventory(z,p)$issues$month_missing_invalid)==1L)
q<-p;q$count[1]<-4
stopifnot(inherits(try(monthly_inventory(x,q),silent=TRUE),'try-error'))
z<-x;z$dtspec<-as.character(z$dtspec)
stopifnot(inherits(try(monthly_inventory(z,p),silent=TRUE),'try-error'))
z<-x;z$fips[1]<-'99999'
stopifnot(inherits(try(monthly_inventory(z,p),silent=TRUE),'try-error'))
# A zero annual inventory still cannot authorize monthly zero observations.
p$count<-0L;z<-x[FALSE,]
a<-monthly_inventory(z,p)
stopifnot(all(a$grid$record_count==0),all(is.na(a$grid$modeled_count)))
# One source-month disagreement moves one count between months, preserving the year.
b<-data.frame(year=2004L,state='AA',fips='00001',population=366,count=1L)
r<-data.frame(year=2004L,state='AA',fips='00001',dtspec=as.Date('2004-02-29'),month=3L)
c<-monthly_inventory(r,b)$month_comparison
stopifnot(c$difference[c$month==2]==-1,c$difference[c$month==3]==1,sum(c$difference)==0)
r$month<-13L
c<-monthly_inventory(r,b)$month_comparison
stopifnot(sum(c$source_month_records)==0,sum(c$specimen_month_records)==1)
cat('Monthly candidate inventory tests PASS\n')
