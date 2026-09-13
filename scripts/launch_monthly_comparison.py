#!/usr/bin/env python3
"""Launch paired exploratory monthly hindcasts; no accepted outputs are modified."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from county_forecast_protocol import validate_source

FILES=('launch_monthly_comparison.py','run_monthly_comparison.R','monthly_seasonal_model.R','county_forecast_model.R','fit_county_pilot.R','county_forecast_protocol.py')
SOURCES={'SALMONELLA':'monthly_preparation_20260913_173130_111239','CAMPYLOBACTER':'monthly_preparation_20260913_172157_051362'}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

def rows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))

def source_contract(root,pathogen):
    base=root/'output'/SOURCES[pathogen];work=base/pathogen
    plan=json.loads((base/'plan.json').read_text());record=json.loads((work/'task_status.json').read_text())
    if not plan.get('verified') or record.get('task')!=pathogen or record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=sha(base/'plan.json'):raise ValueError('Monthly source identity failed: '+pathogen)
    task=next(t for t in plan['tasks'] if t['id']==pathogen)
    evidence=validate_source(pathogen,task['source'])
    hashes={str(base/'plan.json'):sha(base/'plan.json'),str(work/'task_status.json'):sha(work/'task_status.json')}
    hashes.update(evidence['evidence_sha256'])
    for n,h in plan['inputs'].items():
        if sha(n)!=h:raise ValueError('Monthly preparation input changed: '+n)
        hashes[n]=h
    for n,h in record['outputs'].items():
        path=work/n
        if sha(path)!=h:raise ValueError('Monthly preparation artifact changed: '+str(path))
        hashes[str(path)]=h
    candidate=work/'result/candidate_monthly_INTERNAL.rds'
    if str(candidate) not in hashes:raise ValueError('Unbound monthly checkpoint')
    readiness=rows(work/'result/readiness.csv')
    if len(readiness)!=1 or readiness[0]['pathogen']!=pathogen or readiness[0]['raw_clean_strata_match']!='TRUE' or readiness[0]['monthly_observation_verified']!='FALSE':raise ValueError('Unexpected readiness contract')
    issues=rows(work/'result/date_issues.csv')
    if not issues or any(float(r[k])!=0 for r in issues for k in ('unassigned_records','missing_specimen_date','specimen_year_disagreement','month_missing_invalid')):raise ValueError('Unresolved date assignment')
    calendar=rows(work/'result/calendar_template.csv')
    expected={(s,str(y),str(m)) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for y in range(2004,2020) for m in range(1,13)}
    if len(calendar)!=1920 or {(r['state'],r['year'],r['month']) for r in calendar}!=expected or any(r['observation_status']!='UNVERIFIED' for r in calendar):raise ValueError('Invalid candidate calendar')
    return dict(candidate=str(candidate),audit=evidence['audit'],hashes=hashes)

def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();container=root/'foodnet-inla-fixed.sif'
    sources={};inputs={}
    for pathogen in SOURCES:
        if verified:
            sources[pathogen]=source_contract(root,pathogen);inputs.update(sources[pathogen]['hashes'])
        else:sources[pathogen]=dict(candidate=str(root/'output'/SOURCES[pathogen]/pathogen/'result/candidate_monthly_INTERNAL.rds'),audit='UNVERIFIED')
    if verified:inputs[str(container)]=sha(container)
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
    for name in FILES:
        target=dest/'scripts'/name;shutil.copyfile(str(root/'scripts'/name),str(target));inputs[str(target)]=sha(target)
    tasks=[]
    for pathogen in SOURCES:
        for cutoff in (2011,2013,2016):
            for seasonal in (False,True):
                name='%s_%s_%s'%(pathogen,cutoff,'seasonal' if seasonal else 'reference')
                seed=400000+len(tasks)*100000
                command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_comparison.R'),sources[pathogen]['candidate'],sources[pathogen]['audit'],str(cutoff),'TRUE' if seasonal else 'FALSE',str(dest/name/'result'),str(seed)]
                tasks.append(dict(id=name,pathogen=pathogen,cutoff=cutoff,seasonal=seasonal,seed=seed,command=command))
    plan=dict(version='monthly_comparison_v1',verified=verified,inputs=inputs,tasks=tasks,
      coverage='EXPLORATORY_ASSUMED_CONTINUOUS',coverage_certified=False,event_month='specimen',
      exposure='annual population times calendar-day fraction; realized future exposure',
      origins=[2011,2013,2016],horizons_months=[12,24,36],draws=1000,
      priors=dict(rate_center=.0002,intercept_sd=1,county_sd_bound=1,trend_sd_bound=.5,seasonal_sd_bound=.5,pc_tail=.01,log_size_mean=2.995732273553991,log_size_sd=1),
      weights='equal counties within site; equal sites within pathogen/horizon; origins reported separately',
      promotion='none; exploratory results require statistical review',threads=4)
    calendar=[]
    for pathogen in SOURCES:
        for state in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'):
            for year in range(2004,2020):
                for month in range(1,13):calendar.append(dict(pathogen=pathogen,state=state,year=year,month=month,coverage='EXPLORATORY_ASSUMED_CONTINUOUS',certified=False,exceptions='No interruption ledger supplied; continuity assumed, not verified'))
    with (dest/'coverage_assumption.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(calendar[0]));w.writeheader();w.writerows(calendar)
    inputs[str(dest/'coverage_assumption.csv')]=sha(dest/'coverage_assumption.csv')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote
    base='python3 '+q(str(dest/'scripts/launch_monthly_comparison.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) echo "Invalid array task" >&2; exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --plan-hash '+digest+'\n'
    (dest/'run.sh').write_text(shell)
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --plan-hash '+digest+'\n')
    return plan

def verify(dest,plan,digest):
    if sha(dest/'plan.json')!=digest or not plan.get('verified'):raise ValueError('Unverified or altered plan')
    if plan.get('coverage')!='EXPLORATORY_ASSUMED_CONTINUOUS' or plan.get('coverage_certified') is not False:raise ValueError('Coverage assumption changed')
    for n,h in plan['inputs'].items():
        if sha(n)!=h:raise ValueError('Changed input: '+n)

def validate_result(work,task):
    out=work/'result'
    if (out/'status.txt').read_text().strip()!='EXPLORATORY_FIT_COMPLETE':raise ValueError('Incomplete R result')
    ready=rows(out/'readiness.csv')
    if len(ready)!=1 or ready[0]['coverage']!='EXPLORATORY_ASSUMED_CONTINUOUS' or ready[0]['coverage_certified']!='FALSE' or int(ready[0]['cutoff'])!=task['cutoff'] or ready[0]['seasonal']!=('TRUE' if task['seasonal'] else 'FALSE') or int(ready[0]['heldout_cells'])!=17496 or int(ready[0]['draws'])!=1000:raise ValueError('Result identity mismatch')
    for name in ('fit_INTERNAL.rds','draws_INTERNAL.rds','county_month_predictions.csv','site_horizon_metrics.csv','site_month_predictions.csv','site_year_predictions.csv','catchment_month_predictions.csv','catchment_year_predictions.csv','hyperparameters.csv'):
        if not(out/name).is_file() or not(out/name).stat().st_size:raise ValueError('Missing result: '+name)
    if task['seasonal'] and len(rows(out/'seasonal_effect.csv'))!=12:raise ValueError('Incomplete seasonal curve')
    log=(work/'task.log').read_text(errors='replace')
    if re.search(r'vb[.]correction[^\n]*aborted|maximum number of tries has been reached',log,re.I):raise ValueError('INLA numerical warning requires review')
    metrics=rows(out/'site_horizon_metrics.csv')
    expected={(s,str(h)) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for h in (1,2,3)}
    if len(metrics)!=30 or {(r['state'],r['horizon_year']) for r in metrics}!=expected:raise ValueError('Incomplete metrics')
    if any(not math.isfinite(float(r[k])) for r in metrics for k in ('log_score','log_score_stream_difference','interval_score95','coverage95','coverage50','absolute_error')):raise ValueError('Nonfinite metrics')

def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name)
    work=dest/name;work.mkdir(exist_ok=False);status=dict(task=name,plan_sha256=digest,status='FAILED',exit_status=1)
    try:
        verify(dest,plan,digest)
        with (work/'task.log').open('w') as log:code=subprocess.call(task['command'],stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('R exit '+str(code))
        validate_result(work,task);verify(dest,plan,digest)
        status.update(status='EXPLORATORY_FIT_COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in (work/'result').rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError) as e:status['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(status,indent=2)+'\n');return status['exit_status']

def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[];metrics=[]
    try:verify(dest,plan,digest)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for task in plan['tasks']:
        work=dest/task['id']
        try:
            r=json.loads((work/'task_status.json').read_text())
            if r.get('status')!='EXPLORATORY_FIT_COMPLETE' or r.get('task')!=task['id'] or r.get('exit_status')!=0 or r.get('plan_sha256')!=digest:raise ValueError(r.get('reason','Incomplete task identity'))
            validate_result(work,task)
            if not r.get('outputs') or any(sha(work/n)!=h for n,h in r['outputs'].items()):raise ValueError('Changed completed result')
            metrics.extend(dict(task=task['id'],pathogen=task['pathogen'],cutoff=task['cutoff'],seasonal=task['seasonal'],**row) for row in rows(work/'result/site_horizon_metrics.csv'))
            results.append(dict(task=task['id'],status='EXPLORATORY_FIT_COMPLETE'))
        except (OSError,ValueError,KeyError) as e:results.append(dict(task=task['id'],status='FAILED_OR_MISSING',reason=str(e)))
    if metrics:
        with (dest/'all_site_metrics.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
    paired=[]
    metric_keys=('log_score','interval_score95','coverage95','coverage50','absolute_error')
    indexed={(r['pathogen'],r['cutoff'],r['state'],r['horizon_year'],r['seasonal']):r for r in metrics}
    for (pathogen,cutoff,state,horizon,seasonal),r in indexed.items():
        other=indexed.get((pathogen,cutoff,state,horizon,True))
        if seasonal or other is None:continue
        pair=dict(pathogen=pathogen,cutoff=cutoff,state=state,horizon_year=horizon)
        pair.update({k+'_seasonal_minus_reference':float(other[k])-float(r[k]) for k in metric_keys});paired.append(pair)
    if paired:
        with (dest/'paired_site_metrics.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
        groups={}
        for r in paired:groups.setdefault((r['pathogen'],r['cutoff'],r['horizon_year']),[]).append(r)
        catchment=[]
        for (pathogen,cutoff,horizon),rs in groups.items():
            if len(rs)!=10:continue
            r=dict(pathogen=pathogen,cutoff=cutoff,horizon_year=horizon,sites=10)
            r.update({k+'_seasonal_minus_reference':sum(x[k+'_seasonal_minus_reference'] for x in rs)/10 for k in metric_keys});catchment.append(r)
        if catchment:
            with (dest/'paired_equal_site_metrics.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(catchment[0]));w.writeheader();w.writerows(catchment)
    summary=dict(tasks=results,issues=issues,execution_complete=len(results)==12 and all(r['status']=='EXPLORATORY_FIT_COMPLETE' for r in results) and not issues,coverage_certified=False,accepted=False)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.log','.txt','.py','.r','.sh') and p.name!='report_sha256.json']
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in files+[dest/'report_sha256.json']:t.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--plan-hash');a=p.parse_args()
    if a.worker or a.collect:
        if not a.plan_hash or (a.worker and not a.task):p.error('Missing plan hash or worker task')
        return worker(a.worker,a.task,a.plan_hash) if a.worker else collect(a.collect,a.plan_hash)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_comparison_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load module: '+tool)
    try:prepare(root,dest,not a.prepare_only)
    except (OSError,ValueError,KeyError,StopIteration) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    job=subprocess.check_output(base+['-N','foodnet_monthly_fit','-t','1-12','-pe','smp','4','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-o',str(dest),str(dest/'run.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Fit array: '+job,flush=True)
    match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise ValueError('Unrecognized qsub response; inspect queue before retry')
    col=subprocess.check_output(base+['-N','foodnet_monthly_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n')
    print('Collector: '+col+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
