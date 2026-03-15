# FoodNetTrends Results Dashboard — Implementation Plan

## 1. Architecture Decision

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **R Markdown / Quarto** | Already in R ecosystem; `DT`, `plotly` for interactive tables/plots; Quarto supports self-contained HTML | Requires adding packages to `foodnet.yml`; Quarto needs separate install; limited control over custom JS (lightbox, virtual scroll) | Not recommended |
| **Pure R script generating HTML** | No new runtime; total control over output; only needs `r-base64enc` and `r-jsonlite`; no pandoc dependency; bioinformaticians can maintain it | More boilerplate for HTML template; must hand-wire JS | **RECOMMENDED** |
| **Python script** | Good templating (Jinja2); pandas handles large CSV | Adds Python to an R-only container; team less familiar | Not recommended |
| **Node.js tool** | Best JS ecosystem | Foreign runtime; needs Node in Singularity container | Not recommended |

### Recommended: Pure R Script (`generate_dashboard.R`)

The dashboard generator will be a standalone R script that:
- Reads all pipeline output files from the `output/{projID}/` directory tree
- Converts CSV data to JSON, images to Base64
- Injects everything into an HTML template string
- Writes a single self-contained `dashboard.html` file

**New conda dependencies** (add to `foodnet.yml`):
```yaml
  - r-jsonlite=1.8.9
  - r-base64enc=0.1_3
```

**Frontend libraries** (inlined, no CDN needed):
- **Tabulator.js** (MIT, ~90KB gzipped) — sortable/filterable/paginated/virtual-scroll tables
- **medium-zoom** (MIT, ~4KB) — click-to-zoom for images
- No framework (React, Vue, etc.) — plain vanilla JS only

---

## 2. Integration with Nextflow

### New Module: `modules/local/dashboard.nf`

```groovy
process DASHBOARD {
    tag "Generating results dashboard"
    label 'process_low'
    container 'foodnet.sif'

    publishDir "${params.outdir}/${params.projID}", mode: 'copy'

    input:
    val ready   // dummy signal that all TRENDY jobs completed
    val projID

    output:
    path "dashboard.html", emit: html

    script:
    """
    Rscript ${workflow.projectDir}/dashboard/generate_dashboard.R \
      --output_dir ${params.outdir}/${projID} \
      --projID ${projID} \
      --output dashboard.html
    """
}
```

### Workflow Wiring in `workflows/spline.nf`

Use the simpler "directory-scanning" approach — the R script uses `list.files()` to discover all outputs, avoiding fragile channel gymnastics:

```groovy
include { DASHBOARD } from '../modules/local/dashboard'

// At the end of both preprocessed and non-preprocessed paths:
TRENDY.out.csv.collect().map { "done" } | set { trendy_done }
DASHBOARD(trendy_done, params.projID)
```

### DAG Position

```
PREPROCESS ──> RESOURCE_PROFILER ──> TRENDY (per pathogen, parallel)
                                          │
                                          ├──> {PATHOGEN}_brm.Rds
                                          ├──> {PATHOGEN}_IRCatch.csv
                                          ├──> {PATHOGEN}_IRSite.csv
                                          ├──> {PATHOGEN}_EstIRRCatch_*.csv
                                          ├──> {PATHOGEN}_summary.txt
                                          └──> {PATHOGEN}_*.png
                                                    │
                                                    v (collect all)
                                              DASHBOARD
                                                    │
                                                    v
                                             dashboard.html
```

---

## 3. Data Handling Strategy

### CSV Data Embedding

| File | Typical Size | Strategy |
|------|-------------|----------|
| `resource_profile.csv` | ~8 rows | Embed as JSON in `<script>` tag |
| `metadata_*.csv` | ~3-10 rows | Embed as JSON |
| `preprocessing_report.csv` | varies | Embed as JSON |
| `{PATHOGEN}_IRCatch.csv` | ~29 rows/pathogen | Embed as JSON |
| `{PATHOGEN}_IRSite.csv` | ~290 rows/pathogen | Embed as JSON |
| `{PATHOGEN}_EstIRRCatch_*.csv` | ~29 rows/pathogen | Embed as JSON |
| `clean_mmwr.csv` | 10K-100K+ rows | **Summary only** (see below) |

### clean_mmwr.csv Handling

This file can be enormous. The dashboard will NOT embed the raw data. Instead, the R script will compute summary statistics:

```r
clean_summary <- list(
  total_rows = nrow(clean_data),
  year_range = range(clean_data$year, na.rm = TRUE),
  pathogens = clean_data %>% count(pathogen) %>% arrange(desc(n)),
  states = clean_data %>% count(state) %>% arrange(desc(n)),
  cases_by_pathogen_year = clean_data %>% count(pathogen, year) %>%
    pivot_wider(names_from = year, values_from = n, values_fill = 0)
)
```

This produces a ~8 pathogens x ~28 years cross-tabulation (~224 cells) displayed as a heatmap. A note links to the full file on disk.

### Image Embedding

