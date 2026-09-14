#!/usr/bin/env python3
"""Verify a portable monthly factorial report and export exploratory review tables."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import tarfile

PATHOGENS = ('CAMPYLOBACTER', 'CRYPTOSPORIDIUM', 'CYCLOSPORA', 'LISTERIA',
             'SALMONELLA', 'SHIGELLA', 'STEC', 'VIBRIO', 'YERSINIA')
STATES = ('CA', 'CO', 'CT', 'GA', 'MD', 'MN', 'NM', 'NY', 'OR', 'TN')
METRICS = ('ar1_minus_rw1_nonseasonal', 'ar1_minus_rw1_seasonal',
           'seasonality_under_rw1', 'seasonality_under_ar1', 'interaction')
MAX_BYTES = 1024 ** 3


def safe_name(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or p.is_absolute() or any(x in ('..', '.') for x in name.split('/')) or ':' in name:
        raise ValueError('Unsafe report path: ' + name)
    return str(p)


class Report:
    """Read regular files without extracting archives or following symlinks."""
    def __init__(self, source):
        self.source = Path(source)
        self.archive = None
        self.files = {}
        if self.source.is_symlink():
            raise ValueError('Symlink report source is not allowed')
        total = 0
        if self.source.is_dir():
            for p in self.source.rglob('*'):
                if p.is_symlink():
                    raise ValueError('Symlinks are not allowed in reports')
                if p.is_file():
                    name = safe_name(p.relative_to(self.source).as_posix())
                    self.files[name] = p
                    total += p.stat().st_size
        else:
            self.archive = tarfile.open(str(self.source), 'r:*')
            for m in self.archive.getmembers():
                name = safe_name(m.name.rstrip('/'))
                if m.isdir():
                    continue
                if not m.isfile() or name in self.files:
                    raise ValueError('Nonregular or duplicate archive member: ' + name)
                self.files[name] = m
                total += m.size
        if total > MAX_BYTES:
            raise ValueError('Report exceeds 1 GiB safety limit')
        if 'report_sha256.json' not in self.files:
            raise ValueError('Missing root report_sha256.json')
        manifest = self.json('report_sha256.json')
        if not isinstance(manifest, dict) or set(manifest) != set(self.files) - {'report_sha256.json'}:
            raise ValueError('Manifest must bind every report file exactly once')
        for name, expected in manifest.items():
            safe_name(name)
            if not isinstance(expected, str) or hashlib.sha256(self.read(name)).hexdigest() != expected:
                raise ValueError('Manifest hash mismatch: ' + name)
        self.verified_files = len(manifest)

    def read(self, name):
        obj = self.files[name]
        if self.archive is not None:
            return self.archive.extractfile(obj).read()
        return obj.read_bytes()

    def json(self, name):
        def pairs(items):
            result = {}
            for k, v in items:
                if k in result:
                    raise ValueError('Duplicate JSON key: ' + k)
                result[k] = v
            return result
        return json.loads(self.read(name).decode('utf-8'), object_pairs_hook=pairs)

    def rows(self, name):
        if name not in self.files:
            return []
        reader = csv.DictReader(io.StringIO(self.read(name).decode('utf-8-sig')))
        if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Missing or duplicate CSV header: ' + name)
        data = list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in data):
            raise ValueError('Malformed CSV row: ' + name)
        return data

    def __del__(self):
        self.close()

    def close(self):
        if self.archive is not None:
            self.archive.close()


def boolean(value):
    if value in ('True', 'TRUE') or value is True:
        return True
    if value in ('False', 'FALSE') or value is False:
        return False
    raise ValueError('Invalid Boolean: ' + str(value))


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite number')
    return result


def integer(value):
    result = number(value)
    if result != int(result):
        raise ValueError('Nonintegral value')
    return int(result)


def matrix():
    result = {}
    for p in PATHOGENS:
        for c in ((2011, 2013, 2014) if p == 'CRYPTOSPORIDIUM' else (2011, 2013, 2016)):
            for m in ('rw1', 'ar1'):
                for s in (False, True):
                    name = '%s_%d_%s_%s' % (p, c, m, 'seasonal' if s else 'nonseasonal')
                    result[name] = dict(pathogen=p, cutoff=c, temporal=m, seasonal=s,
                                        reused=s or (m == 'rw1' and p in ('SALMONELLA', 'CAMPYLOBACTER')))
    return result


def validate(report):
    plan, summary = report.json('plan.json'), report.json('summary.json')
    if plan.get('version') != 'monthly_factorial_v1' or plan.get('verified') is not True:
        raise ValueError('Unexpected or unverified plan')
    for obj in (plan, summary):
        for flag in ('accepted', 'independent_validation', 'cpo_ranking'):
            if obj.get(flag) is not False:
                raise ValueError('Unsupported claim: ' + flag)
    if plan.get('coverage_certified') is not False:
        raise ValueError('Unsupported coverage claim')
    # The manifest may have been generated after a source artifact changed.
    # Recheck earlier plan bindings for snapshots that travel in this archive.
    suffix = '/scripts/launch_monthly_factorial.py'
    roots = [p[:-len(suffix)] for p in plan.get('inputs', {}) if p.endswith(suffix)]
    if len(roots) != 1:
        raise ValueError('Cannot identify bound snapshot root')
    prefix = roots[0] + '/'
    for path, digest in plan['inputs'].items():
        if path.startswith(prefix):
            local = safe_name(path[len(prefix):])
            if local not in report.files or hashlib.sha256(report.read(local)).hexdigest() != digest:
                raise ValueError('Changed plan-bound snapshot: ' + local)
    expected = matrix()
    tasks = plan['tasks'] + plan['references']
    if len(tasks) != 108 or {t['id'] for t in tasks} != set(expected):
        raise ValueError('Plan is not the frozen 108-cell matrix')
    for t in tasks:
        if any(t.get(k) != v for k, v in expected[t['id']].items()):
            raise ValueError('Task specification mismatch: ' + t['id'])
        if t['reused'] != (t in plan['references']):
            raise ValueError('Incorrect new/reference allocation')
    if (plan.get('new_fits'), plan.get('reused_fits'), plan.get('total_cells')) != (48, 60, 108):
        raise ValueError('Wrong plan counts')
    records = summary['tasks']
    if len(records) != 108 or {r['task'] for r in records} != set(expected):
        raise ValueError('Summary must identify all 108 cells, including missing cells')
    complete = set()
    for r in records:
        if r['reused'] is not expected[r['task']]['reused'] or r['status'] not in ('COMPLETE', 'FAILED_OR_MISSING'):
            raise ValueError('Invalid summary task label')
        if r['status'] == 'COMPLETE':
            complete.add(r['task'])
    if (summary.get('complete'), summary.get('expected'), summary.get('new_fits'), summary.get('reused_fits')) != (len(complete), 108, 48, 60):
        raise ValueError('Summary completeness/count mismatch')
    issues = summary.get('issues')
    if not isinstance(issues, list) or not all(isinstance(x, str) for x in issues):
        raise ValueError('Invalid collector issues')
    scores = report.rows('all_stream_scores.csv')
    tails = report.rows('all_aggregate_tails.csv')
    for data, tail in ((scores, False), (tails, True)):
        keys = set()
        for r in data:
            task = r['task']
            if task not in complete:
                raise ValueError('Metrics from incomplete/unknown task')
            spec = expected[task]
            for k in ('pathogen', 'temporal'):
                if r[k] != spec[k]:
                    raise ValueError('Metric identity mismatch')
            for k in ('seasonal', 'reused'):
                r[k] = boolean(r[k])
                if r[k] is not spec[k]:
                    raise ValueError('Metric Boolean identity mismatch')
            for k in ('cutoff', 'year', 'stream', 'draws'):
                r[k] = integer(r[k])
            key = task, r['state'], r['year'], r['stream']
            if key in keys:
                raise ValueError('Duplicate metric cell')
            keys.add(key)
            if r['cutoff'] != spec['cutoff'] or r['year'] not in range(spec['cutoff']+1, spec['cutoff']+4) or r['stream'] not in range(5) or r['state'] not in STATES + (('ALL',) if tail else ()):
                raise ValueError('Invalid metric domain')
            if r['draws'] != (8000 if r['stream'] == 0 else 2000):
                raise ValueError('Invalid draw count')
            if tail:
                for k in ('observed', 'mean_expected', 'median_expected', 'p975_expected', 'max_expected', 'top_one_percent_mean_share', 'lower95', 'median_predictive', 'upper95', 'prob_above_twice_observed'):
                    r[k] = number(r[k])
                    if r[k] < 0:
                        raise ValueError('Negative tail value')
                if r['observed'] != int(r['observed']) or not r['lower95'] <= r['median_predictive'] <= r['upper95'] or not r['median_expected'] <= r['p975_expected'] <= r['max_expected']:
                    raise ValueError('Invalid tail ordering/count')
                if any(r[k] > 1 for k in ('top_one_percent_mean_share', 'prob_above_twice_observed')):
                    raise ValueError('Invalid probability/share')
            else:
                for k in ('mean_log_score', 'max_cell_density_relative_mcse'):
                    r[k] = number(r[k])
                if r['mean_log_score'] > 1e-12 or r['max_cell_density_relative_mcse'] < 0:
                    raise ValueError('Invalid predictive score or MCSE')
        required = {(t, s, y, k) for t in complete for s in STATES + (('ALL',) if tail else ()) for y in range(expected[t]['cutoff']+1, expected[t]['cutoff']+4) for k in range(5)}
        if keys != required:
            raise ValueError('Incomplete metric grid for completed tasks')
    # Merged tables are collector products: they must reproduce the earlier
    # per-task reports, not merely have a self-consistent fresh manifest.
    for t in tasks:
        if t['id'] not in complete:
            continue
        prefix = ('references/' + t['id']) if t['reused'] else (t['id'] + '/result')
        for filename, merged in (('stream_scores.csv', scores), ('aggregate_tails.csv', tails)):
            original = report.rows(prefix + '/' + filename)
            merged_rows = [r for r in merged if r['task'] == t['id']]
            key = lambda r: (r['state'], integer(r['year']), integer(r['stream']))
            original_index = {key(r): r for r in original}
            if len(original_index) != len(original) or set(original_index) != {key(r) for r in merged_rows}:
                raise ValueError('Merged report differs from per-task domain')
            for r in merged_rows:
                for field, value in original_index[key(r)].items():
                    if field == 'state':
                        continue
                    if field not in r or not math.isclose(number(value), number(r[field]), rel_tol=1e-12, abs_tol=1e-12):
                        raise ValueError('Merged report differs from per-task values')
    # The portable archive cannot re-read internal county truth. Check both the
    # collector's bound identity evidence and independently visible aggregates.
    truths = {}
    digest = hashlib.sha256(report.read('plan.json')).hexdigest()
    for t in tasks:
        if t['id'] not in complete:
            continue
        if t['reused']:
            truth = t['reference']['truth_sha256']
        else:
            rec = report.json(t['id'] + '/task_status.json')
            if rec.get('task') != t['id'] or rec.get('status') != 'COMPLETE' or rec.get('exit_status') != 0 or rec.get('plan_sha256') != digest:
                raise ValueError('Invalid new task provenance')
            for path, bound in rec.get('outputs', {}).items():
                local = safe_name(t['id'] + '/' + path)
                if local in report.files and hashlib.sha256(report.read(local)).hexdigest() != bound:
                    raise ValueError('Changed task-bound output: ' + local)
            truth = rec['truth_sha256']
        if not isinstance(truth, str) or len(truth) != 64 or any(x not in '0123456789abcdef' for x in truth):
            raise ValueError('Invalid bound truth hash')
        truths.setdefault((t['pathogen'], t['cutoff']), set()).add(truth)
    invalid = {k for k, v in truths.items() if len(v) != 1}
    observed = {}
    by_task = {}
    for r in tails:
        k = r['pathogen'], r['cutoff'], r['state'], r['year']
        observed.setdefault(k, set()).add(r['observed'])
        by_task[(r['task'], r['year'], r['stream'], r['state'])] = r['observed']
    for k, values in observed.items():
        if len(values) != 1:
            invalid.add(k[:2])
    for (task, y, stream, state), value in by_task.items():
        if state == 'ALL' and value != sum(by_task[(task, y, stream, s)] for s in STATES):
            raise ValueError('Catchment observed total differs from site totals')
    # Any collector issue blocks interpretation globally. Do not parse free-text
    # issue strings to guess which untrusted blocks remain usable.
    return plan, summary, scores, tails, invalid, bool(issues), len(complete)


def recompute(scores, excluded):
    index = {}
    for r in scores:
        if (r['pathogen'], r['cutoff']) in excluded:
            continue
        key = (r['pathogen'], r['cutoff'], r['state'], r['year'], r['stream'])
        index.setdefault(key, {})[(r['temporal'], r['seasonal'])] = r['mean_log_score']
    site = []
    for k, arms in sorted(index.items()):
        if len(arms) != 4:
            continue
        a, b, c, d = [arms[x] for x in (('rw1', False), ('ar1', False), ('rw1', True), ('ar1', True))]
        site.append(dict(zip(('pathogen', 'cutoff', 'state', 'year', 'stream'), k),
                         ar1_minus_rw1_nonseasonal=b-a, ar1_minus_rw1_seasonal=d-c,
                         seasonality_under_rw1=c-a, seasonality_under_ar1=d-b,
                         interaction=d-b-c+a))
    grouped = {}
    for r in site:
        k = r['pathogen'], r['cutoff'], r['year'], r['stream']
        grouped.setdefault(k, []).append(r)
    equal = []
    for k, rs in sorted(grouped.items()):
        if len(rs) != 10 or {r['state'] for r in rs} != set(STATES):
            raise ValueError('Incomplete sites in contrast')
        equal.append(dict(zip(('pathogen', 'cutoff', 'year', 'stream'), k), sites=10,
                          **{m: sum(r[m] for r in rs)/10 for m in METRICS}))
    return site, equal


def compare_published(actual, reported, site):
    keys = ('pathogen', 'cutoff', 'state', 'year', 'stream') if site else ('pathogen', 'cutoff', 'year', 'stream')
    def key(r):
        return tuple(r[k] if k in ('pathogen', 'state') else integer(r[k]) for k in keys)
    published = {key(r): r for r in reported}
    if len(published) != len(reported) or set(published) != {key(r) for r in actual}:
        raise ValueError('Published contrast domain differs from recomputation')
    for r in actual:
        source = published[key(r)]
        if not site and integer(source['sites']) != 10:
            raise ValueError('Published equal-site denominator differs')
        for m in METRICS:
            if not math.isclose(number(source[m]), r[m], rel_tol=1e-9, abs_tol=1e-10):
                raise ValueError('Published contrast differs from recomputation: ' + m)


def write_csv(path, data):
    if not data:
        path.write_text('')
        return
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def figures(out, contrasts, calibration):
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/foodnet-factorial-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for p in sorted({r['pathogen'] for r in contrasts}):
        rs = [r for r in contrasts if r['pathogen'] == p]
        fig, axes = plt.subplots(3, 1, figsize=(12, 9), constrained_layout=True)
        labels = ['%s / H%s' % (r['cutoff'], r['horizon']) for r in rs]
        for ax, metrics in zip(axes, (METRICS[:2], METRICS[2:4], METRICS[4:])):
            for j, m in enumerate(metrics):
                x = [i + (j-.5)*.12 for i in range(len(rs))]
                y = [r[m] for r in rs]
                ax.scatter(x, y, label=m, s=20)
                ax.vlines(x, [r[m+'_stream_min'] for r in rs], [r[m+'_stream_max'] for r in rs], alpha=.6)
            ax.axhline(0, color='grey', lw=.7)
            ax.set_xticks(range(len(rs)), labels, rotation=30, ha='right')
            ax.set_ylabel('Equal-site log-score difference')
            ax.legend(fontsize=8)
        fig.suptitle(p + ': exploratory component comparisons\nPoints: pooled draws; lines: four-stream range, not confidence intervals')
        for ext in ('png', 'pdf'):
            fig.savefig(str(out/(p+'_contrasts.'+ext)), dpi=160)
        plt.close(fig)
    # Calibration retains origin/horizon; it never pools overlapping evaluations.
    for p in sorted({r['pathogen'] for r in calibration}):
        rs = [r for r in calibration if r['pathogen'] == p]
        fig, axes = plt.subplots(3, 1, figsize=(12, 9), constrained_layout=True)
        blocks = sorted({(r['cutoff'], r['horizon']) for r in rs})
        for arm in sorted({r['arm'] for r in rs}):
            lookup = {(r['cutoff'], r['horizon']): r for r in rs if r['arm'] == arm}
            for ax, metric in zip(axes, ('site_coverage_fraction', 'equal_site_relative_bias', 'equal_site_relative_interval_width')):
                ax.plot(range(len(blocks)), [lookup[b][metric] if b in lookup and lookup[b][metric] != '' else float('nan') for b in blocks], marker='o', ms=3, label=arm)
                ax.set_ylabel(metric.replace('_', ' '))
                ax.set_xticks(range(len(blocks)), ['%d / H%d' % b for b in blocks], rotation=30, ha='right')
        axes[0].axhline(.95, color='grey', lw=.7, linestyle=':')
        axes[1].axhline(0, color='grey', lw=.7)
        axes[0].legend(fontsize=8, ncols=2)
        fig.suptitle(p + ': exploratory calibration (10 sites per origin/horizon)\nCoverage is descriptive; repeated evaluations are dependent')
        for ext in ('png', 'pdf'):
            fig.savefig(str(out/(p+'_calibration.'+ext)), dpi=160)
        plt.close(fig)


def review(source, destination, plots=True):
    report = Report(source)
    try:
        plan, summary, scores, tails, invalid, blocked, complete = validate(report)
        if blocked or invalid:
            site, equal = [], []
        else:
            site, equal = recompute(scores, invalid)
            compare_published(site, report.rows('factorial_site_contrasts.csv'), True)
            compare_published(equal, report.rows('factorial_equal_site_contrasts.csv'), False)
        out = Path(destination)
        out.mkdir(parents=True, exist_ok=False)
        pooled = []
        for r in equal:
            if r['stream'] != 0:
                continue
            group = [x for x in equal if (x['pathogen'], x['cutoff'], x['year']) == (r['pathogen'], r['cutoff'], r['year']) and x['stream'] != 0]
            z = dict(r, horizon=r['year']-r['cutoff'])
            for m in METRICS:
                z[m+'_stream_min'] = min(x[m] for x in group)
                z[m+'_stream_max'] = max(x[m] for x in group)
            pooled.append(z)
        arm_groups = {}
        for r in scores:
            arm_groups.setdefault((r['task'], r['year'], r['stream']), []).append(r)
        arm_scores = []
        for (task, year, stream), rs in sorted(arm_groups.items()):
            if stream != 0:
                continue
            z = {k: rs[0][k] for k in ('pathogen', 'cutoff', 'temporal', 'seasonal', 'reused')}
            stream_means = [sum(x['mean_log_score'] for x in arm_groups[(task, year, k)])/10 for k in range(1, 5)]
            z.update(task=task, year=year, horizon=year-z['cutoff'], sites=10,
                     pooled_equal_site_log_score=sum(x['mean_log_score'] for x in rs)/10,
                     stream_min=min(stream_means), stream_max=max(stream_means),
                     maximum_cell_density_relative_mcse=max(x['max_cell_density_relative_mcse'] for x in rs))
            arm_scores.append(z)
        calibration, details = [], []
        groups = {}
        for r in tails:
            if r['stream'] != 0:
                continue
            z = {k: r[k] for k in ('task', 'pathogen', 'cutoff', 'temporal', 'seasonal', 'reused', 'state', 'year', 'observed', 'mean_expected', 'lower95', 'upper95', 'top_one_percent_mean_share', 'prob_above_twice_observed')}
            z.update(horizon=r['year']-r['cutoff'], covered=r['lower95'] <= r['observed'] <= r['upper95'],
                     bias=r['mean_expected']-r['observed'], interval_width=r['upper95']-r['lower95'],
                     relative_bias=(r['mean_expected']/r['observed']-1) if r['observed'] else '',
                     relative_interval_width=((r['upper95']-r['lower95'])/r['observed']) if r['observed'] else '')
            details.append(z)
            groups.setdefault((r['task'], r['year']), []).append(z)
        for (task, year), rs in sorted(groups.items()):
            sites = [r for r in rs if r['state'] != 'ALL']
            catchment = next(r for r in rs if r['state'] == 'ALL')
            z = {k: catchment[k] for k in ('pathogen', 'cutoff', 'horizon', 'temporal', 'seasonal', 'reused')}
            z.update(task=task, year=year, arm=z['temporal']+('_seasonal' if z['seasonal'] else '_nonseasonal'),
                     site_coverage_fraction=sum(r['covered'] for r in sites)/10.,
                     equal_site_bias=sum(r['bias'] for r in sites)/10.,
                     equal_site_interval_width=sum(r['interval_width'] for r in sites)/10.,
                     positive_observed_sites=sum(r['observed'] > 0 for r in sites),
                     equal_site_relative_bias=(sum(r['relative_bias'] for r in sites)/10.) if all(r['observed'] for r in sites) else '',
                     equal_site_relative_interval_width=(sum(r['relative_interval_width'] for r in sites)/10.) if all(r['observed'] for r in sites) else '',
                     equal_site_top_one_percent_mean_share=sum(r['top_one_percent_mean_share'] for r in sites)/10.,
                     catchment_bias=catchment['bias'], catchment_covered=catchment['covered'],
                     catchment_interval_width=catchment['interval_width'])
            calibration.append(z)
        state = 'BLOCKED_COLLECTOR_OR_TRUTH_ISSUES' if blocked or invalid else ('COMPLETE_EXPLORATORY' if complete == 108 else 'PARTIAL_EXPLORATORY')
        counts = {label: sum(r['status'] == 'COMPLETE' and r['reused'] is reuse for r in summary['tasks']) for label, reuse in (('new_complete', False), ('reused_complete', True))}
        result = dict(status=state, complete=complete, expected=108, manifest_files_verified=report.verified_files,
                      invalid_truth_blocks=sorted(invalid), collector_issues=summary['issues'],
                      accepted=False, independent_validation=False, coverage_certified=False,
                      comparisons_interpretable=not (blocked or invalid), **counts)
        (out/'review_summary.json').write_text(json.dumps(result, indent=2)+'\n')
        write_csv(out/'task_inventory.csv', [dict(task=r['task'], status=r['status'], reused=r['reused'], reason=r.get('reason', '')) for r in summary['tasks']])
        # Suppress inferential exports when the collector itself reports issues.
        if not (blocked or invalid):
            write_csv(out/'site_contrasts.csv', site)
            write_csv(out/'equal_site_contrasts.csv', equal)
            write_csv(out/'pooled_component_review.csv', pooled)
            write_csv(out/'pooled_calibration.csv', calibration)
            write_csv(out/'pooled_arm_scores.csv', arm_scores)
            write_csv(out/'pooled_site_and_catchment_details.csv', details)
            if plots and pooled:
                figures(out, pooled, calibration)
        text = '# Monthly factorial review\n\nStatus: **%s**. %d/108 cells complete (%d new, %d reused). %d manifest file hashes verified.\n\n' % (state, complete, counts['new_complete'], counts['reused_complete'], report.verified_files)
        text += ('The portable manifest checks archive consistency, not authenticity or a fresh check of cluster-only source files. County-level held-out identity is taken from bound task/reference hashes; visible site totals are independently checked.\n\n'
                 'This is exploratory development-year evaluation, with assumed continuous coverage. No model is accepted or automatically selected. CPO is not used. Component contrasts compare specified model/prior packages; score interactions are not biological interactions.\n\n'
                 'Scores weight the ten sites equally within each pathogen, origin and horizon. Four-stream ranges describe Monte Carlo stability, not confidence intervals or independent replication. Origins overlap. Calibration uses pooled joint predictive intervals; endpoints are never added across sites. Zero-observation relative summaries are left undefined.\n\n')
        if blocked or invalid:
            text += 'Comparison exports and figures are suppressed because collector/truth issues require resolution. See review_summary.json.\n'
        else:
            text += '| Pathogen | Origin | Horizon | AR1 effect, no seasonality | AR1 effect, seasonal | Seasonality, RW1 | Seasonality, AR1 | Score interaction |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
            for r in pooled:
                text += '| %s | %d | %d | %s |\n' % (r['pathogen'], r['cutoff'], r['horizon'], ' | '.join('%.5g' % r[m] for m in METRICS))
            text += '\nRead these contrasts with pooled_calibration.csv and pooled_site_and_catchment_details.csv. A weak standalone result does not reject a combination candidate. No universal or pathogen-specific winner is inferred here.\n'
        (out/'review.md').write_text(text)
        return result
    finally:
        report.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='Portable .tar.gz report or extracted report directory')
    parser.add_argument('--output', required=True, help='New local review directory')
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()
    result = review(args.source, args.output, not args.no_plots)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'COMPLETE_EXPLORATORY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
