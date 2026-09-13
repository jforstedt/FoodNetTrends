# Monthly preparation before seasonality

This preparation-only run builds Salmonella and Campylobacter candidate monthly inventories for the audited 486-county, 2004–2019 footprint. It does not fit models, regenerate preprocessing, or modify accepted state or county results.

From the repository on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_monthly_preparation.py
```

The launcher submits both pathogens concurrently as a two-task SGE array (two slots and a two-hour limit each), followed by a held collector. It snapshots the source scripts and records input, source, plan and result checksums. The existing `foodnet.sif` is sufficient; no container build is needed. Python 3.6 is supported. `--prepare-only` writes an explicitly unverified plan without submitting jobs; that plan cannot execute.

## Checks and interpretation

Each task rechecks the existing annual audit and raw-to-clean aggregate reconciliation. Recorded preprocessing aliases identify the raw pathogen labels. Selected raw records must reproduce the annual county counts under the existing travel, diagnostic and geographic filters. This establishes aggregate agreement, not individual record linkage.

Specimen dates supply candidate months only when their year agrees with the recorded surveillance year. Missing or conflicting dates remain explicitly unassigned. Invalid source month codes and disagreements with specimen month are summarized for review; this preparation does not silently declare either field authoritative for modeling.

Candidate person-years allocate annual population in proportion to calendar days, including leap years. Their sum must reproduce annual population. This is an exposure proposal, not a validated within-year population model.

All monthly observation statuses remain `UNVERIFIED`, and all modeled counts remain missing. A zero record inventory does not establish observed zero incidence. See [the public coverage review](monthly_coverage_evidence.md) for the supporting program evidence and its limits. Preparation can complete while scientific readiness remains `REVIEW_REQUIRED`.

## Outputs

The launcher prints the output directory, array and collection job IDs, final collection log, and one `.tar.gz` archive. Each pathogen contributes:

- State-month record inventory and candidate person-years.
- State-year reconciliation of annual, assigned and unassigned counts and exposure.
- Aggregate specimen-date and source-month issues.
- An unverified state-month calendar template and readiness report.
- Input checksums and execution logs.

The county-month candidate RDS stays on the cluster and is excluded from the portable archive. The archive contains aggregate reports, source snapshots and provenance; it contains no individual records. Treat reports as study data and do not commit them to Git.

The collector independently checks the full monthly domain, count/exposure reconciliation, readiness flags and completed artifact hashes. Missing or failed tasks produce a partial archive and a nonzero collection status. Do not relaunch completed preparation merely because scientific readiness remains unresolved.

Next, review the returned date issues and reconciliation together, document observation-calendar and exposure assumptions, and only then finalize the monthly seasonal comparison design. Numerically unreliable spline fits remain excluded; the later spline-plus-seasonality comparison remains conditional on resolving those issues.

Local validation covers leap-year exposure, missing and conflicting dates, invalid month codes, annual mismatches, withheld modeled counts, launcher arguments, array dispatch, altered plans and partial collection. Actual SAS ingestion and audited production reconciliation require this cluster run.
