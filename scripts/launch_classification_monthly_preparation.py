#!/usr/bin/env python3
"""Six parallel monthly classification input audits; no model fits."""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import launch_monthly_preparation as monthly
import launch_eligible_diagnostics as eligible

PATHOGENS=('SALMONELLA','CAMPYLOBACTER','SHIGELLA','STEC','VIBRIO','YERSINIA')
SOURCE='eligible_diagnostics_20260914_094654_276977'
FILES=('launch_classification_monthly_preparation.py','prepare_classification_monthly.R','launch_eligible_diagnostics.py')
sha=monthly.sha

def rows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))

def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve()
    clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    raw=Path('/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat')
    plan=monthly.prepare(root,dest,raw,clean,clean.with_name('clean_mmwr_preprocessing_report.csv'),verified,PATHOGENS)
    for name in FILES:
        target=dest/'scripts'/name;shutil.copyfile(str(root/'scripts'/name),str(target));plan['inputs'][str(target)]=sha(target)
    protocol=dest/'classification_combination_protocol.md';shutil.copyfile(str(root/'docs'/protocol.name),str(protocol));plan['inputs'][str(protocol)]=sha(protocol)
    origin=root/'output'/SOURCE
    if verified:
        previous=json.loads((origin/'plan.json').read_text());digest=sha(origin/'plan.json')
        if previous.get('verified') is not True or previous.get('models_fitted') is not False:raise ValueError('Unsupported eligible audit plan')
        plan['inputs'][str(origin/'plan.json')]=digest
    for task in plan['tasks']:
        work=origin/task['id'];support=work/'result/support.csv'
        if verified:
            record=json.loads((work/'task_status.json').read_text())
            if record.get('task')!=task['id'] or record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=digest:raise ValueError('Invalid annual category audit')
            eligible.validate_result(work)
            if not record.get('outputs') or 'result/support.csv' not in record['outputs']:raise ValueError('Annual support not manifested')
            for name,h in record['outputs'].items():
                path=work/name
                if path.resolve().parent!=work.resolve() and work.resolve() not in path.resolve().parents:raise ValueError('Unsafe source artifact path')
                if sha(path)!=h:raise ValueError('Changed eligible audit output')
                plan['inputs'][str(path)]=h
            plan['inputs'][str(work/'task_status.json')]=sha(work/'task_status.json')
        command=task['command'];i=command.index(str(dest/'scripts/prepare_monthly_county.R'))
        command[i]=str(dest/'scripts/prepare_classification_monthly.R');command.append(str(support));task['annual_support']=str(support)
    plan.update(version='classification_monthly_preparation_v1',incidence_adjustment=False,accepted=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote
    base='python3 '+q(str(dest/'scripts/launch_classification_monthly_preparation.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(plan['tasks'],1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
    (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n')
    return plan

def validate(work,task):
    monthly.validate_result(work);out=work/'result'
    if (out/'classification_status.txt').read_text().strip()!='CLASSIFICATION_MONTHLY_PREPARATION_COMPLETE':raise ValueError('Classification preparation incomplete')
    if not(out/'classification_county_month_INTERNAL.rds').is_file():raise ValueError('Missing private classification panel')
    states=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
    keys={(s,y,m) for s in states for y in range(2004,2020) for m in range(1,13)}
    site=rows(out/'classification_site.csv');annual=rows(out/'classification_annual.csv');source=rows(task['annual_support'])
    def num(r,k):
        x=float(r[k])
        if not math.isfinite(x) or x<0 or x!=int(x):raise ValueError('Invalid classification count')
        return int(x)
    if len(site)!=len(keys) or {(r['state'],int(r['year']),int(r['month'])) for r in site}!=keys:raise ValueError('Invalid classification monthly domain')
    sums={};zero=0
    for r in site:
        cx=num(r,'cx_classified');cidt=num(r,'cidt_classified');n=num(r,'classification_denominator')
        if cx+cidt!=n or r['likelihood_eligible']!=('TRUE' if n else 'FALSE'):raise ValueError('Invalid classification denominator')
        if (not n and r['cidt_classification_share']!='') or (n and not math.isclose(float(r['cidt_classification_share']),cidt/n,abs_tol=1e-12)):raise ValueError('Invalid classification share')
        k=(r['state'],int(r['year']));sums[k]=tuple(a+b for a,b in zip(sums.get(k,(0,0,0)),(cx,cidt,n)))
        if int(r['year'])>=2012 and not n:zero+=1
    if len(annual)!=160 or {(r['state'],int(r['year'])) for r in annual}!=set(sums):raise ValueError('Invalid annual domain')
    audit={(r['state'],int(r['year'])):r for r in source};issues=rows(out/'classification_date_issues_by_category.csv');missing={}
    seen=set()
    for r in issues:
        k=(r['state'],int(r['year']),r['category'])
        if k in seen or k[:2] not in sums or k[2] not in ('CX+','CIDT+'):raise ValueError('Invalid category date domain')
        seen.add(k);u=num(r,'unassigned')
        if u>num(r,'records'):raise ValueError('Invalid missing date count')
        missing[k]=u
    total_unassigned=0
    for r in annual:
        k=(r['state'],int(r['year']));cx,cidt,n=sums[k]
        if tuple(num(r,f) for f in ('cx_classified','cidt_classified','classification_denominator'))!=(cx,cidt,n):raise ValueError('Monthly/annual category mismatch')
        uc=missing.get(k+('CX+',),0);ud=missing.get(k+('CIDT+',),0)
        if num(r,'unassigned_records')!=uc+ud:raise ValueError('Missing dates mismatch')
        a=audit[k]
        if num(a,'cx_classified')!=cx+uc or num(a,'cidt_classified')!=cidt+ud or num(a,'classification_denominator')!=n+uc+ud:raise ValueError('Annual source category mismatch')
        if k[1]>=2012:total_unassigned+=uc+ud
    ready=rows(out/'classification_readiness.csv')
    if len(ready)!=1:raise ValueError('Invalid readiness')
    r=ready[0]
    if r['pathogen']!=task['id'] or r['models_fitted']!='FALSE' or r['incidence_adjustment']!='FALSE' or r['readiness']!='REVIEW_REQUIRED' or num(r,'county_month_rows')!=486*96 or num(r,'site_month_rows')!=960 or num(r,'site_zero_denominator')!=zero or num(r,'unassigned_2012_2019')!=total_unassigned or num(r,'county_zero_denominator')>486*96:raise ValueError('Invalid classification readiness')
    if not(out/'classification_support_checksum.csv').is_file():raise ValueError('Missing support checksum')

def verify(dest,plan,digest):
    monthly.verify(dest,plan,digest)
    if plan.get('version')!='classification_monthly_preparation_v1' or [t['id'] for t in plan['tasks']]!=list(PATHOGENS):raise ValueError('Invalid task matrix')

def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name)
    work=dest/name;work.mkdir(exist_ok=False);record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
    try:
        verify(dest,plan,digest);monthly.validate_source(name,task['source'])
        with (work/'task.log').open('w') as log:code=subprocess.call(task['command'],stdout=log,stderr=subprocess.STDOUT,cwd=str(dest))
        if code:raise ValueError('R preparation exit '+str(code))
        validate(work,task);verify(dest,plan,digest);monthly.validate_source(name,task['source'])
        record.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in (work/'result').rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:record['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']

def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[]
    try:verify(dest,plan,digest)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for task in plan['tasks']:
        work=dest/task['id'];r=dict(task=task['id'],status='MISSING_OR_INVALID')
        try:
            if issues:raise ValueError('Global integrity check failed')
            old=json.loads((work/'task_status.json').read_text())
            if old.get('task')!=task['id'] or old.get('status')!='COMPLETE' or old.get('exit_status')!=0 or old.get('plan_sha256')!=digest:raise ValueError('Invalid task completion')
            validate(work,task)
            if not old.get('outputs') or any(sha(work/n)!=h for n,h in old['outputs'].items()):raise ValueError('Changed completed output')
            r['status']='COMPLETE'
        except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
        results.append(r)
    summary=dict(tasks=results,issues=issues,execution_complete=not issues and all(r['status']=='COMPLETE' for r in results),models_fitted=False,incidence_adjustment=False,scientific_readiness='REVIEW_REQUIRED')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and '_INTERNAL' not in p.name and p.name!='report_sha256.json' and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md')]
    manifest=dest/'report_sha256.json';manifest.write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
        for p in files+[manifest]:arc.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--digest');a=p.parse_args()
    if a.worker or a.collect:
        if not a.digest or (a.worker and not a.task):p.error('Missing task/plan identity')
        return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('classification_monthly_preparation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
    try:prepare(root,dest,not a.prepare_only)
    except (OSError,ValueError,KeyError) as e:p.error(str(e))
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    job=subprocess.check_output(base+['-N','foodnet_class_month','-t','1-6','-pe','smp','2','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Preparation array: '+job,flush=True)
    match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise ValueError('Unexpected scheduler response; inspect queue before retry')
    col=subprocess.check_output(base+['-N','foodnet_class_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=01:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n');print('Collector: '+col+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
