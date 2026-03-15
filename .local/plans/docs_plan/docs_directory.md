# Documentation Audit: docs/ Directory

Audited on 2026-03-14 against the actual codebase.

---

## 1. docs/README.md

### Issues

| # | Severity | Finding |
|---|----------|---------|
| 1 | HIGH | Title says **"cdc/spline"** -- should say **"FoodNetTrends"**. The old pipeline name was never updated. |
| 2 | MEDIUM | Only links to `usage.md` and `output.md`. Does **not** link to `configuration.md`, which exists in the same directory. |
| 3 | LOW | No mention of the dashboard, monitor script, or run_workflow.sh launcher. |

---

## 2. docs/usage.md

### Parameter accuracy (vs nextflow.config + trendy.R + preprocess.R)

| # | Severity | Finding |
|---|----------|---------|
| 1 | OK | `--mmwrFile`, `--censusFileB`, `--censusFileP` -- present in nextflow.config. Correct. |
| 2 | OK | `--preprocessed`, `--cleanFile`, `--skip_preprocessing` -- all present in nextflow.config. Correct. |
| 3 | OK | `--pathogen`, `--pathogen_grouping`, `--states`, `--travel`, `--cidt` -- all present. Correct. |
| 4 | OK | Model params (`--chains`, `--iterations`, `--adapt_delta`, `--max_treedepth`, `--seed`, `--stan_backend`) -- all present in nextflow.config. Correct. |
| 5 | OK | `--serotype_config`, `--catchment_config`, `--matching_sensitivity` -- all present. Correct. |
| 6 | OK | `--outdir`, `--projID`, `--skip_dashboard` -- all present. Correct. |

### Undocumented code parameters

| # | Severity | Finding |
|---|----------|---------|
| 7 | MEDIUM | `--whichScript` / `--trendyScript` (nextflow.config lines 19-20) -- undocumented. Internal param but users could theoretically override it. |
| 8 | LOW | `--cpus` (nextflow.config line 22) -- undocumented. Mostly cosmetic logging param. |
| 9 | MEDIUM | trendy.R has `--cores` (line 72), `--subgroup` (line 64), `--debug` (line 90), `--outDir` (line 60), and `--backend` (line 84) as argparse params. While `--backend` maps to `--stan_backend` at the Nextflow level, `--subgroup` and `--debug` are not documented anywhere. Users running trendy.R standalone would not know about them. |
| 10 | LOW | Boilerplate nextflow.config params (`email`, `email_on_fail`, `hook_url`, etc.) -- standard nf-core params, not documenting is acceptable. |

### Example commands

| # | Severity | Finding |
|---|----------|---------|
| 11 | MEDIUM | Example command uses `nextflow run FoodNetTrends` but the manifest mainScript is `main.nf`. On a local checkout, users would need `nextflow run main.nf` or `nextflow run .` -- the doc should clarify that `FoodNetTrends` is the GitHub repo path, or show the local invocation. |
| 12 | LOW | Example shows `-profile singularity` (single hyphen) which is correct Nextflow syntax. OK. |

### Profiles

| # | Severity | Finding |
|---|----------|---------|
| 13 | HIGH | usage.md lists 4 profiles: `test`, `singularity`, `production`, `debug`. But `fnt.scicomp.config` defines **6 additional profiles**: `conda`, `local`, `scicomp_rosalind`, `training`, `debug` (override), and re-declares `singularity`. None of these HPC profiles are documented. |
| 14 | HIGH | The `local` profile (for interactive qlogin testing) is a new feature and completely undocumented. |
| 15 | HIGH | The `scicomp_rosalind` profile (CDC HPC) is undocumented. |
| 16 | MEDIUM | The `training` profile (training queue) is undocumented. |
| 17 | MEDIUM | The `conda` profile is undocumented. |

### Other issues

