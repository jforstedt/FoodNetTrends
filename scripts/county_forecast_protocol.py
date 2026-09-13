#!/usr/bin/env python3
"""Define a bounded, matched county forecast experiment; never submit jobs or fit models."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

PATHOGENS = ('SALMONELLA', 'CAMPYLOBACTER', 'CRYPTOSPORIDIUM', 'CYCLOSPORA', 'LISTERIA', 'SHIGELLA', 'STEC', 'VIBRIO', 'YERSINIA')
MODELS = ('spatial_county_time', 'iid_county_time')
ORIGINS = (2011, 2013, 2016)
CRYPTO_ORIGINS = (2011, 2013, 2014)
HORIZON = 3
TRAIN_START = 2004
PROTOCOL_VERSION = 'county-horizon-validation-v1'


def rows(path):
    with Path(path).open(newline='') as handle:
        data = list(csv.DictReader(handle))
    if not data:
        raise ValueError('Empty report: ' + str(path))
    return data


def checksum(path, algorithm='sha256', cache=None):
    path = Path(path).resolve(); stat = path.stat()
    key = (str(path), algorithm, stat.st_size, stat.st_mtime_ns)
    if cache is not None and key in cache:
        return cache[key]
    digest = hashlib.new(algorithm)
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    value = digest.hexdigest()
    if cache is not None:
        cache[key] = value
    return value


def source_paths(root):
    root = Path(root).resolve(); output = root / 'output'
    generic = output / 'county_pathogen_audit_20260912_235314_491415/reports'
    original = output / 'county_pathogen_models_20260913_001441_311086'
    sources = {p: dict(audit=str(generic / p), reconciliation=str(original / p / 'reconciliation')) for p in PATHOGENS}
    sources['SALMONELLA'] = dict(audit=str(output / 'county_pilot_audit_20260912_205807_702050'),
        reconciliation=str(output / 'raw_county_review_20260912_220745_962511/reports'))
    crypto = output / 'crypto_coverage_correction_20260913_015228_648133'
    sources['CRYPTOSPORIDIUM'] = dict(audit=str(crypto / 'CRYPTOSPORIDIUM'), reconciliation=str(crypto / 'reconciliation'))
    return sources


def validate_source(pathogen, source, verify_inputs=True, hash_cache=None):
    if pathogen not in PATHOGENS:
        raise ValueError('Unsupported pathogen: ' + pathogen)
    audit = Path(source['audit']).resolve(); reconciliation = Path(source['reconciliation']).resolve()
    result = dict(audit=str(audit), reconciliation=str(reconciliation), start_year=TRAIN_START,
                  end_year=2017 if pathogen == 'CRYPTOSPORIDIUM' else 2019)
    if not verify_inputs:
        result['eligibility_status'] = 'UNVERIFIED'; return result
    if (audit / 'reports/status.txt').read_text().splitlines()[0] != 'INPUT_AUDIT_PASS':
        raise ValueError('Input audit did not pass: ' + pathogen)
    if (reconciliation / 'status.txt').read_text().splitlines()[0] != 'RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH':
        raise ValueError('Raw reconciliation did not pass: ' + pathogen)
    panel = audit / 'county_panel_INTERNAL.rds'
    panel_md5 = checksum(panel, 'md5', hash_cache)
    checks = rows(reconciliation / 'input_checksums.csv')
    if not any(Path(r['file']).resolve() == panel and r['md5'] == panel_md5 for r in checks):
        raise ValueError('Reconciliation does not certify the selected panel: ' + pathogen)
    all_checks = checks + rows(audit / 'reports/input_checksums.csv')
    verified = {}
    for row in all_checks:
        if 'unchanged' in row and row['unchanged'].lower() != 'true':
            raise ValueError('Source changed during reconciliation: ' + pathogen)
        path = Path(row['file']).resolve()
        if checksum(path, 'md5', hash_cache) != row['md5']:
            raise ValueError('Previously audited input changed: ' + str(path))
        if str(path) in verified and verified[str(path)] != row['md5']:
            raise ValueError('Audit/reconciliation provenance differs: ' + str(path))
        verified[str(path)] = row['md5']
    scope = audit / 'reports/observation_scope.csv'
    if scope.is_file():
        records = rows(scope)
        if len(records) != 1 or records[0]['pathogen'].upper() != pathogen or int(records[0]['start_year']) != TRAIN_START or int(records[0]['end_year']) != result['end_year']:
            raise ValueError('Incorrect documented observation window: ' + pathogen)
    flow = rows(audit / 'reports/case_flow.csv')
    label = '%s %s-%s' % (pathogen, TRAIN_START, result['end_year'])
    if flow[0]['stage'].upper() != label:
        raise ValueError('Case audit does not establish pathogen and window: ' + pathogen)
    nodes = rows(audit / 'reports/graph_nodes.csv')
    fips = {r['fips'] for r in nodes}
    if len(nodes) != 486 or len(fips) != 486 or len({r['state'] for r in nodes}) != 10:
        raise ValueError('Unexpected county footprint: ' + pathogen)
    state = {r['fips']: r['state'] for r in nodes}
    population = rows(audit / 'reports/population_audit.csv'); keys = set()
    for row in population:
        key = (row['fips'], int(row['year']))
        value = float(row['population'])
        if key in keys or row['fips'] not in fips or row['state'] != state[row['fips']] or row['population_status'] != 'ok' or not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid or duplicate population eligibility cell: ' + pathogen)
        keys.add(key)
    expected = {(county, year) for county in fips for year in range(TRAIN_START, result['end_year'] + 1)}
    if keys != expected:
        raise ValueError('Incomplete or out-of-window population grid: ' + pathogen)
    report_files = ('status.txt', 'input_checksums.csv', 'case_flow.csv', 'graph_nodes.csv', 'graph_edges.csv',
                    'population_audit.csv', 'state_year_reconciliation.csv')
    evidence = {str(audit / 'reports' / name): checksum(audit / 'reports' / name, cache=hash_cache) for name in report_files}
    if scope.is_file(): evidence[str(scope)] = checksum(scope, cache=hash_cache)
    evidence[str(reconciliation / 'status.txt')] = checksum(reconciliation / 'status.txt', cache=hash_cache)
    evidence[str(reconciliation / 'input_checksums.csv')] = checksum(reconciliation / 'input_checksums.csv', cache=hash_cache)
    result.update(eligibility_status='AUDIT_PROVENANCE_VERIFIED', panel_md5=panel_md5, panel_sha256=checksum(panel, cache=hash_cache),
                  input_md5=verified, evidence_sha256=evidence, county_count=486, state_count=10,
                  runtime_requirement='R validate_panel must independently verify the RDS keys/counts/populations and graph before fitting')
    return result


def build_protocol(root, pathogens=None, verify_inputs=True, sources=None):
    chosen = list(PATHOGENS if pathogens is None else pathogens)
    if not chosen or len(set(chosen)) != len(chosen) or any(p not in PATHOGENS for p in chosen):
        raise ValueError('Provide a nonempty unique supported pathogen selection')
    paths = source_paths(root) if sources is None else sources
    verified = {}; tasks = []; cache = {}
    for pathogen in chosen:
        source = validate_source(pathogen, paths[pathogen], verify_inputs, cache); verified[pathogen] = source
        origins = CRYPTO_ORIGINS if pathogen == 'CRYPTOSPORIDIUM' else ORIGINS
        for origin in origins:
            if origin - TRAIN_START + 1 < 8 or origin + HORIZON > source['end_year']:
                raise ValueError('Training length or forecast observation horizon invalid')
            for model in MODELS:
                task = dict(id='%s_%s_%s' % (pathogen, origin, model), kind='forecast', pathogen=pathogen,
                    model=model, origin=origin, horizon=HORIZON, train_start=TRAIN_START, train_end=origin,
                    test_start=origin + 1, test_end=origin + HORIZON, audit=source['audit'],
                    reconciliation=source['reconciliation'], required_gate='CALIBRATION_AND_HORIZON_PASS',
                    historical_reference='training-only county Poisson-rate Jeffreys Gamma(.5,0) posterior',
                    population_assumption='known realized future population: conditional hindcast',
                    evaluation_status='retrospective exploratory; these data informed previous model development')
                tasks.append(task)
    return dict(protocol_version=PROTOCOL_VERSION, sources=verified, tasks=tasks,
        maximum_inla_fits=len(tasks), models=list(MODELS), horizon=HORIZON,
        simple_reference='Computed analytically inside each task on identical training/evaluation county-years',
        no_state_model_reruns=True, automatic_dashboard_promotion=False,
        score_target='Marginal county-year future observed counts; expected-incidence uncertainty is reported separately',
        pairing='Within pathogen and origin: identical training/test keys, panel and population; compare each horizon separately',
        uncertainty='Overlapping origins and spatially correlated cells prohibit naive independent-cell/origin standard errors',
        reuse='Only exact protocol/code/input/container/seed identities and independently validated task artifacts may be reused',
        gate='Synthetic horizon invariance and calibration must pass before real-data workers fit; scheduler completion alone is insufficient')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--pathogen', action='append')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plan-only', action='store_true', help='Do not certify inputs; output explicitly remains UNVERIFIED')
    args = parser.parse_args()
    if args.output.exists(): parser.error('Refusing to overwrite existing protocol')
    plan = build_protocol(args.root, args.pathogen, verify_inputs=not args.plan_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + '\n')
    print('Protocol: ' + str(args.output) + '\nMaximum INLA fits: ' + str(plan['maximum_inla_fits']))
