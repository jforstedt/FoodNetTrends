#!/usr/bin/env python3
"""Recover scoring from saved expansion fits and isolate one numerical retry."""
import sys
sys.dont_write_bytecode=True
import argparse
from datetime import datetime
import csv
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import regional_audit_runtime as base
import launch_covariate_expansion as expansion
from validate_covariate_reports import validate_reports

VERSION='covariate_expansion_recovery_v1'
NUMERICAL='VIBRIO_rw1_2016_local0_weatherlag01_age0'
FILES=('launch_covariate_recovery.py','launch_covariate_expansion.py','regional_audit_runtime.py',
       'rebase_covariate_features.py','validate_covariate_reports.py','prepare_covariate_expansion.R',
       'run_covariate_expansion.R','rescore_covariate_expansion.R')

def seed(index):
    if not 0<=index<187:raise ValueError('Recovery index outside frozen scope')
    return 600000000+index*1000000

def classify(t,log):
    if t['task_id']==NUMERICAL:
        if not re.search(r'vb[.]correction[^\n]*aborted',log,re.I) or 'Local seasonal fit failed numerical gate' not in log:raise ValueError('Unexpected numerical failure')
        return 'refit_once_single_thread'
    if 'Invalid sampling settings' not in log or t['seed']<=1000000000 or re.search(r'vb[.]correction[^\n]*aborted',log,re.I):raise ValueError('Not a verified sampling-only failure')
    return 'saved_fit_rescore'

def verify(dest,p,digest):
    if base.sha(dest/'plan.json')!=digest or p.get('version')!=VERSION or p.get('scientific_acceptance') is not False:raise ValueError('Changed recovery plan')
    if len(p['tasks'])!=187 or len(p['references'])!=173:raise ValueError('Wrong recovery scope')
    if sum(e['mode']=='saved_fit_rescore' for e in p['tasks'])!=186 or sum(e['mode']=='refit_once_single_thread' for e in p['tasks'])!=1:raise ValueError('Wrong recovery modes')
    for i,e in enumerate(p['tasks']):
        if e['task']['seed']!=seed(i) or e['task']['seed']>1e9:raise ValueError('Invalid recovery seed')
        if (e['mode']=='refit_once_single_thread')!=(e['task']['task_id']==NUMERICAL):raise ValueError('Unexpected refit')
    base.check(p['bindings']);image=Path(p['container'])
    if dict(size=image.stat().st_size,mtime_ns=image.stat().st_mtime_ns)!=p['container_stat']:raise ValueError('Runtime changed')

def copy_reports(source,target,outputs):
    if target.exists():raise ValueError('Refusing existing reference directory')
    copied={}
    for n,h in outputs.items():
        if not n.startswith('reports/') or '_INTERNAL' in n:continue
        expansion.safe_outputs(source,{n:h});path=target/n;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(str(source/n),str(path));copied[n]=h
    return copied

