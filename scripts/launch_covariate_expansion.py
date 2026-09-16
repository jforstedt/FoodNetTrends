#!/usr/bin/env python3
"""Visible SGE preparation, 288 independent extension fits, 72 frozen references."""
import sys
sys.dont_write_bytecode=True
import argparse
import csv
from datetime import datetime
import importlib.util
from pathlib import Path
import shlex
import shutil
import subprocess
import regional_audit_runtime as base
from rebase_covariate_features import prepare as rebase_features

VERSION='county_covariate_expansion_v1'
PILOT='county_covariate_experiment_20260915_113139_060588'
MONTHLY='monthly_expansion_20260913_223222_865377'
SHIGELLA='monthly_shigella_recovery_20260914_012243_682311'
REFERENCES={'CRYPTOSPORIDIUM':('ar1',),'CYCLOSPORA':('ar1',),'LISTERIA':('ar1',),
            'SHIGELLA':('ar1',),'STEC':('rw1',),'VIBRIO':('rw1',),'YERSINIA':('rw1','ar1')}
FILES=('launch_covariate_expansion.py','regional_audit_runtime.py','rebase_covariate_features.py',
       'prepare_covariate_expansion.R','run_covariate_expansion.R')

def matrix():
    tasks=[]
    for pathogen,models in REFERENCES.items():
        end=2017 if pathogen=='CRYPTOSPORIDIUM' else 2019
        for temporal in models:
            for cutoff in ((2011,2013,2014) if end==2017 else (2011,2013,2016)):
                for local in (False,True):
                    for window in ('off','current','lag01'):
                        for age in (False,True):
                            tasks.append(dict(task_id='%s_%s_%s_local%d_weather%s_age%d'%(pathogen,temporal,cutoff,local,window,age),
                                pathogen=pathogen,temporal=temporal,cutoff=cutoff,end_year=end,local_seasonality=local,
                                weather=window!='off',weather_window='current' if window=='off' else window,age=age,
                                seed=900000000+len(tasks)*1000000,threads=4,draws_per_stream=1000,expansion_version=VERSION))
    return tasks

