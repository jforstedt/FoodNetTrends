#!/usr/bin/env python3
"""Four CX+ fits and two saved-fit rescoring tasks with frozen combined references."""
import sys
sys.dont_write_bytecode=True
import argparse
import csv
from datetime import datetime
import math
from pathlib import Path
import shlex
import shutil
import subprocess
import regional_audit_runtime as base

VERSION='campylobacter_cx_comparison_v1'
PREPARATION='monthly_preparation_20260913_172157_051362'
PREP_PLAN='1711d3fe3e8817a25d8d013e0cf661b01ad3bff0b27f21ebb90777f4a7613699'
DIAGNOSTICS='saved_covariate_diagnostics_20260915_144424_396353'
DIAG_PLAN='168878d6d389356e6794962b299650f6b61cf027f9c3dbefce5a5843ffce5201'
DIAG_SUMMARY='513b50ec293e8a440487a96ff88c07d6a5db1fc23f7fbcaffedae6bfd3cbaf52'
DIAG_WORKERS={'CAMPYLOBACTER_2011_local0_weatheroff_age0': 'cd48e5db831c312a54ec52abae3f9f43cf6b9c5c8cfd516f6f12f745d9d1a06c', 'CAMPYLOBACTER_2011_local1_weatheroff_age0': 'b2a7f473cf1f639561289ce51781e88fe5b746bb07d5e9a0d5920f1e9079546d', 'CAMPYLOBACTER_2013_local0_weatheroff_age0': 'd1f1e2296c17e8f3a3a3fd572c3a931a620990c8999321cb72f061f3be22f2e7', 'CAMPYLOBACTER_2013_local1_weatheroff_age0': 'd29acffdc96df1a1211fc79ca8feb20464480f55ce7997a01e678edc6a802ad1', 'CAMPYLOBACTER_2016_local0_weatheroff_age0': '285ce976fedf9791bfde2b02ca6d40c6dc4eac11925e5e1ec799483b287b6e41', 'CAMPYLOBACTER_2016_local1_weatheroff_age0': '7b05a05ade7b78ae0ecc8734b47c311a9aac586391ede778c83f7d081b15d18f'}
PREP_SCRIPTS={'prepare_monthly_county.R':'7c0c23aed98db6e586383e8c6288cd74e05ad289bb0fe14f30b6c150657ee318','county_matching.R':'f02b2a2de6d3f6670f90aa4c153b1305a4a461e7dfdfc642c95199982a4afde9','reconcile_raw_county.R':'984e07f98573c7fd425f81fc4a5825b1871566ba79dbd42e21a213b5975e7061','fit_county_pilot.R':'df8fc50f90a1324bb1815d4da4e097ecf2d9dd75322eaa79b3a5964118f4a094'}
SCRIPTS=('launch_campylobacter_cx_comparison.py','regional_audit_runtime.py','prepare_campylobacter_cx_target.R','run_campylobacter_cx_model.R')
MEMBERS=set(SCRIPTS)|{'protocol.md','source_receipt.json'}
STATES={'CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'}


def matrix():
    return [dict(task_id='CAMPYLOBACTER_CX_'+str(c)+'_local'+str(int(l)),pathogen='CAMPYLOBACTER',target='CX+',cutoff=c,local_seasonality=l,temporal='rw1',weather=False,age=False,seed=700000000+i*1000000,draws_per_stream=1000,threads=4) for i,(c,l) in enumerate((c,l) for c in (2011,2013,2016) for l in (False,True))]


def package_check(bundle,digest):
    if base.sha(bundle/'bundle.json')!=digest:raise ValueError('Bundle manifest changed')
    m=base.read(bundle/'bundle.json')
    actual={str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file() and p.name!='bundle.json'}
    if m.get('version')!=VERSION or set(m['files'])!=MEMBERS or actual!=MEMBERS:raise ValueError('Wrong snapshot members')
    base.check({str(bundle/n):h for n,h in m['files'].items()});return m


