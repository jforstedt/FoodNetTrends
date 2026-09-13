#!/usr/bin/env python3
"""Collect a fixed forecast experiment ledger, retaining failures and paired targets."""
import csv
import json
import math
from pathlib import Path
import sys
import tarfile
from county_forecast_artifacts import validate_task_outputs
from run_county_forecast_validation import sha


def csvrows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))


def paired_scores(a,b):
    def index(rows):
        out={}
        for r in rows:
            key=(r['fips'],r['state'],int(r['year']))
            if key in out:raise ValueError('Duplicate forecast cell')
            out[key]=r
        return out
    a=index(a);b=index(b)
    if not a or set(a)!=set(b):raise ValueError('Paired forecast cell inventories differ')
    records=[]
    for key in sorted(a):
        x=a[key];y=b[key]
        if float(x['observed'])!=float(y['observed']) or float(x['population'])!=float(y['population']):raise ValueError('Paired outcomes/exposures differ')
        gain=float(y['log_predictive_density'])-float(x['log_predictive_density'])
        if not math.isfinite(gain):raise ValueError('Nonfinite paired score')
        records.append(dict(state=key[1],year=key[2],gain=gain))
    groups={}
    for r in records:groups.setdefault((r['state'],r['year']),[]).append(r['gain'])
    return [dict(state=state,year=year,cells=len(values),log_score_gain=sum(values)) for (state,year),values in sorted(groups.items())]


def collect(dest):
    dest=Path(dest);plan=json.loads((dest/'manifest.json').read_text());results=[]
    for task in plan['tasks']:
        p=dest/task['id'];status=p/'task_status.json'
        r=json.loads(status.read_text()) if status.exists() else dict(status='MISSING',exit_status=None)
        if r.get('status')=='COMPLETE':
            try:
                if r.get('exit_status')!=0:raise ValueError('Success status has nonzero exit code')
                validate_task_outputs(p,task)
                if not r.get('outputs') or any(sha(p/name)!=h for name,h in r['outputs'].items()):raise ValueError('Recorded output hash mismatch')
            except (OSError,ValueError,KeyError) as e:r.update(status='INVALID_ARTIFACTS',reason=str(e))
        results.append(dict(task=task['id'],kind=task['kind'],**r))
    comparisons=[];issues=[]
    successful={r['task'] for r in results if r.get('status')=='COMPLETE'}
    for task in plan['tasks']:
        if task['kind']!='forecast' or task['id'] not in successful:continue
        p=dest/task['id']/'result/reports'
        try:
            gains=paired_scores(csvrows(p/'historical_reference_cells_INTERNAL.csv'),csvrows(p/'heldout_cells_INTERNAL.csv'))
            for row in gains:comparisons.append(dict(task=task['id'],pathogen=task['pathogen'],model=task['model'],origin=task['origin'],reference='historical_county_rate',**row))
        except (OSError,ValueError,KeyError) as e:issues.append(dict(task=task['id'],issue=str(e)))
    # County candidates are compared only within the same pathogen/origin.
    paired={}
    for task in plan['tasks']:
        if task['kind']=='forecast' and task['id'] in successful:paired.setdefault((task['pathogen'],task['origin']),{})[task['model']]=task
    for (pathogen,origin),models in paired.items():
        if set(models)!= {'spatial_county_time','iid_county_time'}:continue
        try:
            a=dest/models['iid_county_time']['id']/'result/reports/heldout_cells_INTERNAL.csv'
            b=dest/models['spatial_county_time']['id']/'result/reports/heldout_cells_INTERNAL.csv'
            for row in paired_scores(csvrows(a),csvrows(b)):comparisons.append(dict(task=models['spatial_county_time']['id'],pathogen=pathogen,model='spatial_county_time',origin=origin,reference='iid_county_time',**row))
        except (OSError,ValueError,KeyError) as e:issues.append(dict(pathogen=pathogen,origin=origin,issue=str(e)))
    if comparisons:
        with (dest/'paired_scores_INTERNAL.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
    summary=dict(tasks=results,comparison_issues=issues,execution_complete=all(r.get('status')=='COMPLETE' for r in results),
                 scientific_status='REVIEW_REQUIRED',note='Retrospective conditional hindcasts; no untouched validation or automatic dashboard promotion. Paired state/year score sums are descriptive; no independent-cell significance test.')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in sorted(dest.rglob('*')):
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.json','.csv','.txt','.log','.pdf','.r','.py','.sh'):
                t.add(str(p),arcname=str(p.relative_to(dest)),recursive=False)
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if summary['execution_complete'] and not issues else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
