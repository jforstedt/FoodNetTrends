# Monthly evaluation-period inventory

Reviewed 2026-09-14. **No independent final-validation period is established in the current audited monthly inputs.** The completed comparison is exploratory development evidence. Changing a forecast origin or using a different monthly model within the same observed period does not create untouched data.

## Documented use

| Pathogen scope | Prepared domain | Training origins | Union of evaluated years |
|---|---|---|---|
| Salmonella, Campylobacter, Cyclospora, Listeria, Shigella, STEC, Vibrio, Yersinia | 2004–2019 | 2011, 2013, 2016 | 2012–2019 |
| Cryptosporidium | 2004–2017 | 2011, 2013, 2014 | 2012–2017 |

Every year in these prepared domains appears in training, evaluation, or both. The 2013-origin evaluation overlaps the 2011-origin evaluation in 2014. Cryptosporidium additionally has overlapping 2013/2014-origin evaluation. The original annual county comparisons used these periods too; monthly outcomes are subdivisions of those previously inspected annual outcomes, not an unrelated validation sample.

Evidence is the fixed [county protocol](county_forecast_validation_protocol.md), [first monthly protocol](monthly_comparison.md), [seven-pathogen expansion](monthly_expansion.md), and [Shigella recovery](monthly_shigella_recovery.md). Private archive reviews establish the completion history; this public inventory contains protocol metadata only. It does not re-read patient records or claim independent verification of unavailable internal fit objects.

The provisional candidates remain AR1 for Salmonella, Cryptosporidium, Listeria and Shigella; RW1 references for Campylobacter and STEC; neither candidate supported for general forecasting for Cyclospora, Vibrio or Yersinia. Candidate labels are not production acceptance. Freeze these identities and their exact source/provenance before any further evaluation.

## Why later years are not automatically a holdout

The current monthly county loader ends in 2019, or 2017 for Cryptosporidium. Extending its date range alone would bypass the existing input contract. A later calendar date is neither proof of complete surveillance nor proof that its outcomes have never informed this project. Accepted annual/state analyses and their reviews extend beyond this monthly domain. Their outcome-access history must be recorded before using the word independent.

- Cryptosporidium cannot be extended beyond its established 2017 surveillance endpoint.
- A 2020–2022 candidate interval for other pathogens would need new county population/geographic reconciliation and an explicit pandemic-era interpretation. It is not currently eligible or reserved as an untouched evaluation set.
- Connecticut inputs from 2020 onward contain historical-county and planning-region geography issues. Use a reconciled geographic system; never add the two systems together. See [the denominator review](county_coverage_reconciliation.md).
- Later Colorado county scope and Yersinia coverage require their existing safeguards. Campylobacter's current ceiling is 2023. Optional-reporting pathogens cannot automatically include 2025. See [surveillance safeguards](surveillance_input_safeguards.md).
- Monthly reporting continuity remains an explicit assumption, not a certified site-month interruption ledger. Realized future population exposures also make the existing experiments conditional retrospective forecasts.

## Next executable step

The source-only inventory can run on this PC, with no container, raw data, cluster job, model fit or network request:

```bash
python3 scripts/inventory_monthly_validation.py output/monthly_validation_inventory_LOCAL
```

It refuses an existing output directory. `pathogen_inventory.csv` records all nine provisional candidates and their protocol domains; `year_inventory.csv` marks training/evaluation overlap and unassessed or excluded extension years. No row is automatically certified independent. These are documented protocol facts, not discovery of file availability or completeness.

Before any new-period HPC model run, specify a metadata/reconciliation audit that reports only: county/geography keys and denominator validity; effective pathogen/site/month eligibility and evidence; source vintages and checksums; and a manually reviewed log of previous outcome access. Do not export case totals, rates or forecast errors while deciding whether a holdout can be protected. Validating dates or record eligibility against private raw files must be explicitly separated from revealing held-out outcomes. Nonzero records cannot certify reporting continuity. Such an audit is needed only if extending the present domain; repeating the existing monthly preparation gives no new independent years.

Once a genuinely eligible period and its access history are established, freeze the model, comparator, prediction horizon, scoring and uncertainty criteria before scoring. If no sufficiently protected period exists, label the next experiment external-period exploratory assessment or prospective validation as appropriate. Do not relabel another developmental hindcast as confirmation. A bounded exploratory dashboard release need not wait for an unavailable independent holdout, provided its scientific status and unsupported forecasts remain explicit.
