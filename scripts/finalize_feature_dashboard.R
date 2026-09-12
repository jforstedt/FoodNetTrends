args <- commandArgs(TRUE)
stopifnot(length(args)==1)
dest <- args[1]
source(file.path(dest,'functions.R'))
manifest <- jsonlite::fromJSON(file.path(dest,'manifest.json'))
results <- file.path(dest,'spline_results')
for(key in names(manifest$analysis_sources)) {
  if(manifest$analysis_sources[[key]]!=manifest$comparison_directory) next
  setting <- read.csv(file.path(results,paste0(key,'_analysis_settings.csv')),stringsAsFactors=FALSE)
  site <- read.csv(file.path(results,paste0(key,'_IRSite.csv')))
  catch <- read.csv(file.path(results,paste0(key,'_IRCatch.csv')))
  pathogen <- setting$pathogen; subgroup <- setting$subgroup
  stable <- get_catchment_stable_year(read_catchment_config())
  p <- PLOT_SITE_TRENDS(site,pathogen,results,subgroup,stable_year=stable)
  ggplot2::ggsave(file.path(results,paste0(key,'_site_trends.png')),p,width=10,height=8,dpi=300)
  p <- PLOT_OVERALL_TREND(catch,pathogen,results,subgroup,stable_year=stable)
  ggplot2::ggsave(file.path(results,paste0(key,'_overall_trend.png')),p,width=10,height=6,dpi=300)
  for(st in unique(site$state)) {
    p <- PLOT_STATE_TREND(site,st,pathogen,results,subgroup,stable_year=stable)
    if(!is.null(p))ggplot2::ggsave(file.path(results,paste0(key,'_',st,'_trend.png')),p,width=8,height=5,dpi=300)
  }
  model <- readRDS(file.path(results,paste0(key,'_brm.Rds')))
  capture.output(summary(model),file=file.path(results,paste0(key,'_summary.txt')))
  rm(model);gc()
}
cat('Refit plots and summaries regenerated; no models fitted.\n')
