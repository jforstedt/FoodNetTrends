"""Shared fail-closed artifact checks for the forecast runner, gate and collector."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path


def csvrows(path):
    with Path(path).open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows: raise ValueError('Empty required table: ' + str(path))
    return rows


def single(path):
    data = csvrows(path)
    if len(data) != 1: raise ValueError('Expected one metadata row: ' + str(path))
    return data[0]


def numeric(value, name, lower=None, upper=None):
    if isinstance(value, bool): raise ValueError('Invalid numeric ' + name)
    x = float(value)
    if not math.isfinite(x) or (lower is not None and x < lower) or (upper is not None and x > upper):
        raise ValueError('Invalid numeric ' + name)
    return x


def integer(value, name):
    x = numeric(value, name)
    if x != int(x): raise ValueError('Expected integer ' + name)
    return int(x)


def boolean(value, name):
    if value is True or str(value).lower() == 'true': return True
    if value is False or str(value).lower() == 'false': return False
    raise ValueError('Invalid boolean ' + name)


def near(a, b, name):
    if not math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-9): raise ValueError('Inconsistent ' + name)


def first_status(path, expected):
    lines = Path(path).read_text().splitlines()
    if not lines or lines[0] != expected: raise ValueError('Missing successful status: ' + str(path))


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def forecast_cells(path, expected, population, candidate=False):
    indexed = {}
    for row in csvrows(path):
        key = row['fips'], row['state'], integer(row['year'], 'year')
        if key in indexed or key not in expected: raise ValueError('Unexpected or duplicate forecast key')
        observed = numeric(row['observed'], 'observed', 0); integer(observed, 'observed')
        exposure = numeric(row['population'], 'population', 0)
        if exposure <= 0: raise ValueError('Nonpositive forecast population')
        near(exposure, population[key], 'audited forecast population')
        numeric(row['mean_expected'], 'mean_expected', 0)
        quantiles = [numeric(row[n], n, 0) for n in ('lower95', 'lower50', 'median', 'upper50', 'upper95')]
        if quantiles != sorted(quantiles): raise ValueError('Unordered forecast intervals')
        numeric(row['log_predictive_density'], 'log_predictive_density', upper=1e-10)
        zero = numeric(row['predicted_zero_probability'], 'zero probability', 0, 1)
        brier = numeric(row['zero_brier'], 'zero_brier', 0, 1)
        near(brier, (zero - int(observed == 0)) ** 2, 'zero Brier score')
        if boolean(row['covered95'], 'covered95') != (quantiles[0] <= observed <= quantiles[4]):
            raise ValueError('Incorrect 95% interval coverage flag')
        if boolean(row['covered50'], 'covered50') != (quantiles[1] <= observed <= quantiles[3]):
            raise ValueError('Incorrect 50% interval coverage flag')
        if candidate:
            numeric(row['density_relative_mcse'], 'density MCSE', 0)
            numeric(row['randomized_pit'], 'randomized PIT', 0, 1)
            if not row['training_cases_band']: raise ValueError('Missing training-only stratum')
        indexed[key] = row
    if set(indexed) != expected: raise ValueError('Incomplete forecast county/year grid')
    return indexed


def forecast_groups(cells):
    groups = defaultdict(list)
    bands = ((5000, '01 <5000'), (10000, '02 5000-9999'), (25000, '03 10000-24999'),
             (50000, '04 25000-49999'), (100000, '05 50000-99999'), (float('inf'), '06 100000+'))
    for key, row in cells.items():
        pop_band = next(label for boundary, label in bands if float(row['population']) < boundary)
        for grouping, group in (('overall', 'all'), ('state', key[1]), ('year', str(key[2])),
            ('state_year', key[1] + '|' + str(key[2])), ('county', key[1] + '|' + key[0]),
            ('population', pop_band), ('training_cases', row['training_cases_band'])):
            groups[grouping, group].append(row)
    return groups


def validate_aggregates(report, cells):
    groups = forecast_groups(cells)
    for filename, score in (('heldout_aggregate_checks_INTERNAL.csv', False), ('heldout_scores_INTERNAL.csv', True)):
        seen = set()
        for row in csvrows(report / filename):
            key = row['grouping'], row['group']
            if key in seen or key not in groups: raise ValueError('Unexpected or duplicate aggregate group')
            seen.add(key); data = groups[key]; n = len(data)
            if integer(row['cells'], 'aggregate cells') != n: raise ValueError('Wrong aggregate group size')
            if score:
                expected = dict(sum_log_predictive_density=sum(float(r['log_predictive_density']) for r in data),
                    mean_absolute_error=sum(abs(float(r['mean_expected']) - float(r['observed'])) for r in data) / n,
                    mean_zero_brier=sum(float(r['zero_brier']) for r in data) / n,
                    coverage95=sum(boolean(r['covered95'], 'coverage') for r in data) / n,
                    coverage50=sum(boolean(r['covered50'], 'coverage') for r in data) / n,
                    mean_interval95_width=sum(float(r['upper95']) - float(r['lower95']) for r in data) / n,
                    max_density_relative_mcse=max(float(r['density_relative_mcse']) for r in data))
                for field, value in expected.items(): near(numeric(row[field], field), value, 'aggregate ' + field)
            else:
                expected = dict(observed_total=sum(float(r['observed']) for r in data),
                    expected_total=sum(float(r['mean_expected']) for r in data),
                    observed_zeros=sum(float(r['observed']) == 0 for r in data),
                    expected_zeros=sum(float(r['predicted_zero_probability']) for r in data))
                for field, value in expected.items(): near(numeric(row[field], field, 0), value, 'aggregate ' + field)
                for prefix in ('total', 'zero'):
                    q = [numeric(row[prefix + '_' + name], prefix + ' interval', 0, n if prefix == 'zero' else None)
                         for name in ('lower95', 'median', 'upper95')]
                    if q != sorted(q): raise ValueError('Unordered aggregate interval')
                numeric(row['zero_upper_tail'], 'zero upper tail', 0, 1)
        if seen != set(groups): raise ValueError('Incomplete aggregate group inventory')


def validate_forecast(work, task):
    report = work / 'result/reports'
    first_status(report / 'status.txt', 'FORECAST_CHECK_COMPLETE')
    origin = integer(task['origin'], 'origin'); horizon = integer(task['horizon'], 'horizon')
    start = integer(task.get('train_start', 2004), 'train_start')
    if horizon < 1 or origin < start or (task['pathogen'] == 'CRYPTOSPORIDIUM' and origin + horizon > 2017):
        raise ValueError('Ineligible task observation window')
    split = single(report / 'split.csv')
    for name, expected in (('train_start', start), ('train_end', origin), ('test_start', origin + 1),
                           ('test_end', origin + horizon), ('evaluation_horizon', horizon)):
        if integer(split[name], name) != expected: raise ValueError('Forecast split differs from task: ' + name)
    if split['model'] != task['model'] or not boolean(split['heldout_counts_masked'], 'heldout_counts_masked'):
        raise ValueError('Wrong model or missing held-out masking')
    if integer(split['draws'], 'draws') < 4000: raise ValueError('Insufficient declared predictive draws')
    audit = Path(task['audit']); nodes = csvrows(audit / 'reports/graph_nodes.csv')
    states = {n['fips']: n['state'] for n in nodes}
    if len(nodes) != 486 or len(states) != 486 or len(set(states.values())) != 10:
        raise ValueError('Unexpected audited county/state footprint')
    expected = {(fips, state, year) for fips, state in states.items() for year in range(origin + 1, origin + horizon + 1)}
    if integer(split['heldout_cells'], 'heldout cells') != len(expected) or integer(split['training_cells'], 'training cells') != 486 * (origin - start + 1):
        raise ValueError('Wrong training/held-out cell counts')
    population = {}
    for row in csvrows(audit / 'reports/population_audit.csv'):
        key = row['fips'], row['state'], integer(row['year'], 'year')
        if key not in expected: continue
        if key in population or row['population_status'] != 'ok': raise ValueError('Invalid audited population key')
        population[key] = numeric(row['population'], 'population', 0)
    if set(population) != expected: raise ValueError('Incomplete audited prediction exposures')
    panel = audit / 'county_panel_INTERNAL.rds'; recorded = single(report / 'panel_checksum.csv')
    if Path(recorded['file']).resolve() != panel.resolve() or recorded['md5'] != digest(panel, 'md5'):
        raise ValueError('Forecast panel differs from recorded input')
    candidate = forecast_cells(report / 'heldout_cells_INTERNAL.csv', expected, population, candidate=True)
    reference = forecast_cells(report / 'historical_reference_cells_INTERNAL.csv', expected, population)
    for key in expected:
        near(float(candidate[key]['observed']), float(reference[key]['observed']), 'paired observed outcome')
    spec = single(report / 'forecast_specification.csv')
    if spec['version'] != 'training_origin_rw1_v1': raise ValueError('Unrecognized temporal forecast specification')
    for name, value in (('training_start', start), ('training_end', origin), ('prediction_end', origin + horizon),
                        ('training_years', origin - start + 1), ('domain_years', origin + horizon - start + 1)):
        if integer(spec[name], name) != value: raise ValueError('Wrong temporal domain: ' + name)
    numeric(spec['training_precision_scale'], 'training precision scale', lower=1e-15)
    constraint = csvrows(report / 'temporal_constraint.csv'); seen = set()
    for row in constraint:
        year = integer(row['year'], 'constraint year')
        if year in seen: raise ValueError('Duplicate constraint year')
        seen.add(year)
        near(numeric(row['centering_weight'], 'centering weight'), 1.0 / (origin - start + 1) if year <= origin else 0,
             'training-only centering')
    if seen != set(range(start, origin + horizon + 1)): raise ValueError('Incomplete temporal constraint domain')
    validate_aggregates(report, candidate)
    return dict(kind='forecast', validated_cells=len(expected), origin=origin, horizon=horizon)


def validate_calibration(work, task):
    report = work / 'result'
    lines = (report / 'status.txt').read_text().splitlines()
    if not lines or not lines[0].startswith('TASK_COMPLETE:'): raise ValueError('Calibration did not complete')
    summary = json.loads((report / 'task_summary.json').read_text())
    if summary['status'] != 'TASK_COMPLETE' or summary['specification']['version'] != 'county-forecast-calibration-v1':
        raise ValueError('Invalid calibration completion/specification')
    for name in ('density', 'variant', 'replicate'):
        if str(summary[name]) != str(task[name]): raise ValueError('Calibration task identity mismatch')
    if integer(summary['draws'], 'calibration draws') < 1000: raise ValueError('Insufficient calibration draws')
    expected = {(m, h, u) for m in ('INLA_GAUSSIAN', 'KNOWN_PARAMETER_ORACLE') for h in (1, 2, 3) for u in ('cell', 'total', 'zero_total')}
    seen = set()
    for row in csvrows(report / 'metrics.csv'):
        key = row['method'], integer(row['horizon'], 'metric horizon'), row['unit']
        if key in seen or key not in expected: raise ValueError('Invalid or duplicate calibration metric')
        seen.add(key)
        for name in ('density', 'variant', 'replicate'):
            if str(row[name]) != str(task[name]): raise ValueError('Metric identity mismatch')
        numeric(row['coverage'], 'coverage', 0, 1)
        for name in ('mean_width', 'mean_absolute_error', 'mean_predictive_mcse'): numeric(row[name], name, 0)
        if integer(row['draws'], 'metric draws') != integer(summary['draws'], 'summary draws'):
            raise ValueError('Metric draw count differs from summary')
        if integer(row['observations'], 'observations') != (12 if row['unit'] == 'cell' else 1):
            raise ValueError('Wrong calibration evaluation unit size')
    if seen != expected: raise ValueError('Incomplete calibration metrics')
    return dict(kind='calibration', validated_metrics=len(seen))


def _validate_task_outputs(work, task):
    work = Path(work)
    if task['kind'] == 'forecast': return validate_forecast(work, task)
    if task['kind'] == 'calibration': return validate_calibration(work, task)
    report = work / 'result'
    if task['kind'] == 'horizon':
        first_status(report / 'status.txt', 'HORIZON_INVARIANCE_PASS')
        checks = csvrows(report / 'checks.csv'); seen = set()
        for row in checks:
            if not row['check'] or row['check'] in seen or not boolean(row['pass'], 'horizon check'):
                raise ValueError('Failed or duplicate horizon check')
            if row.get('status') != 'PASS': raise ValueError('Horizon numerical check did not pass')
            seen.add(row['check'])
        if seen != {'spatial_baseline', 'spatial_county_time', 'iid_baseline', 'iid_county_time'}:
            raise ValueError('Incomplete horizon-invariance model checks')
        return dict(kind='horizon', validated_checks=len(seen))
    if task['kind'] == 'reference':
        first_status(report / 'status.txt', 'SCALAR_REFERENCE_PASS')
        summary = json.loads((report / 'reference_summary.json').read_text())
        if summary['status'] != 'SCALAR_REFERENCE_PASS' or float(summary['probability_error_limit']) != .05:
            raise ValueError('Invalid scalar reference summary')
        seen = set()
        for row in csvrows(report / 'scalar_reference.csv'):
            scenario = row['scenario']
            if scenario in seen or scenario not in ('zero', 'sparse', 'dense', 'low_rate'): raise ValueError('Invalid scalar scenario')
            seen.add(scenario)
            if not boolean(row['pass'], 'scalar pass') or numeric(row['max_probability_error'], 'probability error', 0, .05) > .05:
                raise ValueError('Scalar reference failed')
            if integer(row['draws'], 'scalar draws') < 4000: raise ValueError('Insufficient scalar reference draws')
            for prefix in ('exact', 'sample'):
                q = [numeric(row[prefix + '_' + name], prefix + ' quantile') for name in ('lower', 'median', 'upper')]
                if q != sorted(q): raise ValueError('Unordered scalar quantiles')
        if seen != {'zero', 'sparse', 'dense', 'low_rate'}: raise ValueError('Incomplete scalar reference scenarios')
        return dict(kind='reference', validated_scenarios=len(seen))
    raise ValueError('Unsupported task kind: ' + str(task['kind']))


def validate_task_outputs(work, task):
    """Raise ValueError/OSError for missing, malformed or inconsistent task evidence."""
    try:
        return _validate_task_outputs(work, task)
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('Malformed task validation evidence: ' + str(error))
