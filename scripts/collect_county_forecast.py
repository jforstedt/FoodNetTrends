#!/usr/bin/env python3
"""Compare retrospective held-out scores and archive internal reports."""
import csv
import json
import math
from pathlib import Path
import statistics
import sys
import tarfile

NAMES=('spatial_baseline','iid_baseline','spatial_county_time','iid_county_time')
def read_csv(path):
    with path.open() as handle:return list(csv.DictReader(handle))
def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def compare(dest):
    data={};splits=[];panels=[]
    for name in NAMES:
        report=dest/name/'reports';rows=read_csv(report/'heldout_cells_INTERNAL.csv')
        keys=[(r['fips'],r['state'],r['year']) for r in rows]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate forecast keys')
        data[name]=dict(zip(keys,rows))
        split=read_csv(report/'split.csv')[0]
        if split['heldout_counts_masked'].lower()!='true' or int(split['heldout_cells'])!=len(rows):raise ValueError('Invalid masking/split record')
        if int(split['train_end'])>=int(split['test_start']) or any(not int(split['test_start'])<=int(r['year'])<=int(split['test_end']) for r in rows):raise ValueError('Invalid forecast years')
        splits.append(tuple(split[k] for k in ('train_start','train_end','test_start','test_end','training_cells','heldout_cells','draws','heldout_counts_masked')))
        panels.append(read_csv(report/'panel_checksum.csv')[0]['md5'])
    if len(set(splits))!=1 or len(set(panels))!=1:raise ValueError('Forecast splits/panels differ')
    pairs=(('spatial_baseline','spatial_county_time'),('iid_baseline','iid_county_time'),('iid_baseline','spatial_baseline'),('iid_county_time','spatial_county_time'))
    comparisons=[]
    for reference,candidate in pairs:
        a=data[reference];b=data[candidate]
        if set(a)!=set(b):raise ValueError('Forecast keys differ')
        for k in a:
            if any(a[k][f]!=b[k][f] for f in ('observed','population','training_cases_band')):raise ValueError('Forecast truth or strata differ')
        for grouping in ('overall','state','year','training_cases_band'):
            groups={}
            for key,row in a.items():groups.setdefault('all' if grouping=='overall' else row[grouping],[]).append(key)
            for group,keys in sorted(groups.items()):
                delta=[float(b[k]['log_predictive_density'])-float(a[k]['log_predictive_density']) for k in keys]
                if not all(math.isfinite(x) for x in delta):raise ValueError('Nonfinite comparison')
                comparisons.append(dict(reference=reference,candidate=candidate,grouping=grouping,group=group,cells=len(keys),
                    log_score_gain=sum(delta),naive_paired_se=math.sqrt(len(delta)*statistics.variance(delta)) if len(delta)>1 else '',
                    zero_brier_change=sum(float(b[k]['zero_brier'])-float(a[k]['zero_brier']) for k in keys)/len(keys)))
    write_csv(dest/'paired_forecast_comparison_INTERNAL.csv',comparisons)
    overview=[]
    for name in NAMES:
        for row in read_csv(dest/name/'reports/heldout_scores_INTERNAL.csv'):
            if row['grouping']=='overall':overview.append(dict(model=name,**row))
    write_csv(dest/'forecast_overview.csv',overview)

def collect(dest):
    dest=Path(dest);results=[]
    for name in NAMES:
        r=dest/name/'reports'
        status=(r/'status.txt').read_text().splitlines()[0] if (r/'status.txt').is_file() else 'MISSING'
        code=(r/'exit_status.txt').read_text().strip() if (r/'exit_status.txt').is_file() else 'MISSING'
        results.append(dict(model=name,status=status,exit_status=code))
    ok=all(r['status']=='FORECAST_CHECK_COMPLETE' and r['exit_status']=='0' for r in results);error=None
    if ok:
        try:compare(dest)
        except Exception as exc:ok=False;error=str(exc)
    if not ok:
        for filename in ('paired_forecast_comparison_INTERNAL.csv','forecast_overview.csv'):
            if (dest/filename).exists():(dest/filename).unlink()
    (dest/'summary.json').write_text(json.dumps(dict(models=results,complete=ok,comparison_error=error),indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
        for name in NAMES:
            for f in (dest/name/'reports',dest/(name+'.log')):
                if f.exists():archive.add(str(f),arcname=str(f.relative_to(dest)))
        for name in ('summary.json','manifest.json','forecast_overview.csv','paired_forecast_comparison_INTERNAL.csv','county_forecast_check.R','county_sensitivity.R','fit_county_pilot.R','diagnose_saved_county_pilot.R','collect_county_forecast.py','fit.sh','collect.sh'):
            f=dest/name
            if f.exists():archive.add(str(f),arcname=name)
    print((dest/'summary.json').read_text());print('Archive: '+str(dest)+'.tar.gz')
    return 0 if ok else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
