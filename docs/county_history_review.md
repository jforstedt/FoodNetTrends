# County history follow-up

Run on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_county_history_review.py
```

This submits one four-slot read-only job using the existing `foodnet.sif`. CSV reading uses four threads; the remaining aggregation and plots are modest serial work. There is no model fitting, INLA sampling or container build. The launcher prints one archive path and logs.

The job reviews the 15 counties appearing among the largest excess-zero contributors in either saved-fit diagnostic, plus their audited graph neighbors. It reads the clean CSV and audited county panel, verifies the clean-file and panel checksums against the prior audit/fits, and reconstructs all 7,776 selected county/year case counts. A mismatch stops the review.

Outputs contain internal aggregate information:

- Annual cases, populations, observed incidence, fitted spatial/IID incidence summaries and expected count means for targets and neighbors.
- Plots of target annual counts against fitted means, and observed incidence against pooled graph neighbors.
- Target summaries showing zero years and concentration of cases in the largest year.
- County/year source-name, travel and diagnosis category totals, and state/year filter and geographic-mapping totals. These use the clean CSV before applying the pilot's selection filters, not the original unprocessed SAS records.
- Checksums and an explicit reporting-completeness limitation.

The archive contains exact county aggregates for this internal diagnostic review. It excludes individual records, the full clean CSV, panel RDS and model checkpoints. No data is sent anywhere automatically. The saved inputs are mounted read-only and written outputs go into a new directory.

The review can identify a case spike, changing labels, excluded records or geography patterns. It cannot establish reporting completeness from case records alone, nor assign state-level unknown-county records to a specific county. Completeness remains unverified unless corroborating surveillance documentation is obtained. No automatic model change follows from these checks.

Validation: unit tests cover exclusions, preservation of zero cells, exact county/year reconciliation and state/FIPS mismatch rejection. An end-to-end synthetic 7,776-cell / 122,024-record fixture exercises checksum gates, all 15 target histories, neighbor aggregation and PDF generation. Launcher tests check read-only binds, four-slot allocation and shell syntax. The real-data archive remains pending cluster execution.
