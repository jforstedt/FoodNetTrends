#!/usr/bin/env python3
"""Inspect matched saved Campylobacter 2011 fits concurrently; no fitting or sampling."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tarfile

SOURCE='next_phase_recovery_20260913_163836_142708'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

def prepare(root,source,dest,verified=True):
    root=Path(root);source=Path(source);dest=Path(dest)
    container=root/'foodnet-inla-fixed.sif'
    plan_source=json.loads((source/'plan.json').read_text()) if verified else None
    summaries=json.loads((source/'summary.json').read_text()) if verified else None
    tasks=[];inputs={}
    if verified:
        if not plan_source.get('verified'):raise ValueError('Source plan not verified')
        for p in (source/'plan.json',source/'summary.json',container):inputs[str(p)]=sha(p)
    for variant in ('spatial','iid'):
        name='spline_CAMPYLOBACTER_2011_'+variant;work=source/name;fit=work/'result/fit_INTERNAL.rds'
        if verified:
            task=next(t for t in plan_source['tasks'] if t['id']==name)
            if (task['kind'],task['pathogen'],task['origin'],task['variant'])!=('spline','CAMPYLOBACTER',2011,variant):raise ValueError('Source task identity mismatch')
            record=json.loads((work/'task_status.json').read_text())
            if record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or not any(t['task']==name and t['status']=='COMPLETE' for t in summaries['tasks']):raise ValueError('Source task incomplete')
            for n,h in record['outputs'].items():
                if sha(work/n)!=h:raise ValueError('Source output changed')
            for p in (fit,work/'task_status.json',work/'task.log'):inputs[str(p)]=sha(p)
            for n,h in record.get('checkpoint_sha256',{}).items():
                if sha(work/n)!=h:raise ValueError('Checkpoint changed since completion')
        tasks.append(dict(id=variant,fit=str(fit),log=str(work/'task.log'),variant=variant))
    dest.mkdir(parents=True,exist_ok=False)
    for n in ('inspect_saved_spline.R','launch_saved_spline_inspection.py'):shutil.copyfile(str(root/'scripts'/n),str(dest/n));inputs[str(dest/n)]=sha(dest/n)
    plan=dict(verified=verified,inputs=inputs,tasks=tasks,container=str(container),source=str(source),models_fitted=False,posterior_sampling=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    q=shlex.quote
    (dest/'run.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(dest/'launch_saved_spline_inspection.py'))+' --worker '+q(str(dest))+' --expected-plan-sha '+sha(dest/'plan.json')+'\n')
    return plan

def run(dest,expected_plan_sha):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[]
    def verify():
        if sha(dest/'plan.json')!=expected_plan_sha:raise ValueError('Plan changed since submission')
        if not plan['verified']:raise ValueError('Unverified plan cannot execute')
        for p,h in plan['inputs'].items():
            if sha(p)!=h:raise ValueError('Source/checkpoint changed: '+p)
    def task(t):
        work=dest/t['id'];work.mkdir(exist_ok=False)
        cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',plan['container'],'Rscript','--vanilla',str(dest/'inspect_saved_spline.R'),t['fit'],str(work/'reports'),t['variant'],'2011']
        with (work/'inspection.log').open('w') as log:code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
        shutil.copyfile(t['log'],str(work/'original_fit.log'))
        marker=work/'reports/status.txt'
        lines=marker.read_text().splitlines() if marker.is_file() else []
        if code==0 and (not lines or lines[0]!='SAVED_SPLINE_INSPECTION_COMPLETE'):code=1
        return dict(task=t['id'],exit_status=code,status='COMPLETE' if code==0 else 'FAILED')
    try:
        verify()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(task,plan['tasks']))
        verify()
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:issues.append(str(e))
    summary=dict(tasks=results,issues=issues,execution_complete=len(results)==2 and all(t['exit_status']==0 for t in results) and not issues,scientific_status='REVIEW_REQUIRED',models_fitted=False,posterior_sampling=False)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.txt','.log','.json','.r','.py','.sh')]
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in files+[dest/'report_sha256.json']:t.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if summary['execution_complete'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker');p.add_argument('--expected-plan-sha');p.add_argument('--prepare-only',action='store_true');p.add_argument('--source-run',default=SOURCE);a=p.parse_args()
    if a.worker:
        if not a.expected_plan_sha:p.error('Missing submitted plan identity')
        return run(a.worker,a.expected_plan_sha)
    root=Path(__file__).resolve().parents[1];source=Path(a.source_run);source=source if source.is_absolute() else root/'output'/source
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Missing '+tool)
    dest=root/'output'/('saved_spline_inspection_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:prepare(root,source,dest,not a.prepare_only)
    except (OSError,ValueError,KeyError,StopIteration) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:print('Preparation only; no job submitted');return 0
    cmd=['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_spline_inspect','-pe','smp','2','-l','h_rt=02:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-j','y','-o',str(dest/'launcher.log'),str(dest/'run.sh')]
    job=subprocess.check_output(cmd,universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(job=job))+'\n')
    print('Inspection job: '+job+'\nLog: '+str(dest/'launcher.log')+'\nArchive: '+str(dest)+'.tar.gz')
    return 0
if __name__=='__main__':sys.exit(main())
