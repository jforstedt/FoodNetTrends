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
    Rscript ${workflow.projectDir}/dashboard/generate_dashboard.R \
      --output_dir ${launchDir}/${params.outdir}/${projID} \
      --projID ${projID} \
      ${cleanFileArg} \
      --output dashboard.html
    """
}
