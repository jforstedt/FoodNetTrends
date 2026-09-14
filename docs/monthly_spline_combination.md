# Monthly spline combination engineering candidate

This candidate tests whether a smooth state temporal trend and a cyclic seasonal effect can work together. It is retained for later evaluation, including possible benefits that standalone comparisons did not establish. It does not change Daniel's state model, any accepted outputs, or the older annual county spline implementation. It is not part of the current real-data temporal-by-seasonality batch.

## Controlled comparison

The interface in `scripts/monthly_spline_combination.R` supports RW1 versus a low-rank thin-plate state trend, each with seasonality off or on. RW1 delegates to the existing monthly implementation. All four candidates use state intercepts with Normal(log(.0002), 1) priors, IID county intercepts with a PC prior P(SD > 1) = .01, and negative-binomial counts with log(size) Normal(log(20), 1). Person-years enter as exposure. There are no county-specific temporal splines in this candidate.

The spline has six basis functions before removal of its constant and linear null space. It is constructed using training months only. Penalized nonlinear coefficients have a PC prior P(SD > .5) = .01 after normalization to unit geometric mean training marginal variance. State linear slopes have fixed Normal(0, .5²) priors, with time measured over the training span. The monthly RW1 uses its existing training-origin scale and temporal SD bound .5. These are deliberately specified priors, not proof that the two temporal structures imply identical prior predictions or effective complexity.

A common cyclic monthly RW1, when enabled, uses exactly the reference model's cyclic scaling, sum constraint and PC prior. Before normalization, the spline's nonlinear design is projected against the training intercept, linear time and 11 month contrasts. The fitted projection is reused for prediction months. The same projection is used with seasonality off and on; otherwise toggling seasonality would also alter the temporal design. This identifies a trend component orthogonal to observed training calendar-month contrasts and avoids letting a low-frequency basis encode a persistent month pattern. The linear slope is separately specified and is not projected away. This is an analysis convention, not evidence that nature separates trend and seasonality this way. It can affect extrapolation and must be included in later prior-predictive and sensitivity review.

## Interfaces and execution boundary

Source `county_forecast_model.R`, `county_spline_candidate.R`, and `monthly_seasonal_model.R` before the new file. `monthly_combination_basis(serial, cutoff, k=6)` constructs a numeric training-only design, where serial is `12 * year + month - 1`. This can be prepared in an environment with mgcv and supplied as `basis` to `fit_monthly_combination`; the fitting container then does not need mgcv.

`fit_monthly_combination(d, cutoff, temporal, seasonal, threads, coverage, basis)` returns an INLA fit with specification attributes. Held-out counts are masked before fitting. The spline uses an observation stack and `APredictor`, with explicit person-years exposure. `sample_monthly_combination` dispatches to the tested joint-posterior count samplers and returns `mu`, replicated counts, negative-binomial size and observation indices. INLA is pinned to 26.08.07.

## Engineering checks and remaining scientific work

`tests/test_monthly_spline_combination.R` checks training-basis invariance when future months are appended, full nonlinear rank, training phase orthogonality, variance normalization, held-out count poisoning, and the shared state-only design for counties in the same state. Its optional `--fit` gate fits all four synthetic candidates and checks finite count-scale predictions and consistency with fitted marginal count means. These checks establish implementation properties, not forecast superiority, scientific acceptance or adequacy for any pathogen.

Before a real-data comparison, freeze the origin/eligibility contract and outcome scoring, inspect joint prior-predictive behavior and extrapolation, and run a matched factorial comparison. Preserve simple reference models and label any pathogen-specific preference with its scientific hypothesis, uncertainty and empirical evidence. Do not use unstable CPO values as a model-selection gate. Explicit held-out predictions remain necessary.
