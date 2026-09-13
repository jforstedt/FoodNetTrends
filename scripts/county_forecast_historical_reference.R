# Training-only constant county-rate reference. Jeffreys Gamma(1/2,0) prior
# for a Poisson rate; positive training exposure makes the posterior proper.
county_historical_reference <- function(d,cutoff,out) {
  needed<-c('fips','state','year','population','count')
  if(!all(needed %in% names(d)) || anyNA(d[needed]) || any(d$population<=0) ||
     any(!is.finite(d$population)) || any(!is.finite(d$count)) || any(d$count<0 | d$count!=floor(d$count))) stop('Invalid reference inputs')
  train<-d[d$year<=cutoff,];test<-d[d$year>cutoff,]
  if(!nrow(train)||!nrow(test))stop('Reference needs training and test observations')
  totals<-aggregate(train[c('count','population')],train['fips'],sum)
  ix<-match(test$fips,totals$fips);if(anyNA(ix))stop('No training history for forecast county')
  shape<-totals$count[ix]+.5;prob<-totals$population[ix]/(totals$population[ix]+test$population)
  z<-test[c('fips','state','year','population')];z$observed<-test$count
  z$mean_expected<-shape*(1-prob)/prob
  z$lower95<-qnbinom(.025,size=shape,prob=prob);z$upper95<-qnbinom(.975,size=shape,prob=prob)
  z$lower50<-qnbinom(.25,size=shape,prob=prob);z$upper50<-qnbinom(.75,size=shape,prob=prob)
  z$median<-qnbinom(.5,size=shape,prob=prob)
  z$log_predictive_density<-dnbinom(z$observed,size=shape,prob=prob,log=TRUE)
  z$predicted_zero_probability<-dnbinom(0,size=shape,prob=prob)
  z$zero_brier<-(z$predicted_zero_probability-as.integer(z$observed==0))^2
  z$covered95<-z$observed>=z$lower95 & z$observed<=z$upper95
  z$covered50<-z$observed>=z$lower50 & z$observed<=z$upper50
  if(any(!is.finite(z$log_predictive_density)))stop('Nonfinite reference log score')
  dir.create(out,recursive=TRUE,showWarnings=FALSE)
  write.csv(z,file.path(out,'historical_reference_cells_INTERNAL.csv'),row.names=FALSE)
  writeLines(c('Training-only constant county Poisson rate; Jeffreys Gamma(0.5,0) rate prior.',
    'Gamma-Poisson predictive probabilities are evaluated analytically.',
    'Known future population exposures; no held-out outcomes used for parameters.',
    'This is a simple benchmark, not the published state spline or an adopted incidence model.'),file.path(out,'historical_reference_specification.txt'))
  invisible(z)
}
