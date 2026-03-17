# FoodNetTrends Test Data

These files contain **synthetic data** generated for automated pipeline validation.
They do not represent real surveillance observations and must not be used for
epidemiological analysis.

## Files

| File | Description |
|---|---|
| `test_mmwr.csv` | ~450 rows of pre-cleaned MMWR-format case records (CAMPYLOBACTER, SALMONELLA, STEC) across 3 states (CA, CO, CT) and 10 years (2010-2019). Formatted to match the output of `preprocess.R` so the pipeline can skip preprocessing (`--preprocessed true`). |
| `test_census_bacterial.csv` | FoodNet catchment population denominators for bacterial pathogens (3 states, 10 years). |
| `test_census_parasitic.csv` | FoodNet catchment population denominators for parasitic pathogens (3 states, 10 years). |

## Usage

Run the test profile:

```bash
nextflow run FoodNetTrends -profile test,singularity
```

The test profile (`conf/test.config`) points to these files and uses minimal MCMC
settings (1 chain, 100 iterations) for fast execution.
