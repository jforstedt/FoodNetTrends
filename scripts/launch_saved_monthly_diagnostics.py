#!/usr/bin/env python3
"""Resample all twelve saved monthly fits in parallel; never refit."""
import argparse
from datetime import datetime
import hashlib
import json
import csv
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile

FILES=('launch_saved_monthly_diagnostics.py','audit_saved_monthly.R','audit_saved_forecast_sampling.R')
SOURCE='monthly_comparison_20260913_203209_481243'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

def rows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))

def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();source=root/'output'/SOURCE;container=root/'foodnet-inla-fixed.sif'
    inputs={};tasks=[]
    if verified:
        original=json.loads((source/'plan.json').read_text());digest=sha(source/'plan.json')
        if not original.get('verified') or original.get('version')!='monthly_comparison_v1' or len(original['tasks'])!=12:raise ValueError('Unexpected source comparison plan')
        inputs[str(source/'plan.json')]=digest;inputs[str(container)]=sha(container)
    else:original=dict(tasks=[dict(id='%s_%s_%s'%(p,c,v),pathogen=p,cutoff=c,seasonal=v=='seasonal') for p in ('SALMONELLA','CAMPYLOBACTER') for c in (2011,2013,2016) for v in ('reference','seasonal')])
    expected={(p,c,s) for p in ('SALMONELLA','CAMPYLOBACTER') for c in (2011,2013,2016) for s in (False,True)}
    if {(t['pathogen'],t['cutoff'],t['seasonal']) for t in original['tasks']}!=expected:raise ValueError('Source pairing differs')
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
    for n in FILES:
        target=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(target));inputs[str(target)]=sha(target)
    for i,t in enumerate(original['tasks']):
        name=t['id'];work=source/name
        if name!='%s_%s_%s'%(t['pathogen'],t['cutoff'],'seasonal' if t['seasonal'] else 'reference'):raise ValueError('Source task name mismatch')
        bound={};fit=work/'result/fit_INTERNAL.rds';pred=work/'result/county_month_predictions.csv'
        if verified:
            r=json.loads((work/'task_status.json').read_text())
            if r.get('task')!=name or r.get('plan_sha256')!=digest or r.get('status')!='EXPLORATORY_FIT_COMPLETE' or r.get('exit_status')!=0:raise ValueError('Unfinished or unbound source fit: '+name)
            for path in (fit,pred,work/'result/site_horizon_metrics.csv',work/'result/catchment_year_predictions.csv'):
                h=r['outputs'].get(str(path.relative_to(work)))
                if not h or sha(path)!=h:raise ValueError('Changed source artifact: '+str(path))
                bound[str(path)]=h
            bound[str(work/'task_status.json')]=sha(work/'task_status.json')
        seed=10000000+i*1000000
        cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/audit_saved_monthly.R'),str(fit),str(pred),str(t['cutoff']),'TRUE' if t['seasonal'] else 'FALSE',str(dest/name/'result'),str(seed)]
        tasks.append(dict(id=name,pathogen=t['pathogen'],cutoff=t['cutoff'],seasonal=t['seasonal'],seed=seed,inputs=bound,command=cmd))
    plan=dict(version='saved_monthly_diagnostics_v1',verified=verified,source=str(source),inputs=inputs,tasks=tasks,refitted=False,streams=4,draws_per_stream=2000,coverage_certified=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');h=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_saved_monthly_diagnostics.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) echo "Invalid array task" >&2; exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --plan-hash '+h+'\n'
    (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --plan-hash '+h+'\n');return plan

def verify(dest,plan,digest,task=None):
    if sha(dest/'plan.json')!=digest or not plan.get('verified') or plan.get('refitted') is not False:raise ValueError('Unverified or altered diagnostic plan')
    inputs=dict(plan['inputs'])
    for t in ([task] if task else plan['tasks']):inputs.update(t['inputs'])
    for p,h in inputs.items():
        if sha(p)!=h:raise ValueError('Changed saved input: '+p)

def validate_result(work,task):
    out=work/'result'
    if (out/'status.txt').read_text().strip()!='SAVED_MONTHLY_DIAGNOSTICS_COMPLETE':raise ValueError('Incomplete diagnostics')
    settings=rows(out/'settings.csv')
    if len(settings)!=1:raise ValueError('Missing settings')
    r=settings[0]
    if r['refitted']!='FALSE' or r['coverage_certified']!='FALSE' or int(r['cutoff'])!=task['cutoff'] or r['seasonal']!=('TRUE' if task['seasonal'] else 'FALSE') or int(r['base_seed'])!=task['seed'] or int(r['draws_per_stream'])!=2000 or int(r['streams'])!=4:raise ValueError('Diagnostic identity differs')
    scores=rows(out/'stream_scores.csv');tails=rows(out/'aggregate_tails.csv')
    states=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN');years=range(task['cutoff']+1,task['cutoff']+4)
    key=lambda r:(r['state'],int(r['year']),int(r['stream']))
    for data,ss in ((scores,states),(tails,states+('ALL',))):
        expected={(s,y,k) for s in ss for y in years for k in range(5)}
        if len(data)!=len(expected) or {key(r) for r in data}!=expected:raise ValueError('Incomplete diagnostic domain')
        if any(int(r['draws'])!=(8000 if int(r['stream'])==0 else 2000) for r in data):raise ValueError('Unexpected draw count')
    for r in scores:
        if not math.isfinite(float(r['mean_log_score'])) or not math.isfinite(float(r['max_cell_density_relative_mcse'])):raise ValueError('Invalid score diagnostics')
    for r in tails:
        for k in ('mean_expected','median_expected','p975_expected','max_expected','top_one_percent_mean_share','lower95','upper95'):
            if not math.isfinite(float(r[k])):raise ValueError('Nonfinite tail diagnostics')
        if not 0<=float(r['top_one_percent_mean_share'])<=1:raise ValueError('Invalid tail share')
    for n in ('aggregate_draws_INTERNAL.rds','pooled_cell_scores.csv','shape_streams.csv','input_checksums.csv','latent_sd_by_site_year.csv'):
        if not(out/n).is_file() or not(out/n).stat().st_size:raise ValueError('Missing '+n)

def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name)
    work=dest/name;work.mkdir(exist_ok=False);r=dict(task=name,plan_sha256=digest,status='FAILED',exit_status=1)
    try:
        verify(dest,plan,digest,task)
        with (work/'task.log').open('w') as log:rc=subprocess.call(task['command'],stdout=log,stderr=subprocess.STDOUT)
        if rc:raise ValueError('R diagnostic exit '+str(rc))
        for path in task['inputs']:
            if Path(path).name in ('site_horizon_metrics.csv','catchment_year_predictions.csv'):shutil.copyfile(path,str(work/'result'/('original_'+Path(path).name)))
        validate_result(work,task);verify(dest,plan,digest,task)
        r.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in (work/'result').rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(r,indent=2)+'\n');return r['exit_status']

