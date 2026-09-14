# Exploratory monthly release checkpoint — 2026-09-14

Checkpoint source line: `feature/rinla-county`. The release packager was committed as `357ea13`. Tag `checkpoint/monthly-exploratory-20260914` marks this documented checkpoint; subsequent work belongs on `feature/rinla-next-phase`.

## Completed scope

The internal exploratory review package combines all nine pathogens, seasonal RW1 and AR1 models at three historical origins (54 combinations), annual forecast totals from monthly models, predictive intervals, descriptive raw diagnostic summaries, provisional model-status labels and integrity/provenance records. Archive/data, browser/export and package checks passed. Accepted annual/state model outputs remain separate and unchanged.

See [release scope and reproduction](monthly_exploratory_release.md), [dashboard interface](monthly_review_dashboard.md), [validation-period inventory](monthly_validation_inventory.md) and [diagnostic readiness](diagnostic_method_readiness.md).

## Scientific status

- Seasonal AR1 remains a candidate for Salmonella, Cryptosporidium, Listeria and Shigella.
- Seasonal RW1 remains the stronger reference for Campylobacter and STEC.
- Neither tested approach supports general forecasting for Cyclospora, Vibrio or Yersinia at present.
- These are exploratory development findings, not independent acceptance. No untouched final-validation period is established in the existing monthly domains.
- Monthly coverage is assumed continuous and forecasts use realized future population exposures. Cryptosporidium retains the 2017 endpoint.
- Diagnostic summaries describe raw source labels and field recording. CX+ is not culture-only; testing-adjusted incidence is not implemented.

## Continue independently where possible

1. Specify any new-period eligibility/denominator/access-history audit before calling later data independent validation; do not rerun the completed comparison matrix.
2. Prepare eligible diagnostic-category aggregates only if pursuing the separately specified classification association target. Preserve literal categories and reconcile to frozen eligible totals before fitting.
3. Treat monthly curves, stronger testing adjustments, new covariates and spline combinations as explicit next-phase additions. They are outside the completed exploratory package and need their own evidence and comparison plans.
4. Preserve candidate failures and uncertainty limitations. Interface completion is not scientific acceptance. Do not silently replace accepted state results or broaden pathogen surveillance eligibility.

## Local artifacts and carryover

The internal ZIP is `output/monthly_exploratory_release_20260914_LOCAL.zip`; its expanded directory contains the dashboard, README, model-status table, assessment and hashes. Supporting private reviews live under `output/*_LOCAL`. These outputs are not in Git and will not appear in a fresh checkout.

Pre-existing uncommitted historical notes and the unrelated local addition to `docs/extension_status.md` are excluded from this checkpoint commit and retained in the working tree. They must not be swept into a later commit. The remote checkpoint contains source and documentation only, not internal study tables, generated HTML or fitted objects.
