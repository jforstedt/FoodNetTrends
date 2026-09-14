# Frozen monthly spline × seasonality experiment

Protocol version: monthly_spline_factorial_v1. Frozen 2026-09-14 before these
real-data spline fits. This is exploratory development using already examined
years, not untouched validation. No production model or accepted dashboard is
changed. The complete RW1/AR1 experiment is reused from
monthly_factorial_20260914_111339_242279.

## Question, scope and rationale

Can a gradually varying state temporal trend, with or without a shared annual
cycle, improve prediction while preserving credible annual uncertainty? The
spline permits more flexible gradual change than a stationary AR1, with
different extrapolation from RW1. This is a modeling hypothesis, not a claim
about pathogen biology. All nine pathogens receive the same candidate arms;
no pathogen is selected or omitted based on previous scores.

Fit 54 new cells: nine pathogens × three origins × spline with seasonality
off/on. Reuse 108 completed cells covering RW1 and AR1 with seasonality off/on.
The assembled comparison contains 162 cells. Origins are 2011/2013/2016 except
Cryptosporidium, which uses 2011/2013/2014 and its established 2017 endpoint.
Other source panels end in 2019. Training begins in 2004; each origin predicts
three years. Use exactly the original audited candidate panels, date resolution,
eligibility and day-weighted person-years. Future exposures remain realized,
retrospective values; coverage remains EXPLORATORY_ASSUMED_CONTINUOUS.

## Prior and extrapolation fixed before fitting

Use `monthly_spline_combination.R` unchanged scientifically: six-function
training-only thin-plate basis, four penalized nonlinear columns after removing
constant/linear null space, state-specific nonlinear coefficients with shared
PC scale P(SD>.5)=.01, and state slopes Normal(0,.5²) per training span. The
nonlinear design is projected against training intercept, linear time and eleven
month contrasts, normalized to unit geometric mean training marginal variance.
The same basis is used in seasonal and nonseasonal arms. There are static county
IID intercepts, no county temporal splines, and no spatial adjacency term here.

The state intercept Normal(log(.0002),1), county PC P(SD>1)=.01,
negative-binomial log-size Normal(log20,1), and optional constrained cyclic
monthly RW1 with standardized PC P(SD>.5)=.01 match the controls. The nonlinear
scale retains the engineering prior; the proper slope gives a finite specified
prior for otherwise unpenalized linear extrapolation. These scales are explicit
assumptions, not empirical biological estimates or functionally matched priors.

The data-free prior audit found wider spline forecast-rate ratios, especially
at shorter training spans. We retain that behavior for this bounded experiment
rather than retune it after seeing held-out outcomes. This is permission to
evaluate the candidate, not acceptance of its forecasts. Assess widening
intervals, bias, tail concentration and horizon dependence explicitly. The
shared log-link/scale priors can have unstable unconditional arithmetic prior
means; prior central quantiles do not prove posterior means are stable.
See `monthly_combination_prior_audit.md` for the simulation and limitations.

## Basis, source and execution integrity

Basis CSVs contain only deterministic calendar coordinates, slope and nonlinear
design values. They are prepared locally using mgcv. Their manifest binds the
entire numeric files, generating script and model/basis source files. The
launcher verifies those hashes and snapshots them into a new run. Workers
recheck the immutable snapshot before and after fitting; R also verifies
training rank, orthogonality, scale, slope and domain on consumption. This
protects prediction rows as well as the training constraints. mgcv is not needed
inside the existing INLA container and there is no container rebuild.

The launcher verifies the complete original factorial and all reused task
bindings, checks matching held-out truth and preserves source inputs. No
original result is overwritten. Unverified `--prepare-only` plans cannot run.
Saved posterior adapter checks outcome masking, row order, exposure and spline
specification. APredictor log-rate draws are multiplied by person-years exactly
once. The common score engine otherwise retains its density calculations,
four independent simulation streams of 2,000 draws, pooled 8,000 draws,
joint annual aggregation and negative-binomial replicated counts.

## Evaluation, reporting and disposition

Compare spline to RW1 and AR1 separately, each as a four-arm factorial:
temporal difference with and without seasonality; seasonal difference within
reference and spline; and their difference-in-differences. Report site/year/
origin/stream and equal-site summaries. An interaction is on the predictive
log-score scale, not evidence of a biological mechanism. A combined model can
be useful without super-additive improvement.

Alongside county-month log scores inspect annual coverage, bias, interval
width, tail concentration and per-cell density MCSE. Four-stream variability
is Monte Carlo uncertainty, not a confidence interval for generalization.
Overlapping origins and sites are dependent. Do not select by CPO, raw average
score, or broad coverage alone. No automatic acceptance or post hoc numerical
threshold is introduced. A later prior change requires a separately named
sensitivity experiment and disclosure of reuse of these evaluation years.

The collector preserves failed/missing cells and logs, suppresses contrasts on
integrity failures and archives portable reports with a checksum manifest.
Saved fits, patient-derived panels and joint draws stay INTERNAL on the cluster.
Review scientific adequacy before any dashboard promotion or default change.

## Execution

`python3 scripts/launch_monthly_spline_factorial.py` submits all 54 new fits as
one SGE array with no concurrency cap, four CPUs each, 48-hour limit,
h_rss/mem_free 53248M and h_vmem 68G. These are limits, not a runtime estimate.
A dependent collector produces one archive. No new controls are fitted.