All PNGs are Base64-encoded inline. With 8 pathogens x 2 images, the total image payload is ~4-8MB — acceptable for self-contained HTML (MultiQC reports are often 5-20MB).

### Pipeline Info Files

Nextflow execution report, timeline, and DAG are themselves HTML files. The dashboard will link to them with relative paths rather than embedding HTML-in-HTML. The execution trace TSV can be embedded as a sortable table.

### File Size Budget

| Component | Estimated Size |
|-----------|---------------|
| HTML/CSS/JS scaffold | ~150KB |
| Tabulator.js + CSS (inlined) | ~120KB |
| medium-zoom (inlined) | ~5KB |
| JSON data (all CSVs except clean_mmwr) | ~200KB |
| clean_mmwr summary JSON | ~20KB |
| Base64 images (8 pathogens x 2 plots) | ~4-8MB |
| **Total** | **~5-9MB** |

---

## 4. Frontend Components

### Navigation Structure

```
┌──────────────────────────────────────────────────────────┐
│  FoodNetTrends Dashboard          Project: {projID}      │
├──────────────────────────────────────────────────────────┤
│  Sidebar:                          Content:              │
│  Overview                          (selected section)    │
│  Pathogens                                               │
│    Campylobacter                                         │
│    Salmonella ▸                                          │
│      Combined                                            │
│      Enteritidis                                         │
│      Typhimurium                                         │
│      ...                                                 │
│    STEC ▸                                                │
│      Combined / O157 / non-O157                          │
│    Shigella / Vibrio / ...                               │
│  States                                                  │
│    California / Colorado / ...                           │
│  Data Quality                                            │
│  Pipeline Info                                           │
└──────────────────────────────────────────────────────────┘
```

**Sections:**