| # | Severity | Finding |
|---|----------|---------|
| 18 | LOW | "Updating the pipeline" section references `nextflow pull FoodNetTrends` -- this only works if the pipeline is published on GitHub. Should note this is for remote usage only. |
| 19 | LOW | Links to nf-core/configs documentation -- may confuse users since FoodNetTrends is not an nf-core pipeline. |

---

## 3. docs/output.md

### Output file accuracy (vs trendy.R, trendy.nf, functions.R, modules.config)

| # | Severity | Finding |
|---|----------|---------|
| 1 | HIGH | **Missing output**: `*_summary.txt` -- brms model summary text files are produced by trendy.R (line 479-482) and declared in trendy.nf output. Not documented. |
| 2 | HIGH | **Missing output**: `*_convergence_diagnostics.csv` -- convergence diagnostic CSVs are produced by `CHECK_CONVERGENCE()` in functions.R (line 356-358) and declared in trendy.nf output. Not documented. |
| 3 | HIGH | **Missing output**: `*_EstIRRCatch_*.csv` -- relative risk / percent change comparison CSVs are produced by `IR_COMP_CATCH()` in trendy.R (line 535-536) and declared in trendy.nf output. Not documented. |
| 4 | MEDIUM | **Missing output**: `*_error.txt` -- error files for failed pathogens are produced by trendy.R (lines 410-424, 559-565) and declared in trendy.nf output. Not documented. |
| 5 | MEDIUM | **Missing output**: `*_site_trends.png` and `*_overall_trend.png` -- these are the actual plot filenames produced by trendy.R (lines 542-549). The doc just says `*.png: Trend plots` which is vaguely correct but omits the specific filenames. |
| 6 | MEDIUM | Output path says `<projID>/spline_results/` for spline outputs. This matches modules.config publishDir (`${params.outdir}/${params.projID}/spline_results`). Correct. |
| 7 | MEDIUM | Preprocessing output says `<projID>/clean_mmwr.csv` but modules.config default publishDir for non-TRENDY processes uses a tokenized path pattern. The actual published location depends on the workflow definition. The preprocessing output path may not be exactly `<projID>/clean_mmwr.csv`. |
| 8 | LOW | Dashboard output path says `<projID>/dashboard.html`. modules.config DASHBOARD publishDir is `${params.outdir}/${params.projID}` with pattern `dashboard.html`. Correct. |
| 9 | MEDIUM | **Missing output**: `clean_mmwr_preprocessing_report.csv` -- the preprocessing step produces a pathogen standardization report (preprocess.R line 278). Not documented. |
| 10 | MEDIUM | The pipeline_info section is correct -- execution_report, execution_timeline, execution_trace, pipeline_dag all match nextflow.config trace/report/timeline/dag settings. |

---

## 4. docs/configuration.md

### Accuracy

| # | Severity | Finding |
|---|----------|---------|
| 1 | OK | Serotype config CSV format matches preprocess.R `read_serotype_config()` and `validate_serotype_config()`. Columns (serotype_value, replacement, pathogen, match_type, notes) are correct. |
| 2 | OK | Catchment config CSV format matches functions.R `read_catchment_config()` and `validate_catchment_config()`. Columns (state, start_year, end_year, pathogen_type, notes) are correct. |
| 3 | OK | Default catchment values listed match the hardcoded defaults in `read_catchment_config()` in functions.R (line 41). |
| 4 | OK | Default serotype values listed match `read_serotype_config()` in preprocess.R (line 26). |
| 5 | OK | Example config file paths reference `analysis_configs/examples/` which exist in the repo. |
| 6 | MEDIUM | R script direct-invocation example (line 65-68) shows `Rscript bin/preprocess.R --serotype-config ...` which uses hyphens. This matches preprocess.R argparse `--serotype-config`. Correct. |
| 7 | MEDIUM | R script direct-invocation example (line 130-136) shows `Rscript bin/trendy.R ... --catchment-config ...`. This matches trendy.R argparse `--catchment-config`. Correct. |

### Completeness

