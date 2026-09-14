#!/usr/bin/env python3
"""Audit eligible diagnostic-category accounting across all nine pathogens; no models."""
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
from county_forecast_protocol import source_paths,validate_source,PATHOGENS

FILES=('launch_eligible_diagnostics.py','audit_eligible_diagnostics.R','county_matching.R','fit_county_pilot.R','county_forecast_protocol.py')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

def prepare(root,dest,clean,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();clean=Path(clean).resolve();sources=source_paths(root);cache={};inputs={};tasks=[]
    container=root/'foodnet.sif'
    if verified:
        for p in (clean,container):inputs[str(p)]=sha(p)
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
    for n in FILES:
        p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=sha(p)
    protocol=dest/'eligible_diagnostics.md';shutil.copyfile(str(root/'docs/eligible_diagnostics.md'),str(protocol));inputs[str(protocol)]=sha(protocol)
    for pathogen in PATHOGENS:
        source=sources[pathogen]
        if verified:
            source=validate_source(pathogen,source,hash_cache=cache)
            if str(clean) not in source['input_md5']:raise ValueError('Clean input is not the audited source')
            inputs.update(source['evidence_sha256']);inputs[str(Path(source['audit'])/'county_panel_INTERNAL.rds')]=source['panel_sha256']
        cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/audit_eligible_diagnostics.R'),str(clean),source['audit'],str(dest/pathogen/'result'),pathogen]
        tasks.append(dict(id=pathogen,pathogen=pathogen,source=source,command=cmd))
    plan=dict(version='eligible_diagnostics_v1',verified=verified,inputs=inputs,tasks=tasks,models_fitted=False,coverage_certified=False,readiness='REVIEW_REQUIRED')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_eligible_diagnostics.py'))
    script='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):script+=str(i)+') task='+t['id']+';;\n'
    script+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --expected-plan-sha '+digest+'\n'
    (dest/'run.sh').write_text(script);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --expected-plan-sha '+digest+'\n');return plan

def verify(dest,plan,expected):
    if sha(dest/'plan.json')!=expected:raise ValueError('Plan changed after submission')
    if not plan.get('verified'):raise ValueError('Unverified preparation cannot execute')
    for p,h in plan['inputs'].items():
        if sha(p)!=h:raise ValueError('Changed input/source: '+p)

def validate_result(work):
    import csv,math
    out=work/'result'
    if (out/'status.txt').read_text().strip()!='ELIGIBLE_DIAGNOSTICS_COMPLETE':raise ValueError('Incomplete eligible audit')
    def read(n):
        with (out/n).open(newline='') as f:return list(csv.DictReader(f))
    def num(r,k):
        x=float(r[k])
        if not math.isfinite(x) or x<0:raise ValueError('Invalid '+k)
        return x
    end=2017 if work.name=='CRYPTOSPORIDIUM' else 2019
    ready=read('readiness.csv')
    if len(ready)!=1 or ready[0]['pathogen']!=work.name or int(ready[0]['end_year'])!=end or ready[0]['counts_reconciled']!='TRUE' or ready[0]['model_fitted']!='FALSE' or ready[0]['coverage_certified']!='FALSE':raise ValueError('Wrong readiness identity')
    categories=read('categories.csv');annual=read('annual.csv');support=read('support.csv');flow=read('flow.csv')
    keys={(s,str(y)) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for y in range(2004,end+1)}
    key=lambda r:(r['state'],r['year'])
    for rr in (annual,support):
        if len(rr)!=len(keys) or {key(r) for r in rr}!=keys:raise ValueError('Annual domain differs')
    expected={k+(c,) for k in keys for c in ('CX+','CIDT+','PARASITIC')}
    if len(categories)!=len(expected) or {key(r)+(r['category'],) for r in categories}!=expected:raise ValueError('Category domain differs')
    counts={key(r)+(r['category'],):num(r,'records') for r in categories}
    if any(n!=int(n) for n in counts.values()):raise ValueError('Fractional counts')
    a={key(r):r for r in annual}
    for r in support:
        k=key(r);cx=counts[k+('CX+',)];cidt=counts[k+('CIDT+',)];para=counts[k+('PARASITIC',)]
        if cx+cidt+para!=num(a[k],'eligible_records') or num(r,'eligible_records')!=cx+cidt+para or num(r,'cx_classified')!=cx or num(r,'cidt_classified')!=cidt or num(r,'parasitic_classified')!=para or num(r,'classification_denominator')!=cx+cidt:raise ValueError('Category totals differ')
        if num(a[k],'population')<=0 or num(r,'population')!=num(a[k],'population'):raise ValueError('Population differs')
        if cx+cidt==0:
            if r['cidt_classification_share']!='':raise ValueError('Undefined share must stay missing')
        elif not math.isclose(float(r['cidt_classification_share']),cidt/(cx+cidt),rel_tol=1e-10,abs_tol=1e-12):raise ValueError('Wrong category share')
    total=sum(num(r,'eligible_records') for r in annual)
    if total!=num(ready[0],'selected_records') or len(flow)!=3 or num(flow[2],'records')!=total or num(flow[0],'records')!=num(flow[1],'records')+total:raise ValueError('Case flow differs')
    if not read('input_checksums.csv'):raise ValueError('Missing input binding')
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
    summary=dict(tasks=results,issues=issues,execution_complete=len(results)==len(plan['tasks']) and len(results)>0 and all(r['status']=='COMPLETE' for r in results) and not issues,
      models_fitted=False,calendar_certified=False,scientific_readiness='REVIEW_REQUIRED')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md')]
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
    dest=root/'output'/('eligible_diagnostics_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    try:plan=prepare(root,dest,clean,not a.prepare_only)
    except (OSError,ValueError,KeyError) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:print('Preparation only; no jobs submitted');return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    job=subprocess.check_output(base+['-N','foodnet_eligible','-t','1-'+str(len(plan['tasks'])),'-pe','smp','2','-l','h_rt=04:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip()
    import re
    match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise ValueError('Unexpected submission response; inspect queue before retry: '+job)
    (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Preparation array: '+job,flush=True)
    col=subprocess.check_output(base+['-N','foodnet_eligible_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=01:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n')
    print('Collector: '+col+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