def prepare(dest,digest):
    if (dest/'plan.json').exists() or (dest/'submission.json').exists():raise ValueError('Refusing prepared recovery directory')
    base.check({str(dest/'bootstrap.json'):digest});boot=base.read(dest/'bootstrap.json');bundle=dest/'bundle'
    base.check({str(bundle/'manifest.json'):boot['bundle_sha256']});manifest=base.read(bundle/'manifest.json')
    members=set(FILES)|{'source_receipt.json','protocol.md'}
    if set(manifest['files'])!=members or {p.name for p in bundle.iterdir() if p.is_file() and p.name!='manifest.json'}!=members:raise ValueError('Changed recovery snapshot')
    bindings={str(bundle/n):h for n,h in manifest['files'].items()};base.check(bindings)
    receipt=base.read(bundle/'source_receipt.json');source=Path(boot['root'])/'output'/receipt['source_run']
    for n,h in receipt['files'].items():base.check({str(source/n):h})
    old=base.read(source/'plan.json');summary=base.read(source/'summary.json')
    expansion.verify(source,old,receipt['files']['plan.json'])
    if summary.get('complete')!=173 or summary.get('expected')!=360 or summary.get('issues'):raise ValueError('Unexpected source completion')
    if base.sha(old['container'])!=old['container_sha256']:raise ValueError('Source runtime differs')
    bindings.update(old['bindings']);bindings[str(source/'plan.json')]=receipt['files']['plan.json']
    bindings[str(source/'summary.json')]=receipt['files']['summary.json']
    states={r['task']:r for r in summary['tasks']};tasks=[];references=[]
    print('Preserving 173 completed results; verifying saved checkpoints for scoring recovery',flush=True)
    for entry in old['tasks']:
        original=entry['task'];name=original['task_id'];work=Path(original['output']);status=base.read(work/'task_status.json')
        base.check(entry['inputs']);base.check({entry['task_json']:entry['task_sha256']})
        if status.get('task')!=name or status.get('plan_sha256')!=receipt['files']['plan.json']:raise ValueError('Worker identity differs')
        if states[name]['status']=='COMPLETE':
            if status.get('status')!='COMPLETE' or status.get('exit_status')!=0:raise ValueError('Completion mismatch')
            truth=validate_reports(work,original)
            if truth!=status['truth_sha256']:raise ValueError('Completed truth mismatch')
            target=dest/'references'/name
            copied=copy_reports(work,target,status['outputs'])
            references.append(dict(task=original,work=str(target),outputs=copied,truth_sha256=truth))
            continue
        if status.get('status')!='FAILED' or status.get('exit_status')!=1:raise ValueError('Unexpected failed worker')
        mode=classify(original,(work/'task.log').read_text(errors='replace'))
        effective=dict(original,seed=seed(len(tasks)),output=str(dest/name))
        consumed=dict(entry['inputs']);consumed[entry['task_json']]=entry['task_sha256']
        consumed[str(work/'task_status.json')]=receipt['files'][name+'/task_status.json']
        consumed[str(work/'task.log')]=base.sha(work/'task.log')
        if mode=='saved_fit_rescore':
            for n in ('fit_INTERNAL.rds','heldout_truth_INTERNAL.csv'):
                path=work/n
                if not path.is_file() or path.is_symlink():raise ValueError('Missing or unsafe checkpoint '+name)
                consumed[str(path)]=base.sha(path)
            job=dict(source_task=entry['task_json'],fit=str(work/'fit_INTERNAL.rds'),truth=str(work/'heldout_truth_INTERNAL.csv'),
                     seed=effective['seed'],output=effective['output'],source_scripts=original['source_scripts'])
        else:
            # Deterministic, single-thread numerical retry of the same model;
            # do not replace priors, likelihood or numerical acceptance gates.
            effective['threads']=1;job=effective
        path=dest/(name+'.json');base.write(path,job)
        tasks.append(dict(task=effective,source_task=original,task_json=str(path),task_sha256=base.sha(path),mode=mode,inputs=consumed))
    for r in old['reused']:
        work=Path(r['work']);expansion.safe_outputs(work,r['outputs'])
        target=dest/'references'/r['task']['task_id'];copied=copy_reports(work,target,r['outputs'])
        references.append(dict(task=r['task'],work=str(target),outputs=copied,truth_sha256=r['truth_sha256']))
    plan=dict(version=VERSION,tasks=tasks,references=references,bindings=bindings,container=old['container'],container_sha256=old['container_sha256'],
              container_stat=old['container_stat'],scientific_acceptance=False,independent_validation=False)
    base.write(dest/'plan.json',plan);pd=base.sha(dest/'plan.json');verify(dest,plan,pd)
    for name,mode in [('run.sh','--worker'),('collect.sh','--collect')]:
        index=' --index "${SGE_TASK_ID:?}"' if mode=='--worker' else ''
        (dest/name).write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+shlex.quote(str(bundle/'launch_covariate_recovery.py'))+' '+mode+' '+shlex.quote(str(dest))+' --digest '+pd+index+'\n')
    # SGE accepts one contiguous task range. All tasks can run concurrently;
    # the numerical retry uses one fitting thread within its two-slot request.
    job=base.submit(dest/'run.sh','foodnet_cov_recover',dest/'array.log',(2,'h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G'),('-t','1-187'))
    ledger={'array':job};base.write(dest/'submission.json',ledger);hold=job.split('.')[0]
    ledger['collector']=base.submit(dest/'collect.sh','foodnet_cov_collect',dest/'collection.log',(1,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'),('-hold_jid',hold))
    base.write(dest/'submission.json',ledger);print(ledger,flush=True)

def validate(work,e):
    truth=validate_reports(work,e['task'],require_fit=e['mode']=='refit_once_single_thread')
    settings=base.read(work/'reports/experiment_settings.json')
    if (settings.get('new_fit')!=(e['mode']=='refit_once_single_thread') or settings.get('threads')!=e['task']['threads']
        or settings.get('expansion_version')!=expansion.VERSION or settings.get('end_year')!=e['task']['end_year']):raise ValueError('Wrong recovery fit/settings identity')
    if e['mode']=='saved_fit_rescore':
        m=base.read(work/'reports/sampling_recovery.json')
        if (m.get('source_task')!=e['source_task'] or m.get('refitted') is not False or m.get('new_seed')!=e['task']['seed']
            or m.get('version')!='county_covariate_rescore_v1' or m.get('status')!='COVARIATE_EXPANSION_RESCORE_COMPLETE'
            or m.get('original_fit_unchanged') is not True):raise ValueError('Wrong saved-fit recovery identity')
    return truth

def worker(dest,index,digest):
    p=base.read(dest/'plan.json');e=p['tasks'][index-1];t=e['task'];work=Path(t['output']);work.mkdir(exist_ok=False)
    record=dict(task=t['task_id'],mode=e['mode'],status='FAILED',exit_status=1,plan_sha256=digest)
    try:
        verify(dest,p,digest);base.check(e['inputs']);base.check({e['task_json']:e['task_sha256']})
        script='rescore_covariate_expansion.R' if e['mode']=='saved_fit_rescore' else 'run_covariate_expansion.R'
        with (work/'task.log').open('w') as log:
            code=subprocess.call(base.runtime_command(p['container'],dest/'bundle'/script,e['task_json']),stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('Recovery R exited '+str(code))
        truth=validate(work,e);base.check(e['inputs']);verify(dest,p,digest)
        record.update(status='COMPLETE',exit_status=0,truth_sha256=truth,outputs={str(x.relative_to(work)):base.sha(x) for x in work.rglob('*') if x.is_file()})
    except (OSError,ValueError,KeyError) as ex:record['reason']=str(ex)
    base.write(work/'task_status.json',record);return record['exit_status']

def collect(dest,digest):
    p=base.read(dest/'plan.json');records=[];issues=[];scores=[];tails=[];truths={}
    try:
        verify(dest,p,digest)
        if base.sha(p['container'])!=p['container_sha256']:raise ValueError('Runtime content differs')
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for e in p['tasks']+p['references']:
        t=e['task'];reference='work' in e;work=Path(e['work'] if reference else t['output']);r=dict(task=t['task_id'],status='FAILED_OR_MISSING',reused=reference)
        try:
            if issues:raise ValueError('Global integrity failure')
            if reference:expansion.safe_outputs(work,e['outputs']);truth=e['truth_sha256']
            else:
                status=base.read(work/'task_status.json')
                if status.get('status')!='COMPLETE' or status.get('task')!=t['task_id'] or status.get('plan_sha256')!=digest or status.get('exit_status')!=0:raise ValueError(status.get('reason','Incomplete recovery'))
                expansion.safe_outputs(work,status['outputs'],complete=True);base.check(e['inputs']);base.check({e['task_json']:e['task_sha256']})
                truth=validate(work,e)
                if truth!=status['truth_sha256']:raise ValueError('Changed truth')
            key=(t['pathogen'],t['cutoff'])
            if key in truths and truths[key]!=truth:raise ValueError('Paired truth mismatch')
            truths[key]=truth;identity={k:t[k] for k in ('task_id','pathogen','temporal','cutoff','local_seasonality','weather','weather_window','age')}
            scores.extend(dict(identity,**row) for row in expansion.rows(work/'reports/stream_scores.csv'))
            tails.extend(dict(identity,**row) for row in expansion.rows(work/'reports/aggregate_tails.csv'));r['status']='COMPLETE'
        except (OSError,ValueError,KeyError) as ex:r['reason']=str(ex)
        records.append(r)
    contrasts,missing=expansion.paired_contrasts(scores);base.write(dest/'incomplete_paired_blocks.json',missing)
    for name,data in [('all_stream_scores.csv',scores),('all_aggregate_tails.csv',tails),('paired_log_score_contrasts.csv',contrasts)]:
        if data:
            with (dest/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    complete=sum(r['status']=='COMPLETE' for r in records)
    base.write(dest/'summary.json',dict(version=VERSION,tasks=records,issues=issues,complete=complete,expected=360,rescored_fits=186,numerical_retries=1,preserved_results=173,scientific_acceptance=False,independent_validation=False))
    base.archive(dest);print('Complete %d/360'%complete,flush=True);return 0 if complete==360 and not issues else 1

def launch(root):
    root=Path(root).resolve()
    if any(not shutil.which(x) for x in ('qsub','singularity')):raise ValueError('Load singularity on SGE host')
    dest=root/'output'/('county_covariate_recovery_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));bundle=dest/'bundle';bundle.mkdir(parents=True)
    for n in FILES:shutil.copyfile(str(root/'scripts'/n),str(bundle/n))
    shutil.copyfile(str(root/'analysis_configs/covariate_expansion_recovery_source.json'),str(bundle/'source_receipt.json'))
    shutil.copyfile(str(root/'docs/covariate_expansion_recovery.md'),str(bundle/'protocol.md'))
    base.write(bundle/'manifest.json',dict(files={p.name:base.sha(p) for p in bundle.iterdir()}))
    base.write(dest/'bootstrap.json',dict(root=str(root),bundle_sha256=base.sha(bundle/'manifest.json')));h=base.sha(dest/'bootstrap.json')
    (dest/'prepare.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+shlex.quote(str(bundle/'launch_covariate_recovery.py'))+' --prepare '+shlex.quote(str(dest))+' --digest '+h+'\n')
    job=base.submit(dest/'prepare.sh','foodnet_cov_recover',dest/'preparation.log',(2,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'))
    base.write(dest/'preparation_submission.json',dict(job=job));print('Preparation job: '+job+'\nLog: '+str(dest/'preparation.log')+'\nArchive: '+str(dest)+'.tar.gz',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    for n in ('prepare','worker','collect','digest'):p.add_argument('--'+n)
    p.add_argument('--index',type=int);a=p.parse_args()
    if a.prepare:
        dest=Path(a.prepare)
        try:prepare(dest,a.digest);return 0
        except Exception as ex:base.write(dest/'preparation_failure.json',dict(error=str(ex)));base.archive(dest);raise
    if a.worker:
        if a.index is None or not 1<=a.index<=187 or not a.digest:p.error('Index1..187 and digest required')
        return worker(Path(a.worker),a.index,a.digest)
    if a.collect:return collect(Path(a.collect),a.digest)
    launch(a.root);return 0
if __name__=='__main__':sys.exit(main())
