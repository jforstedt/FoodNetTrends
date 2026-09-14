# Targeted singleton cross-validation check

## Why this check

Observed CPO flags persisted after the documented recomputation. Repeating that
procedure is not justified. Compare the alternative singleton group-CV calculation
with explicit observation omission while keeping the likelihood, priors, site
structure and historical mask fixed. This tests diagnostic calculation behavior;
it is not a new pathogen model or independent predictive validation.

## Frozen selection

Use the six bacterial shared-trend hindcast fits from the verified classification
saved-diagnostic batch. Within each pathogen, select one observed training cell
from each available flagged/unflagged × zero/nonzero CIDT stratum, ordered by
ascending year then state. Record absent strata. This yields at most 24 cells;
selection must not depend on CPO magnitude, predictive score or desired agreement.
The source reports currently yield 15. All tasks can run concurrently without a
cap. Site-slope and descriptive fits are intentionally outside this first bounded
check; it cannot certify those fits or all observations.

## Three calculations per selected cell

1. Singleton `inla.group.cv`: explicitly specify singleton groups for every row,
   then use the selected cell's result. Verify the returned group indices. In the
   pinned implementation, groups and selection cannot be passed together.
2. Explicit omission with original hyperparameters fixed: mask the selected
   outcome and fit the same model at the original hyperparameter values.
3. Explicit omission with hyperparameters re-estimated: mask the same outcome,
   retaining the model's original priors and allowing posterior re-estimation.

The installed INLA 26.08.07 group-CV implementation fixes hyperparameters at the
original mode and uses empirical-Bayes integration internally. Its comparison
with calculation 2 isolates differences more closely than comparison with 3.
Both differences must be reported, not confused with a scientific-model change.
This is not an exact independent gold standard: all three calculations use INLA.

All original 2017–2019 outcomes remain masked in both explicit fits. Trials and
all predictor rows remain fixed, including the omitted cell's site/year effect.
Restore the serialized formula's evaluation environment without changing its
terms or priors. Check fitted data against the intended mask before sampling.
Four independently seeded streams of 1,000 posterior draws per explicit fit
estimate the omitted outcome's predictive probability using stable log-density
calculations. Retain stream scores and relative Monte Carlo errors.

## Outputs and interpretation

One comparison row per target reports original CPO/flag, singleton group-CV,
explicit full-posterior score and fixed-hyperparameter score. Archive identity,
mask evidence, numerical status and warnings. Keep explicit-fit checkpoints on
the cluster only. Preserve original files and accepted state outputs.

Assess group-CV versus fixed-hyperparameter omission first, then quantify the
additional effect of re-estimation. Disagreement beyond sampling variability
requires investigation, not automatic model rejection. Agreement for selected
cells does not clear the remaining original flags. No automatic acceptance,
incidence correction, method exclusion or new model-selection rule follows.
Retain standalone and combined-method candidates under model_change_rationale.md.

Source: the pinned installed `inla.group.cv` function and the authors' method
[documentation](https://repository.kaust.edu.sa/bitstreams/f166c828-fa46-48b0-b2a0-93a740875d59/download),
which describes predefined groups and the leave-one-out target. The fixed-mode
behavior above was verified directly in the installed implementation.

Launch with `python3 scripts/launch_classification_crosscheck.py` on Rosalind,
with Singularity loaded. Each selected-cell task gets four cores; each performs
its calculations sequentially while different cells run concurrently. One
collector produces one archive and retains explicit failures. No original batch
is rerun or overwritten.
