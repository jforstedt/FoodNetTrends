#!/usr/bin/env Rscript
# Opt-in geography validation and BYM2 county-intercept adapter.
# Source existing monthly and spline fitters first; accepted fit paths stay IID.
monthly_spatial_graph <- function(d,nodes,edges) {
  ids<-sort(unique(as.character(d$area)))
  if(!all(c('fips','state')%in%names(nodes))||!all(c('fips_a','fips_b')%in%names(edges)))stop('Missing graph columns')
  nodes$fips<-as.character(nodes$fips);nodes$state<-as.character(nodes$state)
  edges$fips_a<-as.character(edges$fips_a);edges$fips_b<-as.character(edges$fips_b)
  if(anyNA(nodes[c('fips','state')])||anyDuplicated(nodes$fips)||!setequal(ids,nodes$fips))stop('Graph nodes differ from modeled counties')
  if(anyNA(edges[c('fips_a','fips_b')])||any(!edges$fips_a%in%ids)|any(!edges$fips_b%in%ids)||
     any(edges$fips_a>=edges$fips_b)||anyDuplicated(edges[c('fips_a','fips_b')]))stop('Invalid graph edges')
  expected<-nodes$state[match(as.character(d$area),nodes$fips)]
  if(anyNA(d$state)||any(as.character(d$state)!=expected))stop('Graph county/state mapping differs')
  A<-matrix(0,length(ids),length(ids),dimnames=list(ids,ids))
  a<-match(edges$fips_a,ids);b<-match(edges$fips_b,ids)
  A[cbind(a,b)]<-1;A[cbind(b,a)]<-1
  if(any(rowSums(A)==0))stop('Isolated counties require a separately specified prior; this adapter rejects them')
  component<-integer(length(ids));ncomp<-0L
  for(i in seq_along(ids))if(component[i]==0L) {
    ncomp<-ncomp+1L;todo<-i;component[i]<-ncomp
    while(length(todo)) {
      j<-todo[1];todo<-todo[-1];new<-which(A[j,]>0&component==0L)
      component[new]<-ncomp;todo<-c(todo,new)
    }
  }
  list(ids=ids,adj=A,components=component,n_components=ncomp,n_edges=nrow(edges),
    specification=list(version='monthly_static_bym2_v1',sd_upper=1,sd_tail=.01,
      phi_u=.5,phi_probability=.5,scale_model=TRUE,component_constraints=TRUE,
      cross_state_edges=sum(nodes$state[match(edges$fips_a,nodes$fips)]!=nodes$state[match(edges$fips_b,nodes$fips)])))
}

monthly_bym2_effect <- function(graph) {
  force(graph)
  function(formula,data) {
    if(!identical(sort(unique(as.integer(data$area))),seq_along(graph$ids)))stop('Spatial index mapping differs')
    if(!requireNamespace('INLA',quietly=TRUE))stop('INLA required')
    g<-INLA::inla.read.graph(Matrix::Matrix(diag(rowSums(graph$adj))-graph$adj,sparse=TRUE))
    replacement<-quote(f(area,model='bym2',graph=.monthly_bym2_graph,scale.model=TRUE,constr=TRUE,
      adjust.for.con.comp=TRUE,hyper=list(prec=list(prior='pc.prec',param=c(1,.01)),
        phi=list(prior='pc',param=c(.5,.5)))))
    environment(formula)<-list2env(list(.monthly_bym2_graph=g),parent=environment(formula))
    found<-0L
    replace<-function(x) {
      if(!is.call(x))return(x)
      if(identical(x[[1]],as.name('f'))&&length(x)>1&&identical(x[[2]],as.name('area'))) {
        found<<-found+1L;return(replacement)
      }
      for(i in seq_along(x)[-1])x[[i]]<-replace(x[[i]])
      x
    }
    formula[[3]]<-replace(formula[[3]])
    if(found!=1L)stop('Expected exactly one county effect')
    formula
  }
}

fit_monthly_spatial_combination <- function(d,cutoff,nodes,edges,temporal='rw1',seasonal=TRUE,
  threads=4L,coverage='SYNTHETIC_COMPLETE',basis=NULL) {
  if(length(temporal)!=1||!temporal%in%c('rw1','ar1','spline'))stop('Invalid temporal model')
  graph<-monthly_spatial_graph(d,nodes,edges);effect<-monthly_bym2_effect(graph)
  if(temporal=='spline') {
    fit<-fit_monthly_combination(d,cutoff,temporal='spline',seasonal=seasonal,threads=threads,
      coverage=coverage,basis=basis,area_effect=effect)
  } else {
    fit<-fit_monthly_model(d,cutoff,seasonal=seasonal,threads=threads,coverage=coverage,
      rate_center=.0002,temporal_model=temporal,area_effect=effect)
  }
  attr(fit,'monthly_spatial_specification')<-c(graph$specification,list(ids=graph$ids,
    n_components=graph$n_components,n_edges=graph$n_edges,temporal=temporal,seasonal=seasonal,
    county_temporal=FALSE))
  fit
}
