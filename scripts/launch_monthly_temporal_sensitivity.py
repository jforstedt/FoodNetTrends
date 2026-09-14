#!/usr/bin/env python3
"""Six new tighter-temporal-prior fits; reuse six saved seasonal references."""
import argparse
from datetime import datetime
import json
import csv
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from launch_monthly_comparison import source_contract
from launch_saved_monthly_diagnostics import sha,rows,validate_result as validate_sampling

BASELINE='saved_monthly_diagnostics_20260913_205110_899575'
FILES=('launch_monthly_temporal_sensitivity.py','launch_monthly_comparison.py','launch_saved_monthly_diagnostics.py','run_monthly_temporal_sensitivity.R','run_monthly_comparison.R','monthly_seasonal_model.R','county_forecast_model.R','fit_county_pilot.R','county_forecast_protocol.py','audit_saved_monthly.R','audit_saved_forecast_sampling.R')

def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();baseline=root/'output'/BASELINE;container=root/'foodnet-inla-fixed.sif';inputs={};sources={}
    if verified:
        old=json.loads((baseline/'plan.json').read_text());old_hash=sha(baseline/'plan.json')
        if old.get('version')!='saved_monthly_diagnostics_v1' or not old.get('verified') or old.get('refitted') is not False:raise ValueError('Unexpected baseline diagnostics')
        inputs[str(baseline/'plan.json')]=old_hash;inputs[str(container)]=sha(container)
    for pathogen in ('SALMONELLA','CAMPYLOBACTER'):
        if verified:
            sources[pathogen]=source_contract(root,pathogen);inputs.update(sources[pathogen]['hashes'])
        else:sources[pathogen]=dict(candidate='UNVERIFIED',audit='UNVERIFIED')
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
    for n in FILES:
        target=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(target));inputs[str(target)]=sha(target)
    tasks=[]
    for pathogen in ('SALMONELLA','CAMPYLOBACTER'):
        for cutoff in (2011,2013,2016):
            name='%s_%s_seasonal'%(pathogen,cutoff);source=baseline/name;truth='UNVERIFIED';bound={}
            if verified:
                original=next(t for t in old['tasks'] if t['id']==name)
                if (original['pathogen'],original['cutoff'],original['seasonal'])!=(pathogen,cutoff,True):raise ValueError('Baseline identity differs')
                record=json.loads((source/'task_status.json').read_text())
                if record.get('task')!=name or record.get('plan_sha256')!=old_hash or record.get('status')!='COMPLETE' or record.get('exit_status')!=0:raise ValueError('Incomplete baseline task')
                validate_sampling(source,original)
                for f in ('stream_scores.csv','aggregate_tails.csv','pooled_cell_scores.csv','settings.csv'):
                    path=source/'result'/f;h=record['outputs'].get('result/'+f)
                    if not h or sha(path)!=h:raise ValueError('Baseline result changed')
                    bound[str(path)]=h
                bound[str(source/'task_status.json')]=sha(source/'task_status.json')
                candidates=[p for p in original['inputs'] if p.endswith('/result/county_month_predictions.csv')]
                if len(candidates)!=1:raise ValueError('Baseline truth not uniquely bound')
                truth=candidates[0]
                if sha(truth)!=original['inputs'][truth]:raise ValueError('Baseline truth changed')
                bound[truth]=original['inputs'][truth]
            seed=40000000+len(tasks)*1000000
            cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_temporal_sensitivity.R'),sources[pathogen]['candidate'],sources[pathogen]['audit'],str(cutoff),str(dest/name/'result'),str(seed)]
            tasks.append(dict(id=name,pathogen=pathogen,cutoff=cutoff,seasonal=True,seed=seed,inputs=bound,baseline=str(source/'result'),baseline_truth=truth,command=cmd))
    plan=dict(version='monthly_temporal_prior_sensitivity_v1',verified=verified,inputs=inputs,tasks=tasks,new_fits=6,reference_fits_reused=6,trend_sd_upper=.25,reference_trend_sd_upper=.5,pc_tail=.01,draws=8000,coverage_certified=False,decision='Exploratory sensitivity; no automatic promotion')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');h=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_monthly_temporal_sensitivity.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) echo "Invalid array task" >&2; exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --plan-hash '+h+'\n'
    (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --plan-hash '+h+'\n');return plan

def verify(dest,plan,digest,task=None):
    if sha(dest/'plan.json')!=digest or not plan.get('verified') or plan.get('trend_sd_upper')!=.25 or plan.get('reference_trend_sd_upper')!=.5:raise ValueError('Unverified or altered sensitivity plan')
    bound=dict(plan['inputs'])
    for t in ([task] if task else plan['tasks']):bound.update(t['inputs'])
    for p,h in bound.items():
        if sha(p)!=h:raise ValueError('Changed sensitivity input: '+p)

def validate(work,task):
    validate_sampling(work,task)
    r=rows(work/'result/sensitivity_settings.csv')
    if len(r)!=1 or r[0]['new_fit']!='TRUE' or float(r[0]['trend_sd_upper'])!=.25 or float(r[0]['reference_trend_sd_upper'])!=.5 or r[0]['seasonal']!='TRUE':raise ValueError('Wrong sensitivity setting')
    if not(work/'fit_INTERNAL.rds').is_file():raise ValueError('Missing new checkpoint')
    key=lambda r:(r['fips'],r['state'],r['year'],r['month'])
    new=rows(work/'heldout_truth_INTERNAL.csv');old=rows(task['baseline_truth'])
    if len(new)!=17496 or len(old)!=17496 or len({key(r) for r in new})!=17496 or {key(r):float(r['observed']) for r in new}!={key(r):float(r['observed']) for r in old}:raise ValueError('Paired heldout observations differ')
    if re.search(r'vb[.]correction[^\n]*aborted', (work/'task.log').read_text(errors='replace'),re.I):raise ValueError('Aborted VB correction')

def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False)
    r=dict(task=name,plan_sha256=digest,status='FAILED',exit_status=1)
    try:
        verify(dest,plan,digest,t)
        with (work/'task.log').open('w') as log:rc=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
        if rc:raise ValueError('R exit '+str(rc))
        validate(work,t);verify(dest,plan,digest,t)
        r.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(r,indent=2)+'\n');return r['exit_status']