def verify(dest,plan,digest,full_container=False):
    if base.sha(dest/'plan.json')!=digest or plan.get('version')!=VERSION or plan.get('scientific_acceptance') is not False or len(plan['tasks'])!=6:raise ValueError('Changed comparison plan')
    for entry,t in zip(plan['tasks'],matrix()):
        if any(entry['task'].get(k)!=v for k,v in t.items()):raise ValueError('Changed matrix')
        base.check({entry['task_json']:entry['task_sha256']})
    base.check(plan['bindings']);container=Path(plan['container'])
    if dict(size=container.stat().st_size,mtime_ns=container.stat().st_mtime_ns)!=plan['container_stat']:raise ValueError('Runtime snapshot changed')
    if full_container and base.sha(container)!=plan['container_sha256']:raise ValueError('Container hash changed')


def copy_combined(root,old,dest,bindings):
    source=root/'output'/DIAGNOSTICS
    base.check({str(source/'plan.json'):DIAG_PLAN,str(source/'summary.json'):DIAG_SUMMARY})
    p=base.read(source/'plan.json');summary=base.read(source/'summary.json')
    if p.get('version')!='saved_covariate_diagnostics_v1' or p.get('refitted') is not False or summary.get('complete')!=30 or summary.get('issues'):raise ValueError('Combined diagnostic source incomplete')
    base.check(p['bindings']);bindings.update(p['bindings'])
    bindings.update({str(source/'plan.json'):DIAG_PLAN,str(source/'summary.json'):DIAG_SUMMARY})
    receipts=[];reuse={}
    for t in matrix():
        matches=[e for e in p['tasks'] if e['task']['source_task']['pathogen']=='CAMPYLOBACTER' and e['task']['source_task']['cutoff']==t['cutoff'] and e['task']['source_task']['local_seasonality']==t['local_seasonality'] and not e['task']['source_task']['weather'] and not e['task']['source_task']['age']]
        if len(matches)!=1:raise ValueError('Ambiguous combined match')
        e=matches[0];name=e['id'];work=source/name
        base.check({str(work/'task_status.json'):DIAG_WORKERS[name]})
        status=base.read(work/'task_status.json')
        if status.get('status')!='COMPLETE' or status.get('plan_sha256')!=DIAG_PLAN or status.get('task')!=name:raise ValueError('Combined worker mismatch')
        original=next(x for x in old['tasks'] if x['task']['task_id']==name)
        if e['task']['source_task']!=original['task']:raise ValueError('Combined source identity changed')
        if t['cutoff']==2011:
            fit=e['task']['fit'];fit_hash=e['inputs'].get(fit)
            if not fit_hash:raise ValueError('Unbound reusable fit')
            base.check({fit:fit_hash});bindings[fit]=fit_hash;reuse[t['task_id']]=dict(reuse_fit=fit,reuse_task=original['task'])
        target=dest/'combined_reused'/name;target.mkdir(parents=True)
        copied={}
        for file in ('stream_scores.csv','aggregate_tails.csv','rng_protocol.csv','saved_diagnostic_settings.json','settings.csv','status.txt'):
            path=work/'reports'/file;h=status['outputs'].get('reports/'+file)
            if not h:raise ValueError('Unbound combined report')
            base.check({str(path):h});bindings[str(path)]=h;shutil.copyfile(str(path),str(target/file));copied[str(target/file)]=h
        identity=base.read(target/'saved_diagnostic_settings.json')
        if identity.get('source_task')!=original['task'] or identity.get('draws_per_stream')!=4000 or identity.get('refitted') is not False:raise ValueError('Combined sampling identity mismatch')
        bindings.update(copied);bindings[str(work/'task_status.json')]=base.sha(work/'task_status.json')
        receipts.append(dict(task_id=t['task_id'],source_task=name,source_run=DIAGNOSTICS,target='combined original selection',draws_per_stream=4000,refitted=False,copied=copied,source_worker_sha256=bindings[str(work/'task_status.json')]))
    base.write(dest/'combined_reuse.json',dict(version=VERSION,reports=receipts,scientific_acceptance=False,warning='Distinct targets: compare local-on/off within target; do not rank raw log scores across CX+ and combined outcomes'))
    bindings[str(dest/'combined_reuse.json')]=base.sha(dest/'combined_reuse.json')
    return reuse


