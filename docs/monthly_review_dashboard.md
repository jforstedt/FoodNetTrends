# Offline monthly-model comparison review

The standalone review combines verified saved monthly diagnostics, the Salmonella/Campylobacter AR1 comparison, the remaining-pathogen expansion and Shigella recovery. It requires all 54 seasonal model/origin combinations across nine pathogens, paired observed totals, complete site/year report domains, validated task identities and archive manifests. It does not fit models or select a winner.

The underlying models are monthly; the current view plots their **annual forecast totals** with joint 95% predictive intervals. Monthly rate curves and diagnostic-method adjustments are not implemented by this interface. Pathogen, last training year and geography controls show both seasonal RW1 and AR1 with observed totals. The table includes mean/median expected counts, predictive intervals and county/month log scores. Catchment log scores average sites equally and are not log scores of the aggregate total. Interval bounds are never added across counties.

A separate, private reviewed-assessment JSON binds the exact input archive SHA256 hashes to per-pathogen candidate directions and limitations. Only `ar1`, `rw1` or null (neither supported) directions are allowed; these remain provisional. The interface prominently states exploratory status, assumed continuous monthly coverage and realized-population exposure. Accepted annual/state outputs remain separate. Changed archives require a new explicit assessment.

Build with Python 3.6 or later:

```bash
python3 scripts/build_monthly_review_dashboard.py --archive SAVED_DIAGNOSTICS.tar.gz --archive AR1_COMPARISON.tar.gz --archive EXPANSION.tar.gz --archive SHIGELLA_RECOVERY.tar.gz --decisions PRIVATE_REVIEW.json --output NEW_DASHBOARD.html
```

The assessment object has `archives` mapping exact archive basenames to SHA256 and `pathogens` mapping each pathogen to `candidate` plus a plain-language `limitation`. Generated HTML contains internal aggregate study data and is not committed or published. It is fully offline and its selected-comparison CSV export carries pathogen, model, origin, year, geography and exploratory status. Archived RDS objects and individual records are not needed.

Tests cover manifest tampering/omission, JSON embedding safety, incomplete report domains and interval validation. The browser check exercises all origins and pathogens, status labels, export, mobile overflow, page errors and external requests:

```bash
python3 tests/test_monthly_review_dashboard.py
python3 tests/check_monthly_review_browser.py PRIVATE_DASHBOARD.html
```

The 14 September local review built all 54 model/origin combinations from the four hash-bound reviewed archives. Browser validation passed all pathogen/origin selections, nine assessment labels, CSV export, mobile layout, and checks for page errors and external requests. This establishes interface functionality, not scientific acceptance of the forecasts.

## Descriptive diagnostic view

The builder also accepts `--diagnostics DEFINITIONS_ARCHIVE.tar.gz`. Add a `diagnostics` mapping from that archive basename to its reviewed SHA256 in the private assessment JSON. The diagnostic loader verifies the completed definition task and every recorded output hash, then reconciles each field's totals to raw pathogen/site/year record counts and the culturestatus crosswalk to cxcidt counts. It exports no laboratory names or record identifiers.

The optional section has independent raw-pathogen, raw-geography and supporting-field controls. It displays annual recorded classification shares, literal-code totals, field completeness (blank, unknown, not tested and other populated labels), and the same-record classification crosswalk. Unknown and toxin-specific codes remain literal labels; none is silently decoded as a performed or positive test. Missing years have no bar. Shares are conditional on raw records, not population or testing denominators. Date range, exclusions and case universe are deliberately not matched to forecast eligibility in this descriptive view.

CSV export retains literal source codes and `RAW_RECORDS_NOT_MODEL_ELIGIBILITY`. This addition performs no fitting, incidence correction, laboratory adoption inference or specimen linkage. The monthly forecast assessment is unchanged. Browser checks cover all diagnostic pathogen selectors and reconcile exported code counts to embedded data.
