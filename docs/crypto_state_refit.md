# Corrected Cryptosporidium state rerun

Run `python3 scripts/launch_crypto_state_refit.py` on Rosalind with Singularity
loaded. One SGE job invokes a snapshot of the existing trendy.R state pipeline
for CRYPTOSPORIDIUM/combined. It does not launch Nextflow, preprocessing, other
pathogens, or an INLA fit. The existing cleaned cases and foodnet.sif are reused.

The agreed reference baseline is 2015–2017. Observation ends in 2017 under the
corrected input rule, and parasite_end_year is explicitly set to 2017. The
state spline formula and priors are copied unchanged. Sampling uses rstan,
6 chains, 10,001 iterations, adapt_delta 0.99, max_treedepth 15 and seed 123.
The job requests 12 slots, 48 hours, h_rss/mem_free 53248M and h_vmem 68G,
matching the earlier successful resource request. BLAS threads are set to two.

A unique output directory preserves all old result files. The collector checks
that incidence and baseline-comparison tables contain the agreed baseline years
and end in 2017. Sampling diagnostics are included for subsequent review;
execution/coverage PASS does not certify convergence. The archive contains
reports, plots, logs and snapshotted source, but excludes the saved brms fit.
The full fit remains on HPC. No original dashboard is replaced automatically.
