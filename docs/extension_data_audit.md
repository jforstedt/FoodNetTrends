# Parallel extension data audit

Run `python3 scripts/launch_extension_data_audit.py` from the feature/rinla-county
checkout on Rosalind after loading singularity. It uses the existing foodnet.sif,
raw MMWR/census paths, cleaned file and reviewed county-panel paths already used
by this project. It builds no container and fits no models.

One 11-task array runs independently: diagnostic methods, dates/seasonality, and
nine pathogen-specific county count/geography/history audits. A held collector
validates report manifests and writes one aggregate internal archive. Each task
requests two CPUs, 16 GB RSS and 32 GB virtual memory; no concurrency cap is added.
Once both scheduler job IDs appear, execution no longer depends on the terminal.

The launcher records input/code/container fingerprints; workers verify them before
and after reads. County workers also recheck audited eligibility and reconciliation.
Missing or failed tasks remain visible in the final summary. An execution-complete
report is not scientific approval. No case rows or identifier values are exported.
Source data and accepted fits are left unchanged.

Diagnostic summaries inventory the actual category field and potential supporting
fields without inventing laboratory linkage or a testing denominator. Seasonal
summaries retain candidate date meanings and parsing problems without assigning
a primary event date or constructing missing-month zeros. County summaries assess
data support for splines, spatial sharing, pathogen priors and count distributions;
they do not fit or select those models.

A data dictionary, laboratory adoption/testing-volume records and an observation
calendar may still be needed after inspection. These cannot be inferred merely
from case-category frequencies or dates present among observed cases. NHSN is a
separate healthcare surveillance source; no NHSN data are downloaded or merged in
this audit.
