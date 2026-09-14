# County/monthly release readiness

This is the release boundary for the exploratory monthly extension, not a claim that every pathogen or future extension is validated. The current AR1 comparison is still pending. Preserve accepted annual state outputs and identify county/monthly products separately.

## Scope and selection

The first monthly release covers only pathogens and time domains that have completed input reconciliation, numerical checks and predictive review. Current seasonal comparisons concern Salmonella and Campylobacter. They do not validate monthly forecasting for all nine pathogens or their serotypes. Pathogen-specific surveillance eligibility remains a data contract; fitted parameters differ by pathogen without automatically requiring different model families.

The running AR1 comparison and the original seasonal RW1 references use previously inspected historical origins. Treat the comparison as exploratory model development. Before a validated forecasting designation, identify a genuinely unused evaluation period with eligible observations and required exposures, freeze the selected specification and criteria, and record the evaluation. If no unused period is available, state that limitation instead of calling another pass independent validation.

Evaluate predictive log scores, calibration and interval width together with horizon-specific bias and posterior numerical stability. Review differences by pathogen, origin and site; do not choose solely from pooled averages, WAIC, attractive curves or corrected mean bias. Sampling streams measure Monte Carlo stability, not independent forecast replications. Separate model selection from artifact generation: dashboard assembly must never silently refit or choose a winner.

## Display contract to implement after selection

Each monthly view needs pathogen, geographic scope, training cutoff, forecast period, model identity and exploratory status. Show monthly observed counts and estimated rates with clearly named units. Distinguish estimated underlying-rate credible intervals from predictive intervals for future counts. Keep observed and forecast periods visually distinct and label retrospective forecasts explicitly.

Show means and medians with their definitions when both are offered; do not silently replace a mean by a median to hide a heavy tail. Aggregate using joint posterior draws. Never sum county interval endpoints or county medians to construct state summaries. State-level outputs from Daniel's model and county-model aggregations must retain their separate identities.

An absent observation, excluded period or unsupported county must not render as a zero. Display the assumed-continuous monthly surveillance limitation and the exposure derivation. Existing offline county maps describe annual pilot outputs; they are not yet a monthly forecast interface. Do not overwrite those outputs with a different model under the same label.

Exports should carry model, origin, horizon, units, uncertainty type and input/source identifiers. Bind tables and plots to the reviewed fit and archive hashes. Generated internal data and dashboards stay outside source commits. Preserve offline behavior; no runtime downloads or automatic publication.

## Release checks

- Completed input reconciliation and documented pathogen eligibility for every offered view.
- Accepted numerical and predictive review for the exact displayed fit, with limitations recorded.
- Exact joins and units; invalid/missing periods stay distinct from zero.
- Correct joint-draw aggregation and interval labeling.
- Desktop/mobile navigation, keyboard county selection, filtering and CSV export.
- No browser errors or external requests in the offline explorer.
- Accepted state artifacts remain unchanged; source provenance and output identity survive packaging.
- One end-to-end reproduction from frozen inputs to reviewed output, followed by archive integrity checks.

Monthly dashboard integration and model acceptance remain outstanding. Additional covariates, spline combinations, wider pathogen scope and reconciliation between state and county forecasts are later extensions, not prerequisites for a clearly limited exploratory release.

## Local readiness pass, 2026-09-13

The existing county explorer passed the browser checks on desktop/mobile: displayed values, map keyboard selection, filters, comparison control, CSV download, no page errors and no external requests. County reconciliation/embedding tests, accepted-state packaging tests and feature-dashboard replacement/preservation checks passed. The synthetic state dashboard also passed payload, 2019 baseline-column, convergence-label and emitted JavaScript syntax checks. These checks validate existing interfaces and packaging, not the pending monthly model or future monthly interface.

Run these scripts explicitly: `test_dashboard.py` requires a fixture HTML argument and `check_county_dashboard_browser.py` requires an explorer HTML argument; they are not unittest discovery modules. Chromium required execution outside the restricted local sandbox. No cluster jobs or model refits were started in this readiness pass.
