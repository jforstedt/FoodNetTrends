# Campylobacter regional history audit

## Launch from Git

After pulling `feature/county-covariates-seasonality` on the cluster and loading
Singularity, run `python3 scripts/launch_campylobacter_regional_audit.py` from the
repository root. No uploaded bundle is required. The launcher snapshots its code
and the source-hash receipt into a new output directory before submitting the
visible SGE job. Heavy source verification runs inside that job. The existing
completed covariate run and monthly preparation must still be present.

The tracked source receipt contains run identifiers and cryptographic hashes,
not surveillance records or private absolute paths. Runtime paths are resolved
from the hash-verified original plan on the cluster. The independent older bundle
remains usable; do not launch both forms for the same intended audit.

This is a read-only diagnostic following persistent early-origin Georgia and
Tennessee underprediction. It does not fit or resample a model, modify inputs,
reclassify diagnostic methods, or promote an analysis.

Use the frozen source plan and Campylobacter candidate/annual panel from
county_covariate_experiment_20260915_113139_060588. Reuse that run's container and
compiled R library. Bind the source archive receipt, plan and relevant inputs;
check input identity before and after the audit. Submit one immediately visible
SGE audit job with 2 CPUs, 16 GB resident memory and an eight-hour limit. No package
installation, container build or model array is needed.

Inspect the complete 2004–2019 history and all ten study states, retaining the
three previous forecast origins for interpretation. Report counts, person-years,
descriptive rates and county-domain changes. Reconcile monthly and annual
aggregates against the frozen preparation evidence and audit panels. Read the
original clean source only when its identity is established by input checksums;
inventory recorded diagnostic, travel and site labels without inferring test
sensitivity, reporting completeness or biological incidence. Unavailable evidence
must be reported as unavailable rather than interpreted as agreement.

State-level summaries and provenance enter a private portable archive. Any
county-level details must retain the INTERNAL filename marker and stay excluded
from the archive. No case-level data are exported. Keep unknown source labels
explicit. Use counts of counties to describe the modeled domain, not to certify
actual participation or reporting completeness.

The model already includes state-specific monthly time trajectories. The audit
tests whether a regional level change, diagnostic composition, exposure or domain
issue warrants a subsequent controlled sensitivity; it cannot determine the
cause by itself. The existing preparation report shows a post-2011 increase in
GA/TN recorded rates and no unassigned specimen dates. Aggregate raw/clean
agreement is not individual record linkage or external ascertainment validation.

Successful execution means audit outputs were produced with unchanged inputs.
Scientific readiness remains false. Any unexplained count/exposure mismatch
must be resolved before model adjustment. Otherwise, choose a matched sensitivity
from documented evidence rather than selectively tuning the highlighted regions.
