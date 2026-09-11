process DASHBOARD {
    tag "Generating results dashboard"
    label 'process_low'
    container 'foodnet.sif'

    input:
    path results, stageAs: 'results/*'
    path metadata, stageAs: 'metadata/*'
    path cleanFile, stageAs: 'metadata/clean_mmwr.csv'
    val projID

    output:
    path "dashboard.html", emit: html

    script:
    def quote = { value -> "'" + value.toString().replace("'", "'\"'\"'") + "'" }
    def outputDir = file(params.outdir).resolve(projID.toString())
    def keys = ['mmwrFile', 'censusFileB', 'censusFileP', 'pathogen', 'pathogen_grouping',
                'chains', 'iterations', 'adapt_delta', 'max_treedepth', 'seed', 'stan_backend',
                'travel', 'cidt', 'states', 'travel_stratify', 'baseline_year', 'baseline_start',
                'baseline_end', 'colorado_coverage', 'parasite_end_year', 'classification_rules', 'serotype_source', 'serotype_config',
                'catchment_config', 'data_rules', 'matching_sensitivity', 'preprocessed', 'cleanFile']
    def runParams = keys.collectEntries { key -> [(key): params[key]] }
    runParams['outdir'] = params.outdir
    def paramsJson = groovy.json.JsonOutput.toJson(runParams)
    """
    cat > .pipeline_params.json << 'PARAMS_EOF'
    ${paramsJson}
    PARAMS_EOF

    Rscript ${quote(workflow.projectDir + '/dashboard/generate_dashboard.R')} \\
      --output_dir ${quote(outputDir)} \\
      --results_dir results \\
      --preprocessed_dir metadata \\
      --projID ${quote(projID)} \\
      --pipeline_params .pipeline_params.json \\
      --output dashboard.html
    """
}
