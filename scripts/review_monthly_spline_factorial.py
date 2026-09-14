#!/usr/bin/env python3
"""Review the frozen 162-cell spline factorial without fitting or selecting models."""
import argparse
import hashlib
import json
from pathlib import Path
import review_monthly_factorial as base

METRICS = ('spline_minus_reference_nonseasonal', 'spline_minus_reference_seasonal',
           'seasonality_under_reference', 'seasonality_under_spline', 'interaction')


def matrix():
    result = {}
    for p in base.PATHOGENS:
        for c in ((2011, 2013, 2014) if p == 'CRYPTOSPORIDIUM' else (2011, 2013, 2016)):
            for m in ('rw1', 'ar1', 'spline'):
                for s in (False, True):
                    name = '%s_%d_%s_%s' % (p, c, m, 'seasonal' if s else 'nonseasonal')
                    result[name] = dict(pathogen=p, cutoff=c, temporal=m, seasonal=s,
                                        end_year=2017 if p == 'CRYPTOSPORIDIUM' else 2019,
                                        reused=m != 'spline')
    return result


def validate_extra(report, plan, summary):
    suffix = '/scripts/launch_monthly_spline_factorial.py'
    root = next(p[:-len(suffix)] for p in plan['inputs'] if p.endswith(suffix))
    # Every portable snapshot/reference must retain its earlier plan binding.
    for name in report.files:
        if name.startswith(('scripts/', 'basis/', 'references/')):
            if root+'/'+name not in plan['inputs']:
                raise ValueError('Missing plan binding: '+name)
    manifest = report.json('basis/manifest.json')
    if any(manifest.get(k) != v for k, v in dict(version='monthly_spline_basis_v1', data_used=False,
            k=6, training_start=2004, horizon_years=3).items()):
        raise ValueError('Unexpected prepared basis specification')
    if set(manifest.get('files', {})) != {'2011.csv', '2013.csv', '2014.csv', '2016.csv', 'generation_session.txt'}:
        raise ValueError('Incomplete prepared basis files')
    sources = {'scripts/prepare_monthly_spline_basis.R', 'scripts/monthly_spline_combination.R', 'scripts/county_spline_candidate.R'}
    if set(manifest.get('sources', {})) != sources:
        raise ValueError('Incomplete prepared basis source binding')
    for names, prefix in ((manifest['files'], 'basis/'), (manifest['sources'], '')):
        for name, digest in names.items():
            path = base.safe_name(prefix+name)
            if path not in report.files or hashlib.sha256(report.read(path)).hexdigest() != digest:
                raise ValueError('Prepared basis binding differs: '+path)
    for c in (2011, 2013, 2014, 2016):
        data = report.rows('basis/%d.csv' % c)
        if len(data) != (c+4-2004)*12 or any(set(r) != {'serial','slope','X1','X2','X3','X4'} for r in data):
            raise ValueError('Invalid prepared basis grid')
        for serial, r in enumerate(data, 2004*12):
            if base.integer(r['serial']) != serial:
                raise ValueError('Invalid prepared basis serial')
            for value in r.values():
                base.number(value)
    for t in plan['tasks']+plan['references']:
        state = next(r for r in summary['tasks'] if r['task'] == t['id'])
        if state['status'] != 'COMPLETE':
            continue
        prefix = 'references/'+t['id'] if t['reused'] else t['id']+'/result'
        if prefix+'/rng_protocol.csv' in report.files:
            raise ValueError('Unsupported sampling-protocol change in frozen factorial')
        settings = report.rows(prefix+'/settings.csv')
        if len(settings) != 1:
            raise ValueError('Missing task settings: '+t['id'])
        r = settings[0]
        if (base.integer(r['cutoff']), base.boolean(r['seasonal']), base.integer(r['streams']),
            base.integer(r['draws_per_stream']), base.boolean(r['coverage_certified'])) != (t['cutoff'], t['seasonal'], 4, 2000, False):
            raise ValueError('Task settings differ: '+t['id'])
        if base.boolean(r['refitted']) is not False:
            raise ValueError('Diagnostic settings claim refitting')
        if (not t['reused'] or 'seed' in t) and base.integer(r['base_seed']) != t['seed']:
            raise ValueError('Task sampling seed differs')
        if not t['reused']:
            rec = report.json(t['id']+'/task_status.json')
            outputs = rec.get('outputs', {})
            required = {'result/stream_scores.csv', 'result/aggregate_tails.csv', 'result/settings.csv', 'result/sensitivity_settings.csv', 'task.log'}
            if not required.issubset(outputs):
                raise ValueError('Missing task-bound output: '+t['id'])
            for name, bound in outputs.items():
                local = base.safe_name(t['id']+'/'+name)
                # Internal checkpoints/truth intentionally stay on the cluster.
                if '_INTERNAL' not in Path(name).name and Path(name).suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and local not in report.files:
                    raise ValueError('Missing portable task-bound output: '+local)
            sensitivity = report.rows(prefix+'/sensitivity_settings.csv')
            if len(sensitivity) != 1:
                raise ValueError('Missing spline settings')
            r = sensitivity[0]
            if r.get('temporal_model') != 'spline' or r.get('comparison') != 'monthly_spline_factorial_v1' or base.boolean(r['seasonal']) != t['seasonal']:
                raise ValueError('Spline model identity differs')
            for name, value in dict(end_year=t['end_year'], rate_center=.0002, k=6, slope_sd=.5, nonlinear_sd_upper=.5).items():
                if base.number(r[name]) != value:
                    raise ValueError('Spline prior/specification differs: '+name)


