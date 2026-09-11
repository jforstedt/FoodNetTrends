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
