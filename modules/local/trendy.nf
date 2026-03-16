process TRENDY {
    tag "${pathogen}${subgroup != 'combined' ? ' (' + subgroup + ')' : ''}"
    shell "/bin/bash"
    container 'foodnet.sif'

    input:
    tuple val(pathogenGrouping), val(pathogen), val(subgroup), val(dataMetrics)
    path mmwrFile
    path censusFileB
    path censusFileP
    val travel
    val cidt
    val states
    val projID
    val whichScript
    val preprocessed
    path cleanFile
    path catchmentConfig

    output:
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_brm.Rds", emit: rds, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_IRCatch.csv", emit: csv, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_IRSite.csv", emit: irsite, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}*.png", emit: png, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}*_EstIRRCatch_*.csv", emit: irr, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_summary.txt", emit: summary, optional: true
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_error.txt", optional: true, emit: errors
    path "${pathogenGrouping.replaceAll('[^a-zA-Z0-9_-]', '_').replaceAll('_+', '_').replaceAll('_$', '')}_convergence_diagnostics.csv", emit: diagnostics, optional: true

    errorStrategy { task.exitStatus in [143,137,104,134,140] ? 'retry' : 'finish' }
    maxRetries 3

    // Chain-based memory: each chain needs ~10 GB + 8 GB overhead
    memory = {
        def chains = params.chains ?: 2
        def req = ((chains * 10 + 8) as int).GB * task.attempt
        def max = params.max_memory as nextflow.util.MemoryUnit
        return req > max ? max : req
    }

    // One CPU per chain, plus BLAS bonus for large datasets
    cpus = {
        def chains = params.chains ?: 2
        def rows = dataMetrics?.rows ?: 10000
        def bonus = rows > 50000 ? 2 : 0
        return Math.min(chains + bonus, params.max_cpus as int)
    }

    // Difficulty-based time allocation from resource profiler metrics
    time = {
        def cat = dataMetrics?.difficulty_category ?: 'moderate'
        def base = cat == 'very_hard' ? 72.h :
                   cat == 'hard' ? 48.h :
                   cat == 'moderate' ? 24.h : 12.h
        def req = base * task.attempt
        def max = params.max_time as nextflow.util.Duration
        return req > max ? max : req
    }

    script:
    // Log resource allocation for this pathogen
    log.info "Pathogen: ${pathogen}, Rows: ${dataMetrics?.rows ?: 'unknown'}, " +
             "Difficulty: ${dataMetrics?.difficulty_category ?: 'unknown'}, " +
             "Allocated CPUs: ${task.cpus}, Memory: ${task.memory}, Time: ${task.time}"
    
    // Properly handle the cleanFile parameter
    def cleanFileParam = ""
    if (preprocessed) {
        if (cleanFile && !cleanFile.name.startsWith('NO_')) {
            cleanFileParam = "--cleanFile ${cleanFile}"
        } else {
            error "Preprocessing enabled but no clean file provided for pathogen: ${pathogen}"
        }
    }
    
    // Handle catchment config parameter
    def catchmentConfigArg = catchmentConfig.name.startsWith('NO_') ? "" : "--catchment-config ${catchmentConfig}"
    
    // Handle states parameter (empty string means all states)
    def statesArg = states ? "--states ${states}" : ""

    """
    # Copy functions.R to the current directory
    cp ${workflow.projectDir}/bin/functions.R .

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
    export OPENBLAS_NUM_THREADS=\$((${task.cpus} / ${params.chains}))

    Rscript ${whichScript} \\
      --mmwrFile ${mmwrFile} \\
      --censusFileB ${censusFileB} \\
      --censusFileP ${censusFileP} \\
      --travel ${travel} \\
      --cidt ${cidt} \\
      ${statesArg} \\
      --projID ${projID} \\
      --outDir . \\
      --pathogen ${pathogen} \\
      --subgroup '${subgroup}' \\
      --preprocessed ${preprocessed} \\
      ${cleanFileParam} \\
      --cores ${task.cpus} \\
      --chains ${params.chains} \\
      --iterations ${params.iterations} \\
      --adapt_delta ${params.adapt_delta} \\
      --max_treedepth ${params.max_treedepth} \\
      --seed ${params.seed} \\
      --backend ${params.stan_backend} \\
      ${catchmentConfigArg} \\
      --debug FALSE
    """
}
