# Saved spatial error structure review

This review describes where static county spatial smoothing changes existing
incidence forecasts. It reuses the complete verified spatial comparison and
requires no new fits or posterior draws. It does not alter Daniel's state model.

Run on the PC after the original, recovery and restart archives have passed
`review_monthly_spatial_results.py`:

```bash
python3 scripts/review_spatial_error_structure.py output/spatial_tradeoffs_20260914_160320_LOCAL --output output/spatial_error_structure_NEW_LOCAL
```

The source must contain all 54 configurations, three origins, ten states, three
forecast years and five stream labels (pooled plus four separate posterior
streams). The reviewer rejects missing or duplicate cells and inconsistent
prediction errors. Output records hashes of the reviewed input tables.

State, origin and horizon tables report paired predictive log-score differences,
coverage, width, absolute error and ratio-of-total bias. Each dimension uses
balanced blocks for mean scores and errors; ratio-of-total bias instead weights
by observed burden. Scores summarize marginal county-month log densities within
state, not predictive log densities of state totals. Separate stream ranges describe simulation variation. They are
not confidence intervals based on independent observations. Leave-one-block-out
summaries measure concentration of the existing evidence without refitting.
Absolute concentration shares measure the magnitude of block means, not the
fraction of net improvement when positive and negative differences cancel.

Nine state heatmaps accompany the tables. Their color scales differ by pathogen;
compare magnitudes using the numeric tables. Count-scale errors reflect population
and incidence as well as predictive quality. Undefined zero-total relative bias
is left missing. All numerical tables and figures stay under ignored `output/`.

These are state-level diagnostics. They cannot establish county-neighbor residual
correlation or justify changing spatial effects over time. County diagnostics
require the saved county-level predictions and truth on the cluster. Remaining
association is a development signal, not proof that a more complex model will
forecast better. Preserve matched controls and the current static specification
until any new comparison is justified and prespecified.

The [final validation plan](spatial_final_validation_plan.md) separates this
repeatedly examined development evidence from a protected final evaluation.
