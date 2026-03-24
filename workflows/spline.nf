#!/usr/bin/env nextflow

// Import modules
include { TRENDY } from '../modules/local/trendy'
include { PREPROCESS } from '../modules/local/preprocess'
include { RESOURCE_PROFILER } from '../modules/local/resource_profiler'
include { DASHBOARD } from '../modules/local/dashboard'

// ---------------------------------------------------------------------------
// Helper closures for resource profile parsing and grouping construction.
// Defined at script scope so both workflows can reference them.
// ---------------------------------------------------------------------------

// Parse a single CSV row into a metrics map, coercing NA-like values to
// sensible defaults.
def parseMetricsRow = { row ->
    [
        rows: row.rows as Integer,
        sites: row.sites as Integer,
        years: row.years as Integer,
        complexity: row.complexity as Long,
        size_category: row.size_category,
        zero_frac: (row.zero_frac in [null, '', 'NA'] ? 0 : row.zero_frac as Double),
        sparse_cells: (row.sparse_cells in [null, '', 'NA'] ? 0 : row.sparse_cells as Double),
        overdispersion: (row.overdispersion in [null, '', 'NA'] ? 0 : row.overdispersion as Double),
        state_cv: (row.state_cv in [null, '', 'NA'] ? 0 : row.state_cv as Double),
        median_count: (row.median_count in [null, '', 'NA'] ? 0 : row.median_count as Double),
        n_years: (row.n_years in [null, '', 'NA'] ? 0 : row.n_years as Integer),
        low_count_penalty: (row.low_count_penalty in [null, '', 'NA'] ? 0 : row.low_count_penalty as Double),
        year_gap_penalty: (row.year_gap_penalty in [null, '', 'NA'] ? 0 : row.year_gap_penalty as Double),
        difficulty: (row.difficulty in [null, '', 'NA'] ? 0 : row.difficulty as Double),
        difficulty_category: (row.difficulty_category in [null, '', 'NA'] ? 'moderate' : row.difficulty_category)
    ]
}

// Parse resource_profile.csv and resource_profile_subgroups.csv into a
// combined map keyed by pathogen name, with a special '__subgroups__' entry
// holding the subgroup-level metrics keyed by "PATHOGEN_subgroup".
def parseResourceProfiles = { profileFile, subgroupFile ->
    def metrics = [:]
    profileFile.splitCsv(header: true, sep: ',', strip: true, quote: '"').each { row ->
        log.debug "CSV row: ${row}"
        metrics[row.pathogen] = parseMetricsRow(row)
    }
    if (metrics.isEmpty()) {
        error "Resource profile is empty - no pathogen data found"
    }

    def subgroupMap = [:]
    if (subgroupFile != null) {
        subgroupFile.splitCsv(header: true, sep: ',', strip: true, quote: '"').each { row ->
            def key = "${row.pathogen}_${row.subgroup}"
            subgroupMap[key] = parseMetricsRow(row)
        }
        if (subgroupMap.size() > 0) {
            log.info "Loaded subgroup metrics for ${subgroupMap.size()} subgroups"
        }
    }
    metrics['__subgroups__'] = subgroupMap

    log.info "Loaded metrics for pathogens: ${metrics.keySet().findAll { it != '__subgroups__' }.join(', ')}"
    return metrics
}

// Build a pathogenGrouping channel for AUTO_DISCOVER mode from a metrics
// channel. Each pathogen found in the profile gets a "PATHOGEN~combined" entry.
def createAutoDiscoverGrouping = { metricsChannel ->
    metricsChannel
        .flatMap { metrics ->
            def pathogenList = metrics.keySet().findAll { it != '__subgroups__' }.toList()
            if (pathogenList.isEmpty()) {
                error "No pathogens found in metrics. Check if preprocessing completed successfully."
            }
            log.info "Auto-discovered pathogens: ${pathogenList.join(', ')}"
            return pathogenList
        }
        .map { p -> "${p}~combined" }
}