| # | Severity | Finding |
|---|----------|---------|
| 8 | HIGH | Does NOT document `--matching_sensitivity` parameter even though it is listed as a key parameter. The serotype config section describes the default recoding but not the matching sensitivity option (STRICT/MEDIUM/RELAXED) which controls pathogen name standardization in preprocess.R. |
| 9 | HIGH | Does NOT cover Nextflow config files at all -- only CSV data configs. The title says "Data Configuration Options" which is accurate but the audit question asked whether it covers all config files. It does NOT cover: `nextflow.config`, `conf/base.config`, `conf/fnt.scicomp.config`, `conf/modules.config`, `conf/test.config`. |
| 10 | HIGH | Does NOT document the pixi-based R environment setup (referenced in nextflow.config env block: `R_LIBS = "/opt/pipeline/.pixi/envs/default/lib/R/library"`). |

---

## 5. Cross-cutting audit questions

### Q5: Is the dashboard documented?

**Partially.** output.md describes the dashboard output file (`dashboard.html`). usage.md mentions `--skip_dashboard`. However, there is no documentation of:
- What the dashboard contains (pathogen-by-pathogen results, state views, preprocessing summaries, pipeline execution info)
- The `generate_dashboard.R` script and its arguments (`--output_dir`, `--projID`, `--cleanFile`, `--output`)
- The dashboard template system (`dashboard/template.html`, vendored JS/CSS in `dashboard/lib/`)
- How to regenerate the dashboard from existing results

### Q6: Is the monitor script documented?

**No.** `bin/monitor_pipeline.sh` is completely undocumented in any of the docs files. This is a useful operational tool that provides real-time terminal monitoring of pipeline progress. Its usage, options (`-i`, `-1`, `-h`), and purpose should be documented.

### Q7: Are new features documented?

| Feature | Documented? | Notes |
|---------|-------------|-------|
| cmdstanr backend | YES | usage.md line 63: `--stan_backend rstan` with note about "rstan" or "cmdstanr" |
| local executor | NO | The `local` profile in fnt.scicomp.config is undocumented. Also, nextflow.config sets PREPROCESS/RESOURCE_PROFILER/DASHBOARD to `executor = 'local'` which is undocumented. |
| Convergence diagnostics | NO | `CHECK_CONVERGENCE()` in functions.R and the `_convergence_diagnostics.csv` output are undocumented in output.md or usage.md |

### Q8: Does configuration.md cover all config files?

**No.** configuration.md only covers CSV data configuration files (serotype_config, catchment_config). It does not cover:
- `nextflow.config` (main pipeline config)
- `conf/base.config` (base resource config)
- `conf/fnt.scicomp.config` (CDC HPC profiles)
- `conf/modules.config` (DSL2 module publishing and resource allocation)
- `conf/test.config` (test profile)
- The pixi-based container environment setup

### Q9: Are there references to removed things?

| Item | Status |
|------|--------|
| FastQC/MultiQC | **YES - stale images remain.** `docs/images/` contains `mqc_fastqc_adapter.png`, `mqc_fastqc_counts.png`, `mqc_fastqc_quality.png`. These are leftover from the nf-core template and are not referenced by any current docs, but they are dead weight in the repo. |
| cdc-dev.config | No references found in docs. `conf/cdc-dev.config` does not exist. Clean. |
| source/ directory | No references found in docs. `source/` directory does not exist. Clean. |
| "cdc/spline" name | **YES.** docs/README.md title still says "cdc/spline" instead of "FoodNetTrends". |

---

## 6. Summary of findings

### Critical (HIGH) -- 11 items

