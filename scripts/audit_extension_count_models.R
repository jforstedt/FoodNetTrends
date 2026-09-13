# Descriptive support audit only; no likelihood selection or prior tuning.
audit_extension_count_models <- function(obj,pathogen) {
  d<-obj$data;needed<-c('year','state','fips','population','count')
  if(!all(needed%in%names(d))||!nrow(d)||anyNA(d[needed])||
     any(!is.finite(d$population)|d$population<=0)||any(!is.finite(d$count)|d$count<0|d$count!=floor(d$count))||
     any(!is.finite(d$year)|d$year!=floor(d$year)))stop('Invalid audited county panel')
  ids<-as.character(obj$ids);years<-sort(unique(d$year));key<-paste(d$fips,d$year)
  if(length(years)<3||!identical(as.numeric(years),as.numeric(seq(min(years),max(years))))||
     anyDuplicated(ids)||anyDuplicated(key)||!setequal(key,with(expand.grid(fips=ids,year=years),paste(fips,year))))stop('Incomplete county-year observation grid')
  adj<-obj$adj
  if(!is.matrix(adj)||!identical(dim(adj),c(length(ids),length(ids)))||anyNA(adj)||any(!adj%in%c(0,1))||
     any(adj!=t(adj))||any(diag(adj)!=0))stop('Invalid county adjacency')
  components<-integer(length(ids));component<-0L
  for(i in seq_along(ids))if(components[i]==0L) {
    component<-component+1L;todo<-i;components[i]<-component
    while(length(todo)) {
      j<-todo[1];todo<-todo[-1];neighbors<-which(adj[j,]>0&components==0L)
      components[neighbors]<-component;todo<-c(todo,neighbors)
    }
  }
  summarize<-function(z) data.frame(pathogen=pathogen,state=as.character(z$state[1]),year=z$year[1],
    observed_county_cells=nrow(z),total_count=sum(z$count),zero_fraction=mean(z$count==0),
    mean_count=mean(z$count),variance_count=if(nrow(z)>1)var(z$count)else NA_real_,
    count_q50=unname(quantile(z$count,.5)),count_q95=unname(quantile(z$count,.95)),
    population_min=min(z$population),population_q50=unname(quantile(z$population,.5)),population_max=max(z$population))
  state_year<-do.call(rbind,lapply(split(d,interaction(d$state,d$year,drop=TRUE)),summarize))
  histories<-lapply(split(d,d$fips),function(z) {
    if(length(unique(z$state))!=1L)stop('County state assignment changes')
    data.frame(state=as.character(z$state[1]),years=nrow(z),nonzero_years=sum(z$count>0),total=sum(z$count))
  })
  h<-do.call(rbind,histories)
  support<-do.call(rbind,lapply(split(h,h$state),function(z)data.frame(pathogen=pathogen,state=z$state[1],counties=nrow(z),
    history_years_min=min(z$years),history_years_max=max(z$years),all_zero_histories=sum(z$total==0),
    nonzero_years_q25=unname(quantile(z$nonzero_years,.25)),nonzero_years_q50=unname(quantile(z$nonzero_years,.5)),
    total_count_q25=unname(quantile(z$total,.25)),total_count_q50=unname(quantile(z$total,.5)))))
  list(state_year_count_support=state_year,county_history_support=support,
    geography=data.frame(pathogen=pathogen,counties=length(ids),components=component,isolated_counties=sum(rowSums(adj)==0),
      edges=sum(adj)/2,neighbors_min=min(rowSums(adj)),neighbors_median=median(rowSums(adj)),neighbors_max=max(rowSums(adj))),
    interpretation=data.frame(topic=c('scope','zeros','spline','priors','distribution','spatial'),
      limitation=c('Descriptive audit of already reviewed historical panels; not independent forecast evidence or model approval.',
      'Observed zeros only within validated complete panels; structural zeros cannot be inferred from zero frequency.',
      'History length and sparsity describe support; they do not establish that independent county curves are identifiable.',
      'No priors selected; future tuning must use training-only data and independent domain knowledge.',
      'Raw count variance includes differing exposures and trends; it cannot select a likelihood or estimate residual overdispersion.',
      'Graph connectivity supports implementation checks, not proof of spatial predictive benefit.')))
}