// Combine a pathogenGrouping channel with a metricsChannel to produce tuples
// of (grouping, pathogen, subgroup, pathogenMetrics). Handles subgroup lookup
// with a 15% fallback when no profiled subgroup data exists, and filters out
// entries with zero rows.
def buildGroupingWithMetrics = { pathogenGrouping, metricsChannel ->
    pathogenGrouping
        .combine(metricsChannel)
        .map { grouping, metrics ->
            def parts = grouping.split('~')
            def pathogen = parts[0]
            def subgroup = parts.length > 1 ? parts[1] : 'combined'

            log.debug "Metrics map keys: ${metrics.keySet()}"
            log.debug "Looking for pathogen: '${pathogen}'"

            def subgroupMap = metrics['__subgroups__'] ?: [:]

            // Resolve raw metrics, handling unexpected types defensively
            def rawMetrics = metrics[pathogen]
            def pathogenMetrics
            if (rawMetrics instanceof Map) {
                pathogenMetrics = rawMetrics
            } else if (rawMetrics instanceof List && rawMetrics.size() > 0) {
                log.warn "Metrics for ${pathogen} is a list, not a map: ${rawMetrics}"
                pathogenMetrics = [rows: rawMetrics[0], complexity: 0]
            } else if (rawMetrics) {
                log.warn "Metrics for ${pathogen} is a single value: ${rawMetrics}"
                pathogenMetrics = [rows: rawMetrics, complexity: 0]
            } else {
                pathogenMetrics = [rows: 0, complexity: 0]
            }
            if (pathogenMetrics.rows == 0) {
                log.warn "No data found for pathogen: ${pathogen}. Using default metrics."
            }

            // For non-combined subgroups, prefer profiled subgroup metrics.
            // Fall back to 15% of the parent pathogen estimate when unavailable.
            if (subgroup != 'combined') {
                def subgroupKey = "${pathogen}_${subgroup}"
                def subMetrics = subgroupMap[subgroupKey]

                if (subMetrics) {
                    pathogenMetrics = subMetrics
                    log.info "Using profiled subgroup metrics for ${pathogen}:${subgroup} - rows: ${subMetrics.rows}, difficulty: ${subMetrics.difficulty} [${subMetrics.difficulty_category}]"
                } else {
                    def adjustedRows = Math.max(1000, (pathogenMetrics.rows * 0.15) as Integer)
                    def adjustedComplexity = Math.max(10000, (pathogenMetrics.complexity * 0.15) as Long)
                    pathogenMetrics = [
                        rows: adjustedRows,
                        sites: pathogenMetrics.sites,
                        years: pathogenMetrics.years,
                        complexity: adjustedComplexity,
                        size_category: adjustedRows > 20000 ? "large" : adjustedRows > 10000 ? "medium" : "small",
                        zero_frac: pathogenMetrics.zero_frac,
                        sparse_cells: pathogenMetrics.sparse_cells,
                        overdispersion: pathogenMetrics.overdispersion,
                        state_cv: pathogenMetrics.state_cv,
                        median_count: pathogenMetrics.median_count,
                        n_years: pathogenMetrics.n_years,
                        low_count_penalty: pathogenMetrics.low_count_penalty,
                        year_gap_penalty: pathogenMetrics.year_gap_penalty,
                        difficulty: pathogenMetrics.difficulty,
                        difficulty_category: pathogenMetrics.difficulty_category
                    ]
                    log.info "No subgroup profile for ${pathogen}:${subgroup}, estimated rows: ${adjustedRows} (15% of ${rawMetrics?.rows ?: 0})"
                }
            }

            log.debug "Creating tuple for ${pathogen}: grouping=${grouping}, subgroup=${subgroup}, metrics=${pathogenMetrics}"
            tuple(grouping, pathogen, subgroup, pathogenMetrics)
        }
        .filter { grouping, pathogen, subgroup, pathogenMetrics ->
            if (pathogenMetrics.rows == 0) {
                log.warn "Skipping ${pathogen} - no data available"
                return false
            }
            return true
        }
}

