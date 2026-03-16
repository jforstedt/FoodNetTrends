process DASHBOARD {
    tag "Generating results dashboard"
    label 'process_low'
    container 'foodnet.sif'

    input:
    val ready      // synchronization signal — ensures all TRENDY jobs are done
    val projID

    output:
    path "dashboard.html", emit: html

    script:
    def cleanFileArg = params.preprocessed && params.cleanFile ? "--cleanFile ${launchDir}/${params.cleanFile}" : ""
    """
    # Write pipeline params for dashboard re-run command
    cat > .pipeline_params.json << 'PARAMS_EOF'
    {
      "mmwrFile": "${params.mmwrFile ?: ''}",
      "censusFileB": "${params.censusFileB ?: ''}",
      "censusFileP": "${params.censusFileP ?: ''}",
      "pathogen": "${params.pathogen ?: ''}",
      "chains": ${params.chains ?: 2},
      "iterations": ${params.iterations ?: 500},
      "adapt_delta": ${params.adapt_delta ?: 0.95},
      "max_treedepth": ${params.max_treedepth ?: 10},
      "seed": ${params.seed ?: 123},
      "stan_backend": "${params.stan_backend ?: 'rstan'}",
      "travel": "${params.travel ?: 'NO,UNKNOWN,YES'}",
      "cidt": "${params.cidt ?: 'CIDT+,CX+,PARASITIC'}"
    }
    PARAMS_EOF

    Rscript ${workflow.projectDir}/dashboard/generate_dashboard.R \
      --output_dir ${launchDir}/${params.outdir}/${projID} \
      --projID ${projID} \
      ${cleanFileArg} \
      --pipeline_params .pipeline_params.json \
      --output dashboard.html
    """
}
