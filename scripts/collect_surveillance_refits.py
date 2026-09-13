#!/usr/bin/env python3
"""Validate corrected state artifacts and saved-fit proofs without refitting models."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import tarfile

RATE_FIELDS = ('population', 'population_check', 'raw_count', 'raw_check', 'raw_ir',
    'median', 'mean', 'lower_equitailed', 'upper_equitailed', 'lower_hdi', 'upper_hdi',
    'median_ir', 'mean_ir', 'lower_equitailed_ir', 'upper_equitailed_ir', 'lower_hdi_ir', 'upper_hdi_ir')
COMPARISON_FIELDS = ('baseline_raw_ir', 'baseline_median_ir', 'baseline_lower_hdi_ir',
    'baseline_upper_hdi_ir', 'relative_risk_lower_hdi', 'relative_risk_upper_hdi',
    'relative_risk_est', 'percent_change_lower_hdi', 'percent_change_upper_hdi', 'percent_change_est')
ARCHIVE_SUFFIXES = ('.csv', '.json', '.txt', '.log', '.r', '.py', '.sh', '.png', '.pdf')


def rows(path):
    with Path(path).open(newline='') as handle:
        result = list(csv.DictReader(handle))
    if not result:
        raise ValueError('Empty table: ' + str(path))
    return result


def one_row(path):
    data = rows(path)
    if len(data) != 1:
        raise ValueError('Expected exactly one row: ' + str(path))
    return data[0]


def number(value, label, minimum=None):
    if isinstance(value, bool):
        raise ValueError('Invalid numeric value: ' + label)
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError('Invalid numeric value: ' + label)
    return result


def integer(value, label):
    result = number(value, label)
    if result != int(result):
        raise ValueError('Expected integer: ' + label)
    return int(result)


def close(actual, expected, label, tolerance=0.000002):
    if abs(actual - expected) > tolerance + 1e-10 * max(abs(actual), abs(expected)):
        raise ValueError('Inconsistent ' + label)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def state_key(row):
    state = row['state']
    if not isinstance(state, str) or len(state) != 2 or not state.isalpha() or state != state.upper():
        raise ValueError('Invalid state key')
    return integer(row['year'], 'year'), state


def indexed(data, site=False):
    result = {}
    for row in data:
        key = state_key(row) if site else integer(row['year'], 'year')
        if key in result:
            raise ValueError('Duplicate output key: ' + str(key))
        result[key] = row
    return result


def check_diagnostics(diagnostics):
    if str(diagnostics.get('converged', '')).lower() != 'true':
        raise ValueError('Convergence not certified')
    warnings = diagnostics.get('warnings', '')
    if warnings not in ('', [], None):
        raise ValueError('Diagnostic warnings require review')
    for key, accept in (('max_rhat', lambda v: 0 < v <= 1.01),
                        ('min_ess', lambda v: v >= 400), ('n_divergent', lambda v: v == 0)):
        if not accept(number(diagnostics[key], key)):
            raise ValueError('Sampling diagnostic requires review: ' + key)


def validate_table(data, comparison=False):
    for row in data:
        # Legacy dplyr summaries overwrite population before sd(population), yielding NA.
        # This redundant check is unavailable in those files; model/site/catchment population
        # reconciliation below remains mandatory. Scientific estimates may never be NA.
        vals = {key: (0.0 if key == 'population_check' and row[key] == 'NA' else number(row[key], key, 0))
                for key in RATE_FIELDS}
        if vals['population'] <= 0:
            raise ValueError('Nonpositive population')
        integer(vals['raw_count'], 'raw_count')
        close(vals['population_check'], 0, 'population_check')
        close(vals['raw_check'], 0, 'raw_check')
        for suffix in ('', '_ir'):
            if not vals['lower_equitailed' + suffix] <= vals['median' + suffix] <= vals['upper_equitailed' + suffix]:
                raise ValueError('Unordered equal-tailed interval')
            if vals['lower_hdi' + suffix] > vals['upper_hdi' + suffix]:
                raise ValueError('Unordered HDI interval')
        scale = 100000.0 / vals['population']
        for key in ('raw', 'median', 'mean', 'lower_equitailed', 'upper_equitailed', 'lower_hdi', 'upper_hdi'):
            count_key = 'raw_count' if key == 'raw' else key
            close(vals[key + '_ir'], vals[count_key] * scale, key + ' count/rate units',
                  tolerance=0.0000011 * (1 + scale))
        if comparison:
            extra = {key: number(row[key], key, -100 if key.startswith('percent_change') else 0)
                     for key in COMPARISON_FIELDS}
            if extra['baseline_lower_hdi_ir'] > extra['baseline_upper_hdi_ir']:
                raise ValueError('Unordered baseline interval')
            for name in ('relative_risk', 'percent_change'):
                if extra[name + '_lower_hdi'] > extra[name + '_upper_hdi']:
                    raise ValueError('Unordered comparison interval')
            for suffix in ('lower_hdi', 'upper_hdi', 'est'):
                close(extra['percent_change_' + suffix], 100 * (extra['relative_risk_' + suffix] - 1),
                      'relative risk/percent change', tolerance=0.00011)


def validate_proof(proof_path, fit, first, last):
    proof = json.loads(Path(proof_path).read_text())
    if proof.get('schema_version') != 1:
        raise ValueError('Unsupported saved-fit proof schema')
    if proof.get('status') != 'PASS' or proof.get('eligibility_status') != 'PASS' or proof.get('issues'):
        raise ValueError('Saved-fit or eligibility validation did not pass')
    if proof.get('fit_sha256') != sha256(fit):
        raise ValueError('Saved-fit proof checksum mismatch')
    diagnostics = proof['diagnostics']
    check_diagnostics(diagnostics)
    ess_threshold = max(400, 100 * integer(diagnostics['chains'], 'chains'))
    for key in ('min_ess', 'min_ess_bulk', 'min_ess_tail'):
        if number(diagnostics[key], key) < ess_threshold:
            raise ValueError('Saved-fit effective sample size requires review: ' + key)
    if integer(diagnostics['n_treedepth_hits'], 'treedepth hits') != 0:
        raise ValueError('Saved-fit treedepth saturation requires review')
    if number(diagnostics['min_ebfmi'], 'E-BFMI') < 0.3:
        raise ValueError('Saved-fit E-BFMI requires review')
    if integer(diagnostics['chains'], 'chains') != 6 or integer(diagnostics['post_warmup_draws_per_chain'], 'draw count') <= 0:
        raise ValueError('Saved-fit chain/draw evidence incomplete')
    model = indexed(proof['model_data'], site=True)
    expected = indexed(proof['expected_keys'], site=True)
    if not model or set(model) != set(expected):
        raise ValueError('Saved model differs from independently validated eligible grid')
    if {key[0] for key in model} != set(range(first, last + 1)):
        raise ValueError('Saved model coverage differs from corrected years')
    for row in model.values():
        count = number(row['count'], 'model count', 0)
        integer(count, 'model count')
        if number(row['population'], 'model population', 0) <= 0:
            raise ValueError('Nonpositive model population')
    return model


def validate_export_binding(output, prefix, bs, be):
    output = Path(output)
    manifest_path = output / (prefix + '_fit_export_manifest.csv')
    if not manifest_path.is_file():
        raise ValueError('Missing fit-bound export manifest; legacy tables need saved-fit re-export without sampling')
    manifest = rows(manifest_path)
    required = {prefix + suffix for suffix in ('_IRCatch.csv', '_IRSite.csv',
        '_EstIRRCatch_%s_%s.csv' % (bs, be), '_analysis_settings.csv',
        '_population_used.csv', '_classification_rules.csv', '_convergence_diagnostics.csv')}
    if len(manifest) != len(required) or {r.get('file') for r in manifest} != required:
        raise ValueError('Fit export manifest has missing, extra or duplicate artifacts')
    fit_hash = sha256(output / (prefix + '_brm.Rds'))
    for record in manifest:
        if record.get('schema_version') != '1' or record.get('fit_sha256') != fit_hash:
            raise ValueError('Export manifest does not match saved fitted posterior')
        if record.get('sha256') != sha256(output / record['file']):
            raise ValueError('Fit-bound exported artifact changed: ' + record['file'])
    return manifest


def validate_outputs(output, prefix, model, first, last, bs, be):
    validate_export_binding(output, prefix, bs, be)
    catch_rows = rows(output / (prefix + '_IRCatch.csv'))
    site_rows = rows(output / (prefix + '_IRSite.csv'))
    comparison_rows = rows(output / (prefix + '_EstIRRCatch_%s_%s.csv' % (bs, be)))
    validate_table(catch_rows)
    validate_table(site_rows)
    validate_table(comparison_rows, comparison=True)
    catch = indexed(catch_rows)
    sites = indexed(site_rows, site=True)
    comparisons = indexed(comparison_rows)
    years = set(range(first, last + 1))
    if set(catch) != years or set(comparisons) != years:
        raise ValueError('Unexpected or incomplete year coverage')
    if not set(range(bs, be + 1)).issubset(years):
        raise ValueError('Missing baseline years')
    if set(sites) != set(model):
        raise ValueError('Site-year keys differ from validated model data')
    totals = defaultdict(lambda: [0.0, 0.0, 0.0])
    for key, row in sites.items():
        close(float(row['raw_count']), float(model[key]['count']), 'model/site count')
        close(float(row['population']), float(model[key]['population']), 'model/site population')
        totals[key[0]][0] += float(row['raw_count'])
        totals[key[0]][1] += float(row['population'])
        totals[key[0]][2] += float(row['mean'])
    baseline_raw_ir = (sum(totals[y][0] for y in range(bs, be + 1)) /
                       sum(totals[y][1] for y in range(bs, be + 1)) * 100000)
    for year in years:
        c, r = catch[year], comparisons[year]
        for i, key in enumerate(('raw_count', 'population', 'mean')):
            close(float(c[key]), totals[year][i], 'site/catchment ' + key, tolerance=0.00002)
        for key in RATE_FIELDS:
            if key == 'population_check' and c[key] == 'NA' and r[key] == 'NA':
                continue
            close(float(c[key]), float(r[key]), 'catchment/comparison ' + key)
        if integer(r['baseline_start'], 'baseline_start') != bs or integer(r['baseline_end'], 'baseline_end') != be:
            raise ValueError('Incorrect baseline values')
        if r['comparison_period'] != '%s-%s' % (bs, be):
            raise ValueError('Incorrect comparison period label')
        close(float(r['baseline_raw_ir']), baseline_raw_ir, 'baseline raw incidence')
    return dict(site_rows=len(sites), catchment_rows=len(catch), comparison_rows=len(comparisons))


def collect(dest, validation_dir=None, report_dir=None):
    dest = Path(dest).resolve()
    external = report_dir is not None
    report = Path(report_dir).resolve() if external else dest
    if external and (report == dest or dest in report.parents):
        raise ValueError('External report directory must be outside the original run')
    if external:
        if (report / 'review_summary.json').exists():
            raise ValueError('Existing external review summary; choose a new report directory')
        report.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((dest / 'manifest.json').read_text())
    results = []
    for job in manifest['jobs']:
        work = dest / job['task']; output = work / 'spline_results'; prefix = job['prefix']
        issues = []; diagnostics = {}; inventory = {}
        first, last = integer(job['first_year'], 'first_year'), integer(job['last_year'], 'last_year')
        s = job['settings']; bs, be = integer(s['baseline_start'], 'baseline_start'), integer(s['baseline_end'], 'baseline_end')
        try:
            if (work / 'exit_status.txt').read_text().strip() != '0':
                issues.append('Fit process failed')
        except OSError:
            issues.append('Missing fit exit status')
        try:
            settings = one_row(output / (prefix + '_analysis_settings.csv'))
            for key in ('pathogen', 'subgroup', 'travel', 'cidt', 'states', 'baseline_start', 'baseline_end',
                        'colorado_coverage', 'parasite_end_year', 'serotype_source', 'selected_serotypes'):
                if settings.get(key) != s.get(key):
                    issues.append('Setting changed: ' + key)
            if integer(settings['analysis_start_year'], 'start') != first or integer(settings['analysis_end_year'], 'end') != last:
                issues.append('Incorrect settings coverage')
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append('Settings: ' + str(error))
        try:
            diagnostics = one_row(output / (prefix + '_convergence_diagnostics.csv'))
            check_diagnostics(diagnostics)
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append('Diagnostics: ' + str(error))
        proof_path = ((Path(validation_dir) / job['task']) if validation_dir else work) / 'saved_fit_validation.json'
        try:
            model = validate_proof(proof_path, output / (prefix + '_brm.Rds'), first, last)
            inventory = validate_outputs(output, prefix, model, first, last, bs, be)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            issues.append('Artifact validation: ' + str(error))
        if list(output.glob('*_error.txt')):
            issues.append('Model error artifact present')
        results.append(dict(task=job['task'], analysis=prefix, source=job['source'],
                            status='CHECKS_PASS' if not issues else 'REVIEW_REQUIRED', issues=issues,
                            diagnostics=diagnostics, validated_inventory=inventory, saved_fit_proof=str(proof_path)))
    if not results:
        raise ValueError('No planned fits to validate')
    summary = dict(results=results, pending_review=manifest.get('pending_review', []), dashboard_replaced=False,
                   source_run=str(dest), original_run_modified=not external,
                   note='Checks validate eligible model keys, artifact values/aggregation and saved-fit proof; scientific adoption still requires review.')
    (report / 'review_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if external:
        (report / 'source_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with tarfile.open(str(report) + '.tar.gz', 'w:gz') as archive:
        for f in sorted(report.rglob('*')):
            if f.is_file() and not f.is_symlink() and f.suffix.lower() in ARCHIVE_SUFFIXES:
                archive.add(str(f), arcname=str(f.relative_to(report)), recursive=False)
        if external:
            # Include reviewable aggregate evidence directly, leaving the original run untouched.
            for f in sorted(dest.rglob('*')):
                if f.is_file() and not f.is_symlink() and f.suffix.lower() in ARCHIVE_SUFFIXES:
                    archive.add(str(f), arcname='source_run/' + str(f.relative_to(dest)), recursive=False)
            for job in manifest['jobs']:
                proof = ((Path(validation_dir) / job['task']) if validation_dir else dest / job['task']) / 'saved_fit_validation.json'
                if proof.is_file():
                    archive.add(str(proof), arcname='validation/' + job['task'] + '/saved_fit_validation.json', recursive=False)
    print(json.dumps(summary, indent=2)); print('Archive: ' + str(report) + '.tar.gz')
    return 0 if all(r['status'] == 'CHECKS_PASS' for r in results) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dest')
    parser.add_argument('--validation-dir')
    parser.add_argument('--report-dir')
    args = parser.parse_args()
    raise SystemExit(collect(args.dest, args.validation_dir, args.report_dir))