def legacy(path):
    spec=importlib.util.spec_from_file_location('frozen_covariate_validator',str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def rows(path):
    with Path(path).open() as f:return list(csv.DictReader(f))

def paired_contrasts(scores):
    """Only complete, matched factorial blocks; absent arms never become zeros."""
    grouped={};result=[];incomplete=[]
    for r in scores:
        key=tuple(r[k] for k in ('pathogen','temporal','cutoff','state','year','stream'))
        arm=(r['local_seasonality'],r['weather_window'] if r['weather'] else 'off',r['age'])
        if arm in grouped.setdefault(key,{}):raise ValueError('Duplicate paired score arm')
        grouped[key][arm]=float(r['mean_log_score'])
    expected={(l,w,a) for l in (False,True) for w in ('off','current','lag01') for a in (False,True)}
    for key,arms in grouped.items():
        identity=dict(zip(('pathogen','temporal','cutoff','state','year','stream'),key))
        if set(arms)!=expected:
            incomplete.append(dict(identity,available_arms=len(arms)));continue
        def add(name,local,window,age,value):
            result.append(dict(identity,contrast=name,local_seasonality=local,weather_window=window,age=age,log_score_difference=value))
        for l in (False,True):
            for w in ('off','current','lag01'):
                add('age_on_minus_off',l,w,'paired',arms[l,w,True]-arms[l,w,False])
            for w in ('current','lag01'):
                for a in (False,True):add('weather_on_minus_off',l,w,a,arms[l,w,a]-arms[l,'off',a])
                add('age_weather_difference_in_differences',l,w,'paired',arms[l,w,True]-arms[l,w,False]-arms[l,'off',True]+arms[l,'off',False])
            for a in (False,True):add('lag01_minus_current',l,'paired',a,arms[l,'lag01',a]-arms[l,'current',a])
        for w in ('off','current','lag01'):
            for a in (False,True):add('local_on_minus_off','paired',w,a,arms[True,w,a]-arms[False,w,a])
            add('local_age_difference_in_differences','paired',w,'paired',
                arms[True,w,True]-arms[True,w,False]-arms[False,w,True]+arms[False,w,False])
        for w in ('current','lag01'):
            for a in (False,True):
                add('local_weather_difference_in_differences','paired',w,a,
                    arms[True,w,a]-arms[True,'off',a]-arms[False,w,a]+arms[False,'off',a])
            for l in (False,True):
                add('combined_minus_neither',l,w,'paired',arms[l,w,True]-arms[l,'off',False])
            add('local_age_weather_three_way_difference','paired',w,'paired',
                (arms[True,w,True]-arms[True,w,False]-arms[True,'off',True]+arms[True,'off',False])
                -(arms[False,w,True]-arms[False,w,False]-arms[False,'off',True]+arms[False,'off',False]))
    return result,incomplete

def safe_outputs(work,outputs,complete=False):
    if not outputs:raise ValueError('Missing output bindings')
    for name,h in outputs.items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name:raise ValueError('Unsafe output path')
        base.check({str(work/p):h})
    if complete:
        actual={str(p.relative_to(work)) for p in work.rglob('*') if p.is_file() and p.name!='task_status.json'}
        if set(outputs)!=actual:raise ValueError('Incomplete output manifest')

def package_check(dest,boot):
    bundle=dest/'bundle';base.check({str(bundle/'manifest.json'):boot['bundle_sha256']})
    m=base.read(bundle/'manifest.json')
    expected=set(FILES)|{'source_receipt.json','protocol.md'}
    actual={p.name for p in bundle.iterdir() if p.is_file() and p.name!='manifest.json'}
    if m.get('version')!=VERSION or set(m['files'])!=expected or actual!=expected:raise ValueError('Wrong source snapshot')
    bindings={str(bundle/n):h for n,h in m['files'].items()};base.check(bindings);return bindings

def prepare(dest,digest):
    base.check({str(dest/'bootstrap.json'):digest});boot=base.read(dest/'bootstrap.json')
    bindings=package_check(dest,boot);root=Path(boot['root']);bundle=dest/'bundle'
    receipt=base.read(bundle/'source_receipt.json')['runs']
    source=root/'output'/PILOT;mh=receipt[MONTHLY]['plan.json']
    for run,names in receipt.items():
        for name,h in names.items():
            if name in ('plan.json','expansion.json','summary.json'):base.check({str(root/'output'/run/name):h})
    old=base.read(source/'plan.json');summary=base.read(source/'summary.json')
    base.verify(source,old,receipt[PILOT]['plan.json'])
    if summary.get('complete')!=72 or summary.get('expected')!=72 or summary.get('issues'):raise ValueError('Incomplete pilot')
    if base.sha(old['container'])!=old['container_sha256']:raise ValueError('Pilot runtime changed')
    validator_path=source/'bundle/scripts/launch_county_covariate_experiment.py'
    if str(validator_path) not in old['bindings']:raise ValueError('Unbound source validator')
    validator=legacy(validator_path)
    # Only common consumed runtime/code bindings go to every worker. Each task
    # separately binds its own source panel and covariate files.
    bindings.update({p:h for p,h in old['bindings'].items() if '/bundle/scripts/' in p or '/r_library/' in p or p==str(source/'prior_check.json')})
    bindings[str(source/'plan.json')]=receipt[PILOT]['plan.json']
    reused=[]
    print('Verifying and copying 72 completed pilot reports; no pilot refits',flush=True)
    for entry in old['tasks']:
        t=entry['task'];work=source/t['task_id'];status=work/'task_status.json'
        base.check({str(status):receipt[PILOT][t['task_id']+'/task_status.json']})
        r=base.read(status)
        if r.get('status')!='COMPLETE' or r.get('plan_sha256')!=receipt[PILOT]['plan.json'] or r.get('task')!=t['task_id'] or r.get('exit_status')!=0:raise ValueError('Pilot completion differs')
        if validator.validate(work,t)!=r['truth_sha256']:raise ValueError('Pilot truth changed')
        copied={};target=dest/'reused'/t['task_id'];target.mkdir(parents=True)
        for name,h in r['outputs'].items():
            if not name.startswith('reports/') or '_INTERNAL' in name:continue
            safe_outputs(work,{name:h});out=target/name;out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(str(work/name),str(out));copied[name]=h
        reused.append(dict(task=t,work=str(target),outputs=copied,truth_sha256=r['truth_sha256'],source_worker_sha256=base.sha(status)))
    monthly=root/'output'/MONTHLY;mp=base.read(monthly/'plan.json')
    if mp.get('verified') is not True:raise ValueError('Unverified monthly source')
    # The reviewed exception changes the source-month gate only; specimen dates
    # and all original input rules stay frozen.
    decision=base.read(root/'output'/SHIGELLA/'expansion.json')
    if decision.get('month_decision')!='SHIGELLA_SPECIMEN_20260913' or decision.get('preparation_sha256')!=mh:raise ValueError('Missing reviewed Shigella date decision')
    mapping={}
    for pathogen in REFERENCES:
        pt=next(t for t in mp['tasks'] if t['id']==pathogen);work=monthly/pathogen
        status=work/'task_status.json';h=receipt[MONTHLY][pathogen+'/task_status.json'];base.check({str(status):h})
        record=base.read(status)
        if record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=mh or record.get('task')!=pathogen:raise ValueError('Failed monthly source '+pathogen)
        safe_outputs(work,record['outputs'])
        if any(float(r['unassigned_records'])!=0 for r in rows(work/'result/annual_reconciliation.csv')):raise ValueError('Unassigned dates '+pathogen)
        if pathogen!='SHIGELLA' and any(float(r['month_disagreement'])!=0 for r in rows(work/'result/date_issues.csv')):raise ValueError('Unreviewed date disagreement '+pathogen)
        candidate=work/'result/candidate_monthly_INTERNAL.rds';audit=pt['source']['audit']
        consumed={p:h for p,h in mp['inputs'].items() if p.startswith(audit+'/')}
        consumed[str(candidate)]=record['outputs']['result/candidate_monthly_INTERNAL.rds']
        consumed[str(status)]=h
        if str(Path(audit)/'county_panel_INTERNAL.rds') not in consumed:raise ValueError('Unbound annual panel')
        base.check(consumed);mapping[pathogen]=(str(candidate),audit,consumed)
    print('Preparing earlier-cutoff public features for Cryptosporidium',flush=True)
    for window in ('current','lag01'):
        src=source/'bundle/weather'/window/'2016'
        rebase_features(src/'weather_experiment.csv',src/'manifest.json',2014,dest/'features'/window/'2014')
    tasks=[]
    for t in matrix():
        candidate,audit,consumed=mapping[t['pathogen']]
        feature=(dest/'features' if t['cutoff']==2014 else source/'bundle/weather')/t['weather_window']/str(t['cutoff'])
        t.update(candidate=candidate,audit=audit,weather_features=str(feature/'weather_experiment.csv'),weather_manifest=str(feature/'manifest.json'),
            source_scripts=str(source/'bundle/scripts'),prior_check=str(source/'prior_check.json'),output=str(dest/t['task_id']))
        inputs=dict(consumed)
        for p in (t['weather_features'],t['weather_manifest']):inputs[p]=base.sha(p)
        taskpath=dest/(t['task_id']+'.json');base.write(taskpath,t)
        tasks.append(dict(task=t,task_json=str(taskpath),task_sha256=base.sha(taskpath),inputs=inputs))
    checks=[]
    for pathogen in REFERENCES:
        path=dest/(pathogen+'_preflight.json');base.write(path,[e['task'] for e in tasks if e['task']['pathogen']==pathogen])
        bindings[str(path)]=base.sha(path);checks.append(dict(pathogen=pathogen,path=str(path)))
    plan=dict(version=VERSION,tasks=tasks,reused=reused,preflights=checks,bindings=bindings,container=old['container'],
        container_sha256=old['container_sha256'],container_stat=old['container_stat'],validator=str(validator_path),
        mode='historical_conditional',new_fits=288,reused_fits=72,scientific_acceptance=False,independent_validation=False)
    base.write(dest/'plan.json',plan);pd=base.sha(dest/'plan.json');verify(dest,plan,pd)
    for filename,mode in [('preflight.sh','--preflight'),('run.sh','--worker'),('collect.sh','--collect')]:
        index=' --index "${SGE_TASK_ID:?}"' if mode!='--collect' else ''
        (dest/filename).write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+shlex.quote(str(bundle/'launch_covariate_expansion.py'))+' '+mode+' '+shlex.quote(str(dest))+' --digest '+pd+index+'\n')
    ledger={}
    prep=base.submit(dest/'preflight.sh','foodnet_cov_inputs',dest/'input_array.log',(2,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'),('-t','1-7'))
    ledger['input_array']=prep;base.write(dest/'submission.json',ledger)
    fits=base.submit(dest/'run.sh','foodnet_cov_expand',dest/'array.log',(4,'h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G'),('-t','1-288','-hold_jid',prep.split('.')[0]))
    ledger['fit_array']=fits;base.write(dest/'submission.json',ledger)
    collector=base.submit(dest/'collect.sh','foodnet_cov_collect',dest/'collection.log',(1,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'),('-hold_jid',fits.split('.')[0]))
    ledger['collector']=collector;base.write(dest/'submission.json',ledger);print(ledger,flush=True)

def verify(dest,p,digest):
    if base.sha(dest/'plan.json')!=digest or p.get('version')!=VERSION or p.get('scientific_acceptance') is not False or p.get('mode')!='historical_conditional':raise ValueError('Changed expansion plan')
    if len(p['tasks'])!=288 or len(p['reused'])!=72:raise ValueError('Wrong experiment size')
    for entry,t in zip(p['tasks'],matrix()):
        if any(entry['task'].get(k)!=v for k,v in t.items()):raise ValueError('Changed task matrix')
    base.check(p['bindings']);container=Path(p['container'])
    if dict(size=container.stat().st_size,mtime_ns=container.stat().st_mtime_ns)!=p['container_stat']:raise ValueError('Runtime snapshot changed')

def preflight(dest,index,digest):
    p=base.read(dest/'plan.json');verify(dest,p,digest);item=p['preflights'][index-1];pathogen=item['pathogen']
    status=dict(pathogen=pathogen,status='FAILED',plan_sha256=digest)
    try:
        entries=[e for e in p['tasks'] if e['task']['pathogen']==pathogen]
        bindings={k:h for e in entries for k,h in e['inputs'].items()};base.check(bindings)
        report=dest/(pathogen+'_readiness.json')
        with (dest/(pathogen+'_preflight.log')).open('w') as log:
            code=subprocess.call(base.runtime_command(p['container'],dest/'bundle/prepare_covariate_expansion.R',item['path'],report),stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('Input preflight exited '+str(code))
        r=base.read(report)
        if r.get('status')!='COVARIATE_EXPANSION_INPUT_PASS' or r.get('pathogen')!=pathogen:raise ValueError('Wrong readiness report')
        base.check(bindings);verify(dest,p,digest)
        status.update(status='COMPLETE',readiness_sha256=base.sha(report))
    except (OSError,ValueError,KeyError) as e:status['reason']=str(e)
    base.write(dest/(pathogen+'_preflight_status.json'),status);return 0 if status['status']=='COMPLETE' else 1

def worker(dest,index,digest):
    p=base.read(dest/'plan.json');entry=p['tasks'][index-1];t=entry['task'];work=Path(t['output']);work.mkdir(exist_ok=False)
    result=dict(task=t['task_id'],status='FAILED',exit_status=1,plan_sha256=digest)
    try:
        verify(dest,p,digest);base.check(entry['inputs']);base.check({entry['task_json']:entry['task_sha256']})
        status=base.read(dest/(t['pathogen']+'_preflight_status.json'))
        if status.get('status')!='COMPLETE' or status.get('plan_sha256')!=digest:raise ValueError('Pathogen input gate did not pass')
        base.check({str(dest/(t['pathogen']+'_readiness.json')):status['readiness_sha256']})
        with (work/'task.log').open('w') as log:
            code=subprocess.call(base.runtime_command(p['container'],dest/'bundle/run_covariate_expansion.R',entry['task_json']),stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('R worker exited '+str(code))
        truth=legacy(p['validator']).validate(work,t)
        settings=base.read(work/'reports/experiment_settings.json')
        if settings.get('expansion_version')!=VERSION or settings.get('end_year')!=t['end_year']:raise ValueError('Expansion identity differs')
        base.check(entry['inputs']);verify(dest,p,digest)
        result.update(status='COMPLETE',exit_status=0,truth_sha256=truth,outputs={str(x.relative_to(work)):base.sha(x) for x in work.rglob('*') if x.is_file()})
    except (OSError,ValueError,KeyError) as e:result['reason']=str(e)
    base.write(work/'task_status.json',result);return result['exit_status']

def collect(dest,digest):
    p=base.read(dest/'plan.json');records=[];issues=[];scores=[];tails=[];truths={}
    try:
        verify(dest,p,digest)
        if base.sha(p['container'])!=p['container_sha256']:raise ValueError('Runtime content changed')
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    validator=legacy(p['validator']) if not issues else None
    for entry in p['tasks']+p['reused']:
        t=entry['task'];reused='work' in entry;work=Path(entry['work'] if reused else t['output']);r=dict(task=t['task_id'],reused=reused,status='FAILED_OR_MISSING')
        try:
            if issues:raise ValueError('Global integrity failure')
            if reused:
                safe_outputs(work,entry['outputs']);truth=entry['truth_sha256']
            else:
                status=base.read(work/'task_status.json')
                if status.get('status')!='COMPLETE' or status.get('exit_status')!=0 or status.get('plan_sha256')!=digest or status.get('task')!=t['task_id']:raise ValueError(status.get('reason','Incomplete task'))
                safe_outputs(work,status['outputs'],complete=True);base.check(entry['inputs']);base.check({entry['task_json']:entry['task_sha256']})
                truth=validator.validate(work,t)
                if truth!=status['truth_sha256']:raise ValueError('Changed truth')
            key=(t['pathogen'],t['cutoff'])
            if key in truths and truths[key]!=truth:raise ValueError('Paired truth mismatch')
            truths[key]=truth
            common={k:t[k] for k in ('task_id','pathogen','cutoff','temporal','local_seasonality','weather','age','weather_window')}
            scores.extend(dict(common,**x) for x in rows(work/'reports/stream_scores.csv'))
            tails.extend(dict(common,**x) for x in rows(work/'reports/aggregate_tails.csv'))
            r['status']='COMPLETE'
        except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
        records.append(r)
    contrasts,missing=paired_contrasts(scores)
    base.write(dest/'incomplete_paired_blocks.json',missing)
    for name,data in [('all_stream_scores.csv',scores),('all_aggregate_tails.csv',tails),('paired_log_score_contrasts.csv',contrasts)]:
        if data:
            with (dest/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    complete=sum(r['status']=='COMPLETE' for r in records)
    base.write(dest/'summary.json',dict(version=VERSION,tasks=records,issues=issues,complete=complete,expected=360,new_fits=288,reused_fits=72,scientific_acceptance=False,independent_validation=False))
    base.archive(dest);print('Completed %d/360; statistical review required'%complete,flush=True)
    return 0 if complete==360 and not issues else 1

def launch(root):
    root=Path(root).resolve()
    if any(not shutil.which(x) for x in ('qsub','singularity')):raise ValueError('Load singularity on an SGE host')
    dest=root/'output'/('county_covariate_expansion_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));bundle=dest/'bundle';bundle.mkdir(parents=True)
    for name in FILES:shutil.copyfile(str(root/'scripts'/name),str(bundle/name))
    shutil.copyfile(str(root/'analysis_configs/county_covariate_expansion_sources.json'),str(bundle/'source_receipt.json'))
    shutil.copyfile(str(root/'docs/county_covariate_expansion_protocol.md'),str(bundle/'protocol.md'))
    base.write(bundle/'manifest.json',dict(version=VERSION,files={p.name:base.sha(p) for p in bundle.iterdir()}))
    base.write(dest/'bootstrap.json',dict(root=str(root),bundle_sha256=base.sha(bundle/'manifest.json')));digest=base.sha(dest/'bootstrap.json')
    (dest/'prepare.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+shlex.quote(str(bundle/'launch_covariate_expansion.py'))+' --prepare '+shlex.quote(str(dest))+' --digest '+digest+'\n')
    job=base.submit(dest/'prepare.sh','foodnet_cov_prepare',dest/'preparation.log',(2,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'))
    base.write(dest/'preparation_submission.json',dict(job=job))
    print('Preparation job: '+job+'\nLog: '+str(dest/'preparation.log')+'\nArchive: '+str(dest)+'.tar.gz',flush=True)
    return dest

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    for name in ('prepare','preflight','worker','collect','digest'):p.add_argument('--'+name)
    p.add_argument('--index',type=int);a=p.parse_args()
    if a.prepare:
        dest=Path(a.prepare)
        try:prepare(dest,a.digest);return 0
        except Exception as e:base.write(dest/'preparation_failure.json',dict(error=str(e)));base.archive(dest);raise
    if a.preflight or a.worker:
        limit=7 if a.preflight else 288
        if a.index is None or not 1<=a.index<=limit or not a.digest:p.error('Valid index and digest required')
        return preflight(Path(a.preflight),a.index,a.digest) if a.preflight else worker(Path(a.worker),a.index,a.digest)
    if a.collect:return collect(Path(a.collect),a.digest)
    launch(a.root);return 0
if __name__=='__main__':sys.exit(main())
