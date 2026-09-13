source('scripts/refit_surveillance_sampler.R')
error_contains<-function(expr,pattern) {
  error<-tryCatch({force(expr);NULL},error=function(e)conditionMessage(e))
  stopifnot(!is.null(error),grepl(pattern,error,fixed=TRUE))
}
sim<-list(chains=6L,iter=10001L,warmup=5000L,thin=1L)
args<-replicate(6,list(seed=123L,control=list(adapt_delta=.999,max_treedepth=15L)),simplify=FALSE)
plan<-surveillance_sampler_plan(sim,args)
stopifnot(plan$control$adapt_delta==.9999,plan$control$max_treedepth==15,
  plan$warmup==sim$warmup,plan$thin==sim$thin,plan$chains==6,plan$iter==10001,plan$seed==123,plan$cores==12)
bad<-sim;bad$chains<-2L;error_contains(surveillance_sampler_plan(bad,args),'six chains')
bad<-args;bad[[2]]$control$max_treedepth<-16L
error_contains(surveillance_sampler_plan(sim,bad),'chain controls differ')
bad<-args;bad[[1]]$seed<-124L;error_contains(surveillance_sampler_plan(sim,bad),'seed')
old<-list(data=data.frame(year=2010:2012,state=factor(c('CA','CO','CT')),count=c(1,2,3),population=10000),
  prior=data.frame(prior='inv_gamma(0.4,0.3)'),code='unchanged Stan program')
new<-old;attr(new$data,'data_name')<-'old$data'
stopifnot(all(sampler_model_identity(old,new,function(x)x$code)))
new$data$count[1]<-0
stopifnot(!sampler_model_identity(old,new,function(x)x$code)[['same_data']])
new<-old;new$prior$prior<-'normal(0,1)'
stopifnot(!sampler_model_identity(old,new,function(x)x$code)[['same_priors']])
new<-old;new$code<-'different model'
stopifnot(!sampler_model_identity(old,new,function(x)x$code)[['same_stan_code']])
b<-tempfile('sampler-checkpoint-test-');dir.create(b);path<-file.path(b,'checkpoint.rds')
save_sampler_checkpoint(old,path);stopifnot(identical(readRDS(path),old))
error_contains(save_sampler_checkpoint(new,path),'overwrite')
stopifnot(identical(readRDS(path),old),length(list.files(b,all.files=TRUE,no..=TRUE))==1)
before<-data.frame(year=2010:2012,population=10000,raw_count=1:3,raw_ir=(1:3)*10,median_ir=c(11,20,32),pathogen='TEST')
after<-before;after$median_ir<-c(12,19,33)
comparison<-compare_sampler_exports(before,after)
stopifnot(identical(comparison$median_ir_difference,c(1,-1,1)))
bad<-after;bad$raw_count[1]<-0;error_contains(compare_sampler_exports(before,bad),'Observed data or baseline changed')
bad<-after[-1,];error_contains(compare_sampler_exports(before,bad),'keys changed')
value<-after[3:1,setdiff(names(after),'pathogen')]
labelled<-preserve_sampler_labels(value,before)
stopifnot(all(labelled$pathogen=='TEST'),identical(labelled$year,3:1+2009L))
unlink(b,recursive=TRUE)
cat('PASS fixed sampler schedule/control, data/prior/code identity, immutable atomic checkpoint, exact observation comparisons and label joins\n')
stopifnot(sampler_controls_match(list(max_treedepth=15,adapt_delta=.9999),list(adapt_delta=.9999,max_treedepth=15L)))
stopifnot(!sampler_controls_match(list(max_treedepth=15,adapt_delta=.999),list(adapt_delta=.9999,max_treedepth=15L)))
stopifnot(!sampler_controls_match(list(adapt_delta=.9999),list(adapt_delta=.9999,max_treedepth=15L)))
cat('PASS reordered/equivalent controls accepted; changed/missing controls rejected\n')
