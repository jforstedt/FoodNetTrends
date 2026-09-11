# FoodNet analysis options

These options implement the FoodNet requests for selectable baselines and case groups.
Classification definitions are provisional pending FoodNet review; their rules can be
changed without changing model code. Changed definitions require rerunning affected analyses.

## Baseline

The default remains 2016–2018. Use `--baseline_year 2019` for one year, or
`--baseline_start 2017 --baseline_end 2019` for a range. A single-year setting takes
precedence over start/end. Every requested baseline year must be available.

Comparison CSVs include `baseline_start`, `baseline_end`, `baseline_raw_ir`,
`baseline_median_ir`, `baseline_lower_hdi_ir`, and `baseline_upper_hdi_ir`.
Rates are per 100,000 population. For multiple years, crude incidence is total
cases divided by total population-time. Modeled baseline rates are calculated
per posterior draw using the same weighting, then summarized. Relative risks
are calculated per draw against that baseline.

## Salmonella

The launcher offers a FoodNet preset with seven separate analyses:

```text
ENTERITIDIS
NEWPORT
TYPHIMURIUM
JAVIANA
I 4,[5],12:i:-
OTHER SEROTYPES
NOT SEROTYPED
```

Equivalent direct selection (add your input paths and normal execution profile):

```bash
nextflow run main.nf -profile singularity \
  --pathogen SALMONELLA \
  --pathogen_grouping 'SALMONELLA~ENTERITIDIS|SALMONELLA~NEWPORT|SALMONELLA~TYPHIMURIUM|SALMONELLA~JAVIANA|SALMONELLA~I 4,[5],12:i:-|SALMONELLA~OTHER SEROTYPES|SALMONELLA~NOT SEROTYPED'
```

`OTHER SEROTYPES` is dynamic: it contains identified Salmonella serotypes other
than those individually selected in `pathogen_grouping`. It excludes
`NOT SEROTYPED`. The five-serotype list is a convenience preset, not a permanent
classification. Avoid mixing literal serotype selections with typhoidal group
comparisons if you need mutually exclusive outputs; combined and aggregate
analyses intentionally overlap their constituent analyses.

Use `SALMONELLA~TYPHOIDAL|SALMONELLA~NONTYPHOIDAL|SALMONELLA~UNCLASSIFIED`
for the separate disease categories. Untyped cases remain in overall Salmonella
but are not assumed nontyphoidal. Ambiguous Paratyphi B labels are unclassified
unless an exact typhoidal mapping exists. The CSV supplies provisional exact
mappings for Typhi, Paratyphi A, Paratyphi C, and Paratyphi B Tartrate-Negative.

## Editable classification

`--classification_rules analysis_configs/classification_rules.csv` selects a CSV
with `classification,match_type,value` columns. Classification is `not_serotyped`,
`typhoidal`, `nontyphoidal`, or `unclassified`; matching is `exact` or literal `contains`, ignoring
case and surrounding whitespace. Explicit nontyphoidal mappings override unclassified patterns, then typhoidal
mappings take precedence; missing-serotype rules take final precedence. Other
identified serotypes default to nontyphoidal. Review unfamiliar labels before
interpreting that split. Keep a copy of the original rules when changing them.

Provisional not-serotyped values include blanks, NOT SEROTYPED, NOT SPECIATED,
UNKNOWN, PARTIAL SERO, NOT SERO, MISSING, and labels containing UNDET. A truly
missing value always remains not serotyped.

`--serotype_source auto` prefers `serotypesummary2` whenever that column exists.
Blanks in that column remain blanks; there is no row-by-row fallback. Otherwise,
it reuses preserved `serotypesummary_original`, legacy `serotypesummary`, or
`sero1`, in that order. Raw preprocessing retains the legacy `sero1` recoding
when `serotypesummary2` is absent. An explicit source-column name overrides this.
Existing `serotype_config` rules apply to the legacy source; the authoritative
`serotypesummary2` source is not overwritten by those legacy rules.

Original values are retained in `serotypesummary_original` and
`stec_class_original`. Classification is also applied when reusing a cleaned CSV,
so new rules do not require rereading SAS data if the needed source fields remain.
Older cleaned data that no longer contains original values cannot recover them.

The launcher asks for the rules path and source column; defaults can also be set
with `FNT_CLASSIFICATION_RULES` and `FNT_SEROTYPE_SOURCE` environment variables.
Each model task saves its rules, a classification count report for the full
cleaned input, and analysis settings. These reports are aggregate counts, not
individual case records. Compare the reports when validating a rule change.

## STEC and other pathogens

For STEC, `dx0157` positive overrides `stec_class` to O157; negative overrides it
to non-O157. Other values retain the original class. Matching ignores case.
The selections are `O157`, `nonO157`, and `NOT SEROGROUPED`; unresolved cases no
longer enter the non-O157 group.

