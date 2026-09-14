# Bounded exploratory release

The first internal monthly review package is ready as a descriptive and model-comparison product. It is not a validated forecasting service for all nine pathogens. Its scope is frozen to the reviewed seasonal RW1/AR1 comparisons, provisional model-status labels and descriptive raw diagnostic summaries. Accepted annual/state outputs remain separate.

## Included

- All nine pathogens, both monthly temporal candidates and three origins: 54 fitted model/origin combinations.
- Annual forecast totals from those monthly models, observed totals, joint predictive intervals and comparison exports.
- Raw diagnostic classification shares, literal-code crosswalks and supporting-field recording summaries.
- Offline HTML, readable limitations, a machine-readable candidate-status table, reviewed input assessment and source/input/file hashes.

## Not part of this release

Independent confirmatory validation, live forecasts, monthly curve plots, reporting-delay nowcasting, testing-adjusted true incidence, automatic model selection, additional predictor combinations and repairs to every unsupported pathogen remain outside this release. No new execution is required merely to display the completed comparisons. The provisional candidate labels are not evidence of independent acceptance.

## Build and verify

`scripts/package_monthly_exploratory_release.py` consumes the same four comparison archives and reviewed private assessment as the dashboard builder, plus the optional definitions archive. It rebuilds from validated inputs, refuses existing outputs, writes a small standalone directory and ZIP, and verifies every package member before finishing. No fitting, container, cluster access or web connection is required. Generated packages contain internal aggregate study data and remain uncommitted.

```bash
python3 scripts/package_monthly_exploratory_release.py --archive SAVED.tar.gz --archive AR1.tar.gz --archive EXPANSION.tar.gz --archive SHIGELLA.tar.gz --decisions PRIVATE_ASSESSMENT.json --diagnostics DEFINITIONS.tar.gz --output NEW_RELEASE_DIRECTORY
```

Open `dashboard.html` after unzipping. `README.md` explains use and scientific limits. `model_status.csv` records provisional directions; `provenance.json` and `SHA256SUMS.json` bind sources and package contents. Source identity is not proof of scientific validity.

Validation covers archive/task/domain checks, paired observed totals, literal diagnostic reconciliation, safe HTML embedding, refusal to overwrite, ZIP tamper detection, all pathogen/origin browser controls, CSV exports, mobile layout, and absence of browser errors/external requests. This is evidence for interface and package correctness, not automatic acceptance of forecast calibration.

## Next phase boundary

Any extension to newer periods requires geographic/denominator reconciliation, surveillance eligibility and prior outcome-access review. Current years do not establish an untouched final evaluation. A diagnostic-category association model first requires eligible category aggregates reconciled to the frozen model universe; raw category shares cannot be used as future incidence predictors. Stronger testing adjustment requires definitions and ascertainment evidence not currently established. Those scientific developments can proceed independently, but they do not keep this bounded exploratory package indefinitely open.
