process TRENDY {
    tag "${pathogen}${subgroup != 'combined' ? ' (' + subgroup + ')' : ''}"
    shell "/bin/bash"
    container 'foodnet.sif'

    input:
    tuple val(pathogenGrouping), val(pathogen), val(subgroup), val(dataMetrics)
    path mmwrFile, stageAs: 'raw/*'
    path censusFileB, stageAs: 'census_b/*'
    path censusFileP, stageAs: 'census_p/*'
    val travel
    val cidt
    val states
    val projID
    val whichScript
    val preprocessed
    path cleanFile, stageAs: 'clean/*'
    path catchmentConfig
    path classificationRules

    output:
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_brm.Rds", emit: rds, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}*_IRCatch.csv", emit: csv, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}*_IRSite.csv", emit: irsite, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}*.png", emit: png, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}*_EstIRRCatch_*.csv", emit: irr, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_summary.txt", emit: summary, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_error.txt", optional: true, emit: errors
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_convergence_diagnostics.csv", emit: diagnostics, optional: true

    path "*_classification_report.csv", emit: classificationReport, optional: true
    path "*_classification_rules.csv", emit: classificationRulesUsed, optional: true
    path "*_analysis_settings.csv", emit: settings, optional: true
    path "*_input_exclusions.csv", emit: inputExclusions, optional: true
    path "*_population_used.csv", emit: populationUsed, optional: true
    path "*_domestic_convergence_diagnostics.csv", emit: domesticDiagnostics, optional: true
    path "*_travel_convergence_diagnostics.csv", emit: travelDiagnostics, optional: true

    // errorStrategy and maxRetries defined in nextflow.config withName:TRENDY

    // Resources are configured explicitly in conf/modules.config.

    script:
    def quote = { value -> "'" + value.toString().replace("'", "'\"'\"'") + "'" }
    def reserved = ['combined', 'OTHER SEROTYPES', 'NOT SEROTYPED', 'TYPHOIDAL', 'NONTYPHOIDAL', 'UNCLASSIFIED']
    def selectedSerotypes = (params.pathogen_grouping ?: '').tokenize('|')
        .collect { it.split('~', 2) }
        .findAll { it.size() == 2 && it[0] == 'SALMONELLA' && !(it[1] in reserved) }
        .collect { it[1] }.unique().join('|')
    def baselineStart = params.baseline_year != null ? params.baseline_year : params.baseline_start
    def baselineEnd = params.baseline_year != null ? params.baseline_year : params.baseline_end
    // Log resource allocation for this pathogen
    log.info "Pathogen: ${pathogen}, Rows: ${dataMetrics?.rows ?: 'unknown'}, " +
             "Difficulty: ${dataMetrics?.difficulty_category ?: 'unknown'}, " +
             "Allocated CPUs: ${task.cpus}, Memory: ${task.memory}, Time: ${task.time}"
    
    // Properly handle the cleanFile parameter
    def cleanFileParam = ""
    if (preprocessed) {
        if (cleanFile && !cleanFile.name.startsWith('NO_')) {
            cleanFileParam = "--cleanFile ${quote(cleanFile)}"
        } else {
            error "Preprocessing enabled but no clean file provided for pathogen: ${pathogen}"
        }
    }
    
    // Handle catchment config parameter
    def catchmentConfigArg = catchmentConfig.name.startsWith('NO_') ? "" : "--catchment-config ${quote(catchmentConfig)}"
    
    // Handle states parameter (empty string means all states)
    def statesArg = states ? "--states ${quote(states)}" : ""

    """
    # Copy functions.R to the current directory
    cp ${quote(workflow.projectDir + '/bin/functions.R')} .

    if [ ! -f functions.R ]; then
        echo "Error: Failed to copy functions.R"
        exit 1
    fi

    # Copy CmdStan to writable work dir (container filesystem is read-only)
    if [ "${params.stan_backend}" = "cmdstanr" ] && [ -d /opt/cmdstan ]; then
        cp -r /opt/cmdstan/cmdstan-* .cmdstan_local
        export CMDSTAN=\$(pwd)/.cmdstan_local
    fi

    # Use extra CPUs beyond chain count for BLAS threading
    export OPENBLAS_NUM_THREADS=${Math.max(1, (task.cpus / (params.chains as int)).intValue())}

    Rscript ${quote(whichScript)} \\
      --mmwrFile ${quote(mmwrFile)} \\
      --censusFileB ${quote(censusFileB)} \\
      --censusFileP ${quote(censusFileP)} \\
      --travel ${quote(travel)} \\
      --cidt ${quote(cidt)} \\
      ${statesArg} \\
      --projID ${quote(projID)} \\
      --outDir . \\
      --pathogen ${quote(pathogen)} \\
      --subgroup ${quote(subgroup)} \\
      --preprocessed ${preprocessed} \\
      ${cleanFileParam} \\
      --cores ${task.cpus} \\
      --chains ${params.chains} \\
      --iterations ${params.iterations} \\
      --adapt_delta ${params.adapt_delta} \\
      --max_treedepth ${params.max_treedepth} \\
      --seed ${params.seed} \\
      --backend ${params.stan_backend} \\
      --colorado_coverage ${quote(params.colorado_coverage)} \\
      --parasite_end_year ${params.parasite_end_year} \\
      --baseline_start ${baselineStart} \\
      --baseline_end ${baselineEnd} \\
      --classification_rules ${quote(classificationRules)} \\
      --serotype_source ${quote(params.serotype_source)} \\
      --selected_serotypes ${quote(selectedSerotypes)} \\
      --travel_stratify ${params.travel_stratify} \\
      ${catchmentConfigArg} \\
      --debug FALSE
    """
}