1. **Overview** — Summary cards (total analyses, pathogens, states, cases), resource profile table, pathogen thumbnail grid grouped by parent pathogen, state profile preview cards
2. **Pathogen Results** (hierarchical: Salmonella and STEC are expandable with subgroups/serotypes) — Each analysis unit gets: overall trend plot, site trends plot, IRCatch table, IRSite table (sortable/filterable, with state names as cross-links to State View), EstIRRCatch table (significance-highlighted), model diagnostics
3. **State View** (one page per FoodNet state) — Cross-cutting perspective slicing IRSite data by state across all pathogens. Three sub-tabs:
   - **Summary**: Multi-pathogen overlay trend chart (using each pathogen's color), latest-year comparison table, sparkline cards per pathogen
   - **All Trends**: Full-size individual trend charts per pathogen for that state, each cross-linked back to the pathogen section
   - **Detailed Data**: Filterable table of all IRSite data for that state (note: relative risk is catchment-level only, not available per state)
4. **Data Quality** — Preprocessing report, resource profile, state/CIDT/travel metadata, clean_mmwr summary heatmap
5. **Run Info** — Pipeline parameters, links to Nextflow reports, execution trace table

### Cross-Linking Strategy

Bidirectional navigation between Pathogen and State views:
- In a pathogen's IR by State tab, state abbreviations are clickable links to that state's profile
- In a state view, every pathogen card/row links back to the relevant pathogen analysis section
- Overview provides entry points to both views (pathogen thumbnails + state profile cards)
- State metadata (join year) is respected throughout — states only show data from their FoodNet entry year onward

### Table Library: Tabulator.js

- Virtual DOM rendering for 100K+ rows
- Built-in sort, filter, column resize, CSV export, clipboard copy
- Single JS + CSS file, no dependencies, MIT license

### Image Viewer: medium-zoom

Click-to-zoom on all plot images. ~4KB, single file.

### Statistical Significance Highlighting

For `EstIRRCatch` tables, color-code rows based on whether the 95% HDI for relative risk excludes 1.0:
- **Green** (`#d4edda`): HDI entirely below 1.0 (significant decrease)
- **Red** (`#f8d7da`): HDI entirely above 1.0 (significant increase)
- **No color**: HDI spans 1.0 (not significant)

---

## 5. Implementation Phases

### Phase 1: Core Scaffold and Data Ingestion (2-3 days)

- Write `generate_dashboard.R` with argument parser, file discovery, CSV-to-JSON, PNG-to-Base64
- Create `template.html` with placeholder tokens
- Produce a minimal but valid HTML file

### Phase 2: Per-Pathogen Result Pages (3-4 days)

- Inline Tabulator.js, implement tab navigation
- Wire tables for IRCatch, IRSite, EstIRRCatch per pathogen
- Display plots with proper sizing, model diagnostics in collapsible blocks

### Phase 3: State View and Data Quality (3-4 days)

- Build state data aggregation in R: for each state, extract IRSite rows across all pathogens, compute summary stats
- Implement state page generation with 3 sub-tabs (Summary, All Trends, Detailed Data)
- Generate multi-pathogen overlay SVG charts per state using R's svg() device or construct in JS from JSON data
- Implement bidirectional cross-links between pathogen and state views
- clean_mmwr.csv summary computation and heatmap rendering
- Preprocessing report table, resource profile, metadata displays
- Overview summary cards + state profile preview grid

### Phase 4: Interactive Features (2-3 days)

- medium-zoom integration for image lightbox
- CSV export buttons on each table
- Significance color-coding on relative risk tables
- Overview quick-glance table

### Phase 5: Nextflow Integration, Polish, Testing (2-3 days)

- Create `modules/local/dashboard.nf`, wire into `workflows/spline.nf`
- Add `r-jsonlite` and `r-base64enc` to `foodnet.yml`
- Add `--skip_dashboard` parameter
- Handle edge cases: missing files, model failures, single-pathogen runs
- Test across browsers (Chrome, Firefox, Edge)
- Add print-friendly CSS (`@media print`)

---

## 6. Testing Strategy

### Synthetic Test Data

Create `dashboard/test/generate_test_data.R` that produces fake pipeline outputs:
- 3 pathogens, 5 states, 1000-row clean_mmwr.csv
- All CSV column schemas matching real output format exactly
- Placeholder PNG images

### Real Data Testing

Point `--output_dir` at a completed run. Handle:
- Pathogens with errors (only `_error.txt` present)
- Missing optional files
- Pathogen subgroups (`SALMONELLA_Enteritidis` vs `SALMONELLA_combined`)
- Single-pathogen runs

### Automated Validation

`dashboard/test/validate_dashboard.R`: checks valid HTML, expected section IDs, Base64 image data present, JSON parses without error, file size within budget (<20MB).

---

## 7. File Listing

### Files to Create

| File | Description |
|------|-------------|
| `dashboard/generate_dashboard.R` | Main R script (~300-400 lines) |
| `dashboard/template.html` | HTML template with CSS/JS and `{{PLACEHOLDER}}` tokens (~500-700 lines) |
| `dashboard/lib/tabulator.min.js` | Vendored Tabulator.js v6.2 |
| `dashboard/lib/tabulator.min.css` | Vendored Tabulator CSS |
| `dashboard/lib/medium-zoom.min.js` | Vendored medium-zoom |
| `dashboard/test/generate_test_data.R` | Synthetic test data generator |
| `dashboard/test/validate_dashboard.R` | Dashboard HTML validator |
| `modules/local/dashboard.nf` | Nextflow process definition |

### Files to Modify

| File | Change |
|------|--------|
| `workflows/spline.nf` | Add `include { DASHBOARD }` and wire after TRENDY (~15 lines) |
| `foodnet.yml` | Add `r-jsonlite=1.8.9` and `r-base64enc=0.1_3` (2 lines) |
| `nextflow.config` | Add `skip_dashboard = false` parameter (1 line) |
| `conf/modules.config` | Add `withName: 'DASHBOARD'` publishDir config (~5 lines) |

---

## 8. R Script Architecture (`generate_dashboard.R`)

```
generate_dashboard.R
├── Argument parsing (argparse)
├── File discovery
│   ├── scan preprocessed/ for CSVs
│   ├── scan spline_results/ for CSVs, PNGs, TXTs
│   ├── scan pipeline_info/ for HTMLs and TXT
│   └── identify pathogen list from filenames
├── Data ingestion
│   ├── read_small_csvs() → list of data frames
│   ├── summarize_clean_mmwr() → summary list
│   ├── read_spline_results(pathogen) → list per pathogen
│   ├── encode_images(pathogen) → Base64 strings
│   └── build_state_views() → aggregate IRSite data by state across all pathogens
├── JSON serialization
│   └── build_data_object() → single nested JSON string (includes per-state aggregations)
├── Template assembly
│   ├── read template.html
│   ├── inline JS/CSS from lib/
│   ├── substitute {{DATA_JSON}} with JSON blob
│   ├── substitute {{PATHOGEN_SECTIONS}} with generated HTML
│   └── substitute {{METADATA}} with run info
└── Write output HTML
```

Key design: R handles all data processing/serialization; HTML template handles all presentation. Bioinformaticians modify R without touching HTML/JS, and vice versa.

---

## 9. Key Implementation Details

### Pathogen Name Parsing
Output files use `{PATHOGEN}_{SUBGROUP}_{suffix}`. Use `resource_profile.csv` pathogen list as ground truth and match against filenames.

### Error Handling for Failed Pathogens
When a pathogen fails, only `{PATHOGEN}_error.txt` exists. The dashboard should show the pathogen in navigation with a "Model failed" indicator and the error message.

### Multiple Comparison Periods
Glob for all `_EstIRRCatch_*.csv` per pathogen (currently only 2016-2018 is active, but others may be enabled later).

### Responsive Layout
Target 1920px desktop (primary) degrading to 1024px (laptop). No mobile layout needed (internal CDC tool).

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| `clean_mmwr.csv` too large | Summary-only; chunked reading if >500K rows |
| Container missing new R packages | Make dashboard optional via `--skip_dashboard` |
| CDN unavailable on air-gapped HPC | All JS/CSS vendored and inlined |
| HTML file too large | Budget 5-9MB; add `--compress_images` flag if >15MB |
| Special characters in pathogen names | `jsonlite::toJSON()` handles escaping; HTML-escape in template |
