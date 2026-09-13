for(x in parse('bin/functions.R'))if(is.call(x)&&identical(x[[1]],as.name('<-'))&&
  identical(x[[2]],as.name('WRITE_STATE_EXPORT_MANIFEST')))eval(x)
primary<-WRITE_STATE_EXPORT_MANIFEST
source('scripts/refit_surveillance_sampler.R')
stopifnot(identical(body(primary),body(WRITE_STATE_EXPORT_MANIFEST)))
d<-tempfile();dir.create(d)
fit<-file.path(d,'TEST_brm.Rds');writeLines('fixture posterior',fit)
for(suffix in c('_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv','_analysis_settings.csv',
 '_population_used.csv','_classification_rules.csv','_convergence_diagnostics.csv'))writeLines('fixture',file.path(d,paste0('TEST',suffix)))
z<-WRITE_STATE_EXPORT_MANIFEST(fit,d,'TEST',2019,2019)
stopifnot(nrow(z)==7L,all(z$fit_sha256==digest::digest(file=fit,algo='sha256')),
 all(z$sha256==vapply(file.path(d,z$file),function(p)digest::digest(file=p,algo='sha256'),character(1))))
unlink(file.path(d,'TEST_IRCatch.csv'))
stopifnot(inherits(try(WRITE_STATE_EXPORT_MANIFEST(fit,d,'TEST',2019,2019),silent=TRUE),'try-error'))
unlink(d,recursive=TRUE)
cat('PASS contemporaneous saved-fit binding and self-contained sampler snapshot helper\n')
# Exercise recovery control flow with deterministic export substitutes, no sampler.
source('scripts/reexport_saved_state_tables.R')
b<-tempfile();dir.create(b);old<-file.path(b,'old');dir.create(old);new<-file.path(b,'new')
model<-structure(list(data=data.frame(year=2019L,state='CA',count=2,population=100)),class='brmsfit')
saveRDS(model,file.path(old,'TEST_brm.Rds'))
write.csv(data.frame(baseline_start=2019,baseline_end=2019),file.path(old,'TEST_analysis_settings.csv'),row.names=FALSE)
write.csv(data.frame(year=2019L,state='CA',population=100),file.path(old,'TEST_population_used.csv'),row.names=FALSE)
write.csv(data.frame(classification='fixture'),file.path(old,'TEST_classification_rules.csv'),row.names=FALSE)
for(s in c('_IRCatch.csv','_IRSite.csv'))write.csv(data.frame(year=2019L,state='CA',raw_count=999,pathogen='TEST'),file.path(old,paste0('TEST',s)),row.names=FALSE)
before<-vapply(list.files(old,full.names=TRUE),function(p)digest::digest(file=p,algo='sha256'),character(1))
LINPREAD_DRAW_FN<-function(data,model)data
CATCHMENT<-function(d)d
LINPRED_TO_SITEIR<-function(d)data.frame(year=d$year,state=d$state,raw_count=d$count)
LINPRED_TO_CATCHIR<-LINPRED_TO_SITEIR
IR_COMP_CATCH<-function(d,bs,be,path)write.csv(d,path,row.names=FALSE)
CHECK_CONVERGENCE<-function(model,key,out)write.csv(data.frame(converged=TRUE),file.path(out,paste0(key,'_convergence_diagnostics.csv')),row.names=FALSE)
reexport_saved_state_tables(old,new,'TEST')
stopifnot(read.csv(file.path(new,'TEST_IRCatch.csv'))$raw_count==2,
 identical(before,vapply(list.files(old,full.names=TRUE),function(p)digest::digest(file=p,algo='sha256'),character(1))),
 file.exists(file.path(new,'TEST_fit_export_manifest.csv')))
stopifnot(inherits(try(reexport_saved_state_tables(old,new,'TEST'),silent=TRUE),'try-error'))
unlink(b,recursive=TRUE)
cat('PASS saved-posterior re-export recomputes tables, preserves originals and refuses existing destination\n')
