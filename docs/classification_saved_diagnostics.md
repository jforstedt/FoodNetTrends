# Saved classification diagnostics

This batch reuses classification_trends_20260914_100228_401966 without refitting,
changing priors or replacing any incidence output. The original 24 fits completed,
but execution success does not imply statistical acceptance. This batch is
exploratory and makes no correction for testing or ascertainment.

## Parallel work

One 36-task array contains 24 saved-fit inspections and 12 precision tasks for the
hindcast fits. They can all run concurrently; there is no concurrency cap. Each
task requests two cores, and the collector waits for the entire array. Posterior
streams are sampled serially inside a task for reproducibility; parallelism comes
from independent tasks. Extra cores would not automatically speed that sampling.
No container build or repeat of the original model fits is required.

Inspection exports per-row CPO failure values, CPO and PIT, explicitly identifying
observed training responses versus masked held-out responses. Nonfinite/missing
values are retained as findings. It also exports fixed, hyperparameter and latent
summaries. The distinction resolves whether aggregate failure counts refer to
training or held-out rows; it does not assume the answer in advance. No automatic
CPO recomputation is performed, because that can entail additional model fitting.

Precision tasks use four new independently seeded streams of 2,500 draws each:
10,000 draws per hindcast fit, five times the original sample size. They produce
the same probabilities, count intervals, annual joint-draw aggregates and
stream-specific/pooled marginal log predictive scores. These are new estimates
from the same saved posterior, not independent validation data. Sampling uses the
same skew.corr=FALSE setting as the original comparison. Reduced Monte Carlo
error does not resolve approximation error, prior sensitivity or model bias.
Description fits receive inspection only; spending additional posterior draws on
in-sample model rankings would not resolve the held-out comparison.

## Integrity and interpretation

Source fits, input support and completed task records must match their original
hash-bound provenance. The R reader checks the saved specification, likelihood,
latent terms, training outcomes, held-out masking, trials and predictor ordering
against the source data before any analysis. Inputs are checked again afterward.
Results go in a new directory. Saved originals are never overwritten. Portable
archives contain aggregate diagnostics and source snapshots, not fit checkpoints.
Partial failures remain explicit and prevent a clean completion status.

Review numerical flags and posterior approximation separately from predictive
scores. Compare score direction across streams and residual Monte Carlo error;
do not label stream ranges as confidence intervals. Assess annual bias and
interval width as well as coverage. Retain the simpler model when extra site
slopes have no persuasive benefit. No automatic acceptance, dashboard promotion,
new temporal model, or incidence adjustment follows these diagnostics.

Run `python3 scripts/launch_classification_diagnostics.py` from FoodNetTrends on
Rosalind with Singularity loaded. One array and one dependent collection job
produce one report archive. Missing saved files cause an explicit failure rather
than an implicit refit.

Local verification includes synthetic INLA saved-fit inspection and posterior
sampling, deliberate rejection of changed trial counts and unmasked held-out
responses, CPO row alignment, and the launcher integrity/partial-collection tests.
These checks establish implementation behavior, not scientific acceptance.
