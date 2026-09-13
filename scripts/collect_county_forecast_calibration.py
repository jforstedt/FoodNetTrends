#!/usr/bin/env python3
"""Collect a fixed-truth simulation screen; never certify posterior approximation."""
import argparse
import csv
import json
import math
from pathlib import Path

DENSITIES = ('sparse', 'dense')
VARIANTS = ('spatial', 'iid')
METHODS = ('INLA_GAUSSIAN', 'KNOWN_PARAMETER_ORACLE')
UNITS = ('cell', 'total', 'zero_total')


def interval(values):
    # Replicates are independent units; counties within a replicate are not.
    n = len(values)
    mean = sum(values) / n
    se = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1) / n) if n > 1 else None
    # Hoeffding bound is distribution-free for replicate proportions in [0,1].
    radius = math.sqrt(math.log(40) / (2 * n))
    return mean, max(0, mean - radius), min(1, mean + radius), se


def collect(root, replicates=20):
    root = Path(root)
    expected = {(d, v, r) for d in DENSITIES for v in VARIANTS for r in range(1, replicates + 1)}
    seen = set()
    completed = set()
    errors = []
    rows = []
    for path in sorted(root.rglob('task_summary.json')):
        try:
            data = json.loads(path.read_text())
            key = (data['density'], data['variant'], int(data['replicate']))
            if key not in expected or key in seen:
                raise ValueError('unexpected or duplicate task {}'.format(key))
            seen.add(key)
            if data['status'] != 'TASK_COMPLETE' or int(data['draws']) < 1000:
                raise ValueError('task incomplete or fewer than 1000 draws')
            if data['specification']['version'] != 'county-forecast-calibration-v1':
                raise ValueError('wrong calibration specification')
            with (path.parent / 'metrics.csv').open() as handle:
                task_rows = list(csv.DictReader(handle))
            expected_metrics = {(m, h, u) for m in METHODS for h in (1, 2, 3) for u in UNITS}
            observed = set()
            for row in task_rows:
                mk = (row['method'], int(row['horizon']), row['unit'])
                if mk not in expected_metrics or mk in observed:
                    raise ValueError('missing or duplicate metric')
                observed.add(mk)
                if (row['density'], row['variant'], int(row['replicate'])) != key:
                    raise ValueError('metric task identity mismatch')
                if not 0 <= float(row['coverage']) <= 1 or not math.isfinite(float(row['mean_width'])):
                    raise ValueError('invalid metric value')
            if observed != expected_metrics:
                raise ValueError('incomplete metrics')
            rows.extend(task_rows)
            completed.add(key)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            errors.append('{}: {}'.format(path, exc))
    if seen != expected:
        errors.append('Missing {} expected tasks'.format(len(expected - seen)))
    groups = {}
    for row in rows:
        key = tuple(row[x] for x in ('density', 'variant', 'method', 'horizon', 'unit'))
        groups.setdefault(key, []).append(float(row['coverage']))
    metrics = []
    gross = []
    for key, values in sorted(groups.items()):
        mean, lower, upper, se = interval(values)
        result = dict(zip(('density', 'variant', 'method', 'horizon', 'unit'), key))
        result.update(replicates=len(values), coverage=mean, coverage_lower95_bound=lower,
                      coverage_upper95_bound=upper, replicate_mcse=se,
                      uncertainty_method='Hoeffding bound across independent replicate proportions')
        metrics.append(result)
        if mean < .85:
            gross.append(result)
    sufficient = replicates >= 20
    status = 'NUMERICAL_SCREEN_PASS' if not errors and sufficient and not gross else 'REVIEW_REQUIRED'
    result = dict(status=status, scientific_status='REVIEW_REQUIRED', expected_tasks=len(expected),
                  completed_tasks=len(completed), identified_tasks=len(seen), replicates_per_scenario=replicates,
                  predeclared_gross_coverage_floor=.85, nominal_coverage=.95,
                  errors=errors, gross_undercoverage=gross, metrics=metrics,
                  interpretation='Fixed-truth sparse/dense numerical screen only. Passing permits exploratory comparisons, not adoption or certification of Gaussian joint-tail accuracy.',
                  uncertainty='Coverage bounds and replicate MCSE describe simulation uncertainty; the 0.85 empirical screen is not a hypothesis test or certification of nominal 95% coverage.',
                  posterior_reference='No higher-accuracy posterior reference. Known-parameter oracle validates generator/scoring behavior under more information, not approximation equivalence.')
    (root / 'calibration_summary.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('--replicates', type=int, default=20)
    args = parser.parse_args()
    if args.replicates < 1:
        parser.error('replicates must be positive')
    result = collect(args.root, args.replicates)
    print(json.dumps({k: result[k] for k in ('status', 'scientific_status', 'completed_tasks', 'expected_tasks')}, indent=2))
    raise SystemExit(0 if result['status'] == 'NUMERICAL_SCREEN_PASS' else 1)


if __name__ == '__main__':
    main()