1. **docs/README.md**: Title says "cdc/spline" instead of "FoodNetTrends"
2. **docs/README.md**: Missing link to configuration.md
3. **docs/usage.md**: 5 profiles in fnt.scicomp.config are undocumented (local, scicomp_rosalind, training, conda, debug-override)
4. **docs/usage.md**: The `local` profile (new feature) is undocumented
5. **docs/usage.md**: The `scicomp_rosalind` profile is undocumented
6. **docs/output.md**: Missing `*_summary.txt` output description
7. **docs/output.md**: Missing `*_convergence_diagnostics.csv` output description
8. **docs/output.md**: Missing `*_EstIRRCatch_*.csv` output description
9. **docs/configuration.md**: Does not document `--matching_sensitivity` parameter
10. **docs/configuration.md**: Does not cover any Nextflow config files
11. **docs/configuration.md**: Does not document the pixi-based R environment

### Important (MEDIUM) -- 12 items

1. docs/usage.md: `--whichScript`/`--trendyScript` undocumented
2. docs/usage.md: trendy.R standalone params (`--subgroup`, `--debug`, `--cores`) undocumented
3. docs/usage.md: Example command `nextflow run FoodNetTrends` vs local `nextflow run main.nf` not clarified
4. docs/usage.md: `training` and `conda` profiles undocumented
5. docs/output.md: `*_error.txt` output not documented
6. docs/output.md: Specific plot filenames (`*_site_trends.png`, `*_overall_trend.png`) not documented
7. docs/output.md: `clean_mmwr_preprocessing_report.csv` not documented
8. docs/output.md: Preprocessing output path may not match actual publishDir
9. No docs for the monitor script (`bin/monitor_pipeline.sh`)
10. No docs for the `run_workflow.sh` interactive launcher
11. Convergence diagnostics feature undocumented
12. Dashboard contents/regeneration undocumented

### Cleanup (LOW) -- 6 items

1. docs/README.md: No mention of dashboard, monitor, or run_workflow.sh
2. docs/usage.md: `--cpus` param undocumented (cosmetic)
3. docs/usage.md: nf-core references may confuse users
4. docs/usage.md: `nextflow pull` section assumes remote publishing
5. docs/images/: 3 stale FastQC/MultiQC images (`mqc_fastqc_*.png`) should be removed
6. docs/contributions/ directory exists but is empty

---

## 7. Recommended actions

### Phase 1: Fix inaccuracies (quick wins)
- [ ] Rename "cdc/spline" to "FoodNetTrends" in docs/README.md
- [ ] Add link to configuration.md in docs/README.md
- [ ] Delete stale `docs/images/mqc_fastqc_*.png` files
- [ ] Delete empty `docs/contributions/` directory

### Phase 2: Complete output.md
- [ ] Add `*_summary.txt` (brms model summary text)
- [ ] Add `*_convergence_diagnostics.csv` (R-hat, ESS, divergent transitions)
- [ ] Add `*_EstIRRCatch_*.csv` (relative risk vs baseline period comparisons)
- [ ] Add `*_error.txt` (per-pathogen error reports)
- [ ] Add specific plot filenames (`*_site_trends.png`, `*_overall_trend.png`)
- [ ] Add `clean_mmwr_preprocessing_report.csv` (pathogen standardization report)

### Phase 3: Complete usage.md
- [ ] Document all profiles from fnt.scicomp.config: `local`, `scicomp_rosalind`, `training`, `conda`
- [ ] Add section for `run_workflow.sh` interactive launcher
- [ ] Add section for `bin/monitor_pipeline.sh`
- [ ] Clarify local vs remote invocation (`nextflow run main.nf` vs `nextflow run FoodNetTrends`)

### Phase 4: Expand configuration.md
- [ ] Add `--matching_sensitivity` parameter documentation
- [ ] Add section covering Nextflow config files (nextflow.config, base.config, fnt.scicomp.config, modules.config, test.config)
- [ ] Document the pixi-based R environment setup
- [ ] Document the container (foodnet.sif) and how it relates to the pixi environment

### Phase 5: New documentation
- [ ] Document convergence diagnostics (what CHECK_CONVERGENCE checks, thresholds, how to interpret)
- [ ] Document dashboard contents and how to regenerate from existing results
- [ ] Document the run_workflow.sh interactive options (pathogen selection, STEC/Salmonella grouping, Stan backend selection, etc.)
