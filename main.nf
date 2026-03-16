nextflow.enable.dsl = 2

// Handle help parameter
if (params.help) {
    println """
    ============================================
    FoodNetTrends Pipeline
    ============================================
    Usage:
        nextflow run main.nf [options]

    Input options:
        --mmwrFile              Path to the MMWR data file (or cleaned CSV if preprocessed is TRUE)
        --censusFileB           Path to the bacterial census data file
        --censusFileP           Path to the parasitic census data file
        --preprocessed          TRUE/FALSE indicating if using preprocessed CSV data (default: false)
        --cleanFile             Path to cleaned CSV file (if preprocessed is TRUE)
        --skip_preprocessing    Skip the preprocessing step (default: false)

    Pathogen selection:
        --pathogen              Comma-separated list of pathogens (e.g., CAMPYLOBACTER,SALMONELLA)
        --pathogen_grouping     Pipe-separated subgroup definitions (e.g., STEC~O157|STEC~nonO157)

    Data filtering:
        --states                States to include, comma-separated (default: all)
        --travel                Travel types (default: NO,UNKNOWN,YES)
        --cidt                  CIDT types (default: CIDT+,CX+,PARASITIC)

    Model parameters:
        --chains                Number of MCMC chains (default: 2)
        --iterations            Number of MCMC iterations per chain (default: 500)
        --adapt_delta           HMC adaptation target (default: 0.95)
        --max_treedepth         Maximum HMC tree depth (default: 10)
        --seed                  Random seed for reproducibility (default: 123)
        --stan_backend          Stan backend: rstan or cmdstanr (default: rstan)

    Configuration:
        --serotype_config       Path to CSV with serotype recoding rules
        --catchment_config      Path to CSV with catchment area definitions
        --matching_sensitivity  Pathogen name matching: STRICT, MEDIUM, or RELAXED (default: MEDIUM)

    Output:
        --outdir                Base output directory (default: output)
        --projID                Project identifier (default: auto-generated timestamp)
        --skip_dashboard        Skip dashboard generation (default: false)

    Other:
        --help                  Show this help message
    """
    System.exit(0)
}

// Include workflows
include { FOODNETTRENDS } from './workflows/spline.nf'
include { PREPROCESS_ONLY } from './workflows/spline.nf'

workflow {
    FOODNETTRENDS()
}