For any pathogen, `PATHOGEN~value` selects an exact `serotypesummary` value,
ignoring case and surrounding whitespace. Missing values do not enter a named
species or serotype group. Labels may contain commas, brackets and punctuation;
`|` and `~` are reserved grouping delimiters. Shell-quote the whole grouping
argument. Selections that would produce identical sanitized filenames are
rejected; run those selections separately.

The launcher can display a ranked list from an existing cleaned CSV. Without one,
enter exact labels separated by `|`, or use the FoodNet preset. Resource profiling
is recomputed against current rules. Model surveillance coverage is established
before subgroup filtering, using census state/year cells within the input year
range and requested states, then applying the configured catchment windows.
Zero-case cells therefore remain in subgroup and travel models.

## Launcher modes

| Mode | Settings and purpose |
|---|---|
| Test | 1 chain, 100 iterations, adapt_delta 0.8, treedepth 8; smoke check only |
| Publication | 6 chains, 10001 iterations, adapt_delta 0.99, treedepth 15 |
| Max | 8 chains, 20000 iterations, adapt_delta 0.99, treedepth 15; longest runtime |
| Custom | User-selected sampling settings |
| Resume | Requests Nextflow cache reuse; this launcher does not restore every previous setting |
| Preprocessing only | Cleans/classifies data and profiles resources; no Stan fitting |

Publication and Max are sampling presets, not guarantees of convergence. Inspect
the diagnostic CSVs. For exact reruns, use the saved command; the dashboard rerun
command includes analysis selections and lets Nextflow create a fresh project ID.

## Validation

Run `Rscript tests/test_analysis.R` with dplyr, tidyr and HDInterval installed.
`python3 tests/test_launcher.py` checks the menu selections. With the same R
packages plus argparse/readr available, `python3 tests/test_model_flow.py` tests
the actual model-script filtering and exports using a deterministic Stan substitute.
`tests/mock_model.R` implements that substitute and must not be used for real
incidence estimates. CI also exercises Nextflow staging and dashboard generation.

## HPC input paths

The launcher checks that input files exist and are readable before the remaining
setup questions. If an old default path is unavailable, enter the current full
file path at the prompt; a blank entry cancels without submitting jobs.

Set `FNT_DATA_DIR` to change the default directory while retaining the default
filenames. If filenames have changed too, set `FNT_MMWR_FILE`,
`FNT_CENSUS_FILE_B`, and `FNT_CENSUS_FILE_P` to the current full paths. These can
be exported in your shell session or shell configuration, without editing the
tracked launcher. Preprocessing-only mode requires just the MMWR file.

## Input coverage controls (September 2026 HPC audit)

The default analysis uses `--colorado_coverage historical` and
`--parasite_end_year 2024`. These choices are printed by the launcher and recorded
in each analysis settings CSV. They do not modify the source SAS or cleaned CSV.

Historical Colorado coverage excludes the `COEX` submitting site. For analyses
including 2023 or later, it requires the historical county footprint in the census
file, checks Colorado case counties against that footprint, and requires usable
site identifiers. `--colorado_coverage expanded` keeps expansion cases but requires
expanded county denominators from 2023 onward. The audited `cen9625_CoExp` files
end in 2024 and cannot support a full 2025 expanded analysis. A filename alone does
not establish coverage. The footprint check compares against the latest supplied
pre-2023 Colorado year; source population provenance must still be verified.

Parasite models explicitly omit cases after the selected end year. Raising
`--parasite_end_year 2025` requires actual matching parasite populations. The
pipeline does not copy bacterial populations or extrapolate missing denominators.
Parasite observation years begin no earlier than 1997. Baseline years must exist
within each pathogen's resulting analysis window.

For the launcher, defaults can be changed with `FNT_COLORADO_COVERAGE` and
`FNT_PARASITE_END_YEAR`. For example, after supplying verified denominators:

```bash
export FNT_COLORADO_COVERAGE=expanded
export FNT_PARASITE_END_YEAR=2025
```

Each fitted analysis writes `*_population_used.csv` (state/year totals) and
`*_input_exclusions.csv` (reason, year, number of excluded records). Exclusions
are counted after the user's state, travel, and diagnostic filters and before
subgroup selection. These CSVs accompany the other model results. Analysis
settings in the dashboard include the coverage choice and actual modeled years.

Validation rejects duplicate geographic keys, invalid active populations,
missing modeled state/year denominators, and cases absent from the surveillance
population frame. The supplied Connecticut convention is handled explicitly:
historical counties are active through 2019 and nine planning regions from 2020;
zero or missing inactive rows are allowed, but overlapping populated geographies
or incomplete active regions fail. This is state-level aggregation, not a spatial
crosswalk. County-level modeling still requires geographic reconciliation.

STEC classification recognizes `dxo157` (the lowercased SAS `DxO157` field) and
retains `dx0157` as an alias. Positive/negative results override the original class;
other values retain it. Contradictory positive/negative results across both fields
fail explicitly. When both exist, the actual SAS spelling takes priority except
for blank values.

