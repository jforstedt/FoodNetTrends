# Surveillance input safeguards

These changes affect which observations enter a fit. They do not change the
negative-binomial state spline formula, population offset, prior specification, or posterior
aggregation. The R-INLA county models remain a separately evaluated extension.

The [Weller et al. paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13055632/)
uses 1996–2019 data for its comparisons, recognizes the Cryptosporidium cutoff,
and discusses R-INLA and spatial models as future work. Its comparative metrics
are in-sample; its separate extrapolation example is not a general guarantee of
forecast accuracy. These safeguards do not establish exact reproduction of the
paper's original analysis dataset or software environment.

## Observation rules applied before zero counts are created

- Cryptosporidium ends in 2017, independently of available population years.
- The nonO157 STEC subgroup starts in 2000. O157 retains its earlier start.
- Campylobacter trend inputs end in 2023 pending a separate assessment of the
  diagnostic-reporting change. This ceiling also applies to culture-only selections;
  restricting diagnoses alone is not treated as evidence of comparability.
- For other pathogens with optional reporting from July 2025, an annual window
  including 2025 or later fails until reporting completeness can be established.
  An explicit `--analysis_end_year 2024` permits a historical analysis. This is
  not a claim that optional reporting stopped or that those records are invalid.
- Expanded Colorado Yersinia analyses fail: matching historical county coverage
  is required rather than silently applying a statewide population.

Sources: [CDC reporting dates](https://www.cdc.gov/foodnet/about/index.html),
[CDC Campylobacter comparability explanation](https://www.cdc.gov/foodnet/reports/preliminary-data.html),
and [CDC Colorado/Yersinia scope](https://www.cdc.gov/mmwr/volumes/73/wr/mm7326a1.htm).

`--analysis_end_year` is available in Nextflow and directly in `bin/trendy.R`.
It cannot extend confirmed surveillance boundaries. Baselines are never moved
implicitly: a baseline outside the eligible, catchment-filtered years fails before
sampling. Output settings record the requested ceiling; `*_observation_policy.csv`
records effective bounds even if no individual records were excluded. The
separate exclusion report counts actual removed records.

Preprocessing rejects missing Listeria reportability fields and missing fields
required by configured pathogen rules. Unverified condition values cannot create
phantom rows. The example catchment configuration matches the built-in Georgia
parasite start in 1998.

## Targeted replacement runs

`scripts/launch_surveillance_refits.py` examines saved analysis settings and plans
only affected state analyses. Fits run as independent SGE array tasks without a
three-task throttle. Original results remain in place; collection produces one
review archive, excluding saved model objects. Successful execution is distinct
from acceptable sampling diagnostics. Review the collection report before using
replacement results in a dashboard.

## Questions deliberately left open

Early parasite county coverage and partial-year exposure conventions require
source-data reconciliation. Combined STEC surveillance composition and
pre-2004 travel information require separate review. Diagnostic-method adjustment,
seasonality, pathogen-specific priors, and new county model terms are scientific
extensions, not included in this input repair. No existing dashboard is silently
certified or replaced by these changes.
