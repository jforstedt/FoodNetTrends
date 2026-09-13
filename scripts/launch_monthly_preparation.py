#!/usr/bin/env python3
"""Prepare auditable monthly record inventories for two pathogens; never fit models."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile
from county_forecast_protocol import source_paths,validate_source

FILES=('launch_monthly_preparation.py','prepare_monthly_county.R','county_matching.R','reconcile_raw_county.R','fit_county_pilot.R','county_forecast_protocol.py')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

def prepare(root,dest,raw,clean,mapping,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();sources=source_paths(root)
    container=root/'foodnet.sif';inputs={};tasks=[];cache={}
    if verified:
        for p in (raw,clean,mapping,container):inputs[str(Path(p).resolve())]=sha(p)
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
    for n in FILES:shutil.copyfile(str(root/'scripts'/n),str(dest/'scripts'/n));inputs[str(dest/'scripts'/n)]=sha(dest/'scripts'/n)
    for pathogen in ('SALMONELLA','CAMPYLOBACTER'):
        source=sources[pathogen]
        if verified:
            source=validate_source(pathogen,source,hash_cache=cache)
            for p in (raw,clean,mapping):
                if str(Path(p).resolve()) not in source['input_md5']:raise ValueError('Requested file not established by raw/clean audit: '+str(p))
            inputs.update(source['evidence_sha256'])
            inputs[str(Path(source['audit'])/'county_panel_INTERNAL.rds')]=source['panel_sha256']
        cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/prepare_monthly_county.R'),str(raw),str(clean),str(mapping),source['audit'],str(dest/pathogen/'result'),pathogen]
        tasks.append(dict(id=pathogen,pathogen=pathogen,source=source,command=cmd))
    plan=dict(verified=verified,inputs=inputs,tasks=tasks,models_fitted=False,scientific_readiness='REVIEW_REQUIRED',calendar_certified=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote
    worker='python3 '+q(str(dest/'scripts/launch_monthly_preparation.py'))
    script='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n1) task=SALMONELLA;;\n2) task=CAMPYLOBACTER;;\n*) echo "Invalid task ID" >&2; exit 2;;\nesac\n'
    script+='exec '+worker+' --worker '+q(str(dest))+' --task "$task" --expected-plan-sha '+digest+'\n'
    (dest/'run.sh').write_text(script)
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+worker+' --collect '+q(str(dest))+' --expected-plan-sha '+digest+'\n')
    return plan

def verify(dest,plan,expected):
    if sha(dest/'plan.json')!=expected:raise ValueError('Plan changed after submission')
    if not plan.get('verified'):raise ValueError('Unverified preparation cannot execute')
    for p,h in plan['inputs'].items():
        if sha(p)!=h:raise ValueError('Changed input/source: '+p)

def validate_result(work):
    import csv
    out=work/'result';reports=out
    status=(reports/'status.txt').read_text().splitlines()
    if not status or status[0]!='MONTHLY_PREPARATION_COMPLETE':raise ValueError('Monthly preparation incomplete')
    required=('readiness.csv','state_month_records.csv','annual_reconciliation.csv','date_issues.csv','calendar_template.csv','input_checksums.csv')
    for n in required:
        if not(reports/n).is_file() or not(reports/n).stat().st_size:raise ValueError('Missing report '+n)
    if not(out/'candidate_monthly_INTERNAL.rds').is_file():raise ValueError('Missing candidate checkpoint')
    import math
    def read(name):
        with (reports/name).open(newline='') as f:return list(csv.DictReader(f))
    def number(row,key,integer=False):
        x=float(row[key])
        if not math.isfinite(x) or x<0 or (integer and x!=int(x)):raise ValueError('Invalid '+key)
        return x
    calendar=read('calendar_template.csv');monthly=read('state_month_records.csv');annual=read('annual_reconciliation.csv');ready=read('readiness.csv')
    states={'CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'}
    keys={(state,str(year),str(month)) for state in states for year in range(2004,2020) for month in range(1,13)}
    key=lambda row:(row['state'],row['year'],row['month'])
    for rows in (calendar,monthly):
        if len(rows)!=len(keys) or {key(r) for r in rows}!=keys:raise ValueError('Incomplete or duplicate monthly domain')
        if any(r['observation_status']!='UNVERIFIED' for r in rows):raise ValueError('Uncertified observation status changed')
    if any(r['observed_days'] or r['evidence_reference'] for r in calendar):raise ValueError('Unexpected calendar certification')
    if any(r['modeled_count'] for r in monthly):raise ValueError('Inventory incorrectly promoted to modeled counts')
    if len(ready)!=1 or ready[0]['pathogen']!=work.name or ready[0]['status']!='REVIEW_REQUIRED' or ready[0]['monthly_observation_verified']!='FALSE' or ready[0]['individual_linkage_validated']!='FALSE' or ready[0]['raw_clean_strata_match']!='TRUE' or ready[0]['candidate_rows']!='93312':raise ValueError('Unexpected readiness report')
    sums={}
    for r in monthly:
        k=(r['state'],r['year']);count,exposure=sums.get(k,(0,0))
        value=number(r,'candidate_person_years')
        if value<=0:raise ValueError('Nonpositive exposure')
        sums[k]=(count+number(r,'record_count',True),exposure+value)
    if len(annual)!=160 or {(r['state'],r['year']) for r in annual}!=set(sums):raise ValueError('Invalid annual domain')
    for r in annual:
        count,exposure=sums[(r['state'],r['year'])]
        if number(r,'annual_records',True)!=number(r,'assigned_records',True)+number(r,'unassigned_records',True) or count!=number(r,'assigned_records',True):raise ValueError('Annual counts do not reconcile')
        population=number(r,'population')
        if population<=0 or not math.isclose(exposure,population,rel_tol=1e-10,abs_tol=1e-7) or not math.isclose(number(r,'candidate_person_years'),population,rel_tol=1e-10,abs_tol=1e-7):raise ValueError('Annual exposure does not reconcile')
    return True

def run(dest,name,expected):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name)
    work=dest/name;work.mkdir(exist_ok=False);record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=expected)
    try:
        verify(dest,plan,expected);validate_source(task['pathogen'],task['source'])
        with (work/'task.log').open('w') as log:code=subprocess.run(task['command'],stdout=log,stderr=subprocess.STDOUT,cwd=str(dest)).returncode
        if code:raise ValueError('R preparation exited '+str(code))
        validate_result(work);verify(dest,plan,expected);validate_source(task['pathogen'],task['source'])
        record.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in (work/'result').rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:record['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']

def collect(dest,expected):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[]
    try:verify(dest,plan,expected)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for task in plan['tasks']:
        work=dest/task['id']
        try:
            r=json.loads((work/'task_status.json').read_text())
            if r.get('status')=='COMPLETE':
                if r.get('task')!=task['id'] or r.get('exit_status')!=0 or r.get('plan_sha256')!=expected:raise ValueError('Completion identity/code mismatch')
                validate_result(work)
                if not r.get('outputs') or any(sha(work/n)!=h for n,h in r['outputs'].items()):raise ValueError('Changed completed artifact')
        except (OSError,ValueError,KeyError) as e:r=dict(status='MISSING_OR_INVALID',reason=str(e))
        results.append(dict(task=task['id'],**{k:v for k,v in r.items() if k not in ('task','outputs')}))
    summary=dict(tasks=results,issues=issues,execution_complete=len(results)==2 and all(r['status']=='COMPLETE' for r in results) and not issues,
      models_fitted=False,calendar_certified=False,scientific_readiness='REVIEW_REQUIRED')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh')]
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files if p.name!='report_sha256.json'},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
        for p in files:
            if p.name!='report_sha256.json':archive.add(str(p),arcname=str(p.relative_to(dest)))
        archive.add(str(dest/'report_sha256.json'),arcname='report_sha256.json')
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if summary['execution_complete'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--expected-plan-sha');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if a.worker or a.collect:
        if not a.expected_plan_sha:p.error('Missing submitted plan hash')
        if a.worker:
            if not a.task:p.error('Missing task')
            return run(a.worker,a.task,a.expected_plan_sha)
        return collect(a.collect,a.expected_plan_sha)
    root=Path(__file__).resolve().parents[1]
    if not a.prepare_only:
        for tool in ('singularity','qsub'):
            if not shutil.which(tool):p.error('Missing '+tool)
    dest=root/'output'/('monthly_preparation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv';mapping=clean.with_name('clean_mmwr_preprocessing_report.csv')
    try:prepare(root,dest,Path('/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat'),clean,mapping,not a.prepare_only)
    except (OSError,ValueError,KeyError) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:print('Preparation only; no jobs submitted');return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    job=subprocess.check_output(base+['-N','foodnet_monthly','-t','1-2','-pe','smp','2','-l','h_rt=02:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip()
    import re
    match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise ValueError('Unexpected submission response; inspect queue before retry: '+job)
    (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Preparation array: '+job,flush=True)
    col=subprocess.check_output(base+['-N','foodnet_monthly_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=01:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n')
    print('Collector: '+col+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
