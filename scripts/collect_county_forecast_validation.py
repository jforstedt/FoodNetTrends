#!/usr/bin/env python3
"""Collect a fixed forecast experiment ledger, retaining failures and paired targets."""
import csv
import json
import hashlib
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
    dest=Path(dest);manifest=dest/'manifest.json';plan=json.loads(manifest.read_text());results=[];provenance_issues=[]
    tasks=plan.get('tasks',[])
    ids=[t.get('id') for t in tasks]
    if not tasks or len(set(ids))!=len(ids) or any(not isinstance(x,str) or not x or Path(x).name!=x or x in ('.','..') for x in ids):
        provenance_issues.append('Missing, duplicate or unsafe task inventory')
    if not plan.get('inputs_verified'):provenance_issues.append('Manifest inputs are unverified')
    if not isinstance(plan.get('fingerprints'),dict) or not plan.get('fingerprints'):provenance_issues.append('Missing shared source fingerprints')
    checked={}
    def check(path,digest):
        if path not in checked:checked[path]=sha(path)
        if checked[path]!=digest:raise ValueError('Source/input fingerprint mismatch: '+path)
    for task in tasks:
        p=dest/task['id'];status=p/'task_status.json'
        try:r=json.loads(status.read_text()) if status.exists() else dict(status='MISSING',exit_status=None)
        except (OSError,ValueError):r=dict(status='INVALID_ARTIFACTS',exit_status=None,reason='Unreadable task status')
        if r.get('status')=='COMPLETE':
            try:
                if provenance_issues:raise ValueError('; '.join(provenance_issues))
                if r.get('exit_status')!=0:raise ValueError('Success status has nonzero exit code')
                identity=hashlib.sha256(json.dumps(dict(task=task,fingerprints=plan['fingerprints']),sort_keys=True).encode()).hexdigest()
                if r.get('task_sha256')!=identity:raise ValueError('Task execution identity mismatch')
                for path,digest in dict(plan['fingerprints'],**task.get('input_fingerprints',{})).items():check(path,digest)
                if task['kind']=='forecast':
                    gate=json.loads((dest/'gate.json').read_text())
                    if gate.get('status')!='PASS' or gate.get('manifest_sha256')!=sha(manifest):raise ValueError('Forecast prerequisite gate revoked or changed')
                if any(Path(name).is_absolute() or '..' in Path(name).parts for name in r.get('outputs',{})):raise ValueError('Unsafe recorded output path')
                for name,digest in r.get('checkpoint_sha256',{}).items():
                    rel=Path(name)
                    if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower()!='.rds' or sha(p/rel)!=digest:raise ValueError('Checkpoint fingerprint mismatch')
                r['checkpoint_integrity_verified']=bool(r.get('checkpoint_sha256'))
                validate_task_outputs(p,task)
                if not r.get('outputs') or any(sha(p/name)!=h for name,h in r['outputs'].items()):raise ValueError('Recorded output hash mismatch')
            except (OSError,ValueError,KeyError) as e:r.update(status='INVALID_ARTIFACTS',reason=str(e))
        results.append(dict(task=task['id'],kind=task['kind'],**r))
    comparisons=[];issues=[dict(issue=x) for x in provenance_issues]
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
    summary=dict(tasks=results,comparison_issues=issues,execution_complete=bool(results) and all(r.get('status')=='COMPLETE' for r in results) and not issues,
                 scientific_status='REVIEW_REQUIRED',note='Retrospective conditional hindcasts; no untouched validation or automatic dashboard promotion. Paired state/year score sums are descriptive; no independent-cell significance test.')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in sorted(dest.rglob('*')):
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.json','.csv','.txt','.log','.pdf','.r','.py','.sh'):
                t.add(str(p),arcname=str(p.relative_to(dest)),recursive=False)
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if summary['execution_complete'] and not issues else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