def recompute(scores, excluded):
    site, equal = [], []
    for reference in ('rw1', 'ar1'):
        selected = [dict(r, temporal='rw1' if r['temporal'] == reference else 'ar1')
                    for r in scores if r['temporal'] in (reference, 'spline')]
        a, b = base.recompute(selected, excluded)
        for rows, destination in ((a, site), (b, equal)):
            for r in rows:
                mapped = {k:v for k,v in r.items() if k not in base.METRICS}
                mapped.update(reference=reference, **dict(zip(METRICS, (r[m] for m in base.METRICS))))
                destination.append(mapped)
    return site, equal


def figures(out, contrasts, calibration):
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/foodnet-factorial-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for p in sorted({r['pathogen'] for r in contrasts}):
        fig, axes = plt.subplots(3, 2, figsize=(16, 10), constrained_layout=True)
        for column, reference in enumerate(('rw1', 'ar1')):
            rows = [r for r in contrasts if r['pathogen'] == p and r['reference'] == reference]
            labels = ['%d / H%d' % (r['cutoff'], r['horizon']) for r in rows]
            for ax, metrics in zip(axes[:, column], (METRICS[:2], METRICS[2:4], METRICS[4:])):
                for j, metric in enumerate(metrics):
                    x = [i + (j-.5)*.12 for i in range(len(rows))]
                    ax.scatter(x, [r[metric] for r in rows], s=18, label=metric)
                    ax.vlines(x, [r[metric+'_stream_min'] for r in rows], [r[metric+'_stream_max'] for r in rows], alpha=.6)
                ax.axhline(0, color='grey', lw=.7)
                ax.set_xticks(range(len(rows)), labels, rotation=30, ha='right')
                ax.set_ylabel('Equal-site log-score difference')
                ax.legend(fontsize=7)
            axes[0,column].set_title('Spline versus '+reference.upper())
        fig.suptitle(p+': exploratory spline combinations\nPoints: pooled draws; lines: four-stream range, not confidence intervals')
        for ext in ('png','pdf'):
            fig.savefig(str(out/(p+'_spline_contrasts.'+ext)), dpi=150)
        plt.close(fig)
    # The established calibration plot naturally displays all six arms.
    base.figures(out, [], calibration)


PROTOCOL = dict(version='monthly_spline_factorial_v1', launcher='launch_monthly_spline_factorial.py',
                matrix=matrix, counts=(162,54,108), metrics=METRICS, extra_keys=('reference',),
                validate_extra=validate_extra, recompute=recompute, figures=figures,
                site_file='spline_site_contrasts.csv', equal_file='spline_equal_site_contrasts.csv')


def review(source, destination, plots=True):
    result = base.review(source, destination, plots, PROTOCOL)
    out = Path(destination)
    specs = matrix()
    import csv
    with (out/'task_inventory.csv').open() as handle:
        inventory = list(csv.DictReader(handle))
    complete = {r['task'] for r in inventory if r['status'] == 'COMPLETE'}
    blocks = []
    for p, c in sorted({(v['pathogen'],v['cutoff']) for v in specs.values()}):
        for reference in ('rw1','ar1'):
            missing = sorted(t for t,s in specs.items() if (s['pathogen'],s['cutoff']) == (p,c) and s['temporal'] in (reference,'spline') and t not in complete)
            blocks.append(dict(pathogen=p, cutoff=c, reference=reference, complete=not missing,
                               missing_tasks=';'.join(missing), interpretable=not missing and result['comparisons_interpretable']))
    base.write_csv(out/'comparison_block_inventory.csv', blocks)
    result['complete_four_arm_blocks'] = sum(r['complete'] for r in blocks)
    result['expected_four_arm_blocks'] = 54
    (out/'review_summary.json').write_text(json.dumps(result, indent=2)+'\n')
    path = out/'review.md'
    text = path.read_text().replace('# Monthly factorial review', '# Monthly spline factorial review')
    text += ('\nThis six-arm review compares spline against BOTH RW1 and AR1, separately with and without seasonality. '
             'Four-arm blocks are listed in comparison_block_inventory.csv; an incomplete spline block never substitutes an available arm. '
             'These are state-specific temporal effects with static county effects, not county-specific temporal splines. '
             'Prior/extrapolation differences remain part of each model package. No spline acceptance follows from numerical completion. '
             'Apply docs/monthly_spline_decision_checklist.md and record decisions in analysis_configs/monthly_spline_decision_template.csv.\n')
    path.write_text(text)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output', required=True)
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()
    result = review(args.source, args.output, not args.no_plots)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'COMPLETE_EXPLORATORY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
