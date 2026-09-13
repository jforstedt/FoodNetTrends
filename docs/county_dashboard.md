# Offline exploratory county dashboard

The dashboard is a standalone HTML file built from completed county report archives. It displays the full-period `spatial_county_time` fit for Salmonella, 2004–2019, with an optional `iid_county_time` comparison line. No fitting, posterior sampling, container build, cluster job, web server or runtime library download is required.

Features:

- Offline Census county maps, state zoom, county selection and a year slider.
- Fixed-bin estimated incidence, observed incidence and credible-interval-width maps.
- County counts, population, estimated median incidence and 95% credible intervals.
- Observed-versus-estimated trends in rate or expected-count units, with optional nonspatial comparison.
- Searchable/sortable county table and selected-county CSV download.
- Sparse-history context, retrospective forecast evidence when supplied, and model/validation limitations.
- Embedded source archive hashes and cartographic provenance.

The credible band concerns the underlying rate or expected count, not a predictive interval for a future observed count. Forecast summaries are separately labeled and refer to a different training/evaluation split. Other states become gray context when a state is selected; gray is never interpreted as zero incidence. No state-level uncertainty is manufactured by summing county interval endpoints.

## Rebuild

With Python 3.6 or later, supply the completed audit, raw review and sensitivity archives, plus the optional forecast archive:

```bash
python3 scripts/build_county_dashboard.py --audit AUDIT.tar.gz --raw-review RAW_REVIEW.tar.gz --sensitivity SENSITIVITY.tar.gz --forecast FORECAST.tar.gz --output county_explorer.html
```

The output path must not already exist. The builder reads archive members without extracting or executing them. It verifies passing audit/reconciliation/model statuses, matching panel and clean-input hashes, exact population and fitted keys, state-level case reconciliation, fitted interval ordering, count/rate scaling, and public geometry coverage. It reconstructs county counts from the reconciled aggregate clean-record counts and joins the audited county populations; it never needs the individual-level CSV or saved model RDS.

The generated HTML contains internal county aggregate data and should be handled as internal analysis output. Opening it makes no external network requests. Census source links are optional user navigation. Neither HTML nor downloaded CSV is published automatically, and generated real-data artifacts are not committed to the repository. The established state dashboard remains separate.

## Public display geography

`dashboard/county_boundaries.json` contains public 2019 Census cartographic county/state boundaries, filtered to the audited pilot counties, projected for display and rounded to 0.01 SVG units. Sources and SHA256 hashes are embedded in its provenance. Reproduction uses only the Python standard library:

```bash
python3 scripts/build_county_map_geometry.py COUNTIES_2019_KML.zip STATES_2019_KML.zip analysis_configs/county_pilot/counties.csv dashboard/county_boundaries.json
```

The official [Census 2019 KML directory](https://www2.census.gov/geo/tiger/GENZ2019/kml/) supplies `cb_2019_us_county_5m.zip` and `cb_2019_us_state_5m.zip`. The display projection is spherical Albers with standard parallels 29.5/45.5 and central longitude -96. It is not an EPSG:5070 transformation. Display boundaries do not alter the separately audited 2010 adjacency graph or historical identifiers.

## Verification

Synthetic tests check complete reconciliation, wrong-panel/difference rejection, JSON embedding safety, and geometry coverage. Browser checks exercise desktop/mobile layout, data values, keyboard county selection, year/filter controls, comparison curves, CSV download, absence of page errors and absence of external requests:

```bash
python3 -m unittest discover -s tests -p test_county_dashboard.py
python3 tests/check_county_dashboard_browser.py county_explorer.html
```

Playwright/Chromium is needed only for the optional browser test, not to build or open the dashboard.