def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[];scores=[];tails=[]
    try:verify(dest,plan,digest)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for task in plan['tasks']:
        work=dest/task['id']
        try:
            r=json.loads((work/'task_status.json').read_text())
            if r.get('status')!='COMPLETE' or r.get('task')!=task['id'] or r.get('plan_sha256')!=digest or r.get('exit_status')!=0:raise ValueError(r.get('reason','Missing completion identity'))
            validate_result(work,task)
            if not r.get('outputs') or any(sha(work/n)!=h for n,h in r['outputs'].items()):raise ValueError('Completed diagnostics changed')
            for name,target in (('stream_scores.csv',scores),('aggregate_tails.csv',tails)):
                target.extend(dict(task=task['id'],pathogen=task['pathogen'],cutoff=task['cutoff'],seasonal=task['seasonal'],**x) for x in rows(work/'result'/name))
            results.append(dict(task=task['id'],status='COMPLETE'))
        except (OSError,ValueError,KeyError) as e:results.append(dict(task=task['id'],status='FAILED_OR_MISSING',reason=str(e)))
    def write(name,data):
        if data:
            with (dest/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write('all_stream_scores.csv',scores);write('all_aggregate_tails.csv',tails)
    pairs=[];indexed={(r['pathogen'],r['cutoff'],r['state'],r['year'],r['stream'],r['seasonal']):r for r in scores}
    for (p,c,s,y,k,seasonal),r in indexed.items():
        b=indexed.get((p,c,s,y,k,True))
        if seasonal or not b:continue
        pairs.append(dict(pathogen=p,cutoff=c,state=s,year=y,stream=k,log_score_seasonal_minus_reference=float(b['mean_log_score'])-float(r['mean_log_score'])))
    write('paired_stream_scores.csv',pairs)
    grouped={}
    for r in pairs:grouped.setdefault((r['pathogen'],r['cutoff'],r['year'],r['stream']),[]).append(r)
    equal_site=[]
    for (pathogen,cutoff,year,stream),rs in grouped.items():
        if len(rs)==10:equal_site.append(dict(pathogen=pathogen,cutoff=cutoff,year=year,stream=stream,sites=10,log_score_seasonal_minus_reference=sum(r['log_score_seasonal_minus_reference'] for r in rs)/10))
    write('paired_equal_site_stream_scores.csv',equal_site)
    summary=dict(tasks=results,issues=issues,execution_complete=len(results)==12 and all(r['status']=='COMPLETE' for r in results) and not issues,refitted=False,accepted=False)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.r','.py','.sh','.log','.txt') and p.name!='report_sha256.json']
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in files+[dest/'report_sha256.json']:t.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--plan-hash');a=p.parse_args()
    if a.worker or a.collect:
        if not a.plan_hash or (a.worker and not a.task):p.error('Missing task/hash')
        return worker(a.worker,a.task,a.plan_hash) if a.worker else collect(a.collect,a.plan_hash)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('saved_monthly_diagnostics_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Missing '+tool)
    try:prepare(root,dest,not a.prepare_only)
    except (OSError,ValueError,KeyError) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    job=subprocess.check_output(base+['-N','foodnet_monthly_diag','-t','1-12','-pe','smp','2','-l','h_rt=24:00:00,h_rss=32768M,mem_free=32768M,h_vmem=48G','-o',str(dest),str(dest/'run.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Sampling array: '+job,flush=True)
    match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise ValueError('Unrecognized qsub output; inspect queue before retry')
    col=subprocess.check_output(base+['-N','foodnet_monthly_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n')
    print('Collector: '+col+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
