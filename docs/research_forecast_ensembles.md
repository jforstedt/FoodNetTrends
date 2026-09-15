# Combining predictions as a separate candidate

Research reviewed 2026-09-14. This is a proposed experiment, not a model change
or an established FoodNet result.

A probabilistic ensemble provides a different meaning of “combine everything”:
combine alternative predictive distributions instead of putting every component
into one likelihood. A primary CDC-led comparison of influenza and COVID-19
forecast hubs found benefits from model diversity and ensemble composition, with
diminishing returns as members were added. That evidence motivates a FoodNet
experiment; it does not transfer its model-count recommendation or guarantee
improvement for county enteric disease. [Fox et al., 2024](https://wwwnc.cdc.gov/eid/article/30/9/24-0026_article).

Proposed first control: an equal-weight predictive mixture of the matched seasonal
RW1 and seasonal AR1 county models, separately for IID and BYM2. Keep each member
and its predictive calibration visible. This tests complementary extrapolation
without choosing flexible weights from three overlapping development origins.
Do not automatically add an unstable spline to obtain diversity. A spline-inclusive
sensitivity is meaningful only where its numerical and tail properties meet the
same predeclared gates. Neither an ensemble nor interval widening fixes shared
bias automatically.

The mixture density is p(y)=sum(w_m*p_m(y)); compute its log score from cell-level
component densities with stable log-sum-exp. Averaging the members' log scores is
not the mixture log score. Existing state-averaged scores cannot reconstruct it.
For joint samples, choose one model for an entire county/time trajectory and draw
from its joint predictive distribution, preserving geographic and temporal
aggregation. Do not choose a separate member independently for every county/month
or average interval endpoints. Confirm the saved objects actually contain the
needed densities/draws before promising a no-resampling calculation.

Probabilistic coherence is useful but not a guarantee of better scores; a primary
influenza study found that some reconciliation choices worsened forecasts.
Retain the native coherent county-to-state sums and avoid treating independently
fit state and county distributions as automatically compatible.
[Improving probabilistic infectious disease forecasting through coherence, PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007623).

Assess the ensemble on the same declared count target, forecast origins and
horizons as its members, with log score, calibration, width, bias and tail
stability. Treat already inspected outcomes as development evidence. If learning
weights later, use genuinely earlier training predictions or a suitable nested
rolling-origin procedure; do not train and evaluate weights on the same pooled
scores. No claim of independence comes from using the same outcomes in a new
mixture.