The completed HPC run predating these controls remains a computational test;
rerun affected models and inspect convergence and denominator exports before
interpreting their estimates.

## Acceptance checks and September resource repair

The September 11 follow-up checks cover all requested options with synthetic
cases and independently specified expected counts. `tests/test_feature_matrix.py`
runs the actual R model-script flow for 12 subgroup selections, alternating
2016–2018 and single-year 2019 baselines, and checks the generated dashboard.
Stan fitting and prediction are replaced by deterministic fixture draws in this
test; these are not scientific estimates or evidence of subgroup convergence.

| Requested behavior | Verification |
| --- | --- |
| Single baseline year and range | CLI single-year override in Nextflow 24.10.4 integration; both ranges in R model flow |
| Crude and estimated baseline incidence | Known population-weighted fixture values, exported columns and dashboard payload |
| STEC positive/negative override and fallback | Both field spellings; exact O157/nonO157/unresolved membership |
| Salmonella not serotyped | Blank-source membership and separate output |
| Other Salmonella serotypes | Excludes individually selected serotypes and not-serotyped cases; changes with selection |
| Typhoidal/nontyphoidal | Typhi and the three explicitly named Paratyphi categories; ambiguous B remains unclassified |
| Other serotype/species values | Exact JEJUNI/COLI membership and separate output; blank values excluded |
| Launcher options | Preset/custom selection, unresolved categories and all six mode labels |
| Diagnostics display | Failed diagnostics and nominally converged fits with warnings remain visibly flagged |

Resource selectors were tested with Nextflow **24.10.4** for standard rstan,
cmdstanr, explicit resource caps, and the fully qualified CPU-only override.
Six-chain rstan requests resolve to **12 CPUs / 52 GB / 48 hours**, or
**6 CPUs / 52 GB / 48 hours** with the previous CPU-only override. Formula,
priors, sampler controls, classifications and coverage rules were not changed
by this resource repair. Difficulty profiling remains informational; a
conservative time request replaces difficulty-dependent scheduling.

For the HPC installation, one command collects the R contract tests, the
12-group synthetic end-to-end test, membership checks on the existing cleaned
cases, checks of saved crude baseline calculations, and the saved convergence
reports:

```bash
bash scripts/validate_features.sh 20260911_140750
```

It writes `foodnet_feature_validation_<project>_<timestamp>.txt`, submits no
jobs, fits no new Stan models and leaves completed results untouched. The
real-data group checks require the published `preprocessed/clean_mmwr.csv`.
They check implementation consistency, not FoodNet approval of classification
rules. The baseline comparison uses existing outputs; posterior equivalence to
Daniel's reference implementation remains a separate scientific validation.

The completed run's diagnostic flags remain: Shigella 12 divergent transitions,
Cyclospora 2, STEC 2 and Yersinia 1. All reported R-hat and ESS checks passed.
These warnings should accompany review of those estimates; this follow-up does
not clear them or automatically refit the models.

## Real-data feature validation run

After the acceptance checks pass, launch the separate feature-model batch with:

```bash
python3 scripts/run_feature_models.py 20260911_140750
```

This launches **14 real Stan fits**: the three STEC groups; Hannah's five named
Salmonella serotypes plus other and not serotyped; typhoidal, nontyphoidal and
unclassified Salmonella; and Yersinia ENTEROCOLITICA, confirmed present in the
saved audit. It verifies that the selected species exists in the authoritative
source column before submitting anything. All fits use the example **2019**
baseline, six chains, 10001 iterations, adapt_delta 0.99, max_treedepth 15,
seed 123 and rstan. The biological classifications and historical coverage
choices remain unchanged. This is validation, not a final FoodNet analysis specification.

The launcher directly reuses the completed `preprocessed/clean_mmwr.csv`; it does
not depend on Nextflow cache reuse to avoid preprocessing. Each invocation gets
a new `feature_validation_<timestamp>` project ID and never overwrites the source
run. At most three model tasks execute concurrently. Model selectors retain the
12-CPU, 52-GB, 48-hour initial allocation; the temporary CPU-only resume override
is not loaded.

The new run's `validation_plan` directory contains the exact JSON parameters,
copied classification rules, manifest, Nextflow log, and an explicit-session
resume helper. `--prepare-only` writes this plan without submitting jobs.
After Nextflow exits, the launcher automatically collects task traces, resources,
logs and convergence reports into `validation_plan/run_diagnostics.txt`, including
comparison with the source run. Scheduler accounting is skipped because those
lookups timed out on the cluster. Keep the launch terminal open until completion.

The serotype and typhoidal group sets overlap intentionally; do not add counts
across the two sets. Rare groups may need further convergence review. A successful
Nextflow exit alone does not clear sampler warnings.
