#!/usr/bin/env python3
"""Verify portable saved-residual reports and export descriptive summaries only."""
import argparse
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import statistics
import tempfile
from review_broader_combinations import Archive, PATHOGENS
from launch_spatial_residual_audit import validate_result


def review(path, output):
    arc = Archive(path, 'report_sha256.json')
    try:
        plan = arc.json('plan.json')
        summary = arc.json('summary.json')
        expected = {(p, c, t, s) for p in PATHOGENS
                    for c in ((2011, 2013, 2014) if p == 'CRYPTOSPORIDIUM' else (2011, 2013, 2016))
                    for t in ('rw1', 'ar1', 'spline') for s in (False, True)}
        actual = {(t['pathogen'], t['cutoff'], t['temporal'], t['seasonal']) for t in plan['tasks']}
        if plan['version'] != 'spatial_saved_residual_audit_v1' or len(plan['tasks']) != 162 or actual != expected:
            raise ValueError('Unexpected audit matrix')
        ids = {t['id'] for t in plan['tasks']}
        if len(ids) != 162 or summary['complete'] != 162 or summary['expected'] != 162 or summary['issues']:
            raise ValueError('Incomplete audit')
        if len(summary['tasks']) != 162 or {r['task'] for r in summary['tasks']} != ids or any(r['status'] != 'COMPLETE' for r in summary['tasks']):
            raise ValueError('Incomplete task ledger')
        for key, value in dict(new_fits=0, posterior_resampling=False, county_iid_control=False, scientific_acceptance=False).items():
            if summary.get(key) != value:
                raise ValueError('Changed interpretation flag: ' + key)
        digest = hashlib.sha256(arc.read('plan.json')).hexdigest()
        annual, monthly = [], []
        for task in plan['tasks']:
            name = task['id']
            record = arc.json(name + '/task_status.json')
            if record.get('task') != name or record.get('status') != 'COMPLETE' or record.get('exit_status') != 0 or record.get('plan_sha256') != digest:
                raise ValueError('Invalid task record: ' + name)
            required = {'result/' + f for f in ('settings.csv', 'state_year_residuals.csv', 'monthly_global_residuals.csv', 'status.txt')}
            if not required.issubset(record.get('outputs', {})):
                raise ValueError('Unbound report: ' + name)
            for local, h in record['outputs'].items():
                if Path(local).is_absolute() or '..' in Path(local).parts or '\\' in local:
                    raise ValueError('Unsafe output binding')
                if '_INTERNAL' not in Path(local).name and hashlib.sha256(arc.read(name + '/' + local)).hexdigest() != h:
                    raise ValueError('Changed report: ' + name)
            with tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                (work / 'result').mkdir()
                for local in required:
                    (work / local).write_bytes(arc.read(name + '/' + local))
                validate_result(work, task)
            identity = {k: task[k] for k in ('pathogen', 'cutoff', 'temporal', 'seasonal')}
            for file, target in [('state_year_residuals.csv', annual), ('monthly_global_residuals.csv', monthly)]:
                for row in csv.DictReader(io.StringIO(arc.read(name + '/result/' + file).decode())):
                    target.append(dict(task=name, **identity, **row))
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        def write(name, rows):
            with (output / name).open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
                writer.writeheader(); writer.writerows(rows)
        write('annual.csv', annual); write('monthly.csv', monthly)
        summaries = []
        for p, temporal, seasonal in itertools.product(PATHOGENS, ('rw1', 'ar1', 'spline'), (False, True)):
            selected = lambda rows: [r for r in rows if (r['pathogen'], r['temporal'], r['seasonal']) == (p, temporal, seasonal)]
            m = selected(monthly)
            y = [r for r in selected(annual) if r['state'] == 'ALL']
            row = dict(pathogen=p, temporal=temporal, seasonal=seasonal)
            for label, rows, field in [('monthly_raw', m, 'log1p_residual_moran'), ('monthly_state_centered', m, 'within_state_centered_moran'), ('annual_state_centered', y, 'within_state_centered_moran'), ('monthly_lag', y, 'within_county_centered_month_lag1')]:
                values = [float(r[field]) for r in rows if r[field]]
                row[label + '_defined'] = len(values)
                row[label + '_median'] = statistics.median(values) if values else None
            summaries.append(row)
        write('descriptive_arm_medians.csv', summaries)
        result = dict(complete=162, archive_files=len(arc.files), annual_rows=len(annual), monthly_rows=len(monthly),
                      archive_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                      private_fit_and_county_bytes_reverified=False, scientific_acceptance=False,
                      independent_validation=False, county_iid_residual_control=False,
                      interpretation='Descriptive correlated development windows; no p-values or model ranking')
        (output / 'review.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        arc.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive'); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    review(args.archive, args.output)