workflow FOODNETTRENDS {
    // Define input channels
    if (params.pathogen && params.pathogen != 'AUTO_DISCOVER') {
        // Convert comma-separated string to a channel of pathogens
        def pathogenList = params.pathogen.tokenize(',')
        pathogens = Channel.fromList(pathogenList)
    } else if (params.pathogen == 'AUTO_DISCOVER') {
        // Will be populated after preprocessing
        pathogens = null
    } else {
        // Default to CAMPYLOBACTER and CYCLOSPORA for testing
        pathogens = Channel.of('CAMPYLOBACTER', 'CYCLOSPORA')
    }

    // Handle pathogen grouping if specified
    if (params.pathogen_grouping && params.pathogen_grouping.trim()) {
        // Parse pathogen~subgroup format using pipe delimiter
        def groupingList = params.pathogen_grouping.tokenize('|')
        pathogenGrouping = Channel.fromList(groupingList)
    } else if (params.pathogen == 'AUTO_DISCOVER') {
        // Defer pathogenGrouping creation until after preprocessing
        pathogenGrouping = null
    } else if (pathogens) {
        // If no grouping specified, use simple pathogen list
        pathogenGrouping = pathogens.map { p -> "${p}~combined" }
    } else {
        // Fallback to default pathogens if nothing specified
        log.warn "No pathogens specified, using defaults: CAMPYLOBACTER, CYCLOSPORA"
        pathogens = Channel.of('CAMPYLOBACTER', 'CYCLOSPORA')
        pathogenGrouping = pathogens.map { p -> "${p}~combined" }
    }

    // Input files
    mmwrFile = file(params.mmwrFile)
    censusFileB = file(params.censusFileB)
    censusFileP = file(params.censusFileP)

    // Configuration files (optional)
    serotypeConfig = params.serotype_config ? file(params.serotype_config) : file('NO_SEROTYPE_CONFIG')
    catchmentConfig = params.catchment_config ? file(params.catchment_config) : file('NO_CATCHMENT_CONFIG')
    dataRules = params.data_rules ? file(params.data_rules) : file('NO_DATA_RULES')

    // Check if files exist
    if (!mmwrFile.exists()) {
        error "MMWR file not found: ${params.mmwrFile}"
    }
    if (!censusFileB.exists()) {
        error "Census bacterial file not found: ${params.censusFileB}"
    }
    if (!censusFileP.exists()) {
        error "Census parasitic file not found: ${params.censusFileP}"
    }

    // Log pipeline start
    log.info """
    ==============================================
    FoodNetTrends Pipeline
    ==============================================
    Project ID    : ${params.projID}
    MMWR File     : ${params.mmwrFile}
    Census Files  : ${params.censusFileB}, ${params.censusFileP}
    States        : ${params.states ?: 'all'}
    Travel        : ${params.travel}
    CIDT          : ${params.cidt}
    Pathogens     : ${params.pathogen ?: 'default (CAMPYLOBACTER,CYCLOSPORA)'}
    Cores         : ${params.cpus ?: 'default'}
    Chains        : ${params.chains}
    Iterations    : ${params.iterations}
    Adapt Delta   : ${params.adapt_delta}
    Max Treedepth : ${params.max_treedepth}
    Seed          : ${params.seed}
    Output Dir    : ${params.outdir}/${params.projID}
    ==============================================
    """

    // Conditional preprocessing
    if (params.preprocessed) {
        log.info "Using preprocessed data from: ${params.cleanFile}"
        cleanFile = file(params.cleanFile)
        if (!cleanFile.exists()) {
            error "Preprocessed file not found: ${params.cleanFile}"
        }

        // Check for existing resource profile
        def resourceProfilePath = cleanFile.parent.resolve("resource_profile.csv")
        def resourceProfile = file(resourceProfilePath)

        if (resourceProfile.exists()) {
            log.info "Using existing resource profile: ${resourceProfilePath}"
            def subgroupProfilePath = cleanFile.parent.resolve("resource_profile_subgroups.csv")
            def subgroupProfile = file(subgroupProfilePath)
            def subgroupFile = subgroupProfile.exists() ? subgroupProfile : null

            def metricsMap = parseResourceProfiles(resourceProfile, subgroupFile)
            metricsChannel = Channel.value(metricsMap)
        } else {
            log.info "Generating resource profile for preprocessed data"
            RESOURCE_PROFILER(cleanFile)

            metricsChannel = RESOURCE_PROFILER.out.profile
                .combine(RESOURCE_PROFILER.out.subgroup_profile)
                .map { csvFile, subgroupFile ->
                    parseResourceProfiles(csvFile, subgroupFile)
                }
        }

        // Handle AUTO_DISCOVER with preprocessed data
        if (!pathogenGrouping) {
            if (params.pathogen == 'AUTO_DISCOVER') {
                log.info "Creating pathogen groupings from discovered pathogens"
                pathogenGrouping = createAutoDiscoverGrouping(metricsChannel)
            } else {
                error "Pathogen grouping is not defined. This should not happen for preprocessed data."
            }
        }

        pathogenGroupingWithMetrics = buildGroupingWithMetrics(pathogenGrouping, metricsChannel)

        // Run TRENDY with preprocessed data and metrics
        TRENDY(
            pathogenGroupingWithMetrics,
            mmwrFile,
            censusFileB,
            censusFileP,
            params.travel,
            params.cidt,
            params.states ?: '',  // Use empty string if null
            params.projID,
            params.trendyScript,
            params.preprocessed,
            cleanFile,
            catchmentConfig
        )
    } else {
        log.info "Preprocessing raw data files"

        // Run preprocessing step
        PREPROCESS(
            mmwrFile,
            params.projID,
            serotypeConfig,
            dataRules
        )

        // Create a proper channel from the preprocessed file
        processedFile = PREPROCESS.out.cleanFile

        // Generate resource profile for new data
        RESOURCE_PROFILER(processedFile)

        metricsChannel = RESOURCE_PROFILER.out.profile
            .combine(RESOURCE_PROFILER.out.subgroup_profile)
            .map { csvFile, subgroupFile ->
                parseResourceProfiles(csvFile, subgroupFile)
            }

        // If AUTO_DISCOVER, extract pathogens from the metrics
        if (params.pathogen == 'AUTO_DISCOVER') {
            pathogenGrouping = createAutoDiscoverGrouping(metricsChannel)

            // Create pathogens channel for consistency
            pathogens = pathogenGrouping.map { grouping ->
                grouping.split('~')[0]
            }
        }

        if (!pathogenGrouping) {
            // This handles the edge case where pathogenGrouping wasn't set earlier
            log.warn "Pathogen grouping was not properly initialized. Using defaults."
            if (!pathogens) {
                pathogens = Channel.of('CAMPYLOBACTER', 'CYCLOSPORA')
            }
            pathogenGrouping = pathogens.map { p -> "${p}~combined" }
        }

        if (!pathogenGrouping) {
            error "Pathogen grouping is not defined after preprocessing. This indicates a logic error."
        }

        pathogenGroupingWithMetrics = buildGroupingWithMetrics(pathogenGrouping, metricsChannel)

        // Run TRENDY with processed data and metrics
        TRENDY(
            pathogenGroupingWithMetrics,
            mmwrFile,
            censusFileB,
            censusFileP,
            params.travel,
            params.cidt,
            params.states ?: '',  // Use empty string if null
            params.projID,
            params.trendyScript,
            true,
            processedFile,
            catchmentConfig
        )
    }

    // Generate dashboard after all TRENDY jobs complete
    // Mix csv (always emitted on success) with errors (emitted on failure) for a reliable signal
    if (!params.skip_dashboard) {
        trendy_done = TRENDY.out.csv
            .mix(TRENDY.out.errors)
            .collect()
            .ifEmpty(["done"])
            .map { "done" }

        DASHBOARD(trendy_done, params.projID)
    }

}

/*
========================================================================================
    PREPROCESSING ONLY WORKFLOW
========================================================================================
*/

workflow PREPROCESS_ONLY {
    // Input validation
    def mmwrFile = file(params.mmwrFile)
    if (!mmwrFile.exists()) {
        error "MMWR file not found: ${params.mmwrFile}"
    }

    // Configuration files (optional)
    serotypeConfig = params.serotype_config ? file(params.serotype_config) : file('NO_SEROTYPE_CONFIG')
    dataRules = params.data_rules ? file(params.data_rules) : file('NO_DATA_RULES')

    // Log preprocessing start
    log.info """
    ==============================================
    FoodNet Preprocessing Only
    ==============================================
    Project ID    : ${params.projID}
    MMWR File     : ${params.mmwrFile}
    Matching      : ${params.matching_sensitivity ?: 'MEDIUM'}
    Data Rules    : ${params.data_rules ?: 'bundled default'}
    Output Dir    : ${params.outdir}/${params.projID}
    ==============================================
    """

    // Run preprocessing
    PREPROCESS(
        mmwrFile,
        params.projID,
        serotypeConfig,
        dataRules
    )

    // Run resource profiler on preprocessed data
    RESOURCE_PROFILER(PREPROCESS.out.cleanFile)

}
