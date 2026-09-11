process PREPROCESS {
    tag "Preprocessing MMWR data"
    label 'process_low'
    shell "/bin/bash"
    container 'foodnet.sif'

    publishDir "${params.outdir}/${projID}/preprocessed", mode: 'copy'

    input:
    path mmwrFile
    val projID
    path serotypeConfig
    path dataRules
    path classificationRules

    output:
    path "clean_mmwr.csv", emit: cleanFile
    path "clean_mmwr_preprocessing_report.csv", emit: preprocessingReport
    path "clean_mmwr_classification_report.csv", emit: classificationReport
    path "classification_rules_used.csv", emit: classificationRulesUsed

    script:
    def quote = { value -> "'" + value.toString().replace("'", "'\"'\"'") + "'" }
    // Use absolute path to the script or a relative path from the current directory
    def scriptPath = "${workflow.projectDir}/bin/preprocess.R"
    def serotypeConfigArg = serotypeConfig.name.startsWith('NO_') ? "" : "--serotype-config ${quote(serotypeConfig)}"
    def dataRulesArg = dataRules.name.startsWith('NO_') ? "" : "--data_rules ${quote(dataRules)}"

    // Validate matching sensitivity
    def validSensitivities = ['STRICT', 'MEDIUM', 'RELAXED']
    if (!validSensitivities.contains(params.matching_sensitivity)) {
        error "Invalid matching_sensitivity: ${params.matching_sensitivity}. Must be one of: ${validSensitivities.join(', ')}"
    }

    """
    Rscript ${quote(scriptPath)} \\
      --mmwrFile ${quote(mmwrFile)} \\
      --classification_rules ${quote(classificationRules)} \\
      --serotype_source ${quote(params.serotype_source)} \\
      --outputFile clean_mmwr.csv \\
      --matching-sensitivity ${params.matching_sensitivity} \\
      ${serotypeConfigArg} \\
      ${dataRulesArg}
    """
}