def preparation_command(prep,script,task,bindings):
    # SAS import belongs to the original preprocessing image, not the INLA image.
    base.check({str(prep/'plan.json'):PREP_PLAN})
    plan=base.read(prep/'plan.json')
    matches=[t for t in plan['tasks'] if t.get('id')=='CAMPYLOBACTER']
    if len(matches)!=1:raise ValueError('Ambiguous original preparation task')
    cmd=matches[0]['command'];index=cmd.index('Rscript')
    container=cmd[index-1]
    if index<1 or not container.endswith('.sif') or container not in plan['inputs']:raise ValueError('Unbound preparation container')
    h=plan['inputs'][container];base.check({container:h});bindings[container]=h
    return ['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1',
            '--bind','/scicomp',container,'Rscript','--vanilla',str(script),str(task)]


def prepare(dest,digest):
    if base.sha(dest/'bootstrap.json')!=digest:raise ValueError('Bootstrap changed')
    boot=base.read(dest/'bootstrap.json');bundle=dest/'bundle';bm=package_check(bundle,boot['bundle_sha256']);root=Path(boot['root'])
    receipt=base.read(bundle/'source_receipt.json');source=root/'output'/receipt['source_run']
    base.check({str(source/'plan.json'):receipt['plan_sha256'],str(source/'summary.json'):receipt['summary_sha256']})
    old=base.read(source/'plan.json');base.verify(source,old,receipt['plan_sha256'])
    if base.sha(old['container'])!=old['container_sha256']:raise ValueError('Source container changed')
    bindings=dict(old['bindings']);bindings.update({str(source/'plan.json'):receipt['plan_sha256'],str(source/'summary.json'):receipt['summary_sha256']})
    bindings.update({str(bundle/n):h for n,h in bm['files'].items()})
    entries=[e for e in old['tasks'] if e['task']['pathogen']=='CAMPYLOBACTER'];pairs={(e['task']['candidate'],e['task']['audit']) for e in entries}
    if len(pairs)!=1:raise ValueError('Ambiguous original candidate')
    candidate,audit=pairs.pop()
    for e in entries:bindings.update(e['inputs'])
    for name,h in receipt['preparation_files'].items():
        if Path(name).name!=name:raise ValueError('Unsafe preparation input')
        bindings[str(Path(candidate).parent/name)]=h
    prep=root/'output'/PREPARATION;bindings[str(prep/'plan.json')]=PREP_PLAN
    bindings.update({str(prep/'scripts'/name):h for name,h in PREP_SCRIPTS.items()});base.check(bindings)
    task=dict(source_run=str(source),source_scripts=str(source/'bundle/scripts'),preparation_scripts=str(prep/'scripts'),output=str(dest/'preparation'))
    base.write(dest/'preparation_task.json',task);bindings[str(dest/'preparation_task.json')]=base.sha(dest/'preparation_task.json')
    print('Replaying frozen combined selection and validating the CX+ target; no fits yet',flush=True)
    command=preparation_command(prep,bundle/'prepare_campylobacter_cx_target.R',dest/'preparation_task.json',bindings)
    base.write(dest/'preparation_runtime.json',dict(container=command[7],container_sha256=bindings[command[7]],
        purpose='Original SAS import runtime; INLA fitting runtime remains separate'))
    bindings[str(dest/'preparation_runtime.json')]=base.sha(dest/'preparation_runtime.json')
    with (dest/'preparation.log').open('w') as log:
        code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
    if code:raise ValueError('Target preparation failed; see preparation.log')
    if (dest/'preparation/status.txt').read_text().strip()!='CX_TARGET_PREPARATION_COMPLETE':raise ValueError('Target preparation incomplete')
    metadata=base.read(dest/'preparation/preparation_metadata.json')
    if metadata.get('version')!='campylobacter_cx_target_v1' or metadata.get('scientific_acceptance') is not False or metadata.get('models_fitted') is not False or metadata.get('target')!='recorded_CX_positive' or metadata.get('combined_replay_verified') is not True or metadata.get('raw_clean_cx_strata_verified') is not True or metadata.get('pre2012_cx_equals_combined') is not True or metadata.get('combined_candidate')!=candidate or metadata.get('audit')!=audit:raise ValueError('CX target preparation contract failed')
    cx=dest/'preparation/cx_monthly_INTERNAL.rds'
    if not cx.is_file():raise ValueError('Missing CX target panel')
    for path in (dest/'preparation').rglob('*'):
        if path.is_file():bindings[str(path)]=base.sha(path)
    base.check(bindings);base.verify(source,old,receipt['plan_sha256'])
    reuse=copy_combined(root,old,dest,bindings)
    tasks=[]
    for t in matrix():
        t.update(candidate=str(cx),combined_candidate=candidate,audit=audit,source_scripts=str(source/'bundle/scripts'),output=str(dest/t['task_id']/'result'),preparation_metadata=str(dest/'preparation/preparation_metadata.json'))
        t.update(reuse.get(t['task_id'],{}))
        path=dest/(t['task_id']+'.json');base.write(path,t);tasks.append(dict(task=t,task_json=str(path),task_sha256=base.sha(path)))
    plan=dict(version=VERSION,tasks=tasks,bindings=bindings,container=old['container'],container_sha256=old['container_sha256'],container_stat=old['container_stat'],new_fits=4,rescored_saved_fits=2,target='CX+',combined_refitted=False,scientific_acceptance=False)
    base.write(dest/'plan.json',plan);h=base.sha(dest/'plan.json');verify(dest,plan,h,True);q=shlex.quote
    for file,mode in [('run.sh','--worker'),('collect.sh','--collect')]:
        index=' --index "${SGE_TASK_ID:?}"' if mode=='--worker' else ''
        (dest/file).write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(bundle/'launch_campylobacter_cx_comparison.py'))+' '+mode+' '+q(str(dest))+' --digest '+h+index+'\n')
    print('Target gates passed; submitting four CX+ fits and two guarded saved-fit rescoring tasks',flush=True)
    array=base.submit(dest/'run.sh','foodnet_campy_cx',dest/'array.log',(4,'h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G'),('-t','1-6'));base.write(dest/'submission.json',dict(array=array))
    collector=base.submit(dest/'collect.sh','foodnet_campy_collect',dest/'collection.log',(1,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'),('-hold_jid',array.split('.')[0]));base.write(dest/'submission.json',dict(array=array,collector=collector))


def validate(out,t):
    if (out/'status.txt').read_text().strip()!='CX_MODEL_COMPLETE' or (out/'reports/status.txt').read_text().strip()!='CX_MODEL_COMPLETE':raise ValueError('Incomplete model report')
    result=out;out=out/'reports'
    identity=base.read(out/'cx_model_metadata.json')
    for k in ('cutoff','local_seasonality','seed'):
        if identity.get(k)!=t[k]:raise ValueError('Model identity mismatch')
    if identity.get('version')!='campylobacter_cx_model_v1' or identity.get('streams')!=4 or identity.get('draws_per_stream')!=1000 or identity.get('weather') is not False or identity.get('age') is not False or identity.get('target')!='recorded_CX_positive' or identity.get('scientific_acceptance') is not False or identity.get('refitted')!=(t['cutoff']!=2011) or identity.get('task_id')!=t['task_id']:raise ValueError('Wrong model target/status')
    parsed={}
    for file,states in [('stream_scores.csv',STATES),('aggregate_tails.csv',STATES|{'ALL'})]:
        with (out/file).open() as f:rows=list(csv.DictReader(f))
        expected={(s,y,k) for s in states for y in range(t['cutoff']+1,t['cutoff']+4) for k in range(5)}
        if len(rows)!=len(expected) or {(r['state'],int(r['year']),int(r['stream'])) for r in rows}!=expected:raise ValueError('Wrong score domain')
        parsed[file]=rows
        for r in rows:
            if int(r['draws'])!=(4000 if int(r['stream'])==0 else 1000):raise ValueError('Wrong score draws')
            if any(not math.isfinite(float(v)) for k,v in r.items() if k!='state'):raise ValueError('Nonfinite score')
            if file=='stream_scores.csv' and (float(r['mean_log_score'])>1e-10 or float(r['max_cell_density_relative_mcse'])<0):raise ValueError('Invalid log score')
    for r in parsed['aggregate_tails.csv']:
        if any(float(r[k])<0 for k in ('observed','mean_expected','median_expected','p975_expected','max_expected','lower95','median_predictive','upper95')) or float(r['observed'])!=int(float(r['observed'])):raise ValueError('Invalid count summary')
        if not float(r['lower95'])<=float(r['median_predictive'])<=float(r['upper95']) or not float(r['median_expected'])<=float(r['p975_expected'])<=float(r['max_expected']):raise ValueError('Unordered summary')
        if any(not 0<=float(r[k])<=1 for k in ('top_one_percent_mean_share','prob_above_twice_observed')):raise ValueError('Invalid probability')
    for year in range(t['cutoff']+1,t['cutoff']+4):
        for stream in range(5):
            rs=[r for r in parsed['aggregate_tails.csv'] if int(r['year'])==year and int(r['stream'])==stream];total=next(r for r in rs if r['state']=='ALL')
            for field in ('observed','mean_expected'):
                if not math.isclose(float(total[field]),sum(float(r[field]) for r in rs if r['state']!='ALL'),rel_tol=1e-9,abs_tol=1e-8):raise ValueError('State/catchment mismatch')
    with (out/'rng_protocol.csv').open() as f:rng=list(csv.DictReader(f))
    if len(rng)!=1 or any(rng[0].get(k)!=v for k,v in dict(protocol='explicit_config_v2',base_seed=str(t['seed']),stream_stride='50000',batch_size='100',r_configuration_seed_offset='20000',predictive_seed_offset='10000',inla_version='26.8.7').items()):raise ValueError('RNG mismatch')
    with (out/'settings.csv').open() as f:settings=list(csv.DictReader(f))
    if len(settings)!=1 or int(settings[0]['draws_per_stream'])!=1000 or int(settings[0]['base_seed'])!=t['seed'] or int(settings[0]['streams'])!=4:raise ValueError('Wrong sampler settings')
    for path in (result/'fit_INTERNAL.rds',result/'truth_INTERNAL.csv',out/'pooled_cell_scores_INTERNAL.csv',out/'rng_protocol.csv'):
        if not path.is_file():raise ValueError('Missing '+str(path))


def worker(dest,index,digest):
    p=base.read(dest/'plan.json');entry=p['tasks'][index-1];t=entry['task'];work=dest/t['task_id'];work.mkdir(exist_ok=False);result=dict(task=t['task_id'],status='FAILED',target='CX+',scientific_acceptance=False)
    try:
        verify(dest,p,digest)
        with (work/'task.log').open('w') as log:
            code=subprocess.call(base.runtime_command(p['container'],dest/'bundle/run_campylobacter_cx_model.R',entry['task_json']),stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('R model exited '+str(code))
        validate(Path(t['output']),t);verify(dest,p,digest)
        result.update(status='COMPLETE',plan_sha256=digest,truth_sha256=base.sha(Path(t['output'])/'truth_INTERNAL.csv'),outputs={str(f.relative_to(work)):base.sha(f) for f in work.rglob('*') if f.is_file()})
    except (OSError,ValueError,KeyError,TypeError) as e:result['reason']=str(e)
    base.write(work/'task_status.json',result);return 0 if result['status']=='COMPLETE' else 1


def collect(dest,digest):
    p=base.read(dest/'plan.json');issues=[];rows=[];truth={}
    try:verify(dest,p,digest,True)
    except (OSError,ValueError,KeyError,TypeError) as e:issues.append(str(e))
    for entry in p['tasks']:
        t=entry['task'];work=dest/t['task_id'];row=dict(task=t['task_id'],status='FAILED_OR_MISSING')
        try:
            if issues:raise ValueError('Global source integrity failure')
            status=base.read(work/'task_status.json')
            if status.get('task')!=t['task_id'] or status.get('status')!='COMPLETE' or status.get('plan_sha256')!=digest:raise ValueError(status.get('reason','Incomplete worker'))
            actual={str(f.relative_to(work)) for f in work.rglob('*') if f.is_file() and f.name!='task_status.json'}
            if actual!=set(status['outputs']):raise ValueError('Incomplete output hash set')
            base.check({str(work/n):h for n,h in status['outputs'].items()});validate(Path(t['output']),t)
            h=base.sha(Path(t['output'])/'truth_INTERNAL.csv')
            if h!=status['truth_sha256'] or t['cutoff'] in truth and truth[t['cutoff']]!=h:raise ValueError('Different paired CX truth')
            truth[t['cutoff']]=h;row['status']='COMPLETE'
        except (OSError,ValueError,KeyError,TypeError) as e:row['reason']=str(e)
        rows.append(row)
    n=sum(r['status']=='COMPLETE' for r in rows);base.write(dest/'summary.json',dict(version=VERSION,tasks=rows,complete=n,expected=6,issues=issues,new_fits=4,rescored_saved_fits=2,combined_refitted=False,target='CX+',scientific_acceptance=False));base.archive(dest);return 0 if n==6 and not issues else 1


def launch(root):
    root=Path(root).resolve()
    if any(not shutil.which(x) for x in ('qsub','singularity')):raise ValueError('Load Singularity on an SGE host')
    dest=root/'output'/('campylobacter_cx_comparison_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));dest.mkdir(parents=True);bundle=dest/'bundle';bundle.mkdir()
    for name in SCRIPTS:shutil.copyfile(str(root/'scripts'/name),str(bundle/name))
    shutil.copyfile(str(root/'docs/campylobacter_diagnostic_era_protocol.md'),str(bundle/'protocol.md'));shutil.copyfile(str(root/'analysis_configs/campylobacter_regional_audit_source.json'),str(bundle/'source_receipt.json'))
    base.write(bundle/'bundle.json',dict(version=VERSION,files={n:base.sha(bundle/n) for n in sorted(MEMBERS)}));base.write(dest/'bootstrap.json',dict(root=str(root),bundle_sha256=base.sha(bundle/'bundle.json')))
    q=shlex.quote;(dest/'prepare.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(bundle/'launch_campylobacter_cx_comparison.py'))+' --prepare '+q(str(dest))+' --digest '+base.sha(dest/'bootstrap.json')+'\n')
    job=base.submit(dest/'prepare.sh','foodnet_cx_prepare',dest/'launcher.log',(2,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'));base.write(dest/'preparation_submission.json',dict(job=job));print('Preparation job: '+job+'\nLog: '+str(dest/'launcher.log')+'\nArchive: '+str(dest)+'.tar.gz');return dest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.');p.add_argument('--prepare');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--digest');p.add_argument('--index',type=int);a=p.parse_args()
    if a.prepare:
        try:prepare(Path(a.prepare),a.digest)
        except Exception as e:base.write(Path(a.prepare)/'preparation_failure.json',dict(error=str(e),new_fits=0));base.archive(Path(a.prepare));raise
    elif a.worker:
        if not a.index or not 1<=a.index<=6:p.error('Index1..6 required')
        sys.exit(worker(Path(a.worker),a.index,a.digest))
    elif a.collect:sys.exit(collect(Path(a.collect),a.digest))
    else:launch(a.root)
