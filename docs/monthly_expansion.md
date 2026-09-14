# Parallel monthly expansion

One launch prepares the seven remaining combined pathogens and queues up to 42 exploratory fits, followed by one portable report archive. Existing Salmonella/Campylobacter fits are not rerun. This is development evidence, not independent final validation: annual data and some historical periods have informed prior work.

The candidates are the existing seasonal RW1 and stationary seasonal AR1, with exactly their current priors and likelihood. Both are fit for every eligible pathogen at each origin; no AR1 winner is assumed. Origins are 2011, 2013 and 2016, except Cryptosporidium uses 2011, 2013 and 2014. Forecasts extend three years. The audited domain is 486 counties, starting 2004 and ending 2019, or 2017 for Cryptosporidium. Population forecasts are conditional on realized future annual exposures. No claim is made about newer years, serotypes or coverage certification.

Each pathogen's preparation checks the existing audited panel and raw-to-clean provenance. Parasite population selection is inherited from its audited panel. Listeria raw CSTE must equal YES and cleaned CSTE eligibility is checked, matching the existing reconciliation. All existing travel, diagnostic and county exclusion rules are retained. Monthly exposure uses calendar days and annual population. Source inventories remain UNVERIFIED; modeling copies explicitly use EXPLORATORY_ASSUMED_CONTINUOUS. This remains a substantive assumption, not evidence of reporting completeness.

Automatic fitting requires a completed, hash-bound preparation, complete county/month domain, exact annual count/exposure reconciliation, no unassigned specimen dates and no specimen/source-month disagreements. Any failing pathogen remains blocked with reports available; other pathogens proceed. A gate pass is permission for conditional exploratory analysis, not statistical acceptance. No missing inventory is silently certified as an observed zero.

Fit tasks mask all future counts, run four cores, save internal fit checkpoints, and draw four disjoint streams of 2,000 posterior samples. Diagnose numerical completion, county predictive scores, site/catchment joint predictive intervals and tails, latent uncertainty and hyperparameters. Compare matched pathogen/origin/horizon outcomes; examine sparsity, Monte Carlo stability, coverage and bias alongside predictive scores. Do not select solely from pooled scores or treat correlated counties/overlapping years as independent trials. No automatic model selection, dashboard replacement, publication or retry loop occurs.

SGE submits seven preparation tasks concurrently, then an array of 42 fits with no concurrency cap (up to 168 allocated CPU slots), and a held collector. Fits request four cores, 52 GB RSS and 48 hours using the established resource request pattern. Actual resource interpretation remains cluster-specific. Preparation uses two cores per task for input reading; allocating more would not accelerate its sequential checks. No new container is built. All scripts and inputs are frozen and checked. A failed fit does not stop unrelated array members; partial results are archived with nonzero collection status. Internal RDS checkpoints and individual records are excluded from the archive.

Run from FoodNetTrends on Rosalind:

```bash
git pull --ff-only personal feature/rinla-county && module load singularity && python3 scripts/launch_monthly_expansion.py
```

After all three job IDs are printed, jobs are owned by the scheduler and no terminal connection is needed. The launcher does not submit remotely from the development PC. Final review must distinguish execution completion, monthly data readiness and scientific acceptance.
