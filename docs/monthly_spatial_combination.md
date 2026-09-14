# Monthly spatial × temporal × seasonality comparison

Status: separate exploratory extension; no model acceptance and no change to Daniel's accepted state model.

The complete grid has 324 cells: nine pathogens × three historical forecast origins × three temporal specifications (RW1, AR1, spline) × two seasonal settings × two county effects (IID, BYM2). The 162 completed IID controls are reused from `monthly_spline_factorial_20260914_120120_695932`; only 162 BYM2 arms require new fits. Cryptosporidium keeps origins 2011, 2013, 2014 and its 2017 endpoint; other pathogens retain 2011, 2013, 2016 and endpoint 2019. No outcome-based pathogen exceptions are introduced.

## Scientific question

Does borrowing information between adjacent counties improve forecast accuracy or calibration, and does that improvement depend on temporal structure or seasonality? BYM2 replaces the static IID county intercept with a mixture of scaled structured and independent county effects. It does not add county-specific temporal trajectories. This isolates the county spatial prior while preserving state-specific temporal effects, the common cyclic monthly effect when included, and the negative-binomial likelihood. Spline's poor standalone results do not establish that its spatial combination fails; conversely, spatial borrowing is not assumed to repair extrapolation.

## Fixed specification

The total county-effect SD prior is PC with P(SD > 1) = .01, matching the IID county SD bound. The structured mixing parameter uses the existing county pilot's INLA `pc` prior with `param=c(.5,.5)`. This is a graph-dependent PC prior, not a uniform mixing distribution. BYM2 uses `scale.model=TRUE`, `constr=TRUE`, and `adjust.for.con.comp=TRUE`. Constraints and scaling account for disconnected graph components. Isolated counties are rejected pending a separately specified treatment.

All temporal, slope, seasonality, state-intercept, dispersion, exposure and training-mask choices are retained from the paired IID control. The state trend remains replicated by state; a shared seasonal effect remains cyclic and constrained. The spline basis is the same training-only k=6 phase-orthogonal basis, including the existing slope and nonlinear priors. Comparisons of RW1, AR1 and spline remain comparisons of full model/prior packages, not identical temporal priors.

Graph inputs are `analysis_configs/county_pilot/counties.csv`, `edges.csv`, and `provenance.json`: 486 counties, 1,210 undirected edges, ten connected components, no isolated counties. The existing graph is based on the Census 2010 adjacency reference with the established water-neighbor and cross-state-edge rules. County IDs are mapped to the sorted original area identifiers used by `monthly_model_data`; row order is never an adjacency assumption. Nodes must exactly equal the modeled counties; county/state membership, unique edges, canonical edge orientation, and absence of isolated nodes are checked. No silent induced subgraph is constructed. Historical-vintage adjacency is a structural assumption, not independently time-varying surveillance coverage certification.

## Interpretation and validation

Compare BYM2 minus IID within each temporal/seasonal/origin cell. Then compare spatial gains with and without seasonality, and between temporal families. The three-way interaction is the difference between temporal-by-seasonality interactions under BYM2 and IID. Preserve per-state results and equal-state summaries; do not equate posterior sampling streams with independent forecast experiments. Annual bias, predictive coverage, interval width, median predictions, tail concentration and stream stability accompany predictive log scores. CPO does not rank or accept models.

Reuse requires identical held-out truth, original source and copied report hashes, successful source summaries and matching domains. Graph, basis, code and runtime input files must be snapshot-bound. Future case counts are masked internally; basis construction and temporal centering use training months only. Future population remains realized exposure, so these are exposure-conditional retrospective forecasts. These repeatedly examined origins support development decisions rather than untouched external confirmation.

Diagnostic-method classification is a separate outcome experiment. Case-derived CX/CIDT composition is not inserted into this incidence grid as an ascertainment covariate. A joint observation model needs a separately specified likelihood and defensible ascertainment inputs.

## Local implementation and verification

`monthly_spatial_combination.R` wraps the existing fitters via an opt-in county-effect hook. Default IID calls retain their existing formulas and arguments. The adapter replaces exactly one `f(area,...)` call, preserving its formula environment and every noncounty effect. `run_monthly_spatial_factorial.R` retains the saved-fit audit protocol, four posterior streams and exposure handling; spline uses the tested APredictor adapter, while RW1/AR1 use Predictor.

`tests/test_monthly_spatial_combination.R` checks graph permutation invariance, disconnected components, wrong/missing nodes, isolated nodes, duplicate edges, state mismatches, the real candidate graph and poisoned future counts. With `--fit`, it runs six actual pinned-INLA synthetic BYM2 fits across all temporal/seasonal cells and checks finite count-scale posterior predictions against independent fitted marginal means. These are engineering checks, not validation of real-data predictions.

Local gate completed: all six actual pinned-INLA BYM2 synthetic fits passed, including production-style saved-fit adapters on a three-year forecast horizon. Posterior sample/marginal count-scale ratios ranged from 0.969 to 1.029. The default fitter bodies matched the pre-extension revision after removing only the optional hook and its forwarding argument. This establishes implementation compatibility, not real-data acceptance.
