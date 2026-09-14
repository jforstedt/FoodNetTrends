# Broader combination batch

This exploratory batch starts three independent branches concurrently. It does not alter Daniel's state model or promote any candidate to the dashboard.

The spatial branch fits 162 new models: nine pathogens, three historical forecast origins, three temporal forms (RW1, AR1, spline), and seasonality off/on. Each replaces the independent county intercept with a scaled BYM2 county intercept using the pinned pilot graph. It reuses the 162 completed independent-county controls with matching inputs and forecast targets. County effects are static; this is not a dynamic spatial interaction model. Priors, graph checks, and protected surveillance endpoints are specified in monthly_spatial_combination.md. Paired spatial, temporal, seasonal and three-way contrasts assess whether components help in combination. Historical origins have already informed development and are not independent confirmation data.

Six diagnostic-classification preparations run alongside those fits. They reconstruct monthly CX/CIDT counts and reconcile annual support, preserving unknown dates and codes. The target is CIDT among classified cases, not an incidence adjustment or an independent measure of testing intensity. Classification combination fits follow review of these inputs and binomial priors; existing annual controls cannot substitute for monthly controls. See classification_combination_protocol.md.

The third branch inspects all 54 saved spline fits without fitting or posterior sampling. It separates posterior mean linear and nonlinear state temporal contributions over training and forecast months. These log-scale component summaries exclude the intercept, county and seasonal effects; they are neither mean predicted counts nor joint uncertainty intervals. Examining every pathogen avoids selecting only conspicuous failures.

Existing controls and fit checkpoints remain unchanged. Branch collectors verify task identity and hashes and preserve failures. A final collector bundles the three portable archives. Successful execution is distinct from scientific acceptance. Private row-level RDS files stay on the cluster.

Run from the repository on an SGE host with singularity loaded:

```bash
python3 scripts/launch_broader_combinations.py
```

Preparation runs detached from the terminal. Arrays are submitted as each independent preparation finishes, without a three-task concurrency cap: spatial tasks request four CPUs, classification preparations two, saved inspections one. A single final archive and preparation log are printed at launch. Do not launch again merely because preparation is still running.

The spline basis CSV files are unchanged. The source manifest refresh records an optional county-effect hook; the default independent-county formula remains unchanged.