def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[];scores=[];tails=[]
    try:verify(dest,plan,digest)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for t in plan['tasks']:
        work=dest/t['id']
        try:
            r=json.loads((work/'task_status.json').read_text())
            if r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('task')!=t['id'] or r.get('plan_sha256')!=digest:raise ValueError(r.get('reason','Incomplete task'))
            validate(work,t)
            if not r.get('outputs') or any(sha(work/n)!=h for n,h in r['outputs'].items()):raise ValueError('Changed completed output')
            for name,target in (('stream_scores.csv',scores),('aggregate_tails.csv',tails)):
                for variant,folder in (('tight',work/'result'),('reference',Path(t['baseline']))):
                    target.extend(dict(task=t['id'],pathogen=t['pathogen'],cutoff=t['cutoff'],variant=variant,**x) for x in rows(folder/name))
            results.append(dict(task=t['id'],status='COMPLETE'))
        except (OSError,ValueError,KeyError) as e:results.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e)))
    def write(name,data):
        if data:
            with (dest/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write('all_stream_scores.csv',scores);write('all_aggregate_tails.csv',tails)
    idx={(r['task'],r['state'],r['year'],r['stream'],r['variant']):r for r in scores};paired=[]
    for (task,state,year,stream,variant),r in idx.items():
        b=idx.get((task,state,year,stream,'reference'))
        if variant!='tight' or not b:continue
        paired.append(dict(task=task,pathogen=r['pathogen'],cutoff=r['cutoff'],state=state,year=year,stream=stream,log_score_tight_minus_reference=float(r['mean_log_score'])-float(b['mean_log_score'])))
    write('paired_site_stream_scores.csv',paired);groups={}
    for r in paired:groups.setdefault((r['pathogen'],r['cutoff'],r['year'],r['stream']),[]).append(r)
    equal=[]
    for (p,c,y,s),rs in groups.items():
        if len(rs)==10:equal.append(dict(pathogen=p,cutoff=c,year=y,stream=s,sites=10,log_score_tight_minus_reference=sum(r['log_score_tight_minus_reference'] for r in rs)/10))
    write('paired_equal_site_scores.csv',equal)
    summary=dict(tasks=results,issues=issues,execution_complete=len(results)==6 and all(r['status']=='COMPLETE' for r in results) and not issues,accepted=False,reference_fits_reused=True)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.json','.csv','.r','.py','.txt','.sh','.log') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in files+[dest/'report_sha256.json']:t.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--plan-hash');a=p.parse_args()
    if a.worker or a.collect:
        if not a.plan_hash or (a.worker and not a.task):p.error('Missing task/hash')
        return worker(a.worker,a.task,a.plan_hash) if a.worker else collect(a.collect,a.plan_hash)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_temporal_sensitivity_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Missing '+tool)
    try:prepare(root,dest,not a.prepare_only)
    except (OSError,ValueError,KeyError,StopIteration) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    job=subprocess.check_output(base+['-N','foodnet_monthly_prior','-t','1-6','-pe','smp','4','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-o',str(dest),str(dest/'run.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Fit/sampling array: '+job,flush=True)
    match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise ValueError('Unrecognized qsub output; inspect queue before retry')
    col=subprocess.check_output(base+['-N','foodnet_monthly_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n')
    print('Collector: '+col+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
