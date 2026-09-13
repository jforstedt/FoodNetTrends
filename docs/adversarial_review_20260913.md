# Adversarial review: state acceptance and county extensions

Scope: `a811167..e283df4`, with the subsequent recovery archive reviewed alongside
it. This conservative boundary covers 96 changed files and deliberately overlaps
previous review. Three parallel reviewers examined scientific assumptions,
execution/provenance and the state acceptance boundary; the primary reviewer
checked input audits, integrated fixes and ran regression tests. This is a bounded
source/artifact audit, not a proof of every model or a full posterior-reference study.

## Findings and disposition

| Finding | Impact | Disposition |
|---|---|---|
| State CSVs were not bound to the saved posterior | Coherently changed tables could pass arithmetic checks | New exports create a fit/table hash manifest; acceptance requires it; regression reproduces stale-table rejection |
| Calibration replicate posterior seed ranges overlapped | Monte Carlo errors between simulation replicates were correlated, weakening independence-based uncertainty claims | Future calibration uses disjoint namespaces with maximum-draw overlap tests; earlier screens retain this qualification |
| Forecast collector omitted identity/provenance checks | Changed source/task/gate or an empty manifest could produce a successful collection status | Nonempty verified inventory, task identity, fingerprints and gates rechecked; failures still archived |
| Next-phase collector lacked execution identity | A changed or unverified task plan could be reported as completed without disclosing the gap | Future records include plan/task identity; legacy identity gaps are explicit; recovery checks source-plan rebasing |
| RDS checkpoints lacked completion-time hashes | Later sampling verified structure/current bytes but not original completion bytes | Future runners record checkpoint hashes separately from portable archive contents; recovery preserves verified checkpoints |
| Extension collector accepted insufficient completion evidence | Nonzero status, changed inputs or empty/unverified plans could pass collection | Exit, plan and fingerprint guards added with regression tests |
| Next-phase recovery scheduler inventory check was weaker | Unexpected XML or ambiguous absence could permit duplicate recovery | Reuses the existing strict inventory/per-job completion check |
| Real spline fit approximation can fail after synthetic gates pass | A numerically unreliable real fit could appear in an ordinary score table | Aborted variational corrections are explicitly flagged for saved-fit review; log silence is not a convergence certificate |

The earlier non-array SGE dispatch bug was already corrected before this audit;
its executed `undefined` regression and targeted no-resampling recovery remain in
place. Recovery has completed, so that historical dispatch failure is not an
outstanding cluster blocker.

## Historical evidence and scientific limits

No evidence was found that accepted state estimates were actually replaced by
stale CSVs. However, legacy files cannot acquire the new binding merely by hashing
existing tables. The [state export procedure](state_export_binding.md) recomputes
from saved posteriors into a new destination, without sampling, followed by existing
independent validation. Originals remain intact.

Likewise, the lack of old checkpoint or execution hashes is not evidence of changed
files. Older records must be described as structurally checked/currently
fingerprinted or identity-unverified, as applicable. They must not be relabelled
original-byte verified. These guards do not themselves require repeating completed
sampling tasks. Portable archives cannot verify excluded RDS bytes or external
cluster inputs.

The previous calibration screen still provides simulation evidence, but its strict
independent-replicate uncertainty interpretation is qualified. A new, versioned
screen using disjoint posterior streams is needed before relying on that claim;
no existing model formula, generated truth or posterior prior was changed by the
seed fix. Current experimental forecasts are not promoted on the old screen alone.

The recovered spline comparisons do not support promoting this candidate family
at present. Numerical warnings and poor aggregate predictive behavior require
review even when a task completes and its hashes match. Detailed scores and private
audit findings remain in local output review directories, not in this repository.
Investigate problematic saved checkpoints before assigning a mechanism or changing
priors. A synthetic Gaussian design check does not certify a real negative-binomial
joint posterior approximation.

The combined-extension plan remains exploratory. It correctly separates public
field definitions from extract derivations, requires monthly observation/exposure
support, blocks use of held-out testing mix, and recognizes overlapping origins
and unequal sampling precision. Numerical priors, practical margins and any
confirmatory validation period are still explicit pre-launch decisions. No claim
of equivalence between Daniel's state model and the county spline was established.

## Validation and operational boundary

Regression coverage includes stale coherent state exports, changed task/source
identity, revoked gates, empty/unverified plans, nonzero exits, checkpoint changes,
legacy provenance labels, exact recovery remapping, scheduler uncertainty, disjoint
simulation seeds and numerical warning flags. Existing classification, baseline,
reportability, surveillance-window and saved-fit/control tests were also exercised.

The generic unittest discovery command encounters a pre-existing standalone
`test_dashboard.py` that requires an HTML argument; it must be run with its fixture,
not imported as a unittest module. Calibration tests require the local INLA R
installation rather than the system R environment. Test results must distinguish
these harness requirements from regressions.

Current and completed HPC jobs use immutable snapshots. Updating repository source
does not rewrite their history or launch more work. No private data, result tables
or checkpoint files are included in this change. Forecast formulas and accepted
state model assumptions are unchanged; state changes concern export integrity.

Final local validation: **110 unittest cases passed**, excluding the unchanged
standalone HTML-argument test from discovery. Thirteen relevant R test scripts
passed across the system/package environment and the dedicated INLA environment,
including the disjoint-seed regression and new state export binding test. The
actual mocked model-flow integration also passed. Changed Python files parse with
Python 3.6 grammar; staged whitespace checks pass. These results do not substitute
for the real-fit and legacy-provenance limitations above.
